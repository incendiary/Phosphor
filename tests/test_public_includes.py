import argparse
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from inc.public_includes import (
    do_setup,
    read_xml,
    return_password_reset_string,
    set_creds,
    str2bool,
)

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "test_config.xml")


class TestStr2Bool(unittest.TestCase):

    def test_true_values(self):
        for val in ("yes", "true", "t", "y", "1", "YES", "True"):
            self.assertTrue(str2bool(val), msg=val)

    def test_false_values(self):
        for val in ("no", "false", "f", "n", "0", "NO", "False"):
            self.assertFalse(str2bool(val), msg=val)

    def test_invalid_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            str2bool("maybe")

    def test_invalid_empty_raises(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            str2bool("")


class TestReadXml(unittest.TestCase):

    def test_reads_application_entries(self):
        result = read_xml(FIXTURE, "application")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "app_auth")
        self.assertEqual(result[1]["type"], "app_error")

    def test_reads_cics_entries(self):
        result = read_xml(FIXTURE, "cics")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["string"], "DFHAC2001")

    def test_reads_account_entries(self):
        result = read_xml(FIXTURE, "account")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["user"], "uid1")
        self.assertEqual(result[1]["user"], "uid2")

    def test_reads_environment_entries(self):
        result = read_xml(FIXTURE, "environment")
        self.assertEqual(len(result), 2)
        defaults = [e for e in result if e["default"] == "true"]
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0]["name"], "environment1")

    def test_reads_cics_config(self):
        result = read_xml(FIXTURE, "cics_config")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["launch_command"], "testcics")

    def test_reads_bad_app_codes(self):
        result = [d["code"] for d in read_xml(FIXTURE, "bad_app_code")]
        self.assertIn("aaa", result)
        self.assertIn("bbb", result)
        self.assertEqual(len(result), 2)

    def test_reads_department_config(self):
        result = read_xml(FIXTURE, "department_config")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["launch_transaction"], "DEPT")
        self.assertEqual(result[0]["not_found_string"], "DEPARTMENT NOT FOUND")

    def test_reads_department_screen(self):
        result = read_xml(FIXTURE, "department_screen")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["dept_row"], "3")
        self.assertEqual(result[0]["users_row_start"], "9")

    def test_missing_element_returns_empty(self):
        result = read_xml(FIXTURE, "nonexistent_element")
        self.assertEqual(result, [])


class TestSetCreds(unittest.TestCase):

    def _args(
        self, user="testuser", password="testpass", appuser=None, apppassword=None
    ):
        args = argparse.Namespace(
            user=user, password=password, appuser=appuser, apppassword=apppassword
        )
        return args

    def test_vtam_creds_set(self):
        creds = set_creds(self._args())
        self.assertEqual(creds["vtamcredentials"]["user"], "testuser")
        self.assertEqual(creds["vtamcredentials"]["password"], "testpass")

    def test_app_creds_default_to_vtam(self):
        creds = set_creds(self._args())
        self.assertEqual(creds["appcredentials"]["user"], "testuser")
        self.assertEqual(creds["appcredentials"]["password"], "testpass")

    def test_separate_app_user(self):
        creds = set_creds(self._args(appuser="appuser"))
        self.assertEqual(creds["appcredentials"]["user"], "appuser")
        self.assertEqual(creds["vtamcredentials"]["user"], "testuser")

    def test_separate_app_password(self):
        creds = set_creds(self._args(apppassword="apppass"))
        self.assertEqual(creds["appcredentials"]["password"], "apppass")
        self.assertEqual(creds["vtamcredentials"]["password"], "testpass")

    def test_separate_app_user_and_password(self):
        creds = set_creds(self._args(appuser="auser", apppassword="apass"))
        self.assertEqual(creds["appcredentials"]["user"], "auser")
        self.assertEqual(creds["appcredentials"]["password"], "apass")


class TestPublicPasswordStub(unittest.TestCase):

    def test_stub_returns_string(self):
        result = return_password_reset_string()
        self.assertIsInstance(result, str)

    def test_stub_returns_non_empty(self):
        result = return_password_reset_string()
        self.assertTrue(len(result) > 0)


class TestTargetsArgParsing(unittest.TestCase):
    """Verify --targets is accepted by do_setup() and sets args.targets correctly."""

    def _parse(self, argv):
        with patch("sys.argv", ["phosphor"] + argv):
            return do_setup()

    def test_single_target_via_targets_flag(self):
        args = self._parse(["--targets", "192.168.1.1:3270", "--config", FIXTURE])
        self.assertEqual(args.targets, ["192.168.1.1:3270"])

    def test_multiple_targets(self):
        args = self._parse([
            "--targets", "host1:3270", "host2:3270", "host3:3270",
            "--config", FIXTURE,
        ])
        self.assertEqual(args.targets, ["host1:3270", "host2:3270", "host3:3270"])

    def test_targets_default_is_none(self):
        args = self._parse(["--target", "host:3270", "--config", FIXTURE])
        self.assertIsNone(args.targets)

    def test_legacy_target_flag_still_works(self):
        args = self._parse(["--target", "legacy:3270", "--config", FIXTURE])
        self.assertEqual(args.target, "legacy:3270")


class TestMultiTargetDispatch(unittest.TestCase):
    """Verify _run_target is called once per target via the ThreadPoolExecutor path."""

    def test_multi_target_calls_run_target_for_each(self):
        """main() should call _run_target N times when len(target_list) > 1."""
        import phosphor

        call_log = []

        def fake_run_target(target_addr, **_kwargs):
            call_log.append(target_addr)

        mock_args = argparse.Namespace(
            target=None,
            targets=["host1:3270", "host2:3270"],
            config=FIXTURE,
            sleep=0,
            clobber=False,
            user="u",
            password="p",
            appuser=None,
            apppassword=None,
            debug=False,
            populate_cics=False,
            populate_apps=False,
            populate_users=False,
            bulk_auth_create=False,
            excel=False,
            manual_inport=False,
            manual_export=False,
            db=":memory:",
        )

        with patch("phosphor.do_setup", return_value=mock_args), \
             patch("phosphor.set_creds", return_value={}), \
             patch("phosphor.read_xml", return_value=[]), \
             patch("phosphor._run_target", side_effect=fake_run_target):
            phosphor.main()

        self.assertCountEqual(call_log, ["host1:3270", "host2:3270"])


if __name__ == "__main__":
    unittest.main()
