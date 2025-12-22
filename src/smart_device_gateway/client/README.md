# Edge Voice - OpenAI Realtime Voice Assistant

[![License](https://img.shields.io/badge/license-LA_OPT-red.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![GStreamer](https://img.shields.io/badge/GStreamer-1.0-green.svg)](https://gstreamer.freedesktop.org/)
[![Board badge](https://img.shields.io/badge/Board-i.MX_9-blue)](https://www.nxp.com/products/processors-and-microcontrollers/arm-processors/i-mx-applications-processors/i-mx-9-processors:IMX9-PROCESSORS)
[![Board badge](https://img.shields.io/badge/Board-i.MX_8M-blue)](https://www.nxp.com/products/i.MX8M)
![Category badge](https://img.shields.io/badge/Category-ML/AI-green)

A high-performance, edge-optimized voice assistant client for OpenAI's Realtime API with wake-word detection, Voice Activity Detection (VAD), and custom GStreamer pipeline support.

> **Tested on**: NXP i.MX93 FRDM with Linux BSP **6.12.34-2.1.0** (2025-Q3 Release)
> But it can run in any NXP Platform with support for the i.MX GST plugins in 2025-Q3 Release!

## 🌟 Key Features

### Core Capabilities
- **🎤 Wake-Word Detection**: Trigger conversations using custom wake words via GStreamer VIT (Voice Interaction Technology) plugin
- **🔊 Voice Activity Detection (VAD)**: Intelligent silence detection to automatically end user input
- **🤖 OpenAI Realtime API Integration**: Low-latency streaming audio communication with GPT-4o Realtime
- **🎵 Custom GStreamer Pipelines**: Flexible audio processing with support for custom plugins (ASR, noise reduction, AEC)
- **⚡ Edge-Optimized**: Designed for embedded systems (tested on NXP i.MX93 EVK)
- **🔌 Plugin System**: Extensible action system for LEDs, notifications, and custom integrations
- **📊 Real-time Monitoring**: VAD metrics, audio levels, and pipeline state monitoring

### Audio Processing
- **Custom GStreamer Plugins Support**:
  - `libgstimx_ai_nr.so` - AI-powered Noise Reduction
  - `libgstimxvit.so` - Voice Interaction Technology (wake-word)
  - `libgstimx_ai_aecnr.so` - Acoustic Echo Cancellation + Noise Reduction

- **Flexible Audio Configuration**:
  - ALSA device selection
  - Configurable sample rates, channels, and formats
  - Support for various audio hardware

### Action System
- **LED Control**: Visual feedback during different states
- **Notifications**: Console and system notifications with metadata
- **Extensible**: Easy to add custom actions via plugin interface
- **Async Execution**: Non-blocking action execution with thread pool

## 📋 Table of Contents

- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [State Machine](#-state-machine)
- [Events & Transitions](#-events--transitions)
- [Action System](#-action-system)
- [GStreamer Plugins](#-gstreamer-plugins)
- [Usage Examples](#-usage-examples)
- [Troubleshooting](#-troubleshooting)

## 🚀 Installation

### Prerequisites

```bash
# System dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y \
    python3 python3-pip python3-venv
```

### Install Edge Voice



#### Option 1: From Source
```bash
# Clone the repository
git clone https://github.com/yourusername/edge-voice.git
cd edge-voice

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e .
```

### Verify Installation

```bash
# Check GStreamer installation
gst-inspect-1.0 --version

# List audio devices
arecord -l
aplay -l

# Test Edge Voice
edge-voice --help
```

#### Option 2: From Debian
```bash
# Clone the repository
git clone https://github.com/yourusername/edge-voice.git
cd edge-voice

# Build Debian package
make configure
make build
make install

# Send Debian package to the i.MX device
scp build/deb/edge-voice_1.0_all.deb.deb root@<board_ip>:~
```

```bash
# Install package on the device
dpkg -i edge-voice_1.0_all.deb.deb
```

### Verify Installation
```bash
# Open virtual environment
source ./run_edge_voice.sh

# Test Edge Voice
edge-voice --help
```



## ⚡ Quick Start

### 1. Set Up OpenAI API Key

```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 2. Create Configuration File

Create your own configuration file `config.toml`, for this step you can take the example from [edge-voice.toml](src/edge_voice/edge-voice.toml).
You should configure your ip, connection port, and hardware specifications for your microphone and speaker.


### 3. Run Edge Voice

```bash
edge-voice --config-file config.toml
```

## ⚙️ Configuration

### Configuration File Structure

Edge Voice uses TOML configuration files. See [edge-voice.toml](src/edge_voice/edge-voice.toml) for a complete example.

### Key Configuration Sections

#### Application Settings
```toml
[app]
trigger = "wake-word"        # Trigger mode: "wake-word"
stop_on = "voice-activity"   # Stop mode: "voice-activity"
```
#### Connection Settings
```toml
domain = "api.openai.com"     # OpenAI API server Domain or IP address
# port = 8000                 # OpenAI API server port. Uncomment for custom port
```

#### Microphone Configuration
```toml
[mic]
device = "hw:Microphone,0"    # ALSA device identifier
channels = 1                  # Number of channels
rate = 16000                  # Sample rate in Hz
audio_format = "S16LE"        # Audio format
```

#### Speaker Configuration
```toml
[spkr]
device = "hw:Speaker,0"
rate = 48000
channels = 2
audio_format = "S16LE"
```

#### OpenAI Configuration
```toml
[openai]
url = "api.openai.com"
port = 443
model = "gpt-4o-realtime-preview-2024-12-17"
api_key = "${OPENAI_API_KEY}"  # Environment variable
```

#### Event Actions
```toml
[on.events.listen]
led = true                    # Enable LED feedback
sound = "/path/to/beep.wav"   # Play sound on wake
notification = true           # Show notifications
```

#### Voice Activity Detection
```toml
[vad]
enabled = true
threshold = 0.5               # Silence threshold (0.0-1.0)
```

#### Wake-Word Detection (VIT)
```toml
[vit]
voice_commands = false        # Enable voice commands
silent = true                 # Suppress VIT logs
```

### Command-Line Arguments

Override configuration via command line:

```bash
# Set log level
edge-voice --log-level DEBUG

# Override OpenAI settings
edge-voice --url 192.168.1.100 --port 8080 --model gpt-4o-realtime-preview

# Configure audio devices
edge-voice --mic device=hw:0,0,channels=1,rate=16000
edge-voice --spkr device=hw:1,0,channels=2,rate=48000

# Use custom config file
edge-voice --config-file /path/to/config.toml
```

See [PARSER_USAGE.md](./docs/PARSER_USAGE.md) for detailed argument documentation.

## 🔄 State Machine

Edge Voice operates as a finite state machine with six distinct states:

```
┌─────────────────────────────────────────────────────────────────┐
│                        STATE MACHINE                            │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────┐
    │   IDLE   │ ◄─────────────────────────────────┐
    └────┬─────┘                                   │
         │                                         │
         │ on_wakeword()                           │
         │ [Wake word detected]                    │
         ▼                                         │
    ┌──────────┐                                   │
    │  LISTEN  │ ◄──────────┐                      │
    └────┬─────┘            │                      │
         │                  │                      │
         │ on_voice()       │ on_silence()         │
         │ [Voice detected] │ [Silence detected]   │
         ▼                  │                      │
    ┌──────────┐            │                      │
    │  SEARCH  │────────────┘                      │
    └────┬─────┘                                   │
         │                                         │
         │ on_voice_end()                          │
         │ [End of speech detected]                │
         ▼                                         │
    ┌──────────┐                                   │
    │   WAIT   │                                   │
    └────┬─────┘                                   │
         │                                         │
         │ on_response_start()                     │
         │ [OpenAI response begins]                │
         ▼                                         │
    ┌──────────┐                                   │
    │  SPEAK   │                                   │
    └────┬─────┘                                   │
         │                                         │
         │ on_response_end()                       │
         │ [OpenAI response complete]              │
         └─────────────────────────────────────────┘

    ┌──────────┐
    │ RECOVERY │ ◄─────────────────────────────────┐
    └────┬─────┘                                   │
         │                                         │
         │ on_recovery_success()                   │
         │ [Recovery successful]                   │
         │                                         │
         ├─────────────────────────────────────────┤
         │                                         │
         │ [Error from any state]                  │
         │ IDLE, LISTEN, SEARCH, WAIT, SPEAK ──────┘
         │
         │ on_recovery_failed()
         │ [Recovery failed]
         ▼
    ┌──────────┐
    │   DOWN   │  [Fatal error or shutdown]
    └──────────┘
```

### State Descriptions

| State | Description | Active Components |
|-------|-------------|-------------------|
| **IDLE** | Waiting for wake word | Capture pipeline (valve closed) |
| **LISTEN** | Recording user speech | Capture pipeline (valve open), VAD monitoring |
| **SEARCH** | Detecting end of speech | Capture pipeline, VAD monitoring |
| **WAIT** | Processing user input | OpenAI API processing |
| **SPEAK** | Playing AI response | Playback pipeline, OpenAI streaming |
| **RECOVERY** | Error recovery state | Attempting to recover from errors |
| **DOWN** | Shutdown/error state | All components stopped |

## 🎯 Events & Transitions

### Event Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         EVENT FLOW                              │
└─────────────────────────────────────────────────────────────────┘

Wake Word Detected
       │
       ├─► Open audio valve
       ├─► Start VAD monitoring
       ├─► Start OpenAI listening
       ├─► Play beep (optional)
       ├─► Trigger LED (optional)
       └─► Send notification (optional)
       
Voice Detected (VAD)
       │
       └─► Log voice activity metric

Silence Detected (VAD)
       │
       └─► Continue monitoring

Voice End Detected (VAD)
       │
       ├─► Close audio valve
       ├─► Stop VAD monitoring
       ├─► Commit audio to OpenAI
       ├─► Turn off LED
       └─► Send notification with transcript

OpenAI Response Start
       │
       └─► Begin playback pipeline

OpenAI Response Delta
       │
       └─► Stream audio to speaker

OpenAI Response End
       │
       ├─► Switch to silence
       └─► Return to IDLE
```

### Event Handlers

#### `on_wakeword()`
**Trigger**: Wake word detected by VIT plugin  
**Transition**: `IDLE → LISTEN`  
**Actions**:
- Open capture valve
- Start VAD monitoring
- Begin OpenAI listening session
- Execute configured actions (LED, beep, notification)

#### `on_voice(metric)`
**Trigger**: Voice activity detected by VAD  
**Transition**: `LISTEN → LISTEN` or `SEARCH → LISTEN`  
**Actions**:
- Log voice activity metric
- Continue recording

#### `on_silence(metric)`
**Trigger**: Silence detected by VAD  
**Transition**: `LISTEN → SEARCH`  
**Actions**:
- Begin searching for end of speech

#### `on_voice_end()`
**Trigger**: Extended silence detected (end of speech)  
**Transition**: `SEARCH → WAIT`  
**Actions**:
- Close capture valve
- Stop VAD monitoring
- Commit audio buffer to OpenAI
- Turn off LED
- Send notification with transcript

#### `on_response_start()`
**Trigger**: OpenAI begins streaming response  
**Transition**: `WAIT → SPEAK`  
**Actions**:
- Prepare playback pipeline

#### `on_response_delta(data)`
**Trigger**: Audio chunk received from OpenAI  
**Transition**: `SPEAK → SPEAK`  
**Actions**:
- Push audio data to playback pipeline

#### `on_response_end()`
**Trigger**: OpenAI completes response  
**Transition**: `SPEAK → IDLE`  
**Actions**:
- Switch playback to silence
- Reset to idle state

## 🎬 Action System

Edge Voice includes an extensible action system for executing tasks during state transitions.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Action Manager                        │
│  ┌────────────────────────────────────────────────┐      │
│  │         Thread Pool (max_workers=4)            │      │
│  └────────────────────────────────────────────────┘      │
│                          │                               │
│         ┌────────────────┼────────────────┐              │
│         ▼                ▼                ▼              │
│  ┌───────────┐   ┌──────────────┐  ┌──────────┐          │
│  │    LED    │   │ Notification │  │  Custom  │          │
│  │  Action   │   │    Action    │  │  Action  │          │
│  └───────────┘   └──────────────┘  └──────────┘          │
└──────────────────────────────────────────────────────────┘
```

### Built-in Actions

#### LED Action
Controls RGB LEDs for visual feedback.

**Configuration**:
```toml
[actions.led]
enabled = true
leds = ["rgb:red", "rgb:green", "rgb:blue"]
brightness_scale = 1.0
```

**Usage**:
```python
# Turn on LED (brightness 0-255)
action_manager.queue_action("led", priority=3, brightness=255)

# Turn off LED
action_manager.queue_action("led", priority=3, brightness=0)
```

#### Notification Action
Sends notifications to console and/or system.

**Configuration**:
```toml
[actions.notification]
enabled = true
log_level = "info"
console_output = true
include_metadata = true
```

**Usage**:
```python
action_manager.queue_action(
    "notification",
    priority=3,
    message="Wake word detected",
    metadata={"confidence": 0.95}
)
```

### Creating Custom Actions

Extend the `ActionPlugin` base class:

```python
from edge_voice.actions.base import ActionPlugin

class CustomAction(ActionPlugin):
    def __init__(self, config):
        super().__init__("custom_action", config)
    
    def execute(self, priority: int, *args, **kwargs):
        # Your custom logic here
        self.logger.info(f"Executing custom action: {args}")
        return True

# Register with action manager
action_manager.register_plugin(CustomAction(config))
```

## 🔌 GStreamer Plugins

Edge Voice supports custom GStreamer plugins for advanced audio processing.

### Plugin Directory Structure

This project requires a set of GST imx-voice plugins from NXP to support voice applications on i.MX devices. To use them, you must use a Linux BSP **6.12.34-2.1.0**

| Plugin                 | Version| Description                                                                  |
|------------------------|--------|------------------------------------------------------------------------------|
| libgstimx_ai_nr.so     |1.0     | NXP AI-based single microphone noise reduction                               |
| libgstimx_ai_aecnr.so  |2.1     | NXP AI-based single microphone acoustic echo canceller and noise suppressor  |
| libgstimxvit.so        |Demo 0.5| NXP wakeword and voice commands detection engine                             |


To obtain those plugins and their capabilities, you should contact NXP at voice@nxp.com.


The plugins should be placed inside the `/usr/lib/gstreamer-1.0/` directory.

### Plugin Loading

Plugins are automatically loaded on startup:

```python
from edge_voice import init_voice
init_voice()  # Initializes GStreamer and loads plugins
```

### Verifying Plugin Installation

```
Added /usr/lib/gstreamer-1.0/ to GST_PLUGIN_PATH
GStreamer initialized successfully
✓ Plugin 'imxvit' loaded successfully
✓ Plugin 'imx_ai_nr' loaded successfully
✓ Plugin 'imx_ai_aecnr' loaded successfully
GStreamer setup complete. i.MX plugins are now available for use.
```

### Adding Custom Plugins

1. Place compiled `.so` file in `/usr/lib/gstreamer-1.0/`
2. Restart the application
3. Verify loading in logs

## 📚 Usage Examples

### Example 1: Basic Wake-Word Assistant

```toml
[app]
trigger = "wake-word"
stop_on = "voice-activity"

[mic]
device = "hw:0,0"

[spkr]
device = "hw:1,0"

[on.events.listen]
led = true
notification = true
```

```bash
edge-voice --config-file config.toml
```

### Example 2: Custom Audio Configuration

```bash
edge-voice \
  --mic device=hw:0,0,channels=1,rate=16000,format=S16LE \
  --spkr device=hw:1,0,channels=2,rate=48000,format=S32LE \
  --log-level DEBUG
```

### Example 3: NXP i.MX93 EVK FRDM with Custmo SPK and Mic

```toml
[app]
trigger = "wake-word"
stop_on = "voice-activity"

[mic]
device = "hw:Microphone,0"

[spkr]
device = "hw:2,0"
rate = 48000
channels = 2
audio_format = "S16LE"

[vit]
voice_commands = false
silent = true

[actions.led]
enabled = true
leds = ["rgb:red", "rgb:green", "rgb:blue"]

[on.events.listen]
led = true
sound = "/root/ww_earcon.wav"
notification = true
```

## 🐛 Troubleshooting

### Audio Device Issues

```bash
# List available audio devices
arecord -l  # Microphones
aplay -l    # Speakers

# Test microphone
arecord -D hw:0,0 -f S16_LE -r 16000 -c 1 test.wav

# Test speaker
aplay -D hw:1,0 test.wav
```

### OpenAI Connection Issues

```bash
# Verify API key
echo $OPENAI_API_KEY

# Test connection
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

### Common Errors

| Error | Solution |
|-------|----------|
| `No such device: hw:X,Y` | Check device with `arecord -l` / `aplay -l` |
| `Plugin not found` | Verify `.so` file exists and has correct permissions |
| `OpenAI connection failed` | Check API key and network connectivity |
| `VAD not working` | Adjust `threshold` in `[vad]` configuration |

### Debug Mode

Enable verbose logging:

```bash
edge-voice --log-level DEBUG --config-file config.toml
```

Enable GStreamer debug messages:

```toml
[debug]
verbose_bus_messages = true
```

## 📖 Additional Documentation

- [Parser Usage Guide](docs/PARSER_USAGE.md) - Command-line argument reference
- [Configuration Reference](src/edge_voice/edge-voice.toml) - Complete config example

---------------------------------------------------------
**Built with ❤️ for edge AI applications**