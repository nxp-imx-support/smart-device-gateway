# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import asyncio
import base64
import json
import logging
import os
import threading
from typing import Optional

import websockets

from .config import UserOpenAIConfig


class OpenAISession:
    def __init__(self, controller, config: UserOpenAIConfig) -> None:
        self.ctrl = controller
        self.model = config.model
        self.api_key = config.api_key
        self.config = config  # Store for reconnect
        self.ws: Optional[websockets.ClientConnection] = None

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

        self.logger = logging.getLogger("OpenAISession")
        self.logger.debug(f"Initializing with configuration: {config}")

        # Schedule async initialization
        asyncio.run_coroutine_threadsafe(self._initialize(config), self.loop)

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _initialize(self, config: UserOpenAIConfig):
        """Initialize connection and notify when ready"""
        try:
            await self._connect(config)
            await self._configure_session(config)
            
            # Connection successful - notify controller
            self.ctrl.on_openai_ready()
            
            # Start receiving messages
            asyncio.create_task(self.recv_loop())
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.on_fatal(f"Failed to initialize: {e}")

    async def _connect(self, config: UserOpenAIConfig):
        """Internal async connect method"""
        link = f"{'wss' if config.secure else 'ws'}://{config.domain}{f':{config.port}' if config.port else ''}/v1/realtime?model={self.model}"
        self.logger.info(f"Connecting to: {link}")
        
        self.ws = await asyncio.wait_for(
            websockets.connect(
                link,
                additional_headers={
                    "Authorization": f"Bearer {os.environ.get(self.api_key, self.api_key)}",
                    "OpenAI-Beta": "realtime=v1",
                },
                ping_interval=20,
                ping_timeout=10,
            ),
            timeout=8.0,
        )
        self.logger.info("Connection established")

    async def _configure_session(self, config: UserOpenAIConfig):
        """Internal async configure method"""
        await self.ws.send(
            json.dumps({
                "type": "session.update",
                "session": {
                    "model": config.model,
                    "modalities": ["audio", "text"],
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "turn_detection": None,
                },
            })
        )
        self.logger.info("Session configured")

    # ===== PUBLIC SYNC API (Controller uses these) =====

    def reconnect(self, on_success=None, on_failure=None):
        """
        Synchronously schedule a reconnection (async work happens in background)
        
        Args:
            on_success: Callback to call when reconnect succeeds
            on_failure: Callback to call when reconnect fails
        """
        self.logger.info("Reconnect requested")
        
        async def _reconnect():
            try:
                # Close existing connection
                if self.ws:
                    await self.ws.close()
                    self.ws = None
                
                # Reconnect
                await self._connect(self.config)
                await self._configure_session(self.config)
                
                # Restart recv loop
                asyncio.create_task(self.recv_loop())
                
                self.logger.info("Reconnect successful")
                
                # Notify success
                if on_success:
                    on_success()
                    
            except Exception as e:
                self.logger.error(f"Reconnect failed: {e}")
                
                # Notify failure
                if on_failure:
                    on_failure(e)
        
        # Schedule async work
        asyncio.run_coroutine_threadsafe(_reconnect(), self.loop)

    def start_listening(self):
        """Flush server audio buffer"""
        try:
            self.logger.info("Flushing OpenAI buffer for incoming query")
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({"type": "input_audio_buffer.clear"})),
                self.loop,
            )
        except Exception as e:
            self.on_fatal(f"Fail on start listening: {e}")

    def send_audio(self, pcm: bytes):
        try:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(
                    json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": base64.b64encode(pcm).decode("utf-8"),
                    })
                ),
                self.loop,
            )
        except Exception as e:
            self.on_fatal(f"Failed sending audio over OpenAISession {e}")

    def commit_audio(self):
        try:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({"type": "input_audio_buffer.commit"})),
                self.loop,
            )
            asyncio.run_coroutine_threadsafe(
                self.ws.send(json.dumps({"type": "response.create"})),
                self.loop,
            )
        except Exception as e:
            self.on_fatal(f"Failed to commit audio {e}")

    def close(self):
        if self.ws:
            asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)

    # ===== INTERNAL ASYNC METHODS =====

    async def recv_loop(self):
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                try:
                    if data["type"] == "response.audio.start":
                        self.ctrl.on_response_start()

                    elif data["type"] == "response.audio.delta":
                        pcm = base64.b64decode(data["delta"])
                        self.ctrl.on_response_delta(pcm)

                    elif data["type"] == "response.audio.done":
                        self.ctrl.on_response_end()

                    elif data["type"] == "error":
                        self.on_fatal(f"Server failed with: {data}")

                    else:
                        self.logger.debug(f"Received unhandled OpenAI.Event: {data['type']}")
                        
                except Exception as e:
                    self.on_fatal(f"Failed on {data['type']} message: {e}")
                    return
                    
        except websockets.exceptions.ConnectionClosedError as e:
            self.logger.error(f"Connection closed: {e}")
            # Notify controller of connection loss
            self.on_fatal(str(e))

    def on_fatal(self, reason: str):
        self.logger.error(f"Fatal error: {reason}")
        self.ctrl.on_fatal_error()
