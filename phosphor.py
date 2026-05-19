#!/usr/bin/env python3
# Phosphor -- mainframe TN3270 security assessment tool
# Based on original work by Soldier of Fortran (@mainframed767)

import logging
import os
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pika

from inc.app_mixin import AppMixin
from inc.auth_mixin import AuthMixin
from inc.cemt_mixin import CemtMixin
from inc.cics_mixin import CicsMixin
from inc.db import PhosphorDB
from inc.mq_includes import (
    mq_basic_publish,
    populate_mq,
    populate_mq_for_excel,
    que_dec,
    return_queue_contents,
)
from inc.password_mixin import PasswordMixin
from inc.public_includes import (
    do_setup,
    make_excel_workbook,
    process_mq_results_into_excel,
    read_xml,
    save_excel_workbook,
    set_creds,
)
from inc.users_mixin import UsersMixin
from py3270 import EmulatorBase

logger = logging.getLogger(__name__)

_LEVEL_COLOURS = {
    logging.DEBUG: "\033[92m",
    logging.WARNING: "\033[93m",
    logging.ERROR: "\033[91m",
    logging.CRITICAL: "\033[91m",
}
_LEVEL_PREFIX = {
    logging.DEBUG: "[D] ",
    logging.INFO: "[+] ",
    logging.WARNING: "[!] ",
    logging.ERROR: "[E] ",
    logging.CRITICAL: "[E] ",
}
_ENDC = "\033[0m"


class _ColourFormatter(logging.Formatter):
    def format(self, record):
        colour = _LEVEL_COLOURS.get(record.levelno, "")
        prefix = _LEVEL_PREFIX.get(record.levelno, "")
        msg = record.getMessage()
        return colour + prefix + msg + (_ENDC if colour else "")


def _setup_logging(debug=False):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColourFormatter())
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)


class MainFrame(AuthMixin, CicsMixin, AppMixin, UsersMixin, CemtMixin, PasswordMixin):

    def __init__(self, target, sleep, clobber, credentials, args):
        """
        :param target: Target in the form of host:port
        :param sleep: Sleep to use in default user supplied sleep timings
        :param clobber: Clobers existing file - not used much any more
        :param credentials: Credentials dictonary to login to the mf
        :param args: args object which includes the user supplied args
        """
        self.target = target
        self.host = target.split(":")[0]
        self.port = target.split(":")[1]
        self.sleep = sleep
        self.credentials = credentials
        self.nice_file_name = "%s_%s" % (self.host, self.port)
        self.nice_file_name_html = self.nice_file_name + ".html"
        self.clobber = clobber

        self.args = args
        self.db = PhosphorDB(args.db)

        self.transaction_codes = []
        self.disclosed_accounts = []
        self.disclosed_priv_accounts = []
        self.disclosed_dept = []

        self.region_login_position = None
        self.channel = None
        self.application_list_dict = None
        self.cics_response = None
        self.cics_region = None
        self.cics_continue = None
        self.cics_list_dict = None
        self.app_code = None
        self.application_response = None
        self.app_continue = None
        self.check_username_continue = None
        self.username_to_check = None
        self.password_reset_accounts = None
        self.username_field_location_dict = None
        self.username_responses_list_dict = None
        self.username_response = None
        self.environment = None
        self.bulk_app_mode = False
        self.application_response_folder = None
        self.path_to_folder = None
        self.mq_queue = None
        self.debug = args.debug
        self.overtype = False
        self.bad_app_codes = []
        self.cics_launch_command = "cics"
        self.dept_config = {}
        self.dept_screen_config = {}

        if self.clobber:
            if os.path.exists(self.nice_file_name_html):
                os.remove(self.nice_file_name_html)
            else:
                logger.info("Clobber requested but file doesnt exist")

        if platform.system() == "Darwin":

            class Emulator(EmulatorBase):
                x3270_executable = "MAC_Binaries/x3270"
                s3270_executable = "MAC_Binaries/s3270"

        elif platform.system() == "Linux":

            class Emulator(EmulatorBase):
                x3270_executable = "lin_Binaries/x3270"
                s3270_executable = "lin_Binaries/s3270"

        else:
            logger.error("Unsupported platform: %s", platform.system())
            sys.exit()

        self.em = Emulator(visible=self.args.visable)

    # -------------------------------------------------------------------------
    # Connection
    # -------------------------------------------------------------------------

    def connect_to_zos(self):
        logger.info("Connecting to: %s", self.target)
        try:
            self.em.connect(self.target)
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Configuration setters
    # -------------------------------------------------------------------------

    def set_bulk_app_mode_true(self, state=True):
        self.bulk_app_mode = state

    def set_environment(self, enviroment):
        self.environment = enviroment

    def get_enviroment(self):
        return self.environment

    def set_overtype(self, overtype):
        self.overtype = overtype

    def set_bad_app_codes(self, codes):
        self.bad_app_codes = codes

    def set_cics_launch_command(self, command):
        self.cics_launch_command = command

    def set_department_config(self, config):
        self.dept_config = config

    def set_department_screen_config(self, config):
        self.dept_screen_config = config

    # -------------------------------------------------------------------------
    # Core helpers
    # -------------------------------------------------------------------------

    def terminate(self):
        self.em.terminate()
        self.db.close()

    def wait_for_field(self):
        self.em.wait_for_field()

    def wait_for_field_and_screenshot(self):
        self.em.wait_for_field()
        self.save_screen_normal()

    def do_sleep(self):
        time.sleep(self.sleep)

    def save_screen_normal(self):
        self.make_path_to_file(self.nice_file_name_html)
        self.save_screen_specific(self.nice_file_name_html)

    def save_screen_specific(self, fn):
        self.make_path_to_file(fn)
        logger.info("Saving screen to: %s", fn)
        command = "printtext(html," + fn + ")"
        self.em.exec_command(command)

    def make_path_to_file(self, fn):
        filename = os.path.basename(fn)
        path = fn.split(filename)[0]
        if len(path) > 0:
            os.makedirs(path, exist_ok=True)

    def send_tab_x_times(self, x):
        for i in range(0, x):
            self.em.exec_command("Tab()")

    def check_screen_for_string(self, string):
        data_list = self.em.screen_get()
        return any(string.lower() in data_line.lower() for data_line in data_list)

    def count_occurances_in_screen(self, string):
        data_list = self.em.screen_get()
        if self.check_screen_for_string(string):
            return sum(str(string) in line for line in data_list)
        return False


def _run_target(
    target_addr, args, credentials, app_list_dict, env_list_dict,
    overtype_list_dict, region_login_position_list_dict,
    bad_app_codes_list, cics_config_list, dept_config_list, dept_screen_list,
):
    """Run all selected scan modes against a single target address.

    Designed to be called from a ThreadPoolExecutor when scanning multiple
    targets concurrently.  All read-only configuration objects are passed in
    so they can be shared safely across threads.
    """
    target = MainFrame(target_addr, args.sleep, args.clobber, credentials, args)
    target.set_bad_app_codes(bad_app_codes_list)
    if cics_config_list:
        target.set_cics_launch_command(cics_config_list[0]["launch_command"])
    if dept_config_list:
        target.set_department_config(dept_config_list[0])
    if dept_screen_list:
        target.set_department_screen_config(dept_screen_list[0])

    if args.changepass:
        target.add_password_reset_info(read_xml(args.config, "account"))
        target.change_passwords()
        time.sleep(args.sleep)
        return

    def _connect_and_login(with_app_sleep=False):
        if not target.connect_to_zos():
            return False
        logger.info("Connected to %s", target_addr)
        target.wait_for_field_and_screenshot()
        target.vtam_login()
        target.save_screen_normal()
        target.set_region(region_login_position_list_dict)
        target.login_to_region()
        if with_app_sleep:
            time.sleep(args.sleep)
        target.login_to_app()
        if with_app_sleep:
            time.sleep(args.sleep)
        return True

    if args.logmein:
        if _connect_and_login(with_app_sleep=True):
            while True:
                time.sleep(1)

    if args.check_cics:
        cics_list_dict = read_xml(args.config, "cics")
        if _connect_and_login():
            target.save_screen_normal()
            target.get_to_cics(cics_list_dict)
            logger.info("Should be in CICS")
            time.sleep(1)
            target.check_cics_transactions()
            target.terminate()

    if args.check_user:
        if target.connect_to_zos():
            target.add_username_field_location(
                read_xml(args.config, "username_login_field_location")
            )
            target.add_username_responses(read_xml(args.config, "username_response"))
            logger.info("Connected to %s", target_addr)
            target.check_login()
            target.terminate()

    if args.bulk_auth:
        target.set_bulk_app_mode_true()

    if args.env_switch:
        for environment in env_list_dict:
            if environment["default"].lower() == "false":
                target.set_environment(environment)
                break
    else:
        for environment in env_list_dict:
            if environment["default"].lower() == "true":
                target.set_environment(environment)
                break

    logger.info("%s", target.get_enviroment())

    if args.check_app or args.bulk_auth:
        if _connect_and_login(with_app_sleep=True):
            logger.debug("Environment: %s", target.environment)
            if args.overtype:
                target.set_overtype(overtype_list_dict)
            target.save_screen_normal()
            time.sleep(args.sleep)
            logger.info("Should be in App")
            target.check_application(app_list_dict)
            target.terminate()

    if args.department:
        if _connect_and_login(with_app_sleep=True):
            logger.debug("Environment: %s", target.environment)
            if args.overtype:
                target.set_overtype(overtype_list_dict)
            target.save_screen_normal()
            time.sleep(args.sleep)
            logger.info("Should be in App")
            target.get_department()

    if args.cemt_trans:
        cics_list_dict = read_xml(args.config, "cics")
        if _connect_and_login():
            target.save_screen_normal()
            target.get_to_cics(cics_list_dict)
            logger.info("Should be in CICS")
            target.get_cemt_transactions()


def main():

    args = do_setup()
    app_list_dict = read_xml(args.config, "application")
    env_list_dict = read_xml(args.config, "environment")
    user_list_dict = read_xml(args.config, "account")
    overtype_list_dict = read_xml(args.config, "overtype")
    region_login_position_list_dict = read_xml(args.config, "region_login_position")
    bad_app_codes_list = [d["code"] for d in read_xml(args.config, "bad_app_code")]
    cics_config_list = read_xml(args.config, "cics_config")
    dept_config_list = read_xml(args.config, "department_config")
    dept_screen_list = read_xml(args.config, "department_screen")

    _setup_logging(args.debug)

    if args.populate_cics or args.populate_apps or args.populate_users:
        populate_mq(args)
        sys.exit(0)

    if args.bulk_auth_create:
        args.populate_apps = True
        for user_dict in user_list_dict:
            for env_dictionary in env_list_dict:
                prepend_string = "%s_%s_" % (user_dict["user"], env_dictionary["name"])
                populate_mq(args, prepend_string)
        sys.exit(0)

    if args.excel:
        if args.gen_excel_testing:
            populate_mq_for_excel(user_list_dict, env_list_dict, app_list_dict, args)

        wb = make_excel_workbook(user_list_dict, env_list_dict)

        for user_dict in user_list_dict:
            for env_dictionary in env_list_dict:
                prepend_string = "%s_%s_" % (user_dict["user"], env_dictionary["name"])
                print(prepend_string)

                for app_dict in app_list_dict:
                    que_name = prepend_string + app_dict["type"]
                    application_code_list = return_queue_contents(que_name, args)
                    for application_code in application_code_list:
                        if application_code is not None:
                            wb = process_mq_results_into_excel(
                                wb,
                                user_dict["user"],
                                env_dictionary["name"],
                                app_dict["type"],
                                application_code,
                            )

        save_excel_workbook(wb)
        sys.exit()

    if args.manual_inport:
        with open(args.file_input) as f:
            codelist = f.read().splitlines()

        logger.info("Length is %s", len(codelist))

        connection = pika.BlockingConnection(pika.ConnectionParameters(host=args.mq))
        channel = connection.channel()
        que_dec(channel, args.que, args.destructive)

        for code in codelist:
            logger.debug("Pushing: %s", code)
            mq_basic_publish(channel, args.que, code)
        sys.exit()

    if args.manual_export:
        application_code_list = return_queue_contents(args.que, args)

        if application_code_list[-1] is None:
            application_code_list.pop()

        logger.debug("Exporting %d codes", len(application_code_list))

        with open(args.file_output, "w") as f:
            for ele in application_code_list:
                f.write(ele + "\n")
        sys.exit()

    credentials = set_creds(args)

    # Build target list — --targets takes precedence; fall back to --target
    target_list = getattr(args, "targets", None) or (
        [args.target] if args.target else None
    )
    if not target_list:
        logger.error("Provide --target TARGET or --targets TARGET [TARGET ...]")
        sys.exit(1)

    scan_kwargs = dict(
        args=args,
        credentials=credentials,
        app_list_dict=app_list_dict,
        env_list_dict=env_list_dict,
        overtype_list_dict=overtype_list_dict,
        region_login_position_list_dict=region_login_position_list_dict,
        bad_app_codes_list=bad_app_codes_list,
        cics_config_list=cics_config_list,
        dept_config_list=dept_config_list,
        dept_screen_list=dept_screen_list,
    )

    if len(target_list) == 1:
        _run_target(target_list[0], **scan_kwargs)
    else:
        logger.info("Scanning %d targets concurrently", len(target_list))
        with ThreadPoolExecutor(max_workers=len(target_list)) as executor:
            futures = {
                executor.submit(_run_target, t, **scan_kwargs): t
                for t in target_list
            }
            for future in as_completed(futures):
                t = futures[future]
                exc = future.exception()
                if exc:
                    logger.error("Target %s raised an exception: %s", t, exc)


if __name__ == "__main__":
    main()
