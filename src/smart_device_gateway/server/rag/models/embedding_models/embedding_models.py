# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
import torch
import logging
import numpy as np
import onnxruntime as ort
import torch.nn.functional as F
from transformers import AutoTokenizer
from huggingface_hub import hf_hub_download, try_to_load_from_cache


logger = logging.getLogger(__name__)

class EmbeddingModel:
    name: str = None

    def __new__(cls, name: str,
                config: None = None,
                saving_folder: str = None):
        """Dynamically instantiate the correct subclass based on `name`."""
        name_to_class_dict = {subclass.name: subclass for subclass in cls.__subclasses__()}
        if name in name_to_class_dict:
            return super().__new__(name_to_class_dict[name])  # Instantiate the correct subclass
        else:
            error_text = f"Unknown model name: {name}"
            logger.error(error_text)
            raise ValueError(error_text)

    def __init__(self, name: str,
                 config: None = None,
                 saving_folder: str = None):
        """Initialize common attributes for all embedding models."""
        self.name = name
        self.embedding_model_version = self.name + ".onnx"
        logger.info(f"Embedding model used: {self.embedding_model_version}")

        self._tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

        # Download model
        self._repo_id = "sentence-transformers/all-MiniLM-L6-v2"
        self._model_file = "onnx/model.onnx"
        self._cache_dir = "./.cache"

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

        self._embedding_model = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])

    def encode(self, texts):
        pass  # This method is intended to be overridden in child classes


class AllMiniL6V2(EmbeddingModel):
    name = "all-MiniLM-L6-v2"
    hf_path = "sentence-transformers/all-MiniLM-L6-v2"

    def _mean_pooling(self, token_embeddings, attention_mask):
        #token_embeddings = model_output[0] # First element of model_output contains all token embeddings
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def encode(self, texts):
        if isinstance(texts, str):
            # Convert single text to a list for consistent handling
            texts = [texts]

        # Tokenize all texts into input IDs, attention masks, and token type IDs
        encoded_input = self._tokenizer(texts, padding=True, truncation=True, return_tensors='pt')
        input_ids = encoded_input['input_ids']
        token_type_ids = encoded_input['token_type_ids']
        attention_mask = encoded_input['attention_mask']

        input_feed = {"input_ids": input_ids.to(torch.int64).numpy(),
                      "token_type_ids": token_type_ids.to(torch.int64).numpy(),
                      "attention_mask": attention_mask.to(torch.int64).numpy()}

        model_output = self._embedding_model.run(output_names=["last_hidden_state"],
                                                      input_feed=input_feed)

        model_output = torch.from_numpy(model_output[0])
        sentence_embeddings = self._mean_pooling(model_output, attention_mask)

        # Normalize embeddings
        sentence_embeddings = F.normalize(sentence_embeddings, p=2, dim=1)
        return sentence_embeddings