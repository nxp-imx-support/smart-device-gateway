# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import logging

from .. import init_voice

init_voice()

from gi.repository import GLib, Gst

from ..config import UserMonitorVadConfig


class VadMonitor:
    def __init__(
        self,
        controller,
        name: str,
        vad: Gst.Element,
        config: UserMonitorVadConfig,
        threshold: float,
    ) -> None:
        self.name = name
        self.vad = vad

        self.logger = logging.getLogger(self.name)

        self.logger.debug(f"Monitor initialized with configuration: {config}")

        # Config
        self.print_progress = config.print_progress
        self.vad_threshold = threshold
        self.silence_time_sec = config.silence_time_sec
        self.monitor_time_sec = config.monitor_time_sec
        self.silence_tolerance = self.silence_time_sec // config.monitor_time_sec + 1

        assert self.silence_tolerance > 1

        # Monitor
        self.is_monitoring = False
        self.silence_count = 0
        self.timeout_id = None

        self.ctrl = controller

    def start(self):
        self.is_monitoring = True
        self.silence_count = 0

        timeout_ms = int(self.monitor_time_sec * 1000)
        if self.timeout_id:
            GLib.source_remove(self.timeout_id)

        self.logger.info("Vad Monitor started.")
        self.timeout_id = GLib.timeout_add(timeout_ms, self.monitor)

    def monitor(self):
        vad_metric = self.vad.get_property("vad-metric")

        if vad_metric > self.vad_threshold:
            self.silence_count = 0
            self.logger.debug("Voice activiy detectd - resetting silence counter")
            self.ctrl.on_voice(vad_metric)
            return True

        # Silence detect
        self.silence_count += 1

        # TODO move this to an action plugin, it take to long
        self.__print_progress()

        if self.silence_count >= self.silence_tolerance:
            self.ctrl.on_voice_end()
            self.timeout_id = None
        else:
            self.ctrl.on_silence()

        return self.is_monitoring

    def stop(self):
        self.logger.debug("Stoping Monitor...")
        self.is_monitoring = False

    def __print_progress(self):
        # Calculate perecetage for logging
        percentage = (self.silence_count / self.silence_tolerance) * 100

        # Print
        progress = f"Silence detected: {percentage:06.2f}% ({self.silence_count}/{self.silence_tolerance})"
        if self.print_progress:
            print(progress, end="\r", flush=True)
        else:
            self.logger.debug(progress)

    def get_silence_time_sec(self) -> float:
        return self.silence_count * self.monitor_time_sec

    def shutdown(self):
        if self.is_monitoring:
            self.logger.info("Monitor stopped externally")

        if self.timeout_id:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None

        self.is_monitoring = False
