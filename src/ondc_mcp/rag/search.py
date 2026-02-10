"""Vector search skeleton for RAG pipeline.

Ready to wire up with FAISS + sentence-transformers when needed.
"""

from typing import Any


def search_faiss(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Embed query and search FAISS index for similar document chunks.

    Skeleton — requires faiss-cpu and sentence-transformers.

    Args:
        query: Natural language search query
        top_k: Number of results to return

    Returns:
        List of matching document chunks with scores
    """
    raise NotImplementedError(
        "FAISS search not yet configured. "
        "Install RAG dependencies: poetry install --with rag"
    )
