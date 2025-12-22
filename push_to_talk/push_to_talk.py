# SPDX-License-Identifier: Apache-2.0
# Origin: https://github.com/openai/openai-python/blob/v1.102.0/examples/realtime/push_to_talk_app.py
#
# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

from __future__ import annotations

import base64
import asyncio
import argparse
from typing import Any, cast
from typing_extensions import override

from textual import events
from audio_util import CHANNELS, SAMPLE_RATE, AudioPlayerAsync
from textual.app import App, ComposeResult
from textual.widgets import Button, Static, RichLog
from textual.reactive import reactive
from textual.containers import Container

from openai import AsyncOpenAI
from openai.types.beta.realtime.session import Session
from openai.resources.beta.realtime.realtime import AsyncRealtimeConnection


class SessionDisplay(Static):
    """A widget that shows the current session ID."""

    session_id = reactive("")

    @override
    def render(self) -> str:
        return f"Session ID: {self.session_id}" if self.session_id else "Connecting..."


class AudioStatusIndicator(Static):
    """A widget that shows the current audio recording status."""

    is_recording = reactive(False)

    @override
    def render(self) -> str:
        status = (
            "🔴 Recording... (Press K to stop)" if self.is_recording else "⚪ Press K to start recording (Q to quit)"
        )
        return status


class RealtimeApp(App[None]):
    CSS = """
        Screen {
            background: #1a1b26;  /* Dark blue-grey background */
        }

        Container {
            border: double #69CA00;
        }

        Horizontal {
            width: 100%;
        }

        #input-container {
            height: 5;  /* Explicit height for input container */
            margin: 1 1;
            padding: 1 2;
        }

        Input {
            width: 80%;
            height: 3;  /* Explicit height for input */
        }

        Button {
            width: 20%;
            height: 3;  /* Explicit height for button */
        }

        #bottom-pane {
            width: 100%;
            height: 82%;  /* Reduced to make room for session display */
            border: round #0EAFE0;
            content-align: left top;
            padding: 1 2;
        }

        #status-indicator {
            height: 3;
            content-align: center middle;
            background: #2a2b36;
            border: solid #F9B500;
            margin: 1 1;
        }

        #session-display {
            height: 3;
            content-align: center middle;
            background: #2a2b36;
            border: solid #69CA00;
            margin: 1 1;
        }

        Static {
            color: white;
        }

        RichLog {
            color: white;
        }
    """

    client: AsyncOpenAI
    should_send_audio: asyncio.Event
    audio_player: AudioPlayerAsync
    last_audio_item_id: str | None
    connection: AsyncRealtimeConnection | None
    session: Session | None
    connected: asyncio.Event
    current_text: str
    current_transcription: str
    device: str | None

    def __init__(self, server_ip: str, port: int, device: str | None = None) -> None:
        super().__init__()
        self.connection = None
        self.session = None
        self.client = AsyncOpenAI(websocket_base_url=f"ws://{server_ip}:{port}/v1", api_key="adsa")
        self.audio_player = AudioPlayerAsync()
        self.last_audio_item_id = None
        self.should_send_audio = asyncio.Event()
        self.connected = asyncio.Event()
        self.current_text = ""
        self.current_transcription = ""
        self.device = device

    @override
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Container():
            yield SessionDisplay(id="session-display")
            yield AudioStatusIndicator(id="status-indicator")
            yield RichLog(id="bottom-pane", wrap=True, highlight=True, markup=True)

    async def on_mount(self) -> None:
        self.run_worker(self.handle_realtime_connection())
        self.run_worker(self.send_mic_audio())

    async def handle_realtime_connection(self) -> None:
        async with self.client.beta.realtime.connect(model=None) as conn: # Model name no required by the Smart Device Gateway
            self.connection = conn
            self.connected.set()
            await conn.session.update(session={"turn_detection": {"type": "server_vad"}, "device": self.device})

            async for event in conn:
                if event.type == "session.created":
                    self.session = event.session
                    session_display = self.query_one(SessionDisplay)
                    assert event.session.id is not None
                    session_display.session_id = event.session.id
                    continue

                if event.type == "session.updated":
                    self.session = event.session
                    continue

                if event.type == "transcription.delta":
                    # Stream transcription chunks as they arrive
                    self.current_transcription += event.delta

                    bottom_pane = self.query_one("#bottom-pane", RichLog)
                    bottom_pane.clear()
                    bottom_pane.write(f"[bold green]User:[/bold green] [white]{self.current_transcription}[/white]")
                    continue

                if event.type == "transcription.done":
                    # Finalize user's transcribed text
                    bottom_pane = self.query_one("#bottom-pane", RichLog)
                    bottom_pane.clear()
                    bottom_pane.write(f"[bold green]User:[/bold green] [white]{self.current_transcription}[/white]")
                    bottom_pane.write("")  # Add blank line for separation
                    continue

                if event.type == "response.audio.delta":
                    if event.item_id != self.last_audio_item_id:
                        self.audio_player.reset_frame_count()
                        self.last_audio_item_id = event.item_id

                    bytes_data = base64.b64decode(event.delta)
                    self.audio_player.add_data(bytes_data)
                    continue

                if event.type == "response.text.delta":
                    # Stream individual tokens
                    self.current_text += event.delta

                    bottom_pane = self.query_one("#bottom-pane", RichLog)
                    bottom_pane.clear()
                    bottom_pane.write(f"[bold green]User:[/bold green] [white]{self.current_transcription}[/white]")
                    bottom_pane.write("")  # Add blank line for separation
                    bottom_pane.write(f"[bold green]AI:[/bold green] [white]{self.current_text}[/white]")
                    continue

                if event.type == "response.text.done":
                    # Finalize the text display
                    bottom_pane = self.query_one("#bottom-pane", RichLog)
                    bottom_pane.clear()
                    bottom_pane.write(f"[bold green]User:[/bold green] [white]{self.current_transcription}[/white]")
                    bottom_pane.write("")  # Add blank line for separation
                    bottom_pane.write(f"[bold green]AI:[/bold green] [white]{self.current_text}[/white]")
                    bottom_pane.write("")  # Add blank line for separation
                    continue

                if event.type == "response.audio.done":
                    # Response complete
                    continue

    async def _get_connection(self) -> AsyncRealtimeConnection:
        await self.connected.wait()
        assert self.connection is not None
        return self.connection

    async def send_mic_audio(self) -> None:
        import sounddevice as sd  # type: ignore

        sent_audio = False

        device_info = sd.query_devices()
        print(device_info)

        read_size = int(SAMPLE_RATE * 0.02)

        stream = sd.InputStream(
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            dtype="int16",
        )
        stream.start()

        status_indicator = self.query_one(AudioStatusIndicator)

        try:
            while True:
                if stream.read_available < read_size:
                    await asyncio.sleep(0)
                    continue

                await self.should_send_audio.wait()
                status_indicator.is_recording = True

                data, _ = stream.read(read_size)

                connection = await self._get_connection()
                if not sent_audio:
                    asyncio.create_task(connection.send({"type": "response.cancel"}))
                    sent_audio = True

                await connection.input_audio_buffer.append(audio=base64.b64encode(cast(Any, data)).decode("utf-8"))

                await asyncio.sleep(0)
        except KeyboardInterrupt:
            pass
        finally:
            stream.stop()
            stream.close()

    async def on_key(self, event: events.Key) -> None:
        """Handle key press events."""
        if event.key == "enter":
            self.query_one(Button).press()
            return

        if event.key == "q":
            self.exit()
            return

        if event.key == "k":
            status_indicator = self.query_one(AudioStatusIndicator)
            if status_indicator.is_recording:
                # Stop recording
                self.should_send_audio.clear()
                status_indicator.is_recording = False

                if self.session and self.session.turn_detection is None:
                    # The default in the API is that the model will automatically detect when the user has
                    # stopped talking and then start responding itself.
                    #
                    # However if we're in manual `turn_detection` mode then we need to
                    # manually tell the model to commit the audio buffer and start responding.
                    conn = await self._get_connection()
                    await conn.input_audio_buffer.commit()
                    await conn.response.create()
            else:
                # Start new recording - reset transcription and text
                bottom_pane = self.query_one("#bottom-pane", RichLog)
                bottom_pane.clear()
                self.current_text = ""
                self.current_transcription = ""
                self.should_send_audio.set()
                status_indicator.is_recording = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Push-to-Talk Realtime AI Client")
    parser.add_argument(
        "--server_ip",
        type=str,
        required=True,
        help="IP address of the server"
    )
    parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Port number of the server"
    )
    parser.add_argument(
        "--device",
        type=str,
        required=False,
        default=None,
        help="device rag (optional)"
    )

    args = parser.parse_args()
    app = RealtimeApp(server_ip=args.server_ip, port=args.port, device=args.device)
    app.run()