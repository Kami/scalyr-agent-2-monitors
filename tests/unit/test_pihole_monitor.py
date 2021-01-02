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

from custom_monitors.pihole_monitor import PiHoleMonitor

BASE_DIR = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(BASE_DIR, "../fixtures/pihole")

with open(os.path.join(FIXTURES_DIR, "api.json")) as fp:
    MOCK_200_RESPONSE = fp.read()


EXPECTED_VALUES = [
    ("pihole.dns_queries_today", 64207, {}),
    ("pihole.ads_blocked_today", 2409, {}),
    ("pihole.ads_percentage_today", 3.8, {}),
    ("pihole.domains_being_blocked", 58460, {}),
    ("pihole.queries_cached", 16342, {}),
    ("pihole.queries_forwarded", 43198, {}),
    ("pihole.unique_domains", 696, {}),
    ("pihole.unique_clients", 12, {}),
    ("pihole.status", "enabled", {}),
]


def mock_invalid_auth_view_func():
    headers = dict(request.headers)

    if request.headers.get("Authorization", None) == "Basic dmFsaWQ6dmFsaWQ=":
        return MOCK_200_RESPONSE

    return ("", 401, {})


class PiHoleMonitorTestCase(ScalyrMockHttpServerTestCase):
    @classmethod
    def setUpClass(cls):
        super(PiHoleMonitorTestCase, cls).setUpClass()

        # Register mock route
        cls.mock_http_server_thread.app.add_url_rule(
            "/admin/api.php", view_func=mock_invalid_auth_view_func
        )

        cls.base_url = "http://%s:%s/" % (
            cls.mock_http_server_thread.host,
            cls.mock_http_server_thread.port,
        )

    def test_gather_sample_invalid_auth(self):
        monitor_config = {
            "module": "pihole_monitor",
            "base_url": self.base_url,
            "basic_auth": "invalid:invalid"
        }
        mock_logger = mock.Mock()
        monitor = PiHoleMonitor(monitor_config, mock_logger)

        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_logger.emit_value.call_count, 0)
        monitor.gather_sample()
        self.assertEqual(mock_logger.warn.call_count, 1)
        self.assertEqual(mock_logger.emit_value.call_count, 0)


    def test_gather_sample_success(self):
        monitor_config = {
            "module": "pihole_monitor",
            "base_url": self.base_url,
            "basic_auth": "valid:valid"
        }
        mock_logger = mock.Mock()
        monitor = PiHoleMonitor(monitor_config, mock_logger)

        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_logger.emit_value.call_count, 0)
        monitor.gather_sample()
        self.assertEqual(mock_logger.warn.call_count, 0)
        self.assertEqual(mock_logger.emit_value.call_count, 9)

        index = 0
        for expected_metric_name, expected_metric_value, expected_extra_fields in EXPECTED_VALUES:
            actual_metric_name = mock_logger.emit_value.call_args_list[index][0][0]
            actual_metric_value = mock_logger.emit_value.call_args_list[index][0][1]

            self.assertEqual(expected_metric_name, actual_metric_name)
            self.assertEqual(expected_metric_value, actual_metric_value)
            index += 1
