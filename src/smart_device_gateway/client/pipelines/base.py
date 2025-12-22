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
Pipeline Controller - Handles pipeline execution, state management, and control logic.

This module separates the control logic from pipeline construction, providing
a clean interface for running and managing GStreamer pipelines.
"""

import logging
import time
from enum import Enum
from typing import Callable, Optional

from .. import init_voice

init_voice()

from gi.repository import Gst

Q_PROPS_FOR_RTSP = "max-size-buffers=3 leaky=downstream"


def for_rtsp(pipeline: str) -> str:
    return pipeline.replace("! queue !", f"! queue {Q_PROPS_FOR_RTSP} !")


class PipelineState(str, Enum):
    """Pipeline state enumeration."""

    NULL = "NULL"
    READY = "READY"
    PAUSED = "PAUSED"
    PLAYING = "PLAYING"
    ERROR = "ERROR"


class Pipeline:
    """
    Controls GStreamer pipeline execution and state management.

    This class provides a clean interface for running pipelines, handling
    messages, and managing pipeline state without mixing concerns with
    pipeline construction.
    """

    def __init__(
        self,
        pipeline: str,
        name: str = "Pipeline",
        take_snapshot: bool = False,
        verbose_messages: bool = False,
    ):
        """
        Initialize the pipeline controller.

        Args:
            pipeline: The GStreamer pipeline to control
            name: Human-readable name for logging
        """
        self.name = name
        self.pipeline = for_rtsp(pipeline)
        self.logger = logging.getLogger(self.name.replace(" ", "."))
        self.state = PipelineState.NULL
        self.take_snapshot = take_snapshot
        self.verbose_messages = verbose_messages

        self.logger.info(f"Creating pipeline from str: {self.pipeline}")

        self._pipeline = Gst.parse_launch(self.pipeline)

        if not self._pipeline:
            raise RuntimeError("Unable to create Capture Pipeline.")

        # Callbacks
        self.on_message: Optional[Callable[[Gst.Message], None]] = None
        self.on_error: Optional[Callable[[str, str], None]] = None
        self.on_eos: Optional[Callable[[], None]] = None
        self.on_state_changed: Optional[Callable[[PipelineState], None]] = None

        # Setup bus monitoring
        self.__setup_bus_monitoring()

    def __setup_bus_monitoring(self) -> None:
        """Setup GStreamer bus message monitoring."""
        self.bus = self._pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self.__on_bus_message)

    def __on_bus_message(self, bus: Gst.Bus, message: Gst.Message) -> bool:
        """
        Handle GStreamer bus messages.

        Args:
            bus: The GStreamer bus
            message: The bus message

        Returns:
            True to continue monitoring, False to stop
        """
        msg_type = message.type

        # Call custom message handler if provided
        if self.on_message:
            self.on_message(message)

        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            error_msg = f"Pipeline Error: {err}"
            debug_msg = f"Debug: {debug}"

            self.logger.error(f"{error_msg}")
            self.logger.error(f"{debug_msg}")

            self.__set_state(PipelineState.ERROR)

            if self.on_error:
                self.on_error(error_msg, debug_msg)
            else:
                self.stop()

        elif msg_type == Gst.MessageType.EOS:
            self.logger.debug("End-of-Stream reached")
            if self.on_eos:
                self.on_eos()

        elif msg_type == Gst.MessageType.STATE_CHANGED:
            old_state, new_state, pending_state = message.parse_state_changed()
            src = message.src

            if src == self._pipeline:
                state_name = new_state.name
                self.logger.debug(
                    f"Pipeline state changed: {old_state.name} -> {new_state.name}"
                )

                # Update internal state
                if state_name in PipelineState:
                    self.__set_state(PipelineState(state_name))

            if self.take_snapshot:
                self.logger.debug("Taking snapshot on state changed.")
                Gst.debug_bin_to_dot_file(
                    self._pipeline,
                    Gst.DebugGraphDetails.ALL,
                    f"{self._pipeline.name}-{old_state.name}_{new_state.name}",
                )

        elif msg_type == Gst.MessageType.INFO:
            info, debug = message.parse_info()
            self.logger.info(f"{info}")

        elif msg_type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            self.logger.warning(f"Warning: {warn}")
        else:
            if self.verbose_messages:
                self.logger.warning(f"Unknown msg from: {message.src.name} element")

        return True

    def __set_state(self, new_state: PipelineState) -> None:
        """
        Set internal state and notify callback.

        Args:
            new_state: The new pipeline state
        """
        if self.state != new_state:
            self.state = new_state
            if self.on_state_changed:
                self.on_state_changed(new_state)

    def set_state(self, state: Gst.State) -> bool:
        """
        Set the GStreamer pipeline state.

        Args:
            state: The desired GStreamer state

        Returns:
            True if state change was successful, False otherwise
        """
        self.logger.debug(f"Setting pipeline state to {state.name}")

        ret = self._pipeline.set_state(state)
        if ret == Gst.StateChangeReturn.FAILURE:
            self.logger.error(f"Failed to set pipeline state to {state.name}")
            return False

        # Wait for state change to complete
        ret, current_state, pending_state = self._pipeline.get_state(
            Gst.CLOCK_TIME_NONE
        )
        if ret == Gst.StateChangeReturn.FAILURE:
            self.logger.error("Failed to get pipeline state")
            return False

        self.logger.debug(f"Pipeline state set to {current_state.name}")
        return True

    def ready(self) -> bool:
        return self.set_state(Gst.State.READY)

    def play(self) -> bool:
        """
        Start the pipeline (set to PLAYING state).

        Returns:
            True if successful, False otherwise
        """
        return self.set_state(Gst.State.PLAYING)

    def pause(self) -> bool:
        """
        Pause the pipeline.

        Returns:
            True if successful, False otherwise
        """
        return self.set_state(Gst.State.PAUSED)

    def stop(self) -> bool:
        """
        Stop the pipeline (set to NULL state).

        Returns:
            True if successful, False otherwise
        """
        success = self.set_state(Gst.State.NULL)

        return success

    def get_state(self) -> PipelineState:
        """
        Get the current pipeline state.

        Returns:
            The current pipeline state
        """
        return self.state

    def wait_for_state(self, target_state: PipelineState, timeout: float = 5.0) -> bool:
        """
        Wait for the pipeline to reach a specific state.

        Args:
            target_state: The state to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if target state was reached, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.state == target_state:
                return True
            time.sleep(0.1)

        self.logger.error(f"Timeout waiting for state {target_state}")
        return False

    def is_playing(self) -> bool:
        """Check if the pipeline is currently playing."""
        return self.state == PipelineState.PLAYING

    def is_stopped(self) -> bool:
        """Check if the pipeline is stopped."""
        return self.state == PipelineState.NULL

    def cleanup(self) -> None:
        """Clean up resources."""
        self.logger.debug("Cleanning up pipeline")
        self.stop()

        # Remove bus monitoring
        if self.bus:
            self.bus.remove_signal_watch()
            self.bus = None

    def get_elem(self, element: str) -> Gst.Element:
        e = self._pipeline.get_by_name(element)
        if not e:
            raise RuntimeError(f"Unable to find {element} in pipeline: {self.name}")
        return e
