import logging

logger = logging.getLogger(__name__)


class UsersMixin:
    """Department and user-account scraping methods."""

    def get_department(self):
        launch_transaction = self.dept_config.get("launch_transaction", "DEPT")
        submenu_option = self.dept_config.get("submenu_option", "1")
        not_found_string = self.dept_config.get(
            "not_found_string", "DEPARTMENT NOT FOUND"
        )
        no_more_data_string = self.dept_config.get(
            "no_more_data_string", "NO MORE DATA"
        )

        self.em.send_string(launch_transaction)
        self.em.wait_for_field()
        self.em.send_enter()
        self.em.wait_for_field()
        self.em.send_string(submenu_option)
        self.em.send_enter()

        char_set = "abcdefghijklmnopqrstuvwxyz0123456789"

        for positionone in char_set:
            for positiontwo in char_set:
                string = positionone + positiontwo
                logger.info("Testing %s", string)
                self.em.send_string(string, 4, 23)
                self.em.send_enter()
                should_continue = True
                if self.check_screen_for_string(not_found_string):
                    self.save_screen_specific("dept/nonexist/" + string + ".html")
                    should_continue = False
                else:
                    self.search_user_info()
                    self.save_screen_specific("dept/" + string + ".html")
                i = 1
                if should_continue:
                    while self.check_screen_for_string(no_more_data_string) is False:
                        self.em.send_pf8()
                        self.save_screen_specific("dept/" + string + ".html")
                        self.save_screen_specific(
                            "dept/" + string + "_%s" % str(i) + ".html"
                        )
                        self.search_user_info()
                        i += 1

        self.return_user_info_results()

    def search_user_info(self):
        s = self.dept_screen_config
        dept_row = int(s.get("dept_row", 3))
        dept_col_start = int(s.get("dept_col_start", 29))
        dept_col_check_end = int(s.get("dept_col_check_end", 31))
        dept_col_end = int(s.get("dept_col_end", 80))
        mgr_row = int(s.get("manager_row", 4))
        mgr_code_start = int(s.get("manager_code_col_start", 22))
        mgr_code_end = int(s.get("manager_code_col_end", 26))
        mgr_name_start = int(s.get("manager_name_col_start", 29))
        mgr_name_end = int(s.get("manager_name_col_end", 80))
        users_row_start = int(s.get("users_row_start", 9))
        users_row_end = int(s.get("users_row_end", 19))
        user_code_start = int(s.get("user_code_col_start", 19))
        user_code_end = int(s.get("user_code_col_end", 23))
        user_name_start = int(s.get("user_name_col_start", 27))
        user_name_end = int(s.get("user_name_col_end", 80))

        data_list = self.em.screen_get()

        if len(data_list[dept_row][dept_col_start:dept_col_check_end].strip()) > 0:
            dept = data_list[dept_row][dept_col_start:dept_col_end].strip()
            if dept not in self.disclosed_dept:
                logger.debug("\t\tDept: %s", dept)
                self.disclosed_dept.append(dept)

        if len(data_list[mgr_row][mgr_code_start:mgr_code_end].replace(" ", "")) == 4:
            code = data_list[mgr_row][mgr_code_start:mgr_code_end]
            name = data_list[mgr_row][mgr_name_start:mgr_name_end].strip()
            user = {"code": code, "name": name}
            logger.debug("\t\tuser: %s", user)
            if user not in self.disclosed_priv_accounts:
                self.disclosed_priv_accounts.append(user)
                logger.debug("\t\tpriv: %s", user)

        users_area = [
            data_list[x : x + 1] for x in range(users_row_start, users_row_end, 1)
        ]
        for line in users_area:
            if len(line[0][user_code_start:user_code_end].replace(" ", "")) == 4:
                code = line[0][user_code_start:user_code_end].strip()
                name = line[0][user_name_start:user_name_end].strip()
                user = {"code": code, "name": name}
                logger.debug("\t\tuser: %s", user)
                if user not in self.disclosed_accounts:
                    self.disclosed_accounts.append(user)
                    logger.debug("\t\tuser: %s", user)

    def return_user_info_results(self):
        departments = [
            self.disclosed_dept[x : x + 5]
            for x in range(0, len(self.disclosed_dept), 5)
        ]

        for dept in self.disclosed_dept:
            self.db.record(self.target, "department", dept, "found")
        for user in self.disclosed_accounts:
            self.db.record(
                self.target, "user", user["code"], "found", username=user["name"]
            )
        for user in self.disclosed_priv_accounts:
            self.db.record(
                self.target, "user_priv", user["code"], "found", username=user["name"]
            )

        logger.info("\tDepartments: count %s", len(self.disclosed_dept))
        for department in departments:
            logger.info("\t\t%s", department)

        logger.info("\tPriv Users: count %s", len(self.disclosed_priv_accounts))
        for priv_user in self.disclosed_priv_accounts:
            logger.info("\t\tU| C:%s| Ac:%s", priv_user["code"], priv_user["name"])

        logger.info("\tUsers: count %s", len(self.disclosed_accounts))
        for user in self.disclosed_accounts:
            logger.info("\t\tU| C:%s| Ac:%s", user["code"], user["name"])
