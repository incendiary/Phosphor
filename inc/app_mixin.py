import logging
import sys
import time

import pika

from inc.mq_includes import mq_basic_publish, que_dec

logger = logging.getLogger(__name__)


class AppMixin:
    """Application-code discovery and bulk-auth testing methods."""

    @property
    def _bulk_prepend(self):
        return "%s_%s_" % (
            self.credentials["appcredentials"]["user"],
            self.environment["name"],
        )

    def make_and_set_folder_path(self):
        self.path_to_folder = None

        if self.environment is not None:
            self.path_to_folder = "app/%s/%s/%s/%s/%s" % (
                self.credentials["appcredentials"]["user"],
                self.environment["name"],
                self.application_response,
                self.app_code[0],
                self.app_code[1],
            )
        else:
            self.path_to_folder = "app/%s/%s/%s/%s" % (
                self.credentials["appcredentials"]["user"],
                self.application_response,
                self.app_code[0],
                self.app_code[1],
            )

    def look_for_app_code(self):
        for dict in self.application_list_dict:
            logger.debug(
                "\tLooking for %s at x:%s y:%s",
                dict["string"],
                dict["xpos"],
                dict["ypos"],
            )
            logger.debug(
                "\tfound %s",
                self.em.string_get(
                    int(dict["ypos"]), int(dict["xpos"]), len(dict["string"])
                ),
            )

            if self.em.string_found(
                int(dict["ypos"]), int(dict["xpos"]), dict["string"]
            ):
                self.application_response = dict["type"]

                if self.bulk_app_mode:
                    self.mq_queue = self._bulk_prepend + dict["type"]
                else:
                    self.mq_queue = dict["type"]

                return

    def assess_app_screen(self):
        self.em.send_clear()
        self.em.send_string(self.app_code)
        logger.debug("Sent App Code")
        self.em.send_enter()

        try:
            self.em.wait_for_field()
        except Exception:
            self.do_sleep()

        # Reset on each assessment to avoid bleed-over from previous iteration.
        self.application_response = None
        self.mq_queue = None

        if self.app_code in self.bad_app_codes:
            self.application_response = "app_unknown"
            self.mq_queue = "app_unknown"
            if self.bulk_app_mode:
                self.mq_queue = self._bulk_prepend + "app_unknown"

        if not any(
            d["string"].lower()
            == self.em.string_get(
                int(d["ypos"]), int(d["xpos"]), len(d["string"])
            ).lower()
            for d in self.application_list_dict
        ):
            self.application_response = "app_unknown"
            self.mq_queue = "app_unknown"

            if self.bulk_app_mode:
                self.mq_queue = self._bulk_prepend + "app_unknown"

        if (
            self.check_screen_for_string("Retry later if signon is rejected")
            and self.app_code != "sfa"
            and self.app_code != "sys"
        ):
            logger.error("At login screen stuck, restarting")
            self.terminate()
            sys.exit()

        if (
            self.check_screen_for_string("DFHAC2001")
            and self.app_code != "sfa"
            and self.app_code != "sys"
        ):
            logger.error("At login screen stuck, restarting")
            self.terminate()
            sys.exit()

        elif self.app_code not in self.bad_app_codes:
            self.look_for_app_code()

        self.make_and_set_folder_path()
        self.save_screen_specific("%s/%s.html" % (self.path_to_folder, self.app_code))

    def check_application(self, application_list_dict):
        self.application_list_dict = application_list_dict

        self.app_continue = True
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.args.mq)
        )
        self.channel = connection.channel()
        self.channel.basic_qos(prefetch_count=1)

        if self.bulk_app_mode:
            for dictionary in self.application_list_dict:
                self.channel = que_dec(
                    self.channel, self._bulk_prepend + dictionary["type"]
                )
            que_to_consume = self._bulk_prepend + "app"
        else:
            for dictionary in self.application_list_dict:
                self.channel = que_dec(self.channel, dictionary["type"])
            que_to_consume = "app"

        while self.app_continue:
            logger.info("Consuming: %s", que_to_consume)

            for method_frame, properties, body in self.channel.consume(
                que_to_consume.lower()
            ):
                self.app_code = body.decode()
                logger.debug("Assessing %s", self.app_code)

                if self.app_code in self.bad_app_codes:
                    self.application_response = "app_unknown"
                    self.mq_queue = "app_unknown"
                else:
                    self.assess_app_screen()

                logger.debug("Assessing complete")

                self.channel.basic_ack(method_frame.delivery_tag)

                logger.debug(
                    "\tresponse: %s\tcode:%s", self.application_response, self.app_code
                )
                logger.debug("\tMQ: %s", self.mq_queue)

                self.db.record(
                    self.target,
                    "app",
                    self.app_code,
                    self.application_response,
                    username=self.credentials["appcredentials"]["user"],
                    environment=self.environment["name"] if self.environment else None,
                )
                mq_basic_publish(
                    self.channel,
                    routing_key=self.mq_queue,
                    body=self.app_code,
                )

                if "unknown" in self.application_response:
                    logger.error("Unknown app transaction at %s", self.mq_queue)
                    logger.error("Unknown response — screen in unknown state, stopping")
                    time.sleep(self.sleep)
                    self.app_continue = False
                    self.terminate()
                    break

                if (
                    self.environment["default"].lower() == "false"
                    and "auth" in self.application_response
                ):
                    logger.error("Got Auth in secondary environment, restarting")
                    time.sleep(self.sleep)
                    self.app_continue = False
                    self.terminate()
                    break

                # Process one message per outer loop iteration
                break

            self.channel.cancel()

        self.channel.close()
        connection.close()
