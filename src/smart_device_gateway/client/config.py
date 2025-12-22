# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

from typing import Any, Dict, Literal, Optional, TypeAlias, get_args, Tuple

from . import init_voice

init_voice()

from gi.repository import GstAudio
from pydantic import BaseModel, Field, field_validator

Log_T: TypeAlias = Literal["info", "debug", "warning", "error", "critical"]

LOG_VALUES = get_args(Log_T)


def gst_str(d: Dict[str, Any]) -> str:
    return " ".join(f"{k.replace('_', '-')}={v}" for k, v in d.items())


class GstElemConfig(BaseModel):
    name: str = ""
    channels: int = 1
    audio_format: str = "S16LE"
    rate: int = 24000
    model_config = {"extra": "allow"}

    @field_validator("audio_format")
    @classmethod
    def valdiate_format(cls, v: str) -> str:
        audio_format = GstAudio.AudioFormat.from_string(v.upper())

        if audio_format == GstAudio.AudioFormat.UNKNOWN:
            raise ValueError(f"Invalid audio format {v}")
        return v

    def get_caps(self) -> str:
        return f"audio/x-raw,channels={self.channels},format={self.audio_format},rate={self.rate}"

    @property
    def bytes_per_sample(self) -> int:
        audio_format = GstAudio.AudioFormat.from_string(self.audio_format.upper())
        if audio_format == GstAudio.AudioFormat.UNKNOWN:
            raise ValueError(f"Invalid audio format {self.audio_format}")
        format_info = GstAudio.AudioFormat.get_info(audio_format)

        return format_info.width // 8

    @property
    def bytes_per_frame(self) -> int:
        """The bytes_per_frame property."""
        return self.channels * self.bytes_per_sample

    def __str__(self) -> str:
        d = self.model_dump(
            exclude_defaults=True, exclude={"channels", "rate", "audio_format"}
        )
        return gst_str(d)


class UserAppConfig(BaseModel):
    trigger: Optional[Literal["wake-word", "button", "all"]]
    stop_on: Optional[Literal["voice-activity", "timeout", "button-release"]]
    model_config = {"extra": "forbid"}


class UserOnAction(BaseModel):
    led: bool = False
    sound: str = ""
    notification: bool = True
    model_config = {"extra": "forbid"}


class UserOnEventsConfig(BaseModel):
    listen: UserOnAction = Field(default_factory=UserOnAction)


class UserOnEventConfig(BaseModel):
    listen: bool = False
    events: UserOnEventsConfig = Field(default_factory=UserOnEventsConfig)
    model_config = {"extra": "forbid"}


class UserOpenAIConfig(BaseModel):
    domain: str = "localhost"
    port: Optional[int] = None
    model: str = "gpt-4o-realtime-preview"
    api_key: str = "YOUR_API_KEY"
    secure: bool = True
    sink: GstElemConfig = Field(default_factory=GstElemConfig)
    src: GstElemConfig = Field(default_factory=GstElemConfig)
    model_config = {"extra": "forbid"}


class UserVitConfig(BaseModel):
    name: str = "imxvit0"
    model_path: str = ""
    silent: bool = False
    voice_commands: bool = True
    model_config = {"extra": "forbid"}

    def __str__(self) -> str:
        d = self.model_dump(exclude_defaults=True)
        return gst_str(d)


class UserVadConfig(BaseModel):
    name: str = "imx_ai_nr0"
    bypass: bool = False
    model: str = "large"
    vad_thr: float = Field(default=0.015625, ge=0, le=1)
    model_config = {"extra": "forbid"}

    def __str__(self) -> str:
        d = self.model_dump(exclude_defaults=True)
        return gst_str(d)


class UserMonitorVadConfig(BaseModel):
    silence_time_sec: float = 0.8
    monitor_time_sec: float = 0.5
    print_progress: bool = True
    model_config = {"extra": "forbid"}


VadConfig: TypeAlias = Tuple[UserVadConfig, UserMonitorVadConfig]


class UserMonitorsConfig(BaseModel):
    vad: UserMonitorVadConfig = Field(default_factory=UserMonitorVadConfig)


class UserActionConfig(BaseModel):
    enabled: Optional[bool] = False
    retry_count: Optional[int] = 3
    retry_delay: Optional[float] = 1.0
    priority: Optional[int] = 5
    model_config = {"extra": "forbid"}


class UserActionLedConfig(UserActionConfig):
    path: str = "/sys/class/leds/"
    leds: list[str] = []
    min: int = 0
    max: int = 255


class UserActionNotificationConfig(UserActionConfig):
    log_level: Optional[Log_T] = "debug"
    custom_format: Optional[str] = ""
    console_output: Optional[bool] = True
    include_metadata: Optional[bool] = True


class UserActionsConfig(BaseModel):
    max_workers: int = 2
    led: UserActionLedConfig = Field(default_factory=UserActionLedConfig)
    notification: UserActionNotificationConfig = Field(
        default_factory=UserActionNotificationConfig
    )
    model_config = {"extra": "forbid"}


class UserPipelineConfig(BaseModel):
    name: str
    debug: bool = True
    model_config = {"extra": "forbid"}


class UserPipelinesConfig(BaseModel):
    capture: UserPipelineConfig = UserPipelineConfig(
        name="EdgeVoice-Capture", debug=False
    )
    playback: UserPipelineConfig = UserPipelineConfig(
        name="EdgeVoice-Playback", debug=False
    )
    model_config = {"extra": "forbid"}


class UserLoggingConfig(BaseModel):
    log_level: Log_T = "warning"
    model_config = {"extra": "forbid"}


class UserDebugConfig(BaseModel):
    pipeline_dots: bool = False
    verbose_bus_messages: bool = False
    mic: bool = False
    ww: bool = False
    model_config = {"extra": "forbid"}


class UserConfig(BaseModel):
    app: UserAppConfig
    on: UserOnEventConfig = Field(default_factory=UserOnEventConfig)
    openai: UserOpenAIConfig = Field(default_factory=UserOpenAIConfig)
    mic: GstElemConfig
    spkr: GstElemConfig
    vit: UserVitConfig = Field(default_factory=UserVitConfig)
    vad: UserVadConfig = Field(default_factory=UserVadConfig)
    monitors: UserMonitorsConfig = Field(default_factory=UserMonitorsConfig)
    actions: UserActionsConfig = Field(default_factory=UserActionsConfig)
    pipeline: UserPipelinesConfig = Field(default_factory=UserPipelinesConfig)
    logging: UserLoggingConfig = Field(default_factory=UserLoggingConfig)
    debug: UserDebugConfig = Field(default_factory=UserDebugConfig)
    model_config = {"extra": "forbid"}
