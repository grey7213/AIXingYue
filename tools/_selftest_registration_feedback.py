"""Registration error/dispatch regression; no real email or production database."""
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ai_fengyue_local_server as server


class ClosingVerificationStore(server.VerificationStore):
    # sqlite connection context managers commit/rollback but do not close.
    # Close fixture connections deterministically before Windows temp cleanup.
    @contextmanager
    def connect(self):
        conn = super().connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()


class RegistrationFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='homer-register-')
        self.addCleanup(self.temp.cleanup)
        self.store = Mock()
        self.store.get_user_by_email.side_effect = lambda email: {'id': 'existing'} if email == 'existing@example.test' else None
        self.store.recent_register_success_count.return_value = 0
        self.mail = ClosingVerificationStore(Path(self.temp.name) / 'mail.sqlite3')
        self.handler = SimpleNamespace(store=self.store, verification_store=self.mail,
            command='POST', authenticated_user=lambda: None, client_ip=lambda: '127.0.0.1')
        self.sender = patch.object(server, 'send_verification_email', return_value='fixture-delivery').start()
        self.addCleanup(patch.stopall)

    def request(self, path, body):
        return server.Handler.route(self.handler, '/console/api/' + path, '', body)

    def assert_conflict(self, result):
        self.assertEqual(result['status'], 409)
        self.assertEqual(result['result'], 'failure')
        self.assertEqual(result['error_code'], 'email_already_registered')
        self.assertIn('该邮箱已注册', result['message'])
        self.assertNotIn('retry_after', result)

    def test_existing_email_never_issues_or_sends_code(self):
        for email in ('existing@example.test', ' Existing@EXAMPLE.test '):
            with self.subTest(email=email):
                self.assert_conflict(self.request('register/email', {'email': email}))
        self.sender.assert_not_called()
        with self.mail.connect() as db:
            self.assertEqual(db.execute('select count(*) from email_codes').fetchone()[0], 0)
        self.store.create_registered_user.assert_not_called()

    def test_duplicate_submit_is_explicit_even_before_password_or_code(self):
        for body in ({'email':'existing@example.test'},
                     {'email':' Existing@EXAMPLE.test ', 'password':'fixture-pass', 'code':'000000'}):
            self.assert_conflict(self.request('register', body))
        self.store.create_registered_user.assert_not_called()
        self.sender.assert_not_called()

    def test_new_email_dispatch_and_cooldown_still_work(self):
        first = self.request('register/email', {'email':'new@example.test'})
        second = self.request('register/email', {'email':'new@example.test'})
        self.assertEqual(first['result'], 'success')
        self.assertEqual(first['data']['status'], 'accepted')
        self.assertFalse(first['data']['reused'])
        self.assertTrue(second['data']['reused'])
        self.assertGreater(second['data']['retry_after'], 0)
        self.assertEqual(self.sender.call_count, 1)

    def test_delivery_failure_is_not_success(self):
        self.sender.side_effect = RuntimeError('fixture failure')
        with patch.object(server, 'allow_email_send_failure', return_value=False), patch.object(server, 'log'):
            response = self.request('register/email', {'email':'new@example.test'})
        self.assertEqual(response['result'], 'failure')
        self.assertEqual(response['status'], 500)

    def test_registration_race_has_same_conflict(self):
        self.store.create_registered_user.side_effect = ValueError('email already registered')
        with patch.object(self.mail, 'verify', return_value=True):
            response = self.request('register', {'email':'new@example.test', 'password':'fixture-pass', 'code':'000000'})
        self.assert_conflict(response)

    def test_new_registration_still_sets_session(self):
        self.store.create_registered_user.return_value = {'id':'fixture-new'}
        with patch.object(self.mail, 'verify', return_value=True), patch.object(server, 'token_for', return_value='fixture-token'):
            response = self.request('register', {'email':'new@example.test', 'password':'fixture-pass', 'code':'000000'})
        self.assertEqual(response['result'], 'success')
        self.assertEqual(response['data'], 'fixture-token')
        self.assertIn('HttpOnly', self.handler._pending_set_cookie)


if __name__ == '__main__':
    unittest.main()
