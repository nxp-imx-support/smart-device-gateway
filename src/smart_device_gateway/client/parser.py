# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import argparse
from .config import LOG_VALUES


def parse_key_value_pairs(value):
    """
    Parse key-value pairs separated by semicolons.
    Example: device=hw:0,0;channels=1;audio_format=S32LE;rate=16000
    Returns a dictionary.
    """
    if not value:
        return {}

    pairs = {}
    for item in value.split(";"):
        if "=" not in item:
            raise argparse.ArgumentTypeError(
                f"Invalid key-value pair: '{item}'. Expected format: key=value"
            )
        key, val = item.split("=", 1)
        pairs[key.strip()] = val.strip()

    return pairs


def validate_log_level(value):
    """Validate log level is one of the allowed values."""
    allowed_levels = ["debug", "warning", "info", "error", "critical"]
    if value.lower() not in allowed_levels:
        raise argparse.ArgumentTypeError(
            f"Invalid log level: '{value}'. Must be one of {allowed_levels}"
        )
    return value.lower()


def validate_port(value):
    """Validate port is a positive integer."""
    try:
        port = int(value)
        if port <= 0:
            raise argparse.ArgumentTypeError(
                f"Port must be a positive integer, got: {port}"
            )
        return port
    except ValueError:
        raise argparse.ArgumentTypeError(f"Port must be an integer, got: '{value}'")


def validate_config_file(value):
    """Validate config file ends with .json or .toml."""
    if not (value.endswith(".json") or value.endswith(".toml")):
        raise argparse.ArgumentTypeError(
            f"Config file must end with .json or .toml, got: '{value}'"
        )
    return value


def create_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Parse command line arguments for audio processing application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
%(prog)s --log-level info --domain localhost --port 8080 --model mymodel --config-file config.json --mic "device=hw:0,0;channels=1;audio_format=S32LE;rate=16000" --spkr "device=hw:0,1;channels=2;format=S16LE;rate=48000"
        """,
    )

    parser.add_argument(
        "--log-level",
        type=str,
        help="Logging level: debug, warning, info, error, or critical",
        choices=LOG_VALUES,
    )

    parser.add_argument("--domain", type=str, help="Domain string")

    parser.add_argument(
        "--port", type=validate_port, help="Port number (positive integer)"
    )

    parser.add_argument("--model", type=str, help="Model name string")

    parser.add_argument(
        "--config-file",
        type=validate_config_file,
        help="Configuration file path (must be JSON or TOML)",
    )

    parser.add_argument(
        "--mic",
        type=parse_key_value_pairs,
        help='Microphone settings as key-value pairs separated by semicolons (e.g., "device=hw:0,0;channels=1;audio_format=S32LE;rate=16000")',
    )

    parser.add_argument(
        "--spkr",
        type=parse_key_value_pairs,
        help='Speaker settings as key-value pairs separated by semicolons (e.g., "device=hw:0,1;channels=2;audio_format=S16LE;rate=48000")',
    )

    return parser


def parse_arguments(args=None):
    """
    Parse command line arguments.

    Args:
        args: List of arguments to parse. If None, uses sys.argv[1:]

    Returns:
        Namespace object with parsed arguments
    """
    parser = create_parser()
    return parser.parse_args(args)
