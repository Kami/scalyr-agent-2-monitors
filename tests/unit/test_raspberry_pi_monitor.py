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

import os

from scalyr_agent.test_base import ScalyrTestCase

import mock

from custom_monitors.raspberry_pi_monitor import RaspberryPiMetricsMonitor

__all__ = ["RaspberryPiMetricsMonitor"]


BASE_DIR = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, "../fixtures")

EXPECTED_VALUES = [
    ("rpi.status.throttled_state", "0"),
    ("rpi.soc.temperature", 49),
    ("rpi.arm.clock", 1800),
    ("rpi.core.clock", 500),
    ("rpi.h264.clock", 0),
    ("rpi.sd.clock", 250),
    ("rpi.vec.clock", 0),
    ("rpi.core.volts", 0.94),
    ("rpi.sdram_c.volts", 1.1),
    ("rpi.sdram_i.volts", 1.1),
    ("rpi.sdram_p.volts", 1.1),
]


class RaspberryPiMonitorTestCase(ScalyrTestCase):
    def test_gather_sample(self):
        monitor_config = {
            "module": "raspberry_pi_monitor",
            "vcgencmd_path": os.path.join(FIXTURES_DIR, "mock_vcgencmd")
        }
        mock_logger = mock.Mock()
        monitor = RaspberryPiMetricsMonitor(monitor_config, mock_logger)

        self.assertEqual(mock_logger.emit_value.call_count, 0)
        monitor.gather_sample()
        self.assertEqual(mock_logger.emit_value.call_count, 11)

        index = 0
        for expected_metric_name, expected_metric_value in EXPECTED_VALUES:
            actual_metric_name = mock_logger.emit_value.call_args_list[index][0][0]
            actual_metric_value = mock_logger.emit_value.call_args_list[index][0][1]

            self.assertEqual(expected_metric_name, actual_metric_name)
            self.assertEqual(expected_metric_value, actual_metric_value)
            index += 1
