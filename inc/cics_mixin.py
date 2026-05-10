import logging
import time

import pika

from inc.mq_includes import cicsexceptions, mq_basic_publish, que_dec

logger = logging.getLogger(__name__)


class CicsMixin:
    """CICS navigation and transaction-fuzzing methods."""

    def get_to_cics(self, cics_list_dict):
        self.cics_list_dict = cics_list_dict
        self.em.send_string(self.cics_launch_command)
        self.em.send_enter()
        time.sleep(self.sleep)
        self.em.send_string("CESN", 1, 2)
        self.em.send_enter()
        time.sleep(self.sleep)
        self.em.send_string(self.credentials["appcredentials"]["user"], 10, 26)
        self.em.send_string(
            self.credentials["appcredentials"]["password"],
            11,
            26,
        )
        self.em.send_enter()

    def assess_cics_screen(self):
        if self.cics_region not in cicsexceptions:
            self.em.send_string(self.cics_region)
            self.em.send_enter()
            time.sleep(5)

            for dictionary in self.cics_list_dict:
                if self.em.string_found(
                    int(dictionary["ypos"]),
                    int(dictionary["xpos"]),
                    dictionary["string"],
                ):
                    logger.info(
                        "checking: %s != %s",
                        self.cics_region.lower(),
                        self.em.string_get(
                            int(dictionary["eypos"]),
                            int(dictionary["expos"]),
                            len(self.cics_region),
                        ).lower(),
                    )

                    if (
                        not self.cics_region.lower()
                        == self.em.string_get(
                            int(dictionary["eypos"]),
                            int(dictionary["expos"]),
                            len(self.cics_region),
                        ).lower()
                    ):
                        # Auth and unknown return the cics region at this position.
                        # If it's not here something is wrong — screens can get
                        # stuck with a region restart.
                        self.cics_response = "cics_unknown_weird"
                        logger.error("Found unknown screen: %s", self.cics_region)
                        break
                    else:
                        self.cics_response = dictionary["type"]
                    break

                else:
                    self.cics_response = "cics_unknown"
                    logger.error("Found unknown screen: %s", self.cics_region)

            self.save_screen_specific(
                "cics/%s/%s/%s/%s.html"
                % (
                    self.cics_response,
                    self.cics_region[0],
                    self.cics_region[1],
                    self.cics_region,
                )
            )

    def check_cics_transactions(self):
        self.cics_continue = True
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=self.args.mq)
        )
        self.channel = connection.channel()
        self.channel.basic_qos(prefetch_count=1)

        for name in ["cics_unknown", "cics_unknown_weird"]:
            self.channel = que_dec(self.channel, name)

        for dictionary in self.cics_list_dict:
            self.channel = que_dec(self.channel, dictionary["type"])

        while self.cics_continue:
            for method_frame, properties, body in self.channel.consume("cics"):
                self.cics_region = body.decode()
                self.assess_cics_screen()

                self.channel.basic_ack(method_frame.delivery_tag)

                self.db.record(
                    self.target, "cics", self.cics_region, self.cics_response
                )
                mq_basic_publish(
                    self.channel, routing_key=self.cics_response, body=self.cics_region
                )

                if "unknown" in self.cics_response:
                    logger.error("Interesting transaction at %s", self.cics_region)
                    logger.error("Unknown response — screen in unknown state, stopping")
                    self.do_sleep()
                    self.cics_continue = False
                    self.terminate()
                    break

                # Process one message per outer loop iteration
                break

            self.channel.cancel()

        self.channel.close()
        connection.close()
