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
from typing import Dict
from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel

from ..config import UserActionConfig


class ActionConfig(BaseModel):
    enabled: bool = False
    retry_count: int = 3
    retry_delay: float = 1.0
    model_config = {"extra": "forbid"}


class ActionResult(Enum):
    """Result of action execution"""

    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    SKIP = "skip"


class IActionPlugin(ABC):
    def __init__(self, name: str, config: UserActionConfig):
        self.name = name
        self.enabled = config.enabled
        self.retry_delay = config.retry_delay
        self.retry_count = config.retry_count

        self.__config = config

        self.logger = logging.getLogger(f"Action.{self.name.capitalize()}")
        self.logger.debug(f"Plugin initialized with configuration: {config}")

    @abstractmethod
    def execute(self, *args, **kwargs) -> ActionResult:
        """Execute the action. Must be implemented in subclasses."""
        pass

    def validate(self, *args, **kwargs) -> bool:
        """Validate action parameters. Override if nedded."""
        return True

    def cleanup(self):
        """Cleanup resources. Override if nedded"""
        pass

    def get_config_schema(self) -> Dict:
        """Get configuration schema for this plugin"""
        return self.__config.model_json_schema()

    def is_enabled(self) -> bool:
        return self.enabled

    def get_priority(self) -> int:
        return self.priority
