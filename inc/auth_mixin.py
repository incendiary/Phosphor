import logging

import pika

from inc.mq_includes import que_dec

logger = logging.getLogger(__name__)


class AuthMixin:
    """VTAM/app login and user-enumeration methods."""

    def vtam_login(self):
        self.em.send_string(self.credentials["vtamcredentials"]["user"])
        self.send_tab_x_times(4)
        self.em.send_string(self.credentials["vtamcredentials"]["password"])
        self.do_sleep()
        self.em.wait_for_field()
        self.em.send_enter()

    def set_region(self, region_login_position_list_dict):
        self.region_login_position = region_login_position_list_dict[0]

    def login_to_region(self):
        self.em.send_enter()
        self.em.move_to(
            int(self.region_login_position["ypos"]),
            int(self.region_login_position["xpos"]),
        )
        self.em.send_enter()

    def login_to_app(self):
        self.em.send_string(self.credentials["appcredentials"]["user"])
        self.send_tab_x_times(3)
        self.em.send_string(self.credentials["appcredentials"]["password"])
        if self.environment:
            self.em.send_string(
                self.environment["value"],
                int(self.environment["ypos"]),
                int(self.environment["xpos"]),
            )

        self.wait_for_field()
        self.em.send_enter()
        if self.args.overtype:
            self.wait_for_field()
            for d in self.overtype:
                self.em.send_string(d["value"], int(d["ypos"]), int(d["xpos"]))
                self.do_sleep()

    def add_username_field_location(self, list):
        self.username_field_location_dict = list[0]

    def add_username_responses(self, list):
        self.username_responses_list_dict = list

    def assess_login_screen(self):
        self.em.wait_for_field()
        self.em.send_string(
            self.username_to_check,
            ypos=int(self.username_field_location_dict["ypos"]),
            xpos=int(self.username_field_location_dict["xpos"]),
        )
        self.em.send_enter()

        if not any(
            d["string"].lower()
            == self.em.string_get(
                int(d["ypos"]), int(d["xpos"]), len(d["string"])
            ).lower()
            for d in self.username_responses_list_dict
        ):
            self.username_response = "user_unknown"
        else:
            self.look_for_login_code()

        self.save_screen_specific(
            "login/%s/%s.html" % (self.username_response, self.username_to_check)
        )

    def look_for_login_code(self):
        for d in self.username_responses_list_dict:
            if (
                d["string"].lower()
                == self.em.string_get(
                    int(d["ypos"]), int(d["xpos"]), len(d["string"])
                ).lower()
            ):
                self.username_response = d["type"]
                return

    def check_login(self):
        self.check_username_continue = True
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.args.mq)
        )
        self.channel = connection.channel()
        self.channel.basic_qos(prefetch_count=1)

        for name in ["user_valid", "user_invalid", "user_unknown"]:
            self.channel = que_dec(self.channel, name)

        while self.check_username_continue:
            for method_frame, properties, body in self.channel.consume("users"):
                self.username_to_check = body.decode()
                self.assess_login_screen()

                self.channel.basic_ack(method_frame.delivery_tag)

                logger.info(
                    "user %s is %s", self.username_to_check, self.username_response
                )

                self.db.record(
                    self.target,
                    "user",
                    self.username_to_check,
                    self.username_response,
                )
                self.channel.basic_publish(
                    exchange="",
                    routing_key=self.username_response,
                    body=self.username_to_check,
                    properties=pika.BasicProperties(delivery_mode=2),
                )

                if "unknown" in self.username_response:
                    logger.warning("Unknown response with %s", self.username_to_check)
                    logger.error("Unknown response — screen in unknown state, stopping")
                    self.check_username_continue = False
                    self.terminate()
                    break

                # Process one message per outer loop iteration
                break

            self.channel.cancel()

        self.channel.close()
        connection.close()
