# Copyright 2022 Tomaz Muraus
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
DataSet agent montiors which reports number of hops and rtt duration for each hop for a specific
destination address.

It's based on top of fast-mda-traceroute library.

NOTE: This monitor is Python 3.8+ only
"""

from typing import Dict
from typing import Any
from typing import Optional
from typing import cast

import socket
import time
import subprocess

import six

from scalyr_agent import util as scalyr_util
from scalyr_agent import ScalyrMonitor
from scalyr_agent import define_config_option
from scalyr_agent import define_log_field

__monitor__ = __name__

define_log_field(__monitor__, "monitor", "Always ``traceroute_monitor``.")

define_config_option(
    __monitor__, "destination", "Destination IPv4 address for the traceroute.",
)


class TracerouteMonitor(ScalyrMonitor):
    def _initialize(self) -> None:
        self.__destination = self._config.get(
            "destination", convert_to=six.text_type, required_field=True,
        )

        self.__label = self._config.get(
            "label", convert_to=six.text_type, required_field=False,
        )

        # We only support IPv4 so we manually resolve it to IPv4 address otherwise the underlying
        # library may resolve it to IPv6 address and it won't work
        self.__destination_ipv4 = socket.gethostbyname(self.__destination)

    def gather_sample(self) -> None:
        result = self.__run_traceroute_and_parse_output()

        if not result:
            return None

        extra_fields = {
            "destination": result["destination"],
            "destination_original": self.__destination,
            "label": self.__label or "",
            "hops": ",".join(result["hops"]),
            "hop_rtts": ",".join([str(value) for value in result["hop_rtts"]]),
            "total_rtt": round(sum(result["hop_rtts"]), 2),
            "method": result["method"]
        }
        self._logger.emit_value("traceroute.hops", result["hops_count"], extra_fields=extra_fields)

    def __run_traceroute_and_parse_output(self) -> Optional[Dict[str, Any]]:
        # TODO: Add info on how to configure Docker monitor to exclude fetching log from this
        # container
        ts_now = int(time.time())
        cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            f"fast-mda-traceroute-{ts_now}",
            "ghcr.io/dioptra-io/fast-mda-traceroute",
            "--format",
            "scamper-json",
            "--max-round",
            "10",
            "--wait",
            "3000",
            self.__destination_ipv4,
        ]

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            self._logger.warn(f"Failed to perform traceroute for desination {self.__destination}: {e.stderr}")
            return None

        result = self.__parse_output(output=output)
        return result

    def __parse_output(self, output: bytes) -> Optional[Dict[str, Any]]:
        output = output.decode("utf-8")

        parsed_data = []
        for line in output.splitlines():
            line = line.strip()

            if not line:
                continue

            item = scalyr_util.json_decode(line)
            parsed_data.append(item)

        if len(parsed_data) == 0:
            self._logger.warn(f"Parsed data is empty")
            self._logger.warn(f"Output: {output}")
            return None

        items = [item for item in parsed_data if item["type"] == "tracelb"]

        if len(items) != 1:
            self._logger.warn("Parsed data is missing or having more than one tracelb item")
            self._logger.warn(f"Output: {output}")
            return None

        data: Dict[str, Any] = items[0]

        hops = []
        hop_rtts = []

        if not data.get("nodes", None):
            self._logger.warn("Parsed data is missing nodes key (wait argument may be too low)")
            self._logger.warn(f"Output: {output}")
            return None

        # Parse RTTs from the result
        for node in data["nodes"]:
            hop = node["addr"]
            hop = node["links"][-1][-1]["addr"]
            hops.append(hop)
            # NOTE: We only use the last packet
            try:
                node_rtt = node["links"][-1][-1]["probes"][-1]["replies"][-1]["rtt"]
            except KeyError:
                self._logger.warn(f"Failed to parse node links", exc_info=True)
                self._logger.warn(f"Output: {output}")
                continue

            hop_rtts.append(node_rtt)

        result = {
            "destination": data["dst"],
            "hops_count": data["nodec"],
            "method": data["method"],
            "hop_rtts": hop_rtts,
            "hops": hops,
        }
        return result
