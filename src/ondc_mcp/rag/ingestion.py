"""Document ingestion skeleton for RAG pipeline.

Ready to wire up with FAISS + sentence-transformers when needed.
"""

from pathlib import Path
from typing import Any


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def load_documents(docs_dir: str) -> list[dict[str, Any]]:
    """Load markdown/text documents from a directory.

    Returns:
        List of dicts with 'source', 'content', and 'chunks' keys
    """
    docs = []
    docs_path = Path(docs_dir)

    if not docs_path.exists():
        return docs

    for filepath in docs_path.glob("**/*.md"):
        content = filepath.read_text()
        chunks = chunk_text(content)
        docs.append({
            "source": str(filepath),
            "content": content,
            "chunks": chunks,
        })

    for filepath in docs_path.glob("**/*.txt"):
        content = filepath.read_text()
        chunks = chunk_text(content)
        docs.append({
            "source": str(filepath),
            "content": content,
            "chunks": chunks,
        })

    return docs


def ingest_to_faiss(docs: list[dict[str, Any]]) -> None:
    """Embed document chunks and store in FAISS index.

    Skeleton — requires faiss-cpu and sentence-transformers.
    """
    raise NotImplementedError(
        "FAISS ingestion not yet configured. "
        "Install RAG dependencies: poetry install --with rag"
    )
