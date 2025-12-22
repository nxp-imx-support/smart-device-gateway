# Copyright 2025-2026 NXP
#
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import json
import tomllib
from argparse import Namespace
from pathlib import Path
from typing import Any, Dict

from .config import UserConfig

# Hardcoded configuration file path
CONFIG_FILE = Path(__file__).parent / "./edge-voice.toml"


def load_toml_file(filepath: str | Path) -> Dict[str, Any]:
    """
    Load a TOML file and return its contents as a dictionary.

    Args:
        filepath: Path to the TOML file

    Returns:
        Dictionary with TOML contents, or empty dict if file doesn't exist
    """
    path = Path(filepath)
    if not path.exists():
        print(f"Warning: Default config file not found: {filepath}")
        return {}

    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Error loading TOML file {filepath}: {e}")
        return {}


def load_json_file(filepath: str) -> Dict[str, Any]:
    """
    Load a JSON file and return its contents as a dictionary.

    Args:
        filepath: Path to the JSON file

    Returns:
        Dictionary with JSON contents
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"Error loading JSON file {filepath}: {e}")


def load_config_file(filepath: str) -> Dict[str, Any]:
    """
    Load a configuration file (JSON or TOML) based on its extension.

    Args:
        filepath: Path to the config file

    Returns:
        Dictionary with config contents
    """
    if filepath.endswith(".json"):
        return load_json_file(filepath)
    elif filepath.endswith(".toml"):
        return load_toml_file(filepath)
    else:
        raise ValueError(f"Unsupported config file format: {filepath}")


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with override values taking precedence.

    Args:
        base: Base dictionary
        override: Dictionary with values to override

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def validate_and_merge_config(args) -> tuple[Dict[str, Any], bool]:
    """
    Validate arguments and merge configurations in the following order:
    1. Load hardcoded default config (CONFIG_FILE)
    2. Merge with user-provided config file (args.config_file)
    3. Override with command-line arguments

    Args:
        args: Namespace object from argparse with parsed arguments

    Returns:
        Final merged configuration dictionary
    """
    # Step 1: Load hardcoded default config
    config = load_toml_file(CONFIG_FILE)
    print(f"Loaded default config from: {CONFIG_FILE}")

    # Step 2: Merge with user-provided config file if it exists
    if hasattr(args, "config_file") and args.config_file:
        try:
            user_config = load_config_file(args.config_file)
            print("USER CONFIGURATION")
            config = deep_merge(config, user_config)
            print(f"Merged config from: {args.config_file}")
        except FileNotFoundError as e:
            print(f"Warning: {e}")
        except ValueError as e:
            print(f"Warning: {e}")

    # Step 3: Override with command-line arguments
    # Ensure 'openai' key exists
    if "openai" not in config:
        config["openai"] = {}

    verbose = False
    # Override log-level if provided
    if hasattr(args, "log_level") and args.log_level:
        verbose = args.log_level == "debug"
        config["logging"]["log_level"] = args.log_level
        if verbose:
            print(f"Overriding log_level: {args.log_level}")

    # Override openai settings if provided
    if hasattr(args, "domain") and args.domain:
        config["openai"]["domain"] = args.domain
        if verbose:
            print(f"Overriding domain: {args.domain}")

    if hasattr(args, "port") and args.port:
        config["openai"]["port"] = args.port
        if verbose:
            print(f"Overriding port: {args.port}")

    if hasattr(args, "model") and args.model:
        config["openai"]["model"] = args.model
        if verbose:
            print(f"Overriding model: {args.model}")

    # Override mic settings if provided
    if hasattr(args, "mic") and args.mic:
        config["mic"] = args.mic
        if verbose:
            print(f"Overriding mic: {args.mic}")

    # Override spkr settings if provided
    if hasattr(args, "spkr") and args.spkr:
        config["spkr"] = args.spkr
        if verbose:
            print(f"Overriding spkr: {args.spkr}")

    return config, verbose


def ensure_property(
    object: object,
    property: str,
    new: Any,
    overrride: bool = True,
    verbose: bool = False,
) -> None:
    old = getattr(object, property)
    if old and not overrride:
        if verbose:
            print(f"Validation: property '{property}' is present on object: '{object}'")
        return

    if verbose:
        print(
            f"Validation: Overriding property '{property}': '{old}' -> '{new}' on object: {object}"
        )

    setattr(object, property, new)


def validate(args: Namespace) -> UserConfig:
    """
    Main validation function that processes the arguments namespace.

    Args:
        args: Namespace object from argparse

    Returns:
        Final validated and merged configuration dictionary
    """
    final_config, verbose = validate_and_merge_config(args)
    user_config = UserConfig.model_validate(final_config, strict=True)

    if user_config.app.trigger != "wake-word":
        raise NotImplementedError(
            f"Feature: {user_config.app.trigger} not implemented."
        )

    if user_config.app.stop_on != "voice-activity":
        raise NotImplementedError(
            f"Feature: {user_config.app.stop_on} not implemented."
        )

    # Ensure required appsink properties are enable
    ensure_property(user_config.openai.sink, "emit_signals", True, verbose=verbose)
    ensure_property(
        user_config.openai.sink, "name", "openai_sink", overrride=False, verbose=verbose
    )

    # Ensure required appsrc properties
    ensure_property(user_config.openai.src, "emit_signals", True, verbose=verbose)
    ensure_property(user_config.openai.src, "is_live", False, verbose=verbose)
    ensure_property(user_config.openai.src, "format", "time", verbose=verbose)
    ensure_property(user_config.openai.src, "do_timestamp", False, verbose=verbose)
    ensure_property(
        user_config.openai.src, "name", "openai_src", overrride=False, verbose=verbose
    )

    return user_config
