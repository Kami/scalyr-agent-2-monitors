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

import mock
from flask import request

from scalyr_agent.test_base import ScalyrMockHttpServerTestCase

from custom_monitors.octoprint_monitor import OctoPrintMonitor

BASE_DIR = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, "../fixtures/octoprint")

with open(os.path.join(FIXTURES_DIR, "api_printer.json")) as fp:
    MOCK_200_RESPONSE = fp.read()


EXPECTED_VALUES = [
    ("state", "Printing", {'cancelling': 'False', 'closedOrError': 'False', 'error': 'False', 'finishing': 'False', 'operational': 'True', 'paused': 'False', 'pausing': 'False', 'printing': 'True', 'ready': 'False', 'resuming': 'False', 'sdReady': 'False'}),
    ("octoprint.bed.temperature.actual", 59.97, {}),
    ("octoprint.bed.temperature.target", 60, {}),
    ("octoprint.tool.temperature.actual", 209.92, {'tool': 'tool0'}),
    ("octoprint.tool.temperature.target", 210, {'tool': 'tool0'}),
]


def mock_invalid_auth_view_func():
    headers = dict(request.headers)

    if request.headers["X-Api-Key"] == "valid":
        return MOCK_200_RESPONSE

    return ("", 401, {})


class OctoPrintMonitorTestCase(ScalyrMockHttpServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(OctoPrintMonitorTestCase, cls).setUpClass()

        # Register mock route
        cls.mock_http_server_thread.app.add_url_rule(
            "/api/printer", view_func=mock_invalid_auth_view_func
        )

        cls.base_url = "http://%s:%s/" % (
            cls.mock_http_server_thread.host,
            cls.mock_http_server_thread.port,
        )

    def test_gather_sample_invalid_auth(self):
        monitor_config = {
            "module": "octoprint_monitor",
            "base_url": self.base_url,
            "api_key": "invalid"
        }
        mock_logger = mock.Mock()
        monitor = OctoPrintMonitor(monitor_config, mock_logger)

        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_logger.emit_value.call_count, 0)
        monitor.gather_sample()
        self.assertEqual(mock_logger.warn.call_count, 1)
        self.assertEqual(mock_logger.emit_value.call_count, 0)


    def test_gather_sample_success(self):
        monitor_config = {
            "module": "octoprint_monitor",
            "base_url": self.base_url,
            "api_key": "valid"
        }
        mock_logger = mock.Mock()
        monitor = OctoPrintMonitor(monitor_config, mock_logger)

        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_logger.emit_value.call_count, 0)
        monitor.gather_sample()
        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_logger.emit_value.call_count, 5)

        index = 0
        for expected_metric_name, expected_metric_value, expected_extra_fields in EXPECTED_VALUES:
            actual_metric_name = mock_logger.emit_value.call_args_list[index][0][0]
            actual_metric_value = mock_logger.emit_value.call_args_list[index][0][1]
            actual_extra_fields = mock_logger.emit_value.call_args_list[index][1].get("extra_fields", {})

            self.assertEqual(expected_metric_name, actual_metric_name)
            self.assertEqual(expected_metric_value, actual_metric_value)
            self.assertEqual(expected_extra_fields, actual_extra_fields)
            index += 1
