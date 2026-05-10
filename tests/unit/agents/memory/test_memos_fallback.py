# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,protected-access
"""Tests for MemOS fallback integration."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level mocks
# ---------------------------------------------------------------------------
_MOCK_MODULES = [
    "aiohttp",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

_MOD = "qwenpaw.agents.memory.memos_memory_manager"
_MOD_BASE = "qwenpaw.agents.memory.base_memory_manager"


# ---------------------------------------------------------------------------
# TestMemosFallbackIntegration
# ---------------------------------------------------------------------------


class TestMemosFallbackIntegration:
    """Integration tests for MemOS → ReMeLight fallback."""

    def test_registry_has_both_backends(self):
        """Test that both remelight and memos are registered."""
        from qwenpaw.agents.memory.base_memory_manager import memory_registry

        registered = memory_registry.list_registered()
        assert "remelight" in registered
        assert "memos" in registered

    def test_get_memory_manager_backend_returns_memos(self):
        """Test factory returns MemosMemoryManager for 'memos' backend."""
        from qwenpaw.agents.memory.base_memory_manager import (
            get_memory_manager_backend,
        )

        cls = get_memory_manager_backend("memos")
        assert cls.__name__ == "MemosMemoryManager"

    def test_get_memory_manager_backend_returns_first_registered_for_unknown(self):
        """Test factory falls back to first registered backend for unknown."""
        from qwenpaw.agents.memory.base_memory_manager import (
            get_memory_manager_backend,
        )

        cls = get_memory_manager_backend("unknown-backend")
        # Falls back to first registered, which is 'memos'
        assert cls.__name__ == "MemosMemoryManager"

    @pytest.mark.asyncio
    async def test_memos_start_raises_connection_error_on_failure(self):
        """Test that MemosMemoryManager.start() raises ConnectionError on failure."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager
        from qwenpaw.agents.memory.memos_client import MemOSClient

        mock_client = MagicMock(spec=MemOSClient)
        mock_client.health_check = AsyncMock(return_value=False)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(f"{_MOD}.MemOSClient", return_value=mock_client):
            mgr = MemosMemoryManager(
                working_dir="/tmp/test",
                agent_id="test-agent",
            )

            # Mock config
            config = MagicMock()
            config.memos_url = "http://localhost:8000"
            config.api_key = "test-key"
            config.user_id = "test-user"
            config.cube_name = "test-cube"
            config.create_cube_if_not_exists = True
            config.top_k = 5
            config.search_mode = "fast"
            config.relativity_threshold = 0.45
            config.fallback_to_reme_light = True
            config.timeout_seconds = 30
            mgr._config = config

            # Should raise ConnectionError for fallback
            with pytest.raises(ConnectionError):
                await mgr.start()

    @pytest.mark.asyncio
    async def test_memos_cube_not_found_with_create_flag(self):
        """Test that missing cube with create_cube_if_not_exists=True continues with warning."""
        from qwenpaw.agents.memory.memos_memory_manager import MemosMemoryManager
        from qwenpaw.agents.memory.memos_client import MemOSClient

        mock_client = MagicMock(spec=MemOSClient)
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.exist_cube = AsyncMock(return_value=False)  # Cube doesn't exist
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(f"{_MOD}.MemOSClient", return_value=mock_client):
            with patch(f"{_MOD}.load_agent_config") as mock_load:
                mock_cfg = MagicMock()
                mock_cfg.running.memos_memory_config.memos_url = "http://localhost:8000"
                mock_cfg.running.memos_memory_config.api_key = "test"
                mock_cfg.running.memos_memory_config.user_id = "user1"
                mock_cfg.running.memos_memory_config.cube_name = "test-cube"
                mock_cfg.running.memos_memory_config.create_cube_if_not_exists = True
                mock_cfg.running.memos_memory_config.top_k = 5
                mock_cfg.running.memos_memory_config.search_mode = "fast"
                mock_cfg.running.memos_memory_config.relativity_threshold = 0.45
                mock_cfg.running.memos_memory_config.fallback_to_reme_light = True
                mock_cfg.running.memos_memory_config.timeout_seconds = 30
                mock_load.return_value = mock_cfg

                mgr = MemosMemoryManager(
                    working_dir="/tmp/test",
                    agent_id="test-agent",
                )

                # With create_cube_if_not_exists=True, should continue with warning
                await mgr.start()

                # Should have set cube_id even though cube doesn't exist
                assert mgr._cube_id == "test-cube"


# ---------------------------------------------------------------------------
# TestMemosConfigValidation
# ---------------------------------------------------------------------------


class TestMemosConfigValidation:
    """Tests for MemosMemoryConfig validation."""

    def test_config_default_values(self):
        """Test config has correct default values."""
        from qwenpaw.config.config import MemosMemoryConfig

        config = MemosMemoryConfig()

        assert config.memos_url == "http://memos-api:8000"
        assert config.api_key == ""
        assert config.user_id == "qwenpaw"
        assert config.cube_name == "default"
        assert config.create_cube_if_not_exists is True
        assert config.top_k == 5
        assert config.search_mode == "fast"
        assert config.relativity_threshold == 0.45
        assert config.fallback_to_reme_light is True
        assert config.timeout_seconds == 30

    def test_config_search_mode_validation(self):
        """Test search_mode only accepts valid values."""
        from qwenpaw.config.config import MemosMemoryConfig
        from pydantic import ValidationError

        # Valid modes
        for mode in ["fast", "fine", "mixture"]:
            config = MemosMemoryConfig(search_mode=mode)
            assert config.search_mode == mode

        # Invalid mode should raise
        with pytest.raises(ValidationError):
            MemosMemoryConfig(search_mode="invalid")

    def test_config_bounds_validation(self):
        """Test numeric fields are bounded."""
        from qwenpaw.config.config import MemosMemoryConfig
        from pydantic import ValidationError

        # top_k bounds
        with pytest.raises(ValidationError):
            MemosMemoryConfig(top_k=0)  # Too low

        with pytest.raises(ValidationError):
            MemosMemoryConfig(top_k=100)  # Too high

        # relativity_threshold bounds
        with pytest.raises(ValidationError):
            MemosMemoryConfig(relativity_threshold=-0.1)

        with pytest.raises(ValidationError):
            MemosMemoryConfig(relativity_threshold=1.5)

        # timeout_seconds bounds
        with pytest.raises(ValidationError):
            MemosMemoryConfig(timeout_seconds=1)  # Too low

        with pytest.raises(ValidationError):
            MemosMemoryConfig(timeout_seconds=200)  # Too high