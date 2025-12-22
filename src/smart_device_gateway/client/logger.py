# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import sys
import logging
from colorama import Back, Fore, Style, init

from home_ai_hub.client.config import UserLoggingConfig

init(autoreset=True)

COLORS = {
    "DEBUG": Fore.GREEN,
    "INFO": Fore.BLUE,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.RED + Style.BRIGHT + Back.WHITE,
}


class ColorFormatter(logging.Formatter):
    def format(self, record):
        levelname = record.levelname

        record.color = COLORS.get(levelname, Style.RESET_ALL)
        record.reset = Style.RESET_ALL
        return super().format(record)


class ExitOnErrorHandler(logging.Handler):
    """Handler that exits the program on ERROR or CRITICAL log messages"""

    def __init__(self, exit_code=1):
        super().__init__()
        self.exit_code = exit_code
        # Only trigger on ERROR or CRITICAL
        self.setLevel(logging.CRITICAL)

    def emit(self, record):
        # Exit the program
        sys.exit(self.exit_code)


def configure_logging(config: UserLoggingConfig, exit_on_error=True, exit_code=1):
    """Configure logging with colored output and optional exit-on-error

    Args:
        config: Logging configuration
        exit_on_error: Whether to exit the program on ERROR or CRITICAL logs
        exit_code: Exit code to use when exiting on error
    """

    default_level = getattr(logging, config.log_level.upper(), logging.WARNING)

    # Basic configuration as before...
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Create formatter
    formatter = ColorFormatter(
        fmt="[{name:^10}] [{color}{levelname:^7}{reset}] {asctime}:{msecs:03.0f}: {message}",
        datefmt="%H:%M:%S",
        style="{",
    )
    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger.setLevel(default_level)
    root_logger.addHandler(console_handler)

    # Add exit-on-error handler if requested
    if exit_on_error:
        exit_handler = ExitOnErrorHandler(exit_code=exit_code)
        root_logger.addHandler(exit_handler)
