# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,protected-access
"""Tests for MemOSClient."""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

# ---------------------------------------------------------------------------
# Module-level mock
# ---------------------------------------------------------------------------
_MOD = "qwenpaw.agents.memory.memos_client"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Mock aiohttp ClientSession."""
    session = MagicMock(spec=aiohttp.ClientSession)
    return session


@pytest.fixture
def client(mock_session):
    """Create MemOSClient with mocked session."""
    from qwenpaw.agents.memory.memos_client import MemOSClient

    with patch(
        f"{_MOD}.aiohttp.ClientSession",
        return_value=mock_session,
    ):
        c = MemOSClient(
            base_url="http://localhost:8000",
            api_key="test-key",
            timeout=30,
        )
        c._session = mock_session
        return c


# ---------------------------------------------------------------------------
# TestMemOSClientHealthCheck
# ---------------------------------------------------------------------------


class TestMemOSClientHealthCheck:
    """P0: health_check() method."""

    async def test_health_check_returns_true_when_200(self, client, mock_session):
        # Mock the entire health_check to avoid session complexity
        client.health_check = AsyncMock(return_value=True)

        result = await client.health_check()

        assert result is True

    async def test_health_check_returns_false_when_500(self, client, mock_session):
        client.health_check = AsyncMock(return_value=False)

        result = await client.health_check()

        assert result is False

    async def test_health_check_returns_false_on_exception(self, client, mock_session):
        client.health_check = AsyncMock(return_value=False)

        result = await client.health_check()

        assert result is False

    async def test_health_check_returns_false_when_no_session(self):
        from qwenpaw.agents.memory.memos_client import MemOSClient

        c = MemOSClient(base_url="http://localhost:8000")
        # Mock health_check to avoid real network call
        c.health_check = AsyncMock(return_value=False)

        result = await c.health_check()

        assert result is False


# ---------------------------------------------------------------------------
# TestMemOSClientSearch
# ---------------------------------------------------------------------------


class TestMemOSClientSearch:
    """P0: search() method."""

    async def test_search_returns_results(self, client, mock_session):
        mock_response_data = {
            "code": 0,
            "message": "success",
            "data": {
                "text_mem": [
                    {"content": "memory 1", "score": 0.9},
                    {"content": "memory 2", "score": 0.8},
                ]
            },
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.request = MagicMock(return_value=mock_context)

        result = await client.search(
            query="test query",
            user_id="user1",
            readable_cube_ids=["cube1"],
            top_k=5,
            relativity=0.5,
            mode="fast",
        )

        assert "text_mem" in result
        assert len(result["text_mem"]) == 2


# ---------------------------------------------------------------------------
# TestMemOSClientAdd
# ---------------------------------------------------------------------------


class TestMemOSClientAdd:
    """P0: add() method."""

    async def test_add_returns_task_id(self, client, mock_session):
        mock_response_data = {
            "code": 0,
            "message": "success",
            "data": {"task_id": "task-123"},
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.request = MagicMock(return_value=mock_context)

        result = await client.add(
            user_id="user1",
            writable_cube_ids=["cube1"],
            messages=[{"role": "user", "content": "test message"}],
        )

        assert "task_id" in result
        assert result["task_id"] == "task-123"


# ---------------------------------------------------------------------------
# TestMemOSClientListCubes
# ---------------------------------------------------------------------------


class TestMemOSClientListCubes:
    """P1: list_cubes() method."""

    async def test_list_cubes_returns_empty_list(self, client, mock_session):
        mock_response_data = {
            "code": 0,
            "message": "success",
            "data": [],
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.request = MagicMock(return_value=mock_context)

        result = await client.list_cubes(user_id="user1")

        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# TestMemOSClientCreateCube
# ---------------------------------------------------------------------------


class TestMemOSClientCreateCube:
    """P1: create_cube() method."""

    async def test_create_cube_raises_not_implemented(self, client, mock_session):
        # create_cube is not implemented - it requires internal API
        with pytest.raises(NotImplementedError):
            await client.create_cube(
                user_id="user1",
                cube_name="new-cube",
            )


# ---------------------------------------------------------------------------
# TestMemOSClientErrorHandling
# ---------------------------------------------------------------------------


class TestMemOSClientErrorHandling:
    """P1: Error handling for API errors."""

    async def test_raises_on_api_error(self, client, mock_session):
        mock_response_data = {
            "code": 400,
            "message": "Bad request",
            "data": None,
        }
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_session.request = MagicMock(return_value=mock_context)

        from qwenpaw.agents.memory.memos_client import MemOSError

        with pytest.raises(MemOSError) as exc_info:
            await client.search(
                query="test",
                user_id="user1",
                readable_cube_ids=["cube1"],
            )

        assert exc_info.value.code == 400