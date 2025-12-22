# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

from typing import Optional
from gi.repository import GLib
from typing_extensions import Callable

class WatchDog():
    def __init__(self, timeout: float, callback: Callable):
        self.timeout_id = None
        self.timeout = timeout
        self.callback = callback

    def start(self):
        """Start watchdog timer"""

        def on_timeout():
            self.callback()
            return False # Don't repeat

        self.timeout_id = GLib.timeout_add(int(self.timeout * 1000), on_timeout)

    def cancel(self):
        if not self.timeout_id:
            return

        GLib.source_remove(self.timeout_id)
        self.timeout_id = None
