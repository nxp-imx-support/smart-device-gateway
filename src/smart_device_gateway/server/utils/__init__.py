# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
import numpy as np
from scipy import signal


def resample_audio(audio: np.ndarray, original_rate: int, target_rate: int) -> np.ndarray:
    """
    Resample audio from original sample rate to target sample rate.

    Args:
        audio: Audio array as numpy ndarray
        original_rate: Original sample rate in Hz
        target_rate: Target sample rate in Hz

    Returns:
        Resampled audio array
    """
    if original_rate == target_rate:
        return audio

    # Check if audio is already float32
    if audio.dtype == np.float32:
        audio_float32 = audio

    else:
        # Convert from int16 to float32
        audio_float32 = audio.astype(np.float32) / 32768.0

    # Apply volume gain (1.0 = no change, 2.0 = double volume, etc.)
    #gain = 1.5  # Adjust this value as needed
    #audio_float32 = audio_float32 * gain

    # Clip to prevent distortion from values exceeding [-1.0, 1.0]
    audio_float32 = np.clip(audio_float32, -1.0, 1.0)

    # Compute the greatest common divisor (GCD) for efficient resampling
    gcd = np.gcd(original_rate, target_rate)
    upsample_rate = target_rate // gcd
    downsample_rate = original_rate // gcd

    # Resample using polyphase filtering for better accuracy
    resampled_audio = signal.resample_poly(audio_float32, upsample_rate, downsample_rate)
    return resampled_audio

__all__ = ["resample_audio"]