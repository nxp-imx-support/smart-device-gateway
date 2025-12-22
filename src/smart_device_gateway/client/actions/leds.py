# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

from typing import Literal, TypeAlias

from .base import ActionResult, IActionPlugin, ActionConfig
from ..config import UserActionLedConfig


class LedsAction(IActionPlugin):
    def __init__(self, config: UserActionLedConfig) -> None:
        super().__init__("led", config)

        self.path = config.path
        self.leds = config.leds
        self.min = config.min
        self.max = config.max

    def execute(self, value) -> ActionResult:
        led_value = max(self.min, min(self.max, value))

        for led in self.leds:
            path = self.path + led + "/brightness"
            try:
                with open(path, "w") as f:
                    f.write(str(led_value))
                self.logger.debug(f"led {led} set to {led_value}")
            except FileNotFoundError:
                self.logger.error(f"LED {path} not found.")
            except Exception as e:
                self.logger.error(f"Unkown error: {e}")

        return ActionResult.SUCCESS

    def cleanup(self):
        led_value = 0

        for led in self.leds:
            path = self.path + led + "/brightness"
            try:
                with open(path, "w") as f:
                    f.write(str(led_value))
                self.logger.debug(f"led {led} set to {led_value}")
            except FileNotFoundError:
                self.logger.error(f"LED {path} not found.")
            except Exception as e:
                self.logger.error(f"Unkown error: {e}")
