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

from home_ai_hub.client.config import GstElemConfig, UserVitConfig, VadConfig


class PipeBuilder:
    pass


class PlaybackBuilder(PipeBuilder):
    def __init__(
        self, selector_name: str, filesrc_name: str, silence_name: str
    ) -> None:
        self.selector_name = selector_name
        self.filesrc_name = filesrc_name
        self.silence_name = silence_name

    def build(
        self, card_config: GstElemConfig, openai_src: GstElemConfig, use_filesrc: bool
    ) -> str:
        sink_id = 0
        pipeline = ""
        if use_filesrc:
            pipeline = f"filesrc name={self.filesrc_name} ! wavparse ! {self.selector_name}.sink_{sink_id}"
            sink_id += 1

        openai_caps = (
            f" caps={openai_src.get_caps().replace(' ', '')},layout=interleaved"
        )
        # pipeline += f" appsrc {openai_src} {openai_caps} ! tee name=t t. ! queue ! filesink location=/root/example.raw t. ! queue ! {self.selector_name}.sink_{sink_id}"
        pipeline += f" appsrc {openai_src} {openai_caps} ! queue2 use-buffering=true max-size-time=2000000000 low-watermark=0.1 high-watermark=0.99 ! {self.selector_name}.sink_{sink_id}"

        sink_id += 1
        pipeline += f" audiotestsrc name={self.silence_name} wave=silence is-live=true ! queue ! {self.selector_name}.sink_{sink_id} "

        pipeline += f" input-selector name={self.selector_name} ! audioconvert ! audioresample ! {card_config.get_caps()} ! alsasink {card_config}"
        # pipeline += f" input-selector name={self.selector_name} ! audioconvert ! audioresample ! {card_config.get_caps()} ! filesink location=/root/example2.raw"

        return pipeline


class CaptureBuilder(PipeBuilder):
    def __init__(self, valve_name: str, ww_rec: str) -> None:
        self.valve_name = valve_name
        self.ww_rec = ww_rec

    def build(
        self,
        card_config: GstElemConfig,
        openai_sink: GstElemConfig,
        vit_config: Optional[UserVitConfig] = None,
        vad_config: Optional[VadConfig] = None,
        debug_mic: bool = False,
        debug_ww: bool = False,
    ) -> str:
        tee_name = "t"
        pipeline_str = f"alsasrc {card_config} ! audioconvert ! audioresample ! {card_config.get_caps()}"
        pipeline_str += f" ! tee name={tee_name}"

        # Wake-Up Branch with imxvit
        if vit_config:
            pipeline_str += f" {tee_name}. ! queue ! audioconvert ! audioresample ! imxvit {vit_config}"

        # Main Branch, which send audio to OpenAI
        pipeline_str += f" {tee_name}. ! queue"
        if vad_config:
            pipeline_str += (
                f" ! audioconvert ! audioresample ! imx_ai_nr {vad_config[0]}"
            )

        pipeline_str += f" ! valve name={self.valve_name}"
        if openai_sink:
            pipeline_str += (
                f" ! audioconvert ! audioresample ! {openai_sink.get_caps()}"
            )
        pipeline_str += f" ! appsink {openai_sink}"

        if debug_mic:
            pipeline_str += (
                f" {tee_name}. ! queue ! wavenc ! filesink location=mic_debug.wav"
            )

        if debug_ww:
            pipeline_str += (
                f" {tee_name}. ! queue ! appsink name={self.ww_rec} emit-signals=true"
            )

        return pipeline_str
