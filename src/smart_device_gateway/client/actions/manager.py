# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

"""
Action Manager - Handles action plugin management and execution

This module manages the execution of action plugins in a non-blocking way
using a queue and worker threads.
"""

import logging
import queue
import threading
from time import time, sleep
from typing import Dict, List

from pydantic import BaseModel

from .base import IActionPlugin, ActionResult


class ManagerStats(BaseModel):
    executed: int = 0
    failed: int = 0
    retried: int = 0


class ActionManager:
    """Manages actions plugins and executes actions in separate threads"""

    def __init__(self, max_workers: int = 2) -> None:
        self.__plugins: Dict[str, IActionPlugin] = {}
        self.__action_queue = queue.PriorityQueue()
        self.max_workers = max_workers
        self.__workers: List[threading.Thread] = []
        self.running = True
        self.__stats = ManagerStats()

        for i in range(max_workers):
            worker = threading.Thread(
                target=self.__worker_loop, name=f"ActionManager-{i}", daemon=True
            )
            worker.start()
            self.__workers.append(worker)
        self.logger = logging.getLogger("ActionManager")
        self.logger.info(f"Started ActionManager with {max_workers} workers")

    def register_plugin(self, plugin: IActionPlugin) -> bool:
        if plugin in self.__plugins:
            self.logger.warning(
                f"Tried to register '{plugin.name}' but it is already registered. Please first remove it"
            )
            return False
        self.__plugins[plugin.name] = plugin
        self.logger.info(f"Registered plugin: '{plugin.name.upper()}'")
        return True

    def queue_action(self, plugin_name: str, priority: int, *args, **kwargs) -> bool:
        """Queue an action for execution"""
        if plugin_name not in self.__plugins:
            self.logger.error(f"Plugin {plugin_name} not found")
            return False

        plugin = self.__plugins[plugin_name]
        if not plugin.is_enabled():
            self.logger.warning(f'Plugin "{plugin_name}" is disabled, skipping')
            return False

        if not plugin.validate(*args, **kwargs):
            self.logger.error(f"Validation failed for '{plugin_name}' plugin")
            return False

        action_item = (priority, time(), plugin_name, args, kwargs)
        self.__action_queue.put(action_item)
        return True

    def __worker_loop(self):
        while self.running:
            try:
                # Get action from queue
                priority, timestamp, plugin_name, args, kwargs = (
                    self.__action_queue.get(timeout=1.0)
                )

                plugin = self.__plugins[plugin_name]
                retry_count = 0

                while retry_count <= plugin.retry_count:
                    try:
                        result = plugin.execute(*args, **kwargs)

                        if result == ActionResult.SUCCESS:
                            self.__stats.executed += 1
                            self.logger.debug(
                                f"Action {plugin_name} executed successfully"
                            )
                            break
                        elif (
                            result == ActionResult.RETRY
                            and retry_count < plugin.retry_count
                        ):
                            self.__stats.retried += 1
                            retry_count += 1
                            sleep(plugin.retry_delay)
                            self.logger.debug(
                                f"Retrying action {plugin_name} (attempt {retry_count})"
                            )
                            continue
                        else:
                            self.__stats.failed += 1
                            self.logger.error(
                                f"Action {plugin_name} failed after {retry_count} retries"
                            )
                            break

                    except Exception as e:
                        self.logger.error(f"Exception in action {plugin_name}: {e}")
                        retry_count += 1
                        if retry_count <= plugin.retry_count:
                            sleep(plugin.retry_delay)

                self.__action_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker thread error: {e}")

    def shutdown(self):
        """Shutdown the action manager"""
        self.logger.info("Shutting down ActionManager")
        self.running = False

        # Wait for queue to empty
        try:
            self.__action_queue.join()
        except Exception as e:
            self.logger.error(f"Failed to close queue: {e}")

        # Cleanup plugins
        for plugin in self.__plugins.values():
            try:
                plugin.cleanup()
            except Exception as e:
                self.logger.error(f"'{plugin.name}' plugin cleanup failed: {e}")

        # Wait for workers to finish
        for worker in self.__workers:
            worker.join(timeout=2.0)

    def get_stats(self) -> Dict:
        """Get execution statistics"""
        return self.__stats.model_dump()

    def list_plugins(self) -> List[str]:
        """List registered plugins"""
        return list(self.__plugins.keys())
