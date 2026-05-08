import argparse
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "test_config.xml")


def make_args(**kwargs):
    defaults = dict(
        target="localhost:3270",
        sleep=0.5,
        clobber=False,
        user="uid1",
        password="pass1",
        appuser=None,
        apppassword=None,
        config=FIXTURE,
        debug=False,
        visable=False,
        overtype=False,
        env_switch=False,
        bulk_auth=False,
        check_cics=False,
        check_app=False,
        check_user=False,
        logmein=False,
        changepass=False,
        populate_cics=False,
        populate_apps=False,
        populate_users=False,
        bulk_auth_create=False,
        excel=False,
        gen_excel_testing=False,
        manual_inport=False,
        manual_export=False,
        file_input=None,
        file_output=None,
        que=False,
        mq=False,
        destructive=False,
        department=False,
        cemt_trans=False,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def make_mainframe(args=None):
    """Return a MainFrame instance with a mocked emulator subprocess."""
    from phosphor import MainFrame

    if args is None:
        args = make_args()
    credentials = {
        "vtamcredentials": {"user": args.user, "password": args.password},
        "appcredentials": {"user": args.user, "password": args.password},
    }
    mock_sp = MagicMock()
    mock_sp.stdout.readline.side_effect = [
        b"U F U C(localhost) I 2 24 80 0 0 0x0 0.0\n",
        b"ok\n",
    ] * 200

    with patch("platform.system", return_value="Linux"):
        with patch("subprocess.Popen", return_value=mock_sp):
            mf = MainFrame(args.target, args.sleep, args.clobber, credentials, args)
    return mf


class TestMainFrameConfigSetters(unittest.TestCase):

    def setUp(self):
        self.mf = make_mainframe()

    def test_default_bad_app_codes_empty(self):
        self.assertEqual(self.mf.bad_app_codes, [])

    def test_set_bad_app_codes(self):
        self.mf.set_bad_app_codes(["aaa", "bbb"])
        self.assertEqual(self.mf.bad_app_codes, ["aaa", "bbb"])

    def test_default_cics_launch_command(self):
        self.assertEqual(self.mf.cics_launch_command, "cics")

    def test_set_cics_launch_command(self):
        self.mf.set_cics_launch_command("testcics")
        self.assertEqual(self.mf.cics_launch_command, "testcics")

    def test_default_dept_config_empty(self):
        self.assertEqual(self.mf.dept_config, {})

    def test_set_department_config(self):
        cfg = {"launch_transaction": "DEPT", "submenu_option": "1"}
        self.mf.set_department_config(cfg)
        self.assertEqual(self.mf.dept_config["launch_transaction"], "DEPT")

    def test_default_dept_screen_config_empty(self):
        self.assertEqual(self.mf.dept_screen_config, {})

    def test_set_department_screen_config(self):
        cfg = {"dept_row": "3", "dept_col_start": "29"}
        self.mf.set_department_screen_config(cfg)
        self.assertEqual(self.mf.dept_screen_config["dept_row"], "3")


class TestMainFrameBadAppCodes(unittest.TestCase):

    def setUp(self):
        self.mf = make_mainframe()
        self.mf.set_bad_app_codes(["skip1", "skip2"])
        self.mf.application_list_dict = [
            {"string": "ERROR", "type": "app_error", "xpos": "1", "ypos": "24"}
        ]
        self.mf.environment = {"name": "env1", "default": "True"}
        self.mf.credentials = {"appcredentials": {"user": "uid1", "password": "pass1"}}

    def test_bad_code_sets_unknown_response(self):
        self.mf.app_code = "skip1"
        self.mf.em = MagicMock()
        self.mf.em.wait_for_field = MagicMock()
        self.mf.em.string_get = MagicMock(return_value="")
        self.mf.em.screen_get = MagicMock(return_value=[""] * 25)
        self.mf.save_screen_specific = MagicMock()
        self.mf.make_and_set_folder_path = MagicMock()
        self.mf.assess_app_screen()
        self.assertEqual(self.mf.application_response, "app_unknown")

    def test_non_bad_code_not_auto_unknown(self):
        self.mf.app_code = "abc"
        self.mf.em = MagicMock()
        self.mf.em.wait_for_field = MagicMock()
        self.mf.em.string_get = MagicMock(return_value="ERROR")
        self.mf.em.screen_get = MagicMock(return_value=[""] * 25)
        self.mf.save_screen_specific = MagicMock()
        self.mf.make_and_set_folder_path = MagicMock()
        self.mf.assess_app_screen()
        self.assertNotEqual(self.mf.application_response, "app_unknown")


class TestMainFrameCheckScreenForString(unittest.TestCase):

    def setUp(self):
        self.mf = make_mainframe()

    def test_string_found(self):
        self.mf.em.screen_get = MagicMock(
            return_value=[
                "WELCOME TO THE SYSTEM",
                "ENTER TRANSACTION CODE",
            ]
        )
        self.assertTrue(self.mf.check_screen_for_string("WELCOME"))

    def test_string_not_found(self):
        self.mf.em.screen_get = MagicMock(
            return_value=[
                "ENTER TRANSACTION CODE",
                "READY",
            ]
        )
        self.assertFalse(self.mf.check_screen_for_string("WELCOME"))

    def test_case_insensitive(self):
        self.mf.em.screen_get = MagicMock(return_value=["Security Violation"])
        self.assertTrue(self.mf.check_screen_for_string("security violation"))


class TestMainFrameCountOccurrences(unittest.TestCase):

    def setUp(self):
        self.mf = make_mainframe()

    def test_counts_correctly(self):
        self.mf.em.screen_get = MagicMock(
            return_value=[
                "line with + sign",
                "line with + sign",
                "clean line",
            ]
        )
        self.assertEqual(self.mf.count_occurances_in_screen("+"), 2)

    def test_returns_false_when_absent(self):
        self.mf.em.screen_get = MagicMock(return_value=["clean line", "another line"])
        self.assertFalse(self.mf.count_occurances_in_screen("+"))


if __name__ == "__main__":
    unittest.main()
