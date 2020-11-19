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
Scalyr monitor which collections various Raspberry Pi metrics such as the SoC temperature, voltage,
clock frequencies, etc.

Keep in mind that Raspberry Pi firmware tries to actively scale ARM core frequency based on the
demand to reduce the temperature and power usage.

This means that if you have very short bursty operations on RPI, this won't be really reflected in
the clock frequency metrics unless you decrease sample interval to a lower value (default is 30
seconds) so the values are actually gathering when those short bursty operations are performed.

This of course only holds true for default setups - if you overclocked you RPI or changed idle
frequencies, that may not be needed.
"""

if False:
    from typing import List

import os
import re
import subprocess

from collections import OrderedDict

import six

from scalyr_agent import ScalyrMonitor
from scalyr_agent import define_config_option
from scalyr_agent import define_log_field
from scalyr_agent import define_metric

__monitor__ = __name__

define_config_option(
    __monitor__,
    "vcgencmd_path",
    "Path to /opt/vc/bin/vcgencmd binary. Defaults to /opt/vc/bin/vcgencmd.",
    default="/opt/vc/bin/vcgencmd",
)

define_metric(
    __monitor__,
    "rpi.status.throttle_state",
    "Bit value for the throttle state metric.",
)

define_metric(
    __monitor__,
    "rpi.soc.temperature",
    "SoC temperature in Celsius",
)

define_metric(
    __monitor__,
    "rpi.arm.clock",
    "Clock for the ARM cores in MHz",
)
define_metric(
    __monitor__,
    "rpi.core.clock",
    "Clock for the VC4 scaler cores in MHz",
)
define_metric(
    __monitor__,
    "rpi.h264.clock",
    "Clock for the h264 block in MHz",
)
define_metric(
    __monitor__,
    "rpi.h264.clock",
    "Clock for the SD card interface in MHz",
)
define_metric(
    __monitor__,
    "rpi.h264.clock",
    "Clock for the SD card interface in MHz",
)

define_metric(
    __monitor__,
    "rpi.core.volts",
    "Voltage for VC4 core in Volts",
)
define_metric(
    __monitor__,
    "rpi.sdram_c.volts",
    "Voltage for SDRAM core in Volts",
)
define_metric(
    __monitor__,
    "rpi.sdram_i.volts",
    "Voltage for SDRAM I/O in Volts",
)
define_metric(
    __monitor__,
    "rpi.sdram_p.volts",
    "Voltage for SDRAM Phy in Volts",
)

def parse_clock(value):
    # type: (str) -> int
    clock = int(re.split(r"frequency\(.*?\)", value)[1].replace("=", ""))

    if not clock:
        return clock

    return int(clock / 1000 / 1000)  # MHz


def parse_volts(value):
    # type: (str) -> float
    volts = value.replace("volt=", "").replace("V", "")
    volts = round(float(volts), 2)
    return volts


# Maps Scalyr metric name to vcgencmd command args and result conversion function
COMMAND_ARGS_TO_METRIC_NAME_MAP = OrderedDict([
    ("rpi.status.throttled_state", {
        "args": ["get_throttled"],
        "parse_func": lambda v: bin(int(v.replace("throttled=", ""), 0)).replace("0b", "")
    }),

    # SoC related metrics
    ("rpi.soc.temperature", {
        "args": ["measure_temp"],
        "parse_func": lambda v: float(v.replace("temp=", "").replace("'C", "")),
    }),

    # Frequency clock metrics (in MHz)
    ("rpi.arm.clock", {
        "args": ["measure_clock", "arm"],
        "parse_func": parse_clock,
    }),
    ("rpi.core.clock", {
        "args": ["measure_clock", "core"],
        "parse_func": parse_clock,
    }),
    ("rpi.h264.clock", {
        "args": ["measure_clock", "H264"],
        "parse_func": parse_clock,
    }),
    ("rpi.sd.clock", {
        "args": ["measure_clock", "emmc"],
        "parse_func": parse_clock,
    }),
    ("rpi.vec.clock", {
        "args": ["measure_clock", "vec"],
        "parse_func": parse_clock,
    }),

    # Voltage metrics
    ("rpi.core.volts", {
        "args": ["measure_volts", "core"],
        "parse_func": parse_volts,
    }),
    ("rpi.sdram_c.volts", {
        "args": ["measure_volts", "sdram_c"],
        "parse_func": parse_volts,
    }),
    ("rpi.sdram_i.volts", {
        "args": ["measure_volts", "sdram_i"],
        "parse_func": parse_volts,
    }),
    ("rpi.sdram_p.volts", {
        "args": ["measure_volts", "sdram_p"],
        "parse_func": parse_volts,
    }),
])

define_log_field(__monitor__, "monitor", "Always ``raspberry_pi_monitor``.")


class RaspberryPiMetricsMonitor(ScalyrMonitor):
    def _initialize(self):
        self.__binary_path = self._config.get(
            "vcgencmd_path",
            convert_to=str,
            default="/opt/vc/bin/vcgencmd",
            required_field=True,
        )

        if not os.path.isfile(self.__binary_path):
            raise ValueError("Binary path %s doesn't exist" % (self.__binary_path))

    def gather_sample(self):
        # type: (None) -> None
        for metric_name, values in six.iteritems(COMMAND_ARGS_TO_METRIC_NAME_MAP):
            command_args = values["args"]
            parse_func = values["parse_func"]
            success, value = self._gather_value(command_args=command_args)

            if not success:
                self._logger.warn("Failed to retrieve value for metric %s: %s" % (metric_name, value))
                continue

            metric_value = parse_func(value)

            self._logger.emit_value(metric_name, metric_value)

    def _gather_value(self, command_args):
        # type: (List) -> str
        p = subprocess.Popen(
            args=[self.__binary_path] + command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )

        if six.PY3:
            try:
                (stdout, stderr,) = p.communicate(timeout=5)
            except subprocess.TimeoutExpired as e:
                return False, str(e)
        else:
            (stdout, stderr,) = p.communicate()

        if p.returncode != 0:
            return False, "Process exited with non-zero: stdout=%s,stderr=%s" % (stdout, stderr)

        return True, stdout.decode("utf-8").strip()
