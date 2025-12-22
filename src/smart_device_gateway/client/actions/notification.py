# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import datetime
from typing import Literal, Optional

from home_ai_hub.client.config import UserActionNotificationConfig

from ..utils import GREEN, RESET
from .base import ActionConfig, ActionResult, IActionPlugin


class NotificationAction(IActionPlugin):
    def __init__(self, config: UserActionNotificationConfig):
        super().__init__("notification", config)

        self.log_level = config.log_level
        self.include_metadata = config.include_metadata
        self.custom_format = config.custom_format
        self.console_output = config.console_output

    def execute(
        self,
        is_ww: bool = False,
        ww: Optional[str] = None,
        ww_id: Optional[str] = None,
        timestamp: Optional[float] = None,
        message: Optional[str] = None,
    ) -> ActionResult:
        notification_msg = (
            self.format_default_message(ww, ww_id, timestamp)
            if not message and ww and ww_id
            else message
        )

        # Log the notification
        if self.log_level.upper() == "INFO":
            self.logger.info(notification_msg)
        elif self.log_level.upper() == "DEBUG":
            self.logger.debug(notification_msg)
        elif self.log_level.upper() == "WARNING":
            self.logger.warning(notification_msg)

        if not self.console_output:
            return ActionResult.SUCCESS

        if is_ww:
            print(f"🎙️  Wake word detected: {GREEN}{ww}{RESET}")
        else:
            print(notification_msg)
        return ActionResult.SUCCESS

    def format_default_message(
        self, ww_str: str, ww_id: str, timestamp: Optional[float]
    ) -> str:
        message = f"Wake word: '{ww_str}' ID: {ww_id} "

        if not timestamp:
            return message

        dectected_time = datetime.datetime.fromtimestamp(timestamp)

        return message + f" / Time: {dectected_time.strftime('%Y-%m-%d %H:%M:%S')}"
