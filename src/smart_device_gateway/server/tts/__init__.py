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
import asyncio
import logging
import re
import shutil
from typing import Any, Iterable, Optional, Sequence, Tuple, Union

import numpy as np
import onnxruntime
from huggingface_hub import hf_hub_download, try_to_load_from_cache

class VITSConfig:
    """Configuration for VITS model"""
    audio: dict
    espeak: dict
    inference: dict
    phoneme_type: str
    phoneme_map: dict
    phoneme_id_map: dict
    num_symbols: int
    num_speakers: int
    speaker_id_map: dict
    language: dict
    dataset: str

class VITSModel:
    """Speech-to-Text"""
    def __init__(self):
        # Check if espeak-ng is already installed
        if shutil.which("espeak-ng") is None:
            raise RuntimeError("espeak-ng is required but not installed")

        self._repo_id = "rhasspy/piper-voices"
        self._model_file = "en/en_US/amy/medium/en_US-amy-medium.onnx"
        self._config_file = "en/en_US/amy/medium/en_US-amy-medium.onnx.json"
        self._cache_dir = "./.cache"

        # Download model
        model_path = try_to_load_from_cache(
                repo_id=self._repo_id,
                filename=self._model_file,
                cache_dir=self._cache_dir,
        )

        if model_path is None:
            model_path = hf_hub_download(
                        repo_id=self._repo_id,
                        filename=self._model_file,
                        cache_dir=self._cache_dir,
            )

        # Download config
        config_path = try_to_load_from_cache(
                repo_id=self._repo_id,
                filename=self._config_file,
                cache_dir=self._cache_dir,
        )

        if config_path is None:
            config_path = hf_hub_download(
                        repo_id=self._repo_id,
                        filename=self._config_file,
                        cache_dir=self._cache_dir,
            )

        self.config = self._load_config_from_json(config_path)
        self._model = onnxruntime.InferenceSession(model_path)

    def _load_config_from_json(self, config_path: str) -> VITSConfig:
        """Load VITS configuration from JSON file"""
        with open(config_path, 'r') as f:
            config_dict = json.load(f)
        config = VITSConfig()
        for key, value in config_dict.items():
            setattr(config, key, value)
        return config

    def _phonemizer(self, text) -> list[str]:
        return os.popen(f"espeak-ng -v en-us --ipa=3 -q {repr(text)}")

    def _phonemas_to_ids(self, phonemas: str) -> list[int]:
        """Convert phonemes to their corresponding IDs"""
        PAD = "_"  # padding
        BOS = "^"  # beginning of sentence
        EOS = "$"  # end of sentence

        ids = [self.config.phoneme_id_map[BOS][0]]
        for phoneme in phonemas:
            if phoneme in self.config.phoneme_id_map:
                ids.append(self.config.phoneme_id_map[phoneme][0])
                ids.append(self.config.phoneme_id_map[PAD][0])

        ids.append(self.config.phoneme_id_map[EOS][0])
        return ids

    def _ids_to_audio(self, ids: list[int]) -> np.ndarray:
        """Convert phoneme IDs to audio using ONNX model"""
        length_scale = self.config.inference.get("length_scale", 1.0)
        noise_scale = self.config.inference.get("noise_scale", 0.667)
        noise_w = self.config.inference.get("noise_w", 0.8)

        phoneme_ids_array = np.expand_dims(np.array(ids, dtype=np.int64), 0)
        phoneme_ids_lengths = np.array([phoneme_ids_array.shape[1]], dtype=np.int64)
        scales = np.array([noise_scale, length_scale, noise_w], dtype=np.float32)

        args = {"input": phoneme_ids_array, "input_lengths": phoneme_ids_lengths, "scales": scales}

        output_names = self._model.get_outputs()[0].name
        audio = self._model.run([output_names], args)[0]
        return audio.flatten().astype(np.float32)

    def _normalize_text(self, text: str) -> str:
        """Normalize text by removing unwanted characters and formatting"""
        # Remove newlines, tabs, and carriage returns
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')

        # Remove markdown/formatting characters
        text = text.replace('*', '').replace('_', '').replace('~', '')

        # Remove special characters that don't contribute to speech
        text = text.replace(':', ',').replace(';', ',')

        # Remove brackets and parentheses content (optional - can be modified)
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\{.*?\}', '', text)

        # Remove extra symbols
        text = re.sub(r'[#@$%^&+=<>|\\\/]', '', text)

        # Remove multiple spaces and trim
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove leading/trailing punctuation that might cause issues
        text = text.strip('.,!?;:')

        return text

    async def generate_speech_stream(self, text: str):
        if text:
            text = self._normalize_text(text)
            sentence_phonemas = self._phonemizer(text)
            for phonemas in sentence_phonemas:
                ids = self._phonemas_to_ids(phonemas)
                audio = await asyncio.to_thread(self._ids_to_audio, ids)
                yield audio

        else:
            yield np.empty(0, dtype=np.float32)

    async def async_model_loop(self, tokens_q, audio_q):
        sentence_ending_characters = "?,.!" # If token contains any of these, it's end of sentence
        sentence = ""

        while True:
            try:
                token = await asyncio.wait_for(tokens_q.get(), timeout=0.01)
                if token == "":
                    continue

                # You get the sentinel, which means you have received all tokens.
                if token is None:
                    if sentence:
                        async for _, audio_chunk in self.generate_speech_stream(sentence):
                            await audio_q.put(audio_chunk)
                            #print(audio_chunk)

                    sentence = ""
                    await audio_q.put(None)

                # Generate an audio chunk when you encounter a sentence-ending character. if not
                # continue adding tokens
                else:
                    sentence = sentence + token
                    if any(char in sentence_ending_characters for char in sentence):
                        async for audio_chunk in self.generate_speech_stream(sentence):
                            await audio_q.put(audio_chunk)
                            #print(audio_chunk)

                        sentence = ""

            except asyncio.TimeoutError:
                continue

            except asyncio.CancelledError:
                # Coroutine was cancelled, propagate the cancellation
                raise

            except Exception as e:
                continue

__all__ = ["VITSModel"]