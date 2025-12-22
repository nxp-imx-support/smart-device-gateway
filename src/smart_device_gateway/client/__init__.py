# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import logging
import os
import sys
from pathlib import Path
import time

import gi

from .utils import GREEN, RED, RESET, get_terminal_width

gi.require_version("Gst", "1.0")
gi.require_version("GstAudio", "1.0")
gi.require_version("GLib", "2.0")

from gi.repository import GLib, GObject, Gst

__init = False


def init_gstreamer() -> None:
    """Initialize GStreamer and load custom plugins from the plugins directory."""
    # Get the plugins directory path
    current_dir = Path(__file__).parent
    #plugins_dir = current_dir / "gst-plugins"
    plugins_dir = Path("/usr/lib/gstreamer-1.0/")

    if not plugins_dir.exists():
        print(f"i.MX voice plugins not found at {plugins_dir}")
        sys.exit(-1)

    # Add our plugins directory to GStreamer's plugin path
    plugins_path = str(plugins_dir.absolute())

    # Add to GST_PLUGIN_PATH environment variable
    current_plugin_path = os.environ.get("GST_PLUGIN_PATH", "")
    if plugins_path not in current_plugin_path:
        if current_plugin_path:
            os.environ["GST_PLUGIN_PATH"] = f"{current_plugin_path}:{plugins_path}"
        else:
            os.environ["GST_PLUGIN_PATH"] = plugins_path
        print(f"Added {plugins_path} to GST_PLUGIN_PATH")
    else:
        print("Plugins path is already present under GST_PLUGIN_PATH variable.")

    # Initialize GStreamer
    if not Gst.is_initialized():
        Gst.init(None)
        GObject.type_init()
        print("GStreamer initialized successfully")


def verify_plugin_loading() -> None:
    """Verify that custom plugins are properly loaded by GStreamer."""
    registry = Gst.Registry.get()

    # List of expected custom plugins based on the .so files
    expected_plugins = [
        "imxvit",  # from libgstimxvit.so
        "imx_ai_nr",  # from libgstimx_ai_nr.so
        "imxasr",  # from libgstimxasr.so
        "imx_ai_dual_aecnr",  # from libgstimx_ai_dual_aecnr.so
        "imx_ai_aecnr",  # from libgstimx_ai_aecnr.so
    ]

    loaded_plugins = []
    for plugin_name in expected_plugins:
        plugin = registry.find_plugin(plugin_name)
        if plugin:
            loaded_plugins.append(plugin_name)
            print(f"{GREEN}✓{RESET} Plugin '{plugin_name}' loaded successfully")
        else:
            print(f"{RED}✗{RESET} Plugin '{plugin_name}' not found in registry")


def init_voice():
    global __init
    if __init:
        return

    width = get_terminal_width()
    print(f"{GREEN}{'=' * width}{RESET}")
    print(f"{GREEN}{'NXP Edge Voice Init':-^{width}}{RESET}")
    print(f"{GREEN}{'=' * width}{RESET}")
    init_gstreamer()
    verify_plugin_loading()
    print("GStreamer setup complete. i.MX plugins are now available for use.")
    __init = True


init_voice()


def main() -> None:
    from .logger import configure_logging
    from .parser import parse_arguments
    from .controller import Controller
    from .validate import validate

    args = parse_arguments()
    config = validate(args)

    configure_logging(config.logging)

    ctrl = Controller(config)

    try:
        ctrl.mainloop.run()

    except KeyboardInterrupt:
        print("Ctrl + C")
    finally:
        ctrl.shutdown()
