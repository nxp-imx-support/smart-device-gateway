# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import os

from colorama import Fore, Style

GREEN = f"{Style.BRIGHT}{Fore.GREEN}"
RED = f"{Style.BRIGHT}{Fore.RED}"
RESET = f"{Style.RESET_ALL}"


def get_terminal_width() -> int:
    console_size = os.get_terminal_size()
    return console_size.columns
