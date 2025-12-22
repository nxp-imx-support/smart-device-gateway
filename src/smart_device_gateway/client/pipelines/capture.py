# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

from time import time
from typing import Optional

from .. import init_voice

init_voice()

from gi.repository import Gst

from ..config import (
    UserDebugConfig,
    UserPipelineConfig,
    GstElemConfig,
    UserVitConfig,
    VadConfig,
)
from .base import Pipeline, PipelineState
from .vad_monitor import VadMonitor
from .builder import CaptureBuilder

VALVE = "valve"
WW_REC = "ww_rec"


class CapturePipeline(Pipeline):
    def __init__(
        self,
        controller,
        config: UserPipelineConfig,
        card_config: GstElemConfig,
        openai_sink: GstElemConfig,
        vit_config: Optional[UserVitConfig],
        vad_config: Optional[VadConfig],
        debug_config: UserDebugConfig,
    ) -> None:
        debug_mic = config.debug if config.debug else debug_config.mic
        debug_ww = config.debug if config.debug else debug_config.ww
        take_snapshot = config.debug if config.debug else debug_config.pipeline_dots
        verbose_messages = (
            config.debug if config.debug else debug_config.verbose_bus_messages
        )

        builder = CaptureBuilder('valve', "ww_rec")

        super().__init__(
            pipeline=builder.build(
                card_config=card_config,
                openai_sink=openai_sink,
                vit_config=vit_config,
                vad_config=vad_config,
                debug_mic=debug_mic,
                debug_ww=debug_ww,
            ),
            name=config.name,
            take_snapshot=take_snapshot,
            verbose_messages=verbose_messages,
        )

        self.ctrl = controller
        self.__vit = None
        self.__vad_monitor = None
        self.__ww_sink = None
        self.on_state_changed = self.__on_state_change

        self.__valve = self.get_elem(VALVE)
        self.__openai_sink = self.get_elem(openai_sink.name)
        self.__openai_sink.connect("new-sample", self.__to_openai)

        if vit_config:
            self.__vit = self.get_elem(vit_config.name)
            self.on_message = self.__handle_vit_message

        if vad_config:
            vad, vad_monitor = vad_config
            vad_elem = self.get_elem(vad.name)

            self.__vad_monitor = VadMonitor(
                self.ctrl,
                "VadMonitor",
                vad_elem,
                vad_monitor,
                vad.vad_thr,
            )
        else:
            # TODO: add timer mechanism, so it work with a push button.
            pass
        if debug_ww:
            self.__ww_sink = self.get_elem(WW_REC)

    def __handle_vit_message(self, message: Gst.Message) -> None:
        if not self.__vit:
            return

        if message.src.name != self.__vit.name:
            return
        s = message.get_structure()
        if not s:
            self.logger.error("Failed to get vit structure")
            return

        det_res = s.get_value("detection_result")
        det_id = s.get_value("detected_id")
        det_str = s.get_value("detected_str")
        timestamp = time()

        self.logger.info(f"VIT message: result={det_res}, id={det_id}, str='{det_str}'")

        if det_res == 1:
            self.ctrl.on_wakeword(
                is_ww=True, ww=det_str, ww_id=det_id, timestamp=timestamp
            )

    def __on_state_change(self, new_state: PipelineState):
        if new_state != PipelineState.PLAYING:
            return
        self.close_valve()

    def __to_openai(self, sink: Gst.Element):
        sample = sink.emit("pull-sample")
        if not sample:
            return Gst.FlowReturn.OK

        buffer = sample.get_buffer()
        if buffer.get_size() == 0:
            self.logger.info("no data to send to openai")
            return Gst.FlowReturn.OK

        pcm = buffer.extract_dup(0, buffer.get_size())
        self.ctrl.openai.send_audio(pcm)
        return Gst.FlowReturn.OK

    def open_valve(self):
        if not self.__valve:
            raise RuntimeError("Valve got removed")
        self.logger.info("Openning valve to OpenAI")
        self.__valve.set_property("drop", False)

    def close_valve(self):
        if not self.__valve:
            raise RuntimeError("Valve got removed")
        self.logger.info("Clossing valve to OpenAI")
        self.__valve.set_property("drop", True)

    def start_monitor(self):
        if not self.__vad_monitor:
            self.logger.info("VAD is not enable. Monitoring is not possible")
            # Probably start a timer to switch back after N seconds.
            return
        self.__vad_monitor.start()

    def get_voice_end_message(self) -> str:
        if not self.__vad_monitor:
            # Return the time f the timer in ms
            return f"   Timeout ({1000.0:3.f}ms) reached for asking."
        silence_time = self.__vad_monitor.get_silence_time_sec()
        return f"💬  Speech ended after {silence_time:.3f}sec of silence."

    def stop_monitor(self):
        if not self.__vad_monitor:
            return
        self.__vad_monitor.stop()

    def shutdown_monitor(self):
        if not self.__vad_monitor:
            return
        self.__vad_monitor.shutdown()

    def cleanup(self) -> None:
        self.shutdown_monitor()
        return super().cleanup()
