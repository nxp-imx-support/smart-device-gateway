# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

from copy import deepcopy
from pathlib import Path
from typing import Callable

from home_ai_hub.client.config import UserDebugConfig, UserPipelineConfig, GstElemConfig

from .. import init_voice

init_voice()

from gi.repository import Gst

from .base import Pipeline
from .builder import PlaybackBuilder

SELECTOR = "selector"
SILENCE = "silence"
FILESRC = "filesrc0"


def get_pad(e: Gst.Element, pad_name: str) -> Gst.Pad:
    pad = e.get_static_pad(pad_name)
    if not pad:
        raise RuntimeError(f"Unable to get pad {pad_name} from {e.name}")
    return pad


class PlaybackPipeline(Pipeline):
    def __init__(
        self,
        controller,
        config: UserPipelineConfig,
        card_config: GstElemConfig,
        openai_src: GstElemConfig,
        debug_config: UserDebugConfig,
        beep_wav: str,
    ) -> None:
        take_snapshot = config.debug if config.debug else debug_config.pipeline_dots
        verbose_messages = (
            config.debug if config.debug else debug_config.verbose_bus_messages
        )
        use_filesrc = Path(beep_wav).exists() if beep_wav else False
        builder = PlaybackBuilder(SELECTOR, FILESRC, SILENCE)

        super().__init__(
            builder.build(card_config, openai_src, use_filesrc),
            name=config.name,
            take_snapshot=take_snapshot,
            verbose_messages=verbose_messages,
        )
        if not use_filesrc:
            self.logger.warning(
                f"Unable to create filesrc because '{beep_wav}' doesn't exists"
            )

        self.ctrl = controller
        self.use_filesrc = use_filesrc
        self.src = deepcopy(openai_src)

        self.__selector = self.get_elem(SELECTOR)
        self.__openai_src = self.get_elem(openai_src.name)

        sink_id = 0
        if self.use_filesrc:
            self.__filesrc = self.get_elem(FILESRC)
            self.__file_pad = get_pad(self.__selector, f"sink_{sink_id}")
            self.__filesrc.set_property("location", beep_wav)
            self.current_file = beep_wav
            sink_id += 1

        self.__openai_pad = get_pad(self.__selector, f"sink_{sink_id}")
        sink_id += 1
        self.__silence_pad = get_pad(self.__selector, f"sink_{sink_id}")

        self.switch_to_silence()

    def __flush(self):
        self._pipeline.send_event(Gst.Event.new_flush_start())
        self._pipeline.send_event(Gst.Event.new_flush_stop(False))

    def __restart_pipeline(self):
        self.logger.debug("Restarting pipeline")
        self._pipeline.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 0
        )

    def __warmup(self):
        silence = bytes(480 * 2)
        for i in range(2):
            buf = Gst.Buffer.new_allocate(None, len(silence), None)
            if not buf:
                self.logger.debug(f"Failed to allocated warmup buffer ({i}/2)")
                continue

            buf.fill(0, silence)
            # buf.duration = 20_000_000
            self.__openai_src.emit("push-buffer", buf)

    def push_from_openai(self, pcm: bytes):
        self.logger.debug(f"Pushing {len(pcm)} audio bytes")
        buffer = Gst.Buffer.new_allocate(None, len(pcm), None)

        if not buffer:
            self.logger.error("Failed to allocated Buffer.")
            return

        # chunk_size = len(pcm)
        # buffer.duration = (chunk_size * Gst.SECOND) // (self.src.rate * self.src.bytes_per_frame)

        # buffer.duration = 20_000_000
        buffer.fill(0, pcm)

        ret = self.__openai_src.emit("push-buffer", buffer)
        if ret != Gst.FlowReturn.OK:
            self.logger.warning(f"Failed to push buffer: {ret}")

    def switch_to_file(self) -> None:
        """Switch input selector to file source."""
        self.__selector.set_property("active-pad", self.__file_pad)
        self.logger.info("Switched to file source")

    def switch_to_openai(self) -> None:
        """Switch input selector to file source."""
        self.__selector.set_property("active-pad", self.__openai_pad)
        self.logger.info("Switched to openai source")

    def switch_to_silence(self) -> None:
        """Switch input selector to file source."""
        self.__selector.set_property("active-pad", self.__silence_pad)
        self.logger.info("Switched to silence source")

    def on_eos_reached(self, message: str) -> None:
        def eos():
            self.switch_to_silence()
            self.logger.info(message)
            self.on_eos = None

        self.on_eos = eos

    def push_eos(self, callback: Callable) -> None:
        self.__openai_src.emit("end-of-stream")

        prev_call = self.on_eos

        def _callback():
            callback()
            self.on_eos = prev_call

        self.on_eos = _callback()

    def play_silence(self) -> bool:
        try:
            self.switch_to_silence()
            self.__flush()
            self.logger.info("Playing silence")

        except Exception as e:
            self.logger.error(f"Failed to play silence: {e}")
            return False
        return True

    def play_beep(self, auto_switch_to_tone: bool = True) -> bool:
        """
        Play a WAV file. When complete, optionally switch to tone.

        Args:
            file_path: Path to WAV file to play
            auto_switch_to_tone: Whether to automatically switch to tone when file ends

        Returns:
            True if file playback started successfully
        """
        self.logger.info(f"Configuring pipeline for playing {self.current_file}")
        if not self.use_filesrc:
            self.logger.warning("Can not play 'beep' sound. Playing silence instead")
            self.switch_to_silence()
            return True

        if auto_switch_to_tone:
            self.on_eos_reached("beep sound ended.")

        try:
            self.__flush()

            self.__restart_pipeline()
            self.switch_to_file()
            self.logger.info("Playing beep")
        except Exception as e:
            self.logger.error(f"Failed to play beep sound: {e}")
            return False
        return True

    def play_openai(self) -> bool:
        """
        Play a sinusoidal tone.

        Args:
            frequency: Tone frequency in Hz

        Returns:
            True if tone playback started successfully
        """
        try:
            self.__flush()
            self.switch_to_openai()
            self.__warmup()

            self.logger.info("Started OpenAISession response")
        except Exception as e:
            self.logger.error(f"Failed to play beep sound: {e}")
            return False
        return True
