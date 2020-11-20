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
Scalyr monitors which collects various 3D printer metrics (printer status, tool temperature, bed
temperature, etc.) using OctoPrint API.
"""

import six
import requests

from scalyr_agent import ScalyrMonitor
from scalyr_agent import define_config_option
from scalyr_agent import define_log_field
from scalyr_agent import define_metric

__monitor__ = __name__

define_log_field(__monitor__, "monitor", "Always ``octoprint_monitor``.")

define_config_option(
    __monitor__, "base_url", "Base URL to the octoprint instance.",
)
define_config_option(
    __monitor__, "api_key", "API key used to authenticate.",
)

define_metric(
    __monitor__, "octoprint.state", "3D printer status.",
)

define_metric(
    __monitor__,
    "octoprint.bed.temperature.actual",
    "3D printer actual bed temperature.",
)
define_metric(
    __monitor__,
    "octoprint.bed.temperature.target",
    "3D printer target bed temperature.",
)


define_metric(
    __monitor__,
    "octoprint.tool.temperature.actual",
    "3D printer target tool temperature.",
    extra_fields={"tool": ""},
)
define_metric(
    __monitor__,
    "octoprint.tool.temperature.target",
    "3D printer actual tool temperature.",
    extra_fields={"tool": ""},
)


class OctoPrintMonitor(ScalyrMonitor):
    def _initialize(self):
        # type: () -> None
        self.__base_url = self._config.get(
            "base_url", convert_to=str, required_field=True,
        )
        self.__api_key = self._config.get(
            "api_key", convert_to=str, required_field=True,
        )

        if self.__base_url.endswith("/"):
            self.__base_url = str(self.__base_url[:-1])

    def gather_sample(self):
        # type: () -> None
        url = self.__base_url + "/api/printer"
        headers = {"X-Api-Key": self.__api_key}
        resp = requests.get(url, headers=headers)

        if resp.status_code != 200:
            self._logger.warn("Failed to retrieve printer data: %s" % (resp.text))
            return

        data = resp.json()

        flags = data["state"]["flags"]
        flags = dict([(key, str(value)) for key, value in flags.items()])

        extra_fields = flags
        self._logger.emit_value(
            "state", data["state"]["text"], extra_fields=extra_fields
        )

        self._logger.emit_value(
            "octoprint.bed.temperature.actual", data["temperature"]["bed"]["actual"]
        )
        self._logger.emit_value(
            "octoprint.bed.temperature.target", data["temperature"]["bed"]["target"]
        )

        for key, value in six.iteritems(data["temperature"]):
            if not key.startswith("tool"):
                continue

            extra_fields = {"tool": key}

            self._logger.emit_value(
                "octoprint.tool.temperature.actual",
                data["temperature"]["bed"]["actual"],
                extra_fields=extra_fields,
            )
            self._logger.emit_value(
                "octoprint.tool.temperature.target",
                data["temperature"]["bed"]["target"],
                extra_fields=extra_fields,
            )
