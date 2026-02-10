"""search_docs — Skeleton for RAG-based document search."""

from typing import Any


async def search_docs(query: str) -> dict[str, Any]:
    """Search indexed business documents for relevant context.

    This is a skeleton — no documents are indexed yet. The RAG pipeline
    (ingestion + FAISS search) is ready to be wired up.

    Args:
        query: Natural language search query

    Returns:
        Dict with search results (currently empty)
    """
    return {
        "status": "success",
        "message": "No documents indexed yet. RAG pipeline is ready for configuration.",
        "results": [],
        "query": query,
    }
