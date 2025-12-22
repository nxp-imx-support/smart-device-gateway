# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
import asyncio
import logging

import numpy as np
import onnxruntime
import tokenizers
from silero_vad import VADIterator, load_silero_vad
from huggingface_hub import hf_hub_download, try_to_load_from_cache

from ._audio_buffer import RingBuffer


logger = logging.getLogger(__name__)

class MoonshineModel:
    """Speech-to-Text"""
    def __init__(self):
        # Model hyperparameters
        # Moonshine supports audio segments that are between 0.1s and 64s
        self.token_rate = 6
        self.sampling_rate = 16000
        self.max_num_secs = 64

        self.num_layers = 8
        self.num_key_value_heads = 8
        self.head_dim = 52

        self.decoder_start_token_id = 1
        self.eos_token_id = 2

        self._model_repo_id = "UsefulSensors/moonshine"
        self._encoder_file = "onnx/merged/base/float/encoder_model.onnx"
        self._decoder_file = "onnx/merged/base/float/decoder_model_merged.onnx"

        self._tokenizer_repo_id = "onnx-community/moonshine-base-ONNX"
        self._tokenizer_file = "tokenizer.json"
        self._cache_dir = "./.cache"

        # VAD config
        self._chunk_size = 512
        self._vad_min_silence_duration_ms = 300
        self._vad_threshold = 0.5
        self._loopback_chunks = 3

        # Download encoder
        encoder_path = try_to_load_from_cache(
            repo_id=self._model_repo_id,
            filename=self._encoder_file,
            cache_dir=self._cache_dir,
        )

        if encoder_path is None:
            encoder_path = hf_hub_download(
                repo_id=self._model_repo_id,
                filename=self._encoder_file,
                cache_dir=self._cache_dir,
            )

        # Download decoder
        decoder_path = try_to_load_from_cache(
            repo_id=self._model_repo_id,
            filename=self._decoder_file,
            cache_dir=self._cache_dir,
        )

        if decoder_path is None:
            decoder_path = hf_hub_download(
                repo_id=self._model_repo_id,
                filename=self._decoder_file,
                cache_dir=self._cache_dir,
            )

        # Download tokenizer
        tokenizer_path = try_to_load_from_cache(
            repo_id=self._tokenizer_repo_id,
            filename=self._tokenizer_file,
            cache_dir=self._cache_dir,
        )

        if tokenizer_path is None:
            tokenizer_path = hf_hub_download(
                repo_id=self._tokenizer_repo_id,
                filename=self._tokenizer_file,
                cache_dir=self._cache_dir,
            )

        self.encoder = onnxruntime.InferenceSession(encoder_path)
        self.decoder = onnxruntime.InferenceSession(decoder_path)

        self.encoder_input_names = [x.name for x in self.encoder.get_inputs()]
        self.decoder_input_names = [x.name for x in self.decoder.get_inputs()]

        self.tokenizer = tokenizers.Tokenizer.from_file(tokenizer_path)

        self._vad = load_silero_vad(onnx=True)
        self._vad_iterator = VADIterator(
                                model=self._vad,
                                sampling_rate=self.sampling_rate,
                                threshold=self._vad_threshold,
                                min_silence_duration_ms=self._vad_min_silence_duration_ms,
        )

        # Ring buffer
        self._audio = np.empty(0, dtype=np.float32)
        self._listening = False
        self._recording = False
        self._blocked = False

        self._buffer = RingBuffer(
                        capacity=self.sampling_rate * (self.max_num_secs - 1),
                        dtype=np.float32,
        )

    def push_data_to_buffer(self, audio):
        if not isinstance(audio, np.ndarray):
            raise TypeError(f"Expected a Numpy array but got type: {type(audio).__name__}")

        if not audio.dtype == np.float32:
            raise TypeError(f"Expected float32 dtype but got dtype: {audio.dtype}")

        if self._blocked:
            logger.warning("Attempting to write in the buffer when it's blocked.")
        else:
            self._buffer.write(audio)

    def transcribe_audio_sync(self, audio, max_len=None):
        """Audio has to be a numpy array of shape [1, num_audio_samples]"""
        audio = audio[None,:]
        if max_len is None:
            max_len = int((audio.shape[-1] / self.sampling_rate) * self.token_rate)

        encoder_inputs = dict(input_values=audio)
        audio_attention_mask = np.ones_like(audio, dtype=np.int64)

        if "attention_mask" in self.encoder_input_names:
            encoder_inputs = dict(attention_mask=audio_attention_mask, **encoder_inputs)

        last_hidden_state = self.encoder.run(None, encoder_inputs)[0]

        past_key_values = {
            f"past_key_values.{i}.{a}.{b}": np.zeros(
                (0, self.num_key_value_heads, 1, self.head_dim), dtype=np.float32
            )
            for i in range(self.num_layers)
            for a in ("decoder", "encoder")
            for b in ("key", "value")
        }

        tokens = [self.decoder_start_token_id]
        input_ids = [tokens]

        for i in range(max_len):
            use_cache_branch = i > 0
            decoder_inputs = dict(
                input_ids=input_ids,
                encoder_hidden_states=last_hidden_state,
                use_cache_branch=[use_cache_branch],
                **past_key_values,
            )

            if "encoder_attention_mask" in self.decoder_input_names:
                decoder_inputs = dict(
                    encoder_attention_mask=audio_attention_mask, **decoder_inputs
                )

            logits, *present_key_values = self.decoder.run(None, decoder_inputs)
            next_token = logits[0, -1].argmax().item()
            tokens.append(next_token)
            if next_token == self.eos_token_id:
                break

            # Update values for next iteration
            input_ids = [[next_token]]
            for k, v in zip(past_key_values.keys(), present_key_values):
                if not use_cache_branch or "decoder" in k:
                    past_key_values[k] = v

        result = self.tokenizer.decode_batch([tokens], skip_special_tokens=True)[0]
        return result

    def start(self):
        self._listening = True

    def stop(self):
        self._listening = False

    async def async_model_loop(self, transcriptions_q):
        while True:
            if not self._listening:
                await asyncio.sleep(0.01)
                continue

            while self._listening:
                chunk = self._buffer.read(self._chunk_size)
                if chunk is None:
                    await asyncio.sleep(0.01)
                    continue

                self._audio = np.concatenate((self._audio, chunk))
                if not self._recording:
                    self._audio = self._audio[-self._loopback_chunks * self._chunk_size:]

                vad_time_stamps = self._vad_iterator(chunk)
                if vad_time_stamps:
                    if "start" in vad_time_stamps and not self._recording:
                        self._recording = True

                    if "end" in vad_time_stamps and self._recording:
                        res = await asyncio.to_thread(self.transcribe_audio_sync, self._audio)
                        self._recording = False
                        self._audio = np.empty(0, dtype=np.float32)

                        await transcriptions_q.put(res)

            # Clean the buffer before closing the generator
            if not self._buffer.is_empty():
                chunk = self._buffer.read(self._buffer.size)
                self._audio = np.concatenate((self._audio, chunk))
                res = await asyncio.to_thread(self.transcribe_audio_sync, self._audio)

                await transcriptions_q.put(res)
                await transcriptions_q.put(None) # Sentinel value to signal end

            self._recording = False
            self._audio = np.empty(0, dtype=np.float32)

__all__ = ["MoonshineModel"]