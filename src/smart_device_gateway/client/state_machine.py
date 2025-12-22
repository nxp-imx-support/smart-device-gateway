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
from enum import Enum
from typing import Any, Callable, List, Optional, Set, Dict

class ApplicationStates(Enum):
    IDLE = 0
    LISTEN = 1
    SEARCH = 2
    WAIT = 3
    SPEAK = 4
    RECOVERY = 5
    DOWN = -1



class StateManager:
    __transitions = {
        ApplicationStates.IDLE: {ApplicationStates.LISTEN, ApplicationStates.RECOVERY, ApplicationStates.DOWN},
        ApplicationStates.LISTEN: {ApplicationStates.SEARCH, ApplicationStates.RECOVERY, ApplicationStates.DOWN},
        ApplicationStates.SEARCH: {ApplicationStates.LISTEN, ApplicationStates.WAIT, ApplicationStates.RECOVERY, ApplicationStates.DOWN},
        ApplicationStates.WAIT: {ApplicationStates.IDLE, ApplicationStates.SPEAK, ApplicationStates.RECOVERY, ApplicationStates.DOWN},
        ApplicationStates.SPEAK: {ApplicationStates.IDLE, ApplicationStates.RECOVERY, ApplicationStates.DOWN},
        ApplicationStates.RECOVERY: {ApplicationStates.IDLE, ApplicationStates.DOWN},
        ApplicationStates.DOWN: {}
    }

    def __init__(self, allow_edition: bool = False):
        self.allow_edition = allow_edition
        self.__on_enter: Dict[ApplicationStates, List[Callable]] = {}
        self.__on_exit: Dict[ApplicationStates, List[Callable]] = {}
        self.__allowed: Dict[ApplicationStates, Set[ApplicationStates]] = self.__transitions

    def register_enter_action(self, state: ApplicationStates, action: Callable):
        callbacks = self.__on_enter.setdefault(state, [])
        callbacks.append(action)

    def register_exit_action(self, state: ApplicationStates, action: Callable):
        callbacks = self.__on_exit.setdefault(state, [])
        callbacks.append(action)

    def is_transition_allowed(self, curr: ApplicationStates, new: ApplicationStates) -> bool:
        return new in self.__allowed[curr]

    def enter(self, state: ApplicationStates, context=None):
        for action in self.__on_enter.get(state, []):
            action(context)

    def exit(self, state: ApplicationStates, context=None):
        for action in self.__on_exit.get(state, []):
            action(context)

    def allow_transition(self, from_state: ApplicationStates, to_state: ApplicationStates) -> bool:
        if not self.allow_edition:
            return False
        self.__allowed[from_state].add(to_state)
        return True

    def allow_to_all_from(self, from_state: ApplicationStates) -> bool:
        if not self.allow_edition:
            return False
        self.__allowed[from_state] = set(ApplicationStates)
        return True



class StateMachine:
    def __init__(self, allow_edition: bool = False):
        self.manager = StateManager(allow_edition=allow_edition)
        self.__state = ApplicationStates.IDLE
        self.logger = logging.getLogger("StateMachine")


    def transition_to(self, new_state: ApplicationStates, context: Optional[Any] = None) -> bool:
        if self.state == new_state:
            self.logger.debug(f"System is already in {new_state.name} state")
            return True

        if not self.manager.is_transition_allowed(self.state, new_state):
            self.logger.warning(
                f"Invalid transition: {self.state.name} → {new_state.name}"
            )
            return False

        self.manager.exit(self.state, context)
        self.manager.enter(new_state, context)
        self.logger.info(f"Transition: {self.state.name} → {new_state.name}")

        self.__state = new_state
        return True

    @property
    def state(self) -> ApplicationStates:
        return self.__state
