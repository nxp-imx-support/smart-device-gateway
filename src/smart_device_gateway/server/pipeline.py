# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.
import os
import asyncio
import logging
from typing import Optional, Tuple, List, Any

from .rag import Retriever
from .rag.models.embedding_models.embedding_models import EmbeddingModel
from .rag.preprocessing.generate_embeddings import generate_all_embeddings
from .stt import MoonshineModel
from .tts import VITSModel


class SmartDeviceGatewayPipeline:
    """Manages the audio processing pipeline for real-time communication."""
    def __init__(self):
        logger = logging.getLogger("uvicorn.error")
        
        self.loops = []
        self.stt = MoonshineModel()
        self.tts = VITSModel()

        # Load embedding model once and share across all devices
        logger.info("Loading embedding model...")
        self.embedding_model = EmbeddingModel(name="all-MiniLM-L6-v2")
        
        self._database_path = os.path.join(os.path.dirname(__file__), "database")
        
        # Generate embeddings for any JSON files that don't have PKL files yet (one-time activity)
        self._generate_missing_embeddings()
        
        # Load all retrievers
        self.retrievers = self._load_retrievers()

        # Queues for data flow
        self.transcriptions_q = asyncio.Queue()
        self.tokens_q = asyncio.Queue()
        self.audio_q = asyncio.Queue()
        self.query_q = asyncio.Queue()

    def _check_missing_pkl_files(self) -> list[str]:
        """
        Check which JSON files don't have corresponding PKL files.
        
        Returns:
            List of JSON filenames that need PKL generation
        """
        logger = logging.getLogger("uvicorn.error")
        
        if not os.path.isdir(self._database_path):
            logger.warning(f"Database directory not found: {self._database_path}")
            return []
        
        json_files = [f for f in os.listdir(self._database_path) if f.endswith('.json')]
        missing_pkl_files = []
        
        for json_file in json_files:
            pkl_file = os.path.splitext(json_file)[0] + '.pkl'
            pkl_path = os.path.join(self._database_path, pkl_file)
            
            if not os.path.exists(pkl_path):
                missing_pkl_files.append(json_file)
        
        return missing_pkl_files

    def _generate_missing_embeddings(self):
        """
        Generate embeddings for JSON files that don't have corresponding PKL files.
        This is a one-time activity - if all PKL files exist, skip generation entirely.
        """
        logger = logging.getLogger("uvicorn.error")
        
        # First, check if there are any missing PKL files
        missing_files = self._check_missing_pkl_files()
        
        if not missing_files:
            logger.info("All databases already exist. Skipping embedding generation.")
            return
        
        logger.info("Starting embedding generation (this may take a while)...")
        
        try:
            pkl_files = generate_all_embeddings(
                database_dir=self._database_path,
                embedding_model=self.embedding_model
            )
            
            newly_created = [f for f in pkl_files if os.path.basename(os.path.splitext(f)[0] + '.json') in missing_files]
            
            if newly_created:
                logger.info(f"Successfully generated {len(newly_created)} new database file(s)")
            else:
                logger.info("No new embeddings were generated")
                
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            logger.warning("Pipeline will continue with existing databases only")

    def _load_retrievers(self) -> dict[str, Retriever]:
        """Load all RAG retrievers from database directory."""
        retrievers = {}
        for filename in os.listdir(self._database_path):
            if filename.endswith(".pkl"):
                full_path = os.path.join(self._database_path, filename)
                # Pass the shared embedding model to each retriever
                retrievers[full_path] = Retriever(rag_db=full_path, embedding_model=self.embedding_model)
        return retrievers

    def rag_database_selector(
        self, device: str, query: str
    ) -> Tuple[Optional[List[Any]], Optional[List[float]], Optional[List[Any]]]:
        """
        Select appropriate RAG database based on device and execute query.

        Args:
            device: Device name to match against database filenames.
            query: The query string to search for.

        Returns:
            Tuple of (chunk_list, similarity_list, metadata_list) or (None, None, None) if not found.
        """
        logger = logging.getLogger("uvicorn.error")
        
        # Default to 'oven' if device is None
        if device is None:
            device = "oven"
            logger.info(f"No device specified, defaulting to: {device}")
        
        for filename in os.listdir(self._database_path):
            if device.lower() in filename.lower() and filename.endswith(".pkl"):
                current_database = os.path.join(self._database_path, filename)
                if current_database in self.retrievers:
                    logger.debug(f"Using RAG database: {filename}")
                    return self.retrievers[current_database](query=query)
                break
        
        logger.warning(f"No RAG database found for device: {device}")
        return None, None, None

    async def start_async_loops(self):
        self.loops.append(asyncio.create_task(self.stt.async_model_loop(self.transcriptions_q)))
        self.loops.append(asyncio.create_task(self.tts.async_model_loop(self.tokens_q, self.audio_q)))


__all__ = ["SmartDeviceGatewayPipeline"]