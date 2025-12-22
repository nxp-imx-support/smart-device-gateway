# Push to Talk
![Language badge](https://img.shields.io/badge/Language-Python-yellow)
[![Category badge](https://img.shields.io/badge/Category-GenAI-green)](https://www.nxp.com/applications/technologies/ai-and-machine-learning:MACHINE-LEARNING)
![License badge](https://img.shields.io/badge/License-Proprietary-red)

A Terminal User Interface (TUI) client for the Smart Device Gateway.

## Introduction

This client application provides a terminal-based interface for connecting to the Smart Device Gateway. It captures audio from your microphone, sends it to the server, and plays back AI-generated responses in real-time.

## Features

- ✨ **Terminal User Interface** - Clean, colorful TUI built with [Textual](https://textual.textualize.io/).
- 🎙️ **Push-to-Talk** - Press 'K' to record, press it again to send.
- 🔴 **Visual Feedback** - Live recording status indicator.
- 📝 **Real-time Transcription** - See AI responses as text in the terminal.
- 🔊 **Audio Playback** - Automatic playback of AI voice responses.
- ⚡ **Low Latency** - WebSocket-based streaming for minimal delay.

## Requirements

- Python >= 3.13.9
- Audio input device (microphone)
- Audio output device (speakers/headphones)

## Installation

```bash
uv sync
```

>**NOTE:** On Mac, you'll also need `brew install portaudio ffmpeg`, On Linux, you'll also need `sudo apt-get install portaudio19-dev ffmpeg`

## Usage

Start the client application:

```bash
python -m uv run push_to_talk.py --server_ip $YOUR_BOARD_IP --port $PORT --device [oven / barista]
```

The client will:
1. Connect to the configured WebSocket endpoint
2. Display the session ID once connected
3. Wait for your input

### Basic Workflow

1. **Press 'K'** to start recording your voice
2. **Speak** your question or command
3. **Press 'K'** to stop recording and send audio
4. **Listen** to the AI's voice response
5. **Read** the transcription in the terminal

## Controls

| Key | Action |
|-----|--------|
| `K` | Press to record audio / send audio |
| `Q` | Quit the application |

## Architecture

The client follows this architecture:

```
┌─────────────────────────────────────────────────────────┐
│                  Client Application                     │
│                                                         │
│  ┌──────────────┐         ┌─────────────────┐           │
│  │   Textual    │         │   Audio Player  │           │
│  │     TUI      │         │   (sounddevice) │           │
│  └──────┬───────┘         └────────▲────────┘           │
│         │                          │                    │
│         │                          │ Audio Response     │
│         │ User Input               │                    │
│         │                          │                    │
│  ┌──────▼──────────────────────────┴────────┐           │
│  │        OpenAI AsyncClient                │           │
│  │     (Realtime WebSocket)                 │           │
│  └──────────────┬───────────────────────────┘           │
│                 │                                       │
└─────────────────┼───────────────────────────────────────┘
                  │
                  │ WebSocket (ws://)
                  │
         ┌────────▼────────────────┐
         │  Smart Device Gateway   │
         │  (OpenAI Compatible)    │
         └─────────────────────────┘
```

## Audio Specifications

### Input Audio

| Parameter | Value |
|-----------|-------|
| Sample Rate | 24,000 Hz |
| Channels | 1 (Mono) |
| Format | 16-bit PCM (int16) |
| Encoding | Base64 |

### Output Audio

| Parameter | Value |
|-----------|-------|
| Sample Rate | 24,000 Hz |
| Channels | 1 (Mono) |
| Format | 16-bit PCM (int16) |


## License
This application is licensed under the [LA_OPT_Online Code Hosting NXP_Software_License](./../LICENSE) license.
