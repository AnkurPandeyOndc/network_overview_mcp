"""Tests for RAG ingestion and search (mocks sentence-transformers + LanceDB)."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_st(n_dims: int = 384):
    """Return a SentenceTransformer mock that produces zero-vectors."""
    mock = MagicMock()
    mock.encode.side_effect = lambda texts, **kwargs: np.zeros(
        (len(texts), n_dims), dtype=np.float32
    )
    return mock


def _patch_st(return_value=None):
    """Context manager that patches SentenceTransformer at the package level."""
    rv = return_value if return_value is not None else _mock_st()
    return patch("sentence_transformers.SentenceTransformer", return_value=rv)


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_short_text_single_chunk(self):
        from ondc_mcp.rag.ingestion import chunk_text

        chunks = chunk_text("hello world", chunk_size=500, overlap=50)
        assert chunks == ["hello world"]

    def test_long_text_multiple_chunks(self):
        from ondc_mcp.rag.ingestion import chunk_text

        text = "a" * 1200
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 3
        assert all(len(c) <= 500 for c in chunks)

    def test_overlap_shared_characters(self):
        from ondc_mcp.rag.ingestion import chunk_text

        text = "a" * 110
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        # Second chunk starts at 80 (100-20)
        assert chunks[1] == text[80:180]

    def test_empty_text_returns_empty(self):
        from ondc_mcp.rag.ingestion import chunk_text

        assert chunk_text("") == []

    def test_exact_chunk_size_single_chunk(self):
        from ondc_mcp.rag.ingestion import chunk_text

        text = "x" * 500
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text


# ---------------------------------------------------------------------------
# load_documents
# ---------------------------------------------------------------------------

class TestLoadDocuments:
    def test_load_markdown_file(self):
        from ondc_mcp.rag.ingestion import load_documents

        with tempfile.TemporaryDirectory() as tmpdir:
            md_file = os.path.join(tmpdir, "test.md")
            with open(md_file, "w") as f:
                f.write("# Title\n\nHello world")

            docs = load_documents([md_file])
            assert len(docs) == 1
            assert docs[0]["source"] == md_file
            assert "Hello world" in docs[0]["content"]

    def test_load_txt_file(self):
        from ondc_mcp.rag.ingestion import load_documents

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_file = os.path.join(tmpdir, "test.txt")
            with open(txt_file, "w") as f:
                f.write("Plain text content")

            docs = load_documents([txt_file])
            assert len(docs) == 1
            assert "Plain text content" in docs[0]["content"]

    def test_missing_file_ignored(self):
        from ondc_mcp.rag.ingestion import load_documents

        docs = load_documents(["/nonexistent/path/file.md"])
        assert docs == []

    def test_empty_paths_list(self):
        from ondc_mcp.rag.ingestion import load_documents

        assert load_documents([]) == []

    def test_multiple_files(self):
        from ondc_mcp.rag.ingestion import load_documents

        with tempfile.TemporaryDirectory() as tmpdir:
            for name, content in [("a.md", "Doc A"), ("b.txt", "Doc B")]:
                path = os.path.join(tmpdir, name)
                with open(path, "w") as f:
                    f.write(content)

            docs = load_documents(
                [os.path.join(tmpdir, "a.md"), os.path.join(tmpdir, "b.txt")]
            )
            assert len(docs) == 2


# ---------------------------------------------------------------------------
# embed_chunks
# ---------------------------------------------------------------------------

class TestEmbedChunks:
    def test_returns_list_of_floats(self):
        from ondc_mcp.rag.ingestion import embed_chunks

        with _patch_st():
            result = embed_chunks(["hello"], model_name="all-MiniLM-L6-v2")
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert len(result[0]) == 384

    def test_batch_size_matches_input(self):
        from ondc_mcp.rag.ingestion import embed_chunks

        with _patch_st():
            result = embed_chunks(["chunk one", "chunk two", "chunk three"])
        assert len(result) == 3


# ---------------------------------------------------------------------------
# ingest_to_lancedb
# ---------------------------------------------------------------------------

class TestIngestToLancedb:
    def test_ingest_returns_chunk_count(self):
        from ondc_mcp.rag.ingestion import ingest_to_lancedb

        with tempfile.TemporaryDirectory() as tmpdir:
            with _patch_st():
                docs = [{"source": "doc.md", "content": "ONDC analytics content here."}]
                count = ingest_to_lancedb(docs, tmpdir)
            assert count >= 1

    def test_empty_docs_returns_zero(self):
        from ondc_mcp.rag.ingestion import ingest_to_lancedb

        with tempfile.TemporaryDirectory() as tmpdir:
            count = ingest_to_lancedb([], tmpdir)
            assert count == 0

    def test_ingest_creates_lancedb_table(self):
        import lancedb
        from ondc_mcp.rag.ingestion import ingest_to_lancedb

        with tempfile.TemporaryDirectory() as tmpdir:
            with _patch_st():
                docs = [{"source": "a.md", "content": "Some content"}]
                ingest_to_lancedb(docs, tmpdir)

            db = lancedb.connect(tmpdir)
            assert "documents" in db.table_names()

    def test_second_ingest_appends(self):
        import lancedb
        from ondc_mcp.rag.ingestion import ingest_to_lancedb

        with tempfile.TemporaryDirectory() as tmpdir:
            with _patch_st():
                docs1 = [{"source": "a.md", "content": "First document"}]
                docs2 = [{"source": "b.md", "content": "Second document"}]
                ingest_to_lancedb(docs1, tmpdir)
                ingest_to_lancedb(docs2, tmpdir)

            db = lancedb.connect(tmpdir)
            table = db.open_table("documents")
            assert table.count_rows() >= 2


# ---------------------------------------------------------------------------
# search_lancedb
# ---------------------------------------------------------------------------

class TestSearchLancedb:
    def test_empty_db_returns_empty_list(self):
        from ondc_mcp.rag.search import search_lancedb

        with tempfile.TemporaryDirectory() as tmpdir:
            with _patch_st():
                results = search_lancedb("test query", tmpdir)
            assert results == []

    def test_ingest_then_search_round_trip(self):
        from ondc_mcp.rag.ingestion import ingest_to_lancedb
        from ondc_mcp.rag.search import search_lancedb

        with tempfile.TemporaryDirectory() as tmpdir:
            # Identical vectors → distance = 0 → score near 1.0
            vec = np.array([[0.1] * 384], dtype=np.float32)
            model_mock = MagicMock()
            model_mock.encode.side_effect = lambda t, **kw: np.tile(vec, (len(t), 1))

            with _patch_st(return_value=model_mock):
                docs = [{"source": "test.md", "content": "ONDC analytics schema"}]
                ingest_to_lancedb(docs, tmpdir)
                results = search_lancedb("ONDC analytics", tmpdir, top_k=3)

            assert isinstance(results, list)
            assert len(results) >= 1
            assert "text" in results[0]
            assert "source" in results[0]
            assert "score" in results[0]
            assert results[0]["source"] == "test.md"

    def test_search_result_score_between_0_and_1(self):
        from ondc_mcp.rag.ingestion import ingest_to_lancedb
        from ondc_mcp.rag.search import search_lancedb

        with tempfile.TemporaryDirectory() as tmpdir:
            with _patch_st():
                docs = [{"source": "doc.md", "content": "Some content to index"}]
                ingest_to_lancedb(docs, tmpdir)
                results = search_lancedb("query", tmpdir, top_k=1)

            if results:
                assert 0.0 <= results[0]["score"] <= 1.0
