# Copyright 2020 Tomaz Muraus
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Scalyr monitor which retrieves fully anonymized DNS query related metrics from a Pi-hole
installations using Pi-hole API.
"""

import six
import requests

from scalyr_agent import ScalyrMonitor
from scalyr_agent import define_config_option
from scalyr_agent import define_log_field
from scalyr_agent import define_metric

__monitor__ = __name__

define_log_field(__monitor__, "monitor", "Always ``pihole_monitor``.")

define_config_option(
    __monitor__, "base_url", "Base URL to PiHole admin page (e.g. https://<ip>/).",
)
define_config_option(
    __monitor__, "basic_auth", "Optional basic auth credentials in username:password notation.",
)


class PiHoleMonitor(ScalyrMonitor):
    def _initialize(self):
        # type: () -> None
        self.__base_url = self._config.get(
            "base_url", convert_to=six.text_type, required_field=True,
        )
        self.__basic_auth_credentials = self._config.get(
            "basic_auth", convert_to=six.text_type, required_field=False,
        )

        if self.__base_url.endswith("/"):
            self.__base_url = str(self.__base_url[:-1])

        if self.__basic_auth_credentials:
            self.__auth = tuple(self.__basic_auth_credentials.split(":"))

            if len(self.__auth) != 2:
                raise ValueError("Invalid basic auth credentials")
        else:
            self.__auth = None

    def gather_sample(self):
        # type: () -> None
        url = self.__base_url + "/admin/api.php"

        resp = requests.get(url, auth=self.__auth)

        if resp.status_code != 200:
            self._logger.warn("Failed to retrieve printer data: %s" % (resp.text))
            return

        data = resp.json()

        self._logger.emit_value("pihole.dns_queries_today", data["dns_queries_today"])
        self._logger.emit_value("pihole.ads_blocked_today", data["ads_blocked_today"])
        self._logger.emit_value("pihole.ads_percentage_today", round(data["ads_percentage_today"], 1))
        self._logger.emit_value("pihole.domains_being_blocked", data["domains_being_blocked"])
        self._logger.emit_value("pihole.queries_cached", data["queries_cached"])
        self._logger.emit_value("pihole.queries_forwarded", data["queries_forwarded"])
        self._logger.emit_value("pihole.unique_domains", data["unique_domains"])
        self._logger.emit_value("pihole.unique_clients", data["unique_clients"])
        self._logger.emit_value("pihole.status", data["status"])
