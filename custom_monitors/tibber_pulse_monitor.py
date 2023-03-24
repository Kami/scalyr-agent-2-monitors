# Copyright 2023 Tomaz Muraus
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
Scalyr agent monitor which collects real time electricity usage data (in watts) from Tibber Pulse
device.
"""

import time

from scalyr_agent import ScalyrMonitor
from scalyr_agent import define_config_option
from scalyr_agent import define_log_field
from scalyr_agent import define_metric

import tibber

__monitor__ = __name__

define_config_option(
    __monitor__,
    "access_token",
    "Tibber access token which needs to have home and realtime read permissions.",
)
define_config_option(
    __monitor__,
    "sample_write_interval",
    "How often (in seconds) to write sample into the metrics log file. Data is streamed to the "
    "monitor in real time (every second or so) over a websocket, but we only write it to a file "
    "every X seconds.",
    default=30,
)
define_metric(
    __monitor__,
    "tibber.consumption",
    "Current electricity consumption in watts",
)

import logging

class TibberPulselectricityConsumptionMonitor(ScalyrMonitor):
    def _initialize(self):
        self.__access_token = self._config.get(
            "access_token",
            convert_to=str,
            required_field=True,
        )
        self.__sample_write_interval = self._config.get(
            "sample_write_interval",
            convert_to=int,
            required_field=True,
        )

        self._setup_logging()

        self._account = tibber.Account(self.__access_token)
        self._home = self._account.homes[0]

        self._stopped = False
        self._callbacks_added = False

        self._last_sample_ts = 0

    def _setup_logging(self):
        # Silence default very noisy loggers
        silenced_loggers = [
            "tibber",
            "websockets",
            "aiohttp",
            "home",
            "gql"
        ]

        for logger_name in logging.root.manager.loggerDict:
            for silenced_logger_name in silenced_loggers:
                if logger_name.startswith(silenced_logger_name) and "tibber_pulse_monitor" not in logger_name:
                    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

    def _add_callbacks(self):
        if self._callbacks_added:
            return

        def when_to_stop(data):
            return self._stopped or not self._run_state.is_running()

        @self._home.event("live_measurement")
        async def handle_sample(data):
            now_ts = int(time.time())

            if self._last_sample_ts + self.__sample_write_interval < now_ts:
                extra_fields = {
                    "home": self._home.id,
                    "voltage_phase": data.voltage_phase_1,
                }
                self._logger.emit_value("tibber.consumption", data.power, extra_fields=extra_fields)

                self._last_sample_ts = now_ts

        self._home.start_live_feed(user_agent="ScalyrAgentMonitor/0.0.1", exit_condition=when_to_stop)

        self._callbacks_added = True

    def stop(self, *args, **kwargs):
        self._stopped = True
        super(TibberPulselectricityConsumptionMonitor, self).stop(*args, **kwargs)

    def gather_sample(self):
        # type: () -> None
        # This monitor is async and uses callback so gather_sample is a no-op.
        if not self._callbacks_added:
            # We add callbacks on first iteration since "_initialize()" is called before we call
            # parent constructor so not all the thread related state is available yet
            self._add_callbacks()
