"""Tests for the SQLite-backed conversation memory store."""

import os
import tempfile

import pytest

from ondc_mcp.memory.conversation_store import ConversationStore


@pytest.fixture
async def store():
    """Yield an initialized ConversationStore backed by a temp SQLite file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_conversations.db")
        s = ConversationStore(db_path)
        await s.initialize()
        yield s
        await s.close()


class TestConversationStore:
    @pytest.mark.asyncio
    async def test_save_and_retrieve_message(self, store):
        await store.save_message("s1", "user", "Hello")
        history = await store.get_history("s1")
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_empty_history_for_unknown_session(self, store):
        history = await store.get_history("nonexistent_session")
        assert history == []

    @pytest.mark.asyncio
    async def test_history_is_chronological(self, store):
        await store.save_message("s1", "user", "First")
        await store.save_message("s1", "assistant", "Second")
        history = await store.get_history("s1")
        assert history[0]["content"] == "First"
        assert history[1]["content"] == "Second"

    @pytest.mark.asyncio
    async def test_limit_is_respected(self, store):
        for i in range(10):
            await store.save_message("s1", "user", f"Message {i}")
        history = await store.get_history("s1", limit=5)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_limit_returns_most_recent(self, store):
        for i in range(5):
            await store.save_message("s1", "user", f"Msg {i}")
        history = await store.get_history("s1", limit=3)
        # Should be Msg 2, Msg 3, Msg 4 (last 3 in order)
        assert history[0]["content"] == "Msg 2"
        assert history[-1]["content"] == "Msg 4"

    @pytest.mark.asyncio
    async def test_session_isolation(self, store):
        await store.save_message("session_a", "user", "A message")
        await store.save_message("session_b", "user", "B message")

        hist_a = await store.get_history("session_a")
        hist_b = await store.get_history("session_b")
        assert len(hist_a) == 1
        assert len(hist_b) == 1
        assert hist_a[0]["content"] == "A message"
        assert hist_b[0]["content"] == "B message"

    @pytest.mark.asyncio
    async def test_list_sessions(self, store):
        await store.save_message("alpha", "user", "hi")
        await store.save_message("beta", "assistant", "hello")
        sessions = await store.list_sessions()
        assert "alpha" in sessions
        assert "beta" in sessions

    @pytest.mark.asyncio
    async def test_all_roles_accepted(self, store):
        await store.save_message("s1", "user", "Question")
        await store.save_message("s1", "assistant", "Answer")
        await store.save_message("s1", "tool", "Tool result")
        history = await store.get_history("s1")
        roles = [h["role"] for h in history]
        assert roles == ["user", "assistant", "tool"]

    @pytest.mark.asyncio
    async def test_timestamp_present(self, store):
        await store.save_message("s1", "user", "Test")
        history = await store.get_history("s1")
        assert "timestamp" in history[0]
        assert history[0]["timestamp"]  # non-empty
