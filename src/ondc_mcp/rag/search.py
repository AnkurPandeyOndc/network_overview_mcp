"""Vector search for schema RAG pipeline."""

import os
import json
import faiss
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "rag" / "docs"
INDEX_PATH = DOCS_DIR / "schema_index.faiss"
METADATA_PATH = DOCS_DIR / "schema_metadata.json"

_index = None
_metadata = None
_model = None

def _load_resources():
    global _index, _metadata, _model
    if _index is None:
        if not INDEX_PATH.exists() or not METADATA_PATH.exists():
            raise FileNotFoundError("FAISS index or metadata not found. Run import_docs.py first.")
        
        logger.info("Loading FAISS index and model...")
        _index = faiss.read_index(str(INDEX_PATH))
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            _metadata = json.load(f)
        _model = SentenceTransformer('all-MiniLM-L6-v2')

def search_schema(query: str, top_k: int = 5) -> list[dict]:
    """Embed query and search FAISS index for similar tables/views.

    Args:
        query: Natural language search query
        top_k: Number of results to return

    Returns:
        List of matching table metadata (schema, table_name, content)
    """
    _load_resources()
    
    query_vector = _model.encode([query], convert_to_numpy=True)
    distances, indices = _index.search(query_vector, top_k)
    
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx != -1 and idx < len(_metadata):
            match = _metadata[idx].copy()
            match["distance"] = float(dist)
            results.append(match)
            
    return results
