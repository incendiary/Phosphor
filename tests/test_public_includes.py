import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from inc.public_includes import str2bool, read_xml, set_creds, return_password_reset_string

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'test_config.xml')


class TestStr2Bool(unittest.TestCase):

    def test_true_values(self):
        for val in ('yes', 'true', 't', 'y', '1', 'YES', 'True'):
            self.assertTrue(str2bool(val), msg=val)

    def test_false_values(self):
        for val in ('no', 'false', 'f', 'n', '0', 'NO', 'False'):
            self.assertFalse(str2bool(val), msg=val)

    def test_invalid_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            str2bool('maybe')

    def test_invalid_empty_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            str2bool('')


class TestReadXml(unittest.TestCase):

    def test_reads_application_entries(self):
        result = read_xml(FIXTURE, 'application')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['type'], 'app_auth')
        self.assertEqual(result[1]['type'], 'app_error')

    def test_reads_cics_entries(self):
        result = read_xml(FIXTURE, 'cics')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['string'], 'DFHAC2001')

    def test_reads_account_entries(self):
        result = read_xml(FIXTURE, 'account')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['user'], 'uid1')
        self.assertEqual(result[1]['user'], 'uid2')

    def test_reads_environment_entries(self):
        result = read_xml(FIXTURE, 'environment')
        self.assertEqual(len(result), 2)
        defaults = [e for e in result if e['default'] == 'true']
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0]['name'], 'environment1')

    def test_reads_cics_config(self):
        result = read_xml(FIXTURE, 'cics_config')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['launch_command'], 'testcics')

    def test_reads_bad_app_codes(self):
        result = [d['code'] for d in read_xml(FIXTURE, 'bad_app_code')]
        self.assertIn('aaa', result)
        self.assertIn('bbb', result)
        self.assertEqual(len(result), 2)

    def test_reads_department_config(self):
        result = read_xml(FIXTURE, 'department_config')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['launch_transaction'], 'DEPT')
        self.assertEqual(result[0]['not_found_string'], 'DEPARTMENT NOT FOUND')

    def test_reads_department_screen(self):
        result = read_xml(FIXTURE, 'department_screen')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['dept_row'], '3')
        self.assertEqual(result[0]['users_row_start'], '9')

    def test_missing_element_returns_empty(self):
        result = read_xml(FIXTURE, 'nonexistent_element')
        self.assertEqual(result, [])


class TestSetCreds(unittest.TestCase):

    def _args(self, user='testuser', password='testpass', appuser=None, apppassword=None):
        args = argparse.Namespace(
            user=user, password=password,
            appuser=appuser, apppassword=apppassword
        )
        return args

    def test_vtam_creds_set(self):
        creds = set_creds(self._args())
        self.assertEqual(creds['vtamcredentials']['user'], 'testuser')
        self.assertEqual(creds['vtamcredentials']['password'], 'testpass')

    def test_app_creds_default_to_vtam(self):
        creds = set_creds(self._args())
        self.assertEqual(creds['appcredentials']['user'], 'testuser')
        self.assertEqual(creds['appcredentials']['password'], 'testpass')

    def test_separate_app_user(self):
        creds = set_creds(self._args(appuser='appuser'))
        self.assertEqual(creds['appcredentials']['user'], 'appuser')
        self.assertEqual(creds['vtamcredentials']['user'], 'testuser')

    def test_separate_app_password(self):
        creds = set_creds(self._args(apppassword='apppass'))
        self.assertEqual(creds['appcredentials']['password'], 'apppass')
        self.assertEqual(creds['vtamcredentials']['password'], 'testpass')

    def test_separate_app_user_and_password(self):
        creds = set_creds(self._args(appuser='auser', apppassword='apass'))
        self.assertEqual(creds['appcredentials']['user'], 'auser')
        self.assertEqual(creds['appcredentials']['password'], 'apass')


class TestPublicPasswordStub(unittest.TestCase):

    def test_stub_returns_string(self):
        result = return_password_reset_string()
        self.assertIsInstance(result, str)

    def test_stub_returns_non_empty(self):
        result = return_password_reset_string()
        self.assertTrue(len(result) > 0)


if __name__ == '__main__':
    unittest.main()
