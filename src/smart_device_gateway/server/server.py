# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
import os
import json
import yaml
import base64
import asyncio
import logging
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .pipeline import SmartDeviceGatewayPipeline
from .llm import OpenAIClient
from .utils import resample_audio

class Session:
    """Manages a WebSocket session for real-time audio communication.

    This class handles bidirectional audio streaming between client and server.

    Attributes:
        websocket (WebSocket): WebSocket connection to the client.
        input_audio_buffer_commit (asyncio.Event): Event signal indicating when the
            input audio buffer has been committed and is ready for processing.
        current_item_id (str): Unique identifier for the current conversation item,
            generated using random hex values.
        transcribing (bool): Flag indicating whether transcription is currently
            in progress.
        streaming_audio (bool): Flag indicating whether the server is currently
            streaming audio chunks.
        query (str): Accumulated transcription text from the current audio input.

    Example:
        >>> session = Session(websocket)
        >>> await session.send_event({"type": "session.created"})
        >>> session.input_audio_buffer_commit.set()
    """

    def __init__(self, websocket: WebSocket):
        """Initializes a new Session instance.

        Args:
            websocket (WebSocket): The WebSocket connection instance for
                communication with the client.
        """
        self.current_item_id = "item_" + os.urandom(8).hex()
        self.websocket = websocket

        try:
            with open("/usr/share/smart-device-gateway/config.yaml", 'r') as f:
                self.cfg = yaml.safe_load(f)
        except FileNotFoundError:
            logger.error("Config file not found at /usr/share/smart-device-gateway/config.yaml")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            raise

        self.query = ""
        self.device = None # Each device needs a device tag for context retrieval
        self.client = None  # Will be initialized when device is set

        # Flags for tracking session state
        self.transcribing = False
        self.query_ready = False
        self.streaming_audio = False

    def create_client_for_device(self):
        """Update the OpenAI client with the appropriate system prompt for the device."""
        system_prompts = self.cfg['eiq_aaf_connector']['system_prompt']

        # Get device-specific prompt or fall back to default
        if self.device is None:
            system_prompt = system_prompts.get('oven')
        else:
            system_prompt = system_prompts.get(self.device, system_prompts.get('oven'))

        self.client = OpenAIClient(
            base_url=self.cfg['eiq_aaf_connector']['base_url'],
            api_key=self.cfg['eiq_aaf_connector']['api_key'],
            model=self.cfg['eiq_aaf_connector']['model'],
            system_prompt=system_prompt,
        )

    async def send_event(self, message_data: dict):
        """Safely sends an event message to the client via WebSocket.

        Converts the message data to JSON format and sends it to the client.
        Handles connection errors gracefully by logging and returning False.

        Args:
            message_data (dict | str): The message data to send. If a dictionary,
                it will be serialized to JSON. If a string, it will be sent as-is.

        Returns:
            bool: True if the message was sent successfully, False if an error
                occurred during sending.

        Raises:
            None: All exceptions are caught and logged internally.
        """
        try:
            json_data = json.dumps(message_data)
            await self.websocket.send_text(json_data)
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

async def main_coroutine(session: Session):
    """Handles the complete ASR+RAG+LLM+TTS pipeline.

    This coroutine orchestrates the entire audio processing workflow from speech
    recognition to text-to-speech synthesis.
    It runs in an infinite loop, processing each user query through the following
    stages:

    1. Speech-to-Text (STT): Transcribes incoming audio to text
    2. Retrieval-Augmented Generation (RAG): Retrieves relevant context chunks
    3. Language Model (LLM): Generates response using RAG context
    4. Text-to-Speech (TTS): Synthesizes audio from generated text

    Args:
        session (Session): The WebSocket session instance containing the connection,
            state flags (transcribing, input_audio_buffer_commit), query accumulator,
            and current_item_id for tracking conversation items.

    Raises:
        asyncio.CancelledError: When the coroutine is cancelled during WebSocket
            disconnection or task cleanup.
    """
    while True:
        if not session.query_ready:
            await asyncio.sleep(0.01)
            continue

        try:
            query = await asyncio.wait_for(pipeline.query_q.get(), timeout=0.01)

            rag_query = ""
            # if session.device:
            logger.info(f"Retrieving RAG context for device: {session.device}")
            chunk_list, _, _ = pipeline.rag_database_selector(device=session.device, query=query)
            context = "".join([f"\n\t  Context {i}: {chunk}" for i, chunk in enumerate(chunk_list)]) if chunk_list else ""

            # Create augmented query with RAG context
            rag_query = "\n\t  Use this context to answer the user's question:"
            rag_query += context

            rag_query += f"\n\t  User Question: {query}"
            logger.info("LLM Prompt:" + rag_query)

            session.streaming_audio = True
            async for token in session.client.stream(query=rag_query):
                await pipeline.tokens_q.put(token)
                # Send token to client for display
                await session.send_event({
                    "type": "response.text.delta",
                    "item_id": session.current_item_id,
                    "delta": token,
                })

            # Signal end of token streaming
            await pipeline.tokens_q.put(None)
            await session.send_event({
                "type": "response.text.done",
                "item_id": session.current_item_id,
            })

            session.query_ready = False

        except asyncio.TimeoutError:
            continue

        except asyncio.CancelledError:
            # Coroutine was cancelled, propagate the cancellation
            raise

        except Exception as e:
            logger.error(f"Error in transcription streaming: {e}")
            continue

async def receive_event_coroutine(session: Session):
    """Receives and processes events from the WebSocket client.

    This coroutine continuously listens for incoming messages from the client
    via WebSocket and processes different event types including session updates,
    audio buffer operations, and response creation requests. It handles the complete
    lifecycle of audio input processing from receiving audio chunks to committing
    them for transcription.

    The function processes the following event types:
        - session.update: Updates session configuration and sends confirmation
        - input_audio_buffer.append: Receives audio chunks, resamples them from
          24kHz to 16kHz, and pushes to STT buffer
        - input_audio_buffer.commit: Signals end of audio input and triggers
          transcription processing
        - response.create: Acknowledges response creation request from client

    When the WebSocket connection closes, the function ensures proper cleanup

    Args:
        session (Session): The WebSocket session instance containing the connection,
            audio buffer state, and communication queues for handling user audio
            input and events.

    Raises:
        asyncio.CancelledError: When the coroutine is cancelled during WebSocket
            disconnection or task cleanup.
        json.JSONDecodeError: When received message cannot be parsed as valid JSON.
    """
    async for i in session.websocket.iter_text():
        event = json.loads(i)
        event_type = event.get("type", None)

        if event_type == "session.update":
            session_params = event.get("session", {}) # TODO: Use the rest of the configuration params
            session.device = session_params.get("device", None)
            session.create_client_for_device()

            await session.send_event(
                {
                    "type": "session.updated",
                    "session": {
                        "turn_detection": None,
                    },
                }
            )

        elif event_type == "input_audio_buffer.append":
            if not session.transcribing:
                session.transcribing = True
                # Speech to text module starts consuming the audio chunks that this
                # coroutine is putting into the buffer
                pipeline.stt.start()

            chunk = base64.b64decode(event["audio"])
            if chunk:
                audio_int16 = np.frombuffer(chunk, dtype=np.int16)
                resampled_audio = resample_audio(audio_int16, 24000, 16000)
                pipeline.stt.push_data_to_buffer(resampled_audio) # Fill the Speech to Text buffer

        elif event_type == "input_audio_buffer.commit":
            pipeline.stt.stop()

            await session.send_event(
                {
                    "type": "input_audio_buffer.committed",
                    "total_bytes": 0,
                }
            )

        elif event_type == "response.create":
            await session.send_event(
                {
                    "type": "response.created",
                    "response": {
                        "id": "resp_" + os.urandom(8).hex(),
                    }
                }
            )

async def audio_streaming_coroutine(session: Session):
    """Streams synthesized audio chunks from TTS to the client via WebSocket.

    This coroutine continuously monitors the audio queue for synthesized audio
    chunks from the TTS (Text-to-Speech) process and streams them to the client
    in real-time. It handles audio resampling, format conversion, and chunking
    for efficient transmission over WebSocket.

    The function runs in an infinite loop, retrieving audio chunks from the
    global audio_q queue, resampling from 22050 Hz to 24000 Hz, converting
    from float32 to int16 PCM format, and sending them as base64-encoded
    "response.audio.delta" events. When a None sentinel value is received,
    it signals the end of audio streaming.

    Args:
        session (Session): The WebSocket session instance containing the
            connection and state information for the current client.

    Raises:
        asyncio.CancelledError: When the coroutine is cancelled during
            WebSocket disconnection or task cleanup.
    """
    chunk_size = 1024  # Small chunk size for streaming

    while True:
        if not session.streaming_audio:
            await asyncio.sleep(0.01)
            continue

        try:
            audio_chunk = await asyncio.wait_for(pipeline.audio_q.get(), timeout=0.01)

            if not audio_chunk is None:
                audio_resampled = resample_audio(audio_chunk, 22050, 24000)

                # Convert float32 to int16 PCM
                audio_resampled = np.clip(audio_resampled, -1.0, 1.0)
                audio_int16 = (audio_resampled * 32767).astype(np.int16)

                # Send in chunks
                for i in range(0, len(audio_int16), chunk_size):
                    chunk_data = audio_int16[i:i + chunk_size]
                    encoded_audio = base64.b64encode(chunk_data.tobytes()).decode('utf-8')

                    await session.send_event({
                        "type": "response.audio.delta",
                        "item_id": session.current_item_id,
                        "delta": encoded_audio
                    })

            else:  # End of transcription (None sentinel)
                await session.send_event(
                    {
                        "type": "response.audio.done",
                        "item_id": session.current_item_id,
                    }
                )

                session.streaming_audio = False
                logger.info("Server finished sending all audio chunks")

        except asyncio.TimeoutError:
            continue

        except asyncio.CancelledError:
            # Coroutine was cancelled, propagate the cancellation
            raise

        except Exception as e:
            logger.error(f"Error in audio streaming: {e}")
            continue

async def transcription_streaming_coroutine(session: Session):
    """Sends transcription deltas to the client as they become available.

    This coroutine continuously monitors the transcriptions queue and sends
    transcription chunks to the client in real-time. It accumulates the
    transcription text in the session's query attribute and signals when
    transcription is complete.

    The function runs in an infinite loop, retrieving text chunks from the
    global transcriptions_q queue and sending them to the client as
    "transcription.delta" events. When a None sentinel value is received,
    it signals the end of transcription by setting session.transcribing to False.

    Args:
        session (Session): The WebSocket session instance containing the
            connection and state information for the current client.

    Raises:
        asyncio.CancelledError: When the coroutine is cancelled during
            WebSocket disconnection or task cleanup.
    """
    while True:
        if not session.transcribing:
            await asyncio.sleep(0.01)
            continue

        try:
            text_chunk = await asyncio.wait_for(pipeline.transcriptions_q.get(), timeout=0.01)

            if not text_chunk is None:
                logger.info(f"TTS transcription: {text_chunk}")
                session.query = session.query + text_chunk + " "

                await session.send_event({
                    "type": "transcription.delta",
                    "item_id": session.current_item_id,
                    "delta": text_chunk + " ",
                })

            else:  # End of transcription (None sentinel)
                session.transcribing = False

                # Signal end of transcription stream
                await session.send_event({
                    "type": "transcription.done",
                    "item_id": session.current_item_id,
                    "text": session.query,
                })

                session.query_ready = True
                await pipeline.query_q.put(session.query)
                session.query = ""

        except asyncio.TimeoutError:
            continue

        except asyncio.CancelledError:
            # Coroutine was cancelled, propagate the cancellation
            raise

        except Exception as e:
            logger.error(f"Error in transcription streaming: {e}")
            continue

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes and loads all required models and components on server startup.

    This function is executed once when the FastAPI server starts. It initializes
    the global application state including multiprocessing queues, AI models, and
    the RAG (Retrieval-Augmented Generation) system. The initialization follows
    a specific order to ensure dependencies are properly loaded.

    The function performs the following initialization steps:
        1. Creates multiprocessing queues for inter-process communication
        2. Loads Hydra configuration from the config file
        3. Initializes Speech-to-Text (STT) model using Moonshine
        4. Configures OpenAI client for LLM interactions
        5. Sets up RAG retrieval system with embeddings and database
        6. Spawns TTS worker process and waits for readiness confirmation
    """
    logger.info("Starting up the Smart Device Gateway server...")
    await pipeline.start_async_loops()
    yield

    logger.info("Stoping the Smart Device Gateway server...")

pipeline = SmartDeviceGatewayPipeline()

logger = logging.getLogger("uvicorn.error")
app = FastAPI(title="Smart Device Gateway", lifespan=lifespan)

@app.websocket("/v1/realtime")
async def realtime_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming with Smart Device Gateway.

    Establishes a bidirectional WebSocket connection that handles real-time audio
    communication between client and server. The endpoint manages the complete
    audio processing pipeline including speech recognition, language model processing,
    and text-to-speech synthesis.

    The function orchestrates four concurrent coroutines:
        1. receive_event_coroutine: Receives and processes client events
        2. main_coroutine: Handles ASR, LLM, and TTS pipeline
        3. audio_streaming_coroutine: Streams synthesized audio back to client
        4. transcription_streaming_coroutine: Sends transcription deltas to client

    Args:
        websocket (WebSocket): The WebSocket connection instance for bidirectional
            communication with the client.

    Raises:
        WebSocketDisconnect: When the client disconnects from the WebSocket.
    """
    await websocket.accept()
    session = Session(websocket)

    await session.send_event(
        {
            "type": "session.created",
            "session": {
                "id": "sess_smart_device_gateway", # Special id to recognize when you connect to the server
            }
        }
    )

    try:
        tasks = [
            asyncio.create_task(receive_event_coroutine(session)),
            asyncio.create_task(main_coroutine(session)),
            asyncio.create_task(audio_streaming_coroutine(session)),
            asyncio.create_task(transcription_streaming_coroutine(session)),
        ]

        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Cancel pending tasks gracefully
        for task in pending:
            task.cancel()

        # Wait for cancellation to complete
        await asyncio.gather(*pending, return_exceptions=True)

    except WebSocketDisconnect:
        logger.warning("WebSocket connection disconnected")
