import logging
import time

logger = logging.getLogger(__name__)

try:
    from inc.private_includes import return_password_reset_string
except ImportError:
    from inc.public_includes import return_password_reset_string


class PasswordMixin:
    """Password-reset automation methods."""

    def add_password_reset_info(self, info):
        self.password_reset_accounts = info

    def change_passwords(self):
        daily_password_reset = return_password_reset_string()

        self.connect_to_zos()
        for account in self.password_reset_accounts:
            logger.info("connected")
            self.em.wait_for_field()
            logger.info(
                "Changing password for: %s to: %s",
                account["user"],
                account["password"],
            )

            self.em.send_string(account["user"])
            self.send_tab_x_times(4)
            self.em.send_string(daily_password_reset)
            time.sleep(self.sleep)
            self.send_tab_x_times(8)
            self.em.send_string(account["password"], ypos=18, xpos=17)
            time.sleep(self.sleep)
            self.em.send_enter()
            self.em.send_string(account["password"], ypos=18, xpos=17)
            time.sleep(self.sleep)
            self.em.send_enter()
            time.sleep(self.sleep)
            self.em.reconnect()
