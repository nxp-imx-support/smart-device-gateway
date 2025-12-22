# Copyright 2025-2026 NXP
# NXP Proprietary. This software is owned or controlled by NXP and may only be
# used strictly in accordance with the applicable license terms.  By expressly
# accepting such terms or by downloading, installing, activating and/or
# otherwise using the software, you are agreeing that you have read, and that
# you agree to comply with and are bound by, such license terms.  If you do
# not agree to be bound by the applicable license terms, then you may not
# retain, install, activate or otherwise use the software.

import os
import torch
import logging
from tqdm import tqdm
from ..config import Config as RAGConfig
from ..utils import load_json, save_pkl
from ..models.embedding_models.embedding_models import EmbeddingModel


def generate_embeddings_for_device(
    json_file_path: str,
    embedding_model: EmbeddingModel,
    config: RAGConfig
) -> str:
    """
    Generate embeddings from a single JSON chunk file and save as PKL in the same directory.
    
    Args:
        json_file_path: Full path to the JSON chunks file
        embedding_model: Pre-initialized EmbeddingModel instance
        config: RAG configuration
        
    Returns:
        Path to the generated PKL file
    """
    logger = logging.getLogger("uvicorn.error")
    
    if not os.path.isfile(json_file_path):
        error_text = f"JSON file not found: {json_file_path}"
        logger.error(error_text)
        raise FileNotFoundError(error_text)
    
    # Load chunks from JSON
    chunks = load_json(json_file_path)
    
    # Prepare data structure
    data = {
        "embedding_model": embedding_model.embedding_model_version,
        "database_description": config.database_description,
        "database_generator_files": [os.path.basename(json_file_path)]
    }
    
    index = 0
    file_name = os.path.basename(json_file_path)
    
    # Generate embeddings from documentation
    for id, item in tqdm(chunks.items(), desc=f"Generating embeddings for {file_name}", ascii=True):
        data[index] = {}
        
        if "chunks" not in item:
            error_text = f"Every item must contain at least a chunks attribute.\n {id}: {item}"
            logger.error(error_text)
            raise ValueError(error_text)
        
        chunks = item.pop("chunks")
        
        if "complete_chunks" in item:
            embeddings = embedding_model.encode(item["complete_chunks"])
            embeddings = torch.tile(embeddings, (len(chunks), 1))
            reranking_embedding = embedding_model.encode(item["complete_chunks"].split(';')[0])  # Question only
        else:
            embeddings = embedding_model.encode(chunks)
            reranking_embedding = torch.mean(embeddings, dim=0)
        
        data[index]["embeddings"] = embeddings
        data[index]["reranking_embedding"] = reranking_embedding
        data[index]["chunks"] = chunks
        data[index]["chunked_file_id"] = id
        
        for key, value in item.items():
            data[index][key] = value
        
        if "source" not in data[index]:
            data[index]["source"] = file_name
        
        index += 1
    
    # Save PKL with same name as JSON in the same directory
    base_name = os.path.splitext(json_file_path)[0]
    pkl_path = f"{base_name}.pkl"
    
    save_pkl(destination_path=pkl_path, data=data)
    logger.debug(f"Successfully saved {base_name}.pkl")
    
    return pkl_path


def generate_all_embeddings(database_dir: str, embedding_model: EmbeddingModel) -> list[str]:
    """
    Generate embeddings for all JSON files in the database directory.
    
    Args:
        database_dir: Path to the database directory containing JSON files
        embedding_model: Pre-initialized EmbeddingModel instance
        
    Returns:
        List of paths to generated PKL files
    """
    logger = logging.getLogger("uvicorn.error")
    config = RAGConfig()
    pkl_files = []
    
    if not os.path.isdir(database_dir):
        logger.warning(f"Database directory not found: {database_dir}")
        return pkl_files
    
    # Find all JSON files in database directory
    json_files = [f for f in os.listdir(database_dir) if f.endswith('.json')]
    
    if not json_files:
        logger.warning(f"No JSON files found in {database_dir}")
        return pkl_files
        
    for json_file in json_files:
        json_path = os.path.join(database_dir, json_file)
        pkl_path_base = os.path.splitext(json_path)[0]
        pkl_path = f"{pkl_path_base}.pkl"
        
        # Skip if PKL already exists
        if os.path.exists(pkl_path):
            logger.warning(f"Database already exists, skipping: {pkl_path}")
            pkl_files.append(pkl_path)
            continue
        
        try:
            pkl_path = generate_embeddings_for_device(
                json_file_path=json_path,
                embedding_model=embedding_model,
                config=config
            )
            pkl_files.append(pkl_path)
        except Exception as e:
            logger.error(f"Failed to generate embeddings for {json_file}: {e}")
    
    return pkl_files
