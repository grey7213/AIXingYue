"""Verify real email rendering/transport with mocked delivery; never send email."""
import email
import email.policy
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import ai_fengyue_local_server as server


class VerificationEmailTests(unittest.TestCase):
    def test_locales_and_purposes_keep_copyable_code_and_matching_action(self):
        for lang in ("zh-Hans", "en"):
            for purpose in ("register", "password_reset", "reset_password", "reset"):
                with self.subTest(lang=lang, purpose=purpose):
                    subject, plain, markup = server.build_verification_email("012345", lang, purpose)
                    self.assertIn("012345", plain)
                    self.assertEqual(markup.count("012345"), 1)
                    self.assertIn("<span>012345</span>", markup)
                    self.assertIn('role="presentation"', markup)
                    self.assertNotIn("<script", markup)
                    self.assertNotIn("<img", markup)
                    self.assertIn("10", plain)
                    self.assertIn("10", markup)
                    if purpose != "register":
                        action = "密码重置" if lang.startswith("zh") else "password reset"
                        self.assertIn(action, subject)
                        self.assertIn(action, plain)
                        self.assertIn(action, markup)
                        self.assertNotIn("注册", plain + markup)
                        self.assertNotIn("registration", plain + markup)
                    else:
                        self.assertIn("注册" if lang.startswith("zh") else "registration", plain)

    def test_dynamic_values_are_escaped(self):
        with patch.object(server, "APP_BRAND", '<Homer & "friends">'):
            _, plain, markup = server.build_verification_email("<b>012345</b>")
        self.assertIn('<Homer & "friends">', plain)
        self.assertIn("&lt;Homer &amp; &quot;friends&quot;&gt;", markup)
        self.assertIn("&lt;b&gt;012345&lt;/b&gt;", markup)
        self.assertNotIn("<b>", markup)

    def test_resend_request_contains_same_html_and_plain_text(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b'{"id":"fixture-message"}'
        with patch.dict(os.environ, {"RESEND_API_KEY": "fixture-only"}, clear=True), \
                patch.object(server, "urlopen", return_value=response) as send, \
                patch.object(server, "log"):
            self.assertEqual(server.send_verification_email("fixture@example.test", "012345"), "fixture-message")
        request = send.call_args.args[0]
        payload = json.loads(request.data)
        subject, plain, markup = server.build_verification_email("012345")
        self.assertEqual(payload["to"], ["fixture@example.test"])
        self.assertEqual((payload["subject"], payload["text"], payload["html"]), (subject, plain, markup))

    def test_smtp_fallback_preserves_utf8_multipart(self):
        for lang in ("zh-Hans", "en"):
            with self.subTest(lang=lang), \
                    patch.dict(os.environ, {"SMTP_HOST": "smtp.example.test", "SMTP_STARTTLS": "true"}, clear=True), \
                    patch.object(server, "_resend_api_key", return_value="fixture-only"), \
                    patch.object(server, "_send_verification_email_resend", side_effect=RuntimeError("fixture")), \
                    patch.object(server.smtplib, "SMTP") as smtp, patch.object(server, "log"):
                server.send_verification_email("fixture@example.test", "012345", lang, "password_reset")
                transport = smtp.return_value.__enter__.return_value
                transport.starttls.assert_called_once()
                message = transport.send_message.call_args.args[0]
                decoded = email.message_from_bytes(message.as_bytes(), policy=email.policy.default)
                subject, plain, markup = server.build_verification_email("012345", lang, "password_reset")
                self.assertEqual(decoded.get_content_type(), "multipart/alternative")
                self.assertEqual(str(decoded["Subject"]), subject)
                self.assertEqual(decoded.get_body(preferencelist=("plain",)).get_content().strip(), plain.strip())
                self.assertEqual(decoded.get_body(preferencelist=("html",)).get_content().strip(), markup.strip())


if __name__ == "__main__":
    unittest.main()
