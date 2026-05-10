import logging
import sys
import time

logger = logging.getLogger(__name__)


class CemtMixin:
    """CEMT transaction enumeration methods."""

    def find_cemt_transactions_on_screen(self):
        char = ["Tra", "(", ")"]
        data_list = self.em.screen_get()
        for data_line in data_list:
            for split_elements in data_line.split():
                if "tra(" in split_elements.lower():
                    region = split_elements.translate(
                        str.maketrans("", "", "".join(char))
                    )
                    self.transaction_codes.append(region)

    def get_cemt_transactions(self):
        self.em.send_clear()
        self.em.send_string("cemt")
        self.em.send_enter()
        self.em.send_string("i trans")
        self.em.send_enter()
        logger.info("Should be in CEMT trans. Starting Scrape")
        logger.info("\tIdentifying Transaction Codes:")

        self.find_cemt_transactions_on_screen()
        self.em.send_pf8()

        while self.count_occurances_in_screen("+") >= 2:
            self.find_cemt_transactions_on_screen()
            time.sleep(0.05)
            self.em.send_pf8()

        else:
            if len(self.transaction_codes) > 0:
                self.find_cemt_transactions_on_screen()
                chunks = [
                    self.transaction_codes[x : x + 5]
                    for x in range(0, len(self.transaction_codes), 5)
                ]
                for code in self.transaction_codes:
                    self.db.record(self.target, "cemt", code, "found")
                for chunk in chunks:
                    logger.info("\t\t%s", chunk)
            else:
                logger.error("Unexpected Screen")
                sys.exit()
