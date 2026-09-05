"""Offline guard checks; never connects to production."""
import copy
import unittest
from publish_homer_apk import guard_upgrade_path


class PublisherGuardTest(unittest.TestCase):
    def setUp(self):
        self.old = dict(name='ai-xingyue-latest.apk', package='org.nebula.horizon.composeai',
                        version_code=269, cert_sha256='a'*64, sha256='b'*64)
        self.previous = dict(canonical=copy.copy(self.old), files=[copy.copy(self.old)])
        self.new = {**self.old, 'version_code': 270, 'sha256': 'c'*64, 'debuggable': False}

    def test_upgrade_and_identical_retry(self):
        guard_upgrade_path(self.new, self.previous)
        guard_upgrade_path({**self.old, 'debuggable': False}, self.previous)

    def test_rejects_changed_bytes_at_same_version(self):
        with self.assertRaises(SystemExit):
            guard_upgrade_path({**self.new, 'version_code': 269}, self.previous)

    def test_rejects_downgrade_certificate_package_and_debug(self):
        for change in ({'version_code': 268}, {'cert_sha256': 'd'*64},
                       {'package': 'unrelated.app'}, {'debuggable': True}):
            with self.subTest(change=change), self.assertRaises(SystemExit):
                guard_upgrade_path({**self.new, **change}, self.previous)


if __name__ == '__main__':
    unittest.main()
