# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,protected-access
"""Tests for MemosMemoryManager."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level mock for MemOSClient
# ---------------------------------------------------------------------------
_MOD = "qwenpaw.agents.memory.memos_memory_manager"


# ---------------------------------------------------------------------------
# TestMemosMemoryManagerTools
# ---------------------------------------------------------------------------


class TestMemosMemoryManagerTools:
    """P0: list_memory_tools() returns correct tools."""

    def test_list_memory_tools_returns_only_search(self):
        """Test only memory_search tool is exposed (like ReMeLight)."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager

        with patch(f"{_MOD}.MemOSClient"):
            mgr = MemosMemoryManager(
                working_dir="/tmp/test",
                agent_id="test-agent",
            )

        tools = mgr.list_memory_tools()

        assert len(tools) == 1
        assert tools[0].__name__ == "memos_memory_search"


# ---------------------------------------------------------------------------
# TestMemosMemoryManagerGetPrompt
# ---------------------------------------------------------------------------


class TestMemosMemoryManagerGetPrompt:
    """P1: get_memory_prompt() method."""

    def test_get_memory_prompt_zh(self):
        """Test Chinese prompt."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager

        with patch(f"{_MOD}.MemOSClient"):
            mgr = MemosMemoryManager(
                working_dir="/tmp/test",
                agent_id="test-agent",
            )

        prompt = mgr.get_memory_prompt(language="zh")
        assert "记忆" in prompt

    def test_get_memory_prompt_en(self):
        """Test English prompt."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager

        with patch(f"{_MOD}.MemOSClient"):
            mgr = MemosMemoryManager(
                working_dir="/tmp/test",
                agent_id="test-agent",
            )

        prompt = mgr.get_memory_prompt(language="en")
        assert "memory" in prompt.lower()


# ---------------------------------------------------------------------------
# TestMemosMemoryManagerClose
# ---------------------------------------------------------------------------


class TestMemosMemoryManagerClose:
    """P0: close() method."""

    async def test_close_cleans_up_client(self):
        """Test close cleans up client resources."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager

        mock_client = MagicMock()
        mock_client.__aexit__ = AsyncMock()

        with patch(f"{_MOD}.MemOSClient"):
            mgr = MemosMemoryManager(
                working_dir="/tmp/test",
                agent_id="test-agent",
            )
            mgr._client = mock_client

        result = await mgr.close()

        assert result is True
        assert mgr._client is None
        mock_client.__aexit__.assert_called_once()


# ---------------------------------------------------------------------------
# TestMemosMemoryManagerConfig
# ---------------------------------------------------------------------------


class TestMemosMemoryManagerConfig:
    """Test config loading."""

    def test_default_config(self):
        """Test manager gets default config when not found."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager
        from qwenpaw.config.config import MemosMemoryConfig

        with patch(f"{_MOD}.load_agent_config", side_effect=Exception("not found")):
            with patch(f"{_MOD}.MemOSClient"):
                mgr = MemosMemoryManager(
                    working_dir="/tmp/test",
                    agent_id="test-agent",
                )
                # Config should be loaded lazily
                # Just verify it doesn't crash
                assert mgr.agent_id == "test-agent"


# ---------------------------------------------------------------------------
# TestMemosMemoryManagerMemorySearchTool
# ---------------------------------------------------------------------------


class TestMemosMemoryManagerSearchTool:
    """Test the search tool signature."""

    async def test_memory_search_is_async(self):
        """Test memos_memory_search is an async method."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager
        import inspect

        with patch(f"{_MOD}.MemOSClient"):
            mgr = MemosMemoryManager(
                working_dir="/tmp/test",
                agent_id="test-agent",
            )

        # Check it's a coroutine function
        assert inspect.iscoroutinefunction(mgr.memos_memory_search)

    async def test_memory_search_signature(self):
        """Test memos_memory_search has correct signature."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager
        import inspect

        with patch(f"{_MOD}.MemOSClient"):
            mgr = MemosMemoryManager(
                working_dir="/tmp/test",
                agent_id="test-agent",
            )

        sig = inspect.signature(mgr.memos_memory_search)
        params = list(sig.parameters.keys())

        # Should have query, max_results, min_score
        assert "query" in params
        assert "max_results" in params
        assert "min_score" in params