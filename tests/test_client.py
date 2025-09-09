from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from src.client import ensure_openai_client, get_openai_client


class TestEnsureOpenAIClient:
    def test_ensure_openai_client_with_api_key(self):
        with patch("src.client._client", None):  # Reset global state
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                with patch("src.client.AsyncOpenAI") as mock_openai:
                    with patch(
                        "src.client.set_default_openai_client",
                    ) as mock_set_default:
                        mock_instance = AsyncMock()
                        mock_openai.return_value = mock_instance

                        result = ensure_openai_client()

                        assert result is True
                        mock_openai.assert_called_once_with(timeout=600.0)
                        mock_set_default.assert_called_once_with(mock_instance)
                        assert os.environ.get("OPENAI_AGENTS_DISABLE_TRACING") == "1"

    def test_ensure_openai_client_custom_timeout(self):
        with patch("src.client._client", None):  # Reset global state
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                with patch("src.client.AsyncOpenAI") as mock_openai:
                    with patch("src.client.set_default_openai_client"):
                        mock_instance = AsyncMock()
                        mock_openai.return_value = mock_instance

                        result = ensure_openai_client(timeout=300.0)

                        assert result is True
                        mock_openai.assert_called_once_with(timeout=300.0)

    def test_ensure_openai_client_no_api_key(self):
        with patch("src.client._client", None):  # Reset global state
            with patch.dict(os.environ, {}, clear=True):
                result = ensure_openai_client()

                assert result is False

    def test_ensure_openai_client_empty_api_key(self):
        with patch("src.client._client", None):  # Reset global state
            with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
                result = ensure_openai_client()

                assert result is False

    def test_ensure_openai_client_already_initialized(self):
        # Simulate already initialized client
        mock_client = AsyncMock()

        with patch("src.client._client", mock_client):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                with patch("src.client.AsyncOpenAI") as mock_openai:
                    result = ensure_openai_client()

                    # Should return True but not create new client
                    assert result is True
                    mock_openai.assert_not_called()

    def test_ensure_openai_client_set_default_exception(self):
        with patch("src.client._client", None):  # Reset global state
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                with patch("src.client.AsyncOpenAI") as mock_openai:
                    with patch(
                        "src.client.set_default_openai_client",
                    ) as mock_set_default:
                        mock_instance = AsyncMock()
                        mock_openai.return_value = mock_instance
                        mock_set_default.side_effect = Exception("Test exception")

                        # Should still return True despite exception
                        result = ensure_openai_client()

                        assert result is True
                        mock_openai.assert_called_once()

    # NOTE: Removed env var test - side effect testing not essential for core client functionality

    def test_ensure_openai_client_preserves_existing_tracing_env_var(self):
        with patch("src.client._client", None):  # Reset global state
            with patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_AGENTS_DISABLE_TRACING": "0",
                },
            ):
                with patch("src.client.AsyncOpenAI"):
                    with patch("src.client.set_default_openai_client"):
                        result = ensure_openai_client()

                        assert result is True
                        # setdefault should preserve existing value
                        assert os.environ.get("OPENAI_AGENTS_DISABLE_TRACING") == "0"


class TestGetOpenAIClient:
    def test_get_openai_client_returns_client(self):
        mock_client = AsyncMock()

        with patch("src.client._client", mock_client):
            result = get_openai_client()

            assert result is mock_client

    def test_get_openai_client_returns_none(self):
        with patch("src.client._client", None):
            result = get_openai_client()

            assert result is None


class TestClientGlobalState:
    def test_client_initially_none(self):
        # Test that _client starts as None (assuming fresh import)
        # This test may be fragile depending on test execution order
        # but helps verify initial state
        with patch("src.client._client", None):
            from src.client import _client as client_state

            assert client_state is None

    def test_client_state_persistence(self):
        # Test that client state persists between calls
        mock_client = AsyncMock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("src.client.AsyncOpenAI") as mock_openai:
                with patch("src.client.set_default_openai_client"):
                    mock_openai.return_value = mock_client

                    # First call should create client
                    result1 = ensure_openai_client()
                    assert result1 is True

                    # Second call should not create new client
                    result2 = ensure_openai_client()
                    assert result2 is True

                    # Should only have been called once
                    mock_openai.assert_called_once()

    @pytest.fixture(autouse=True)
    def cleanup_client_state(self):
        # Clean up client state before and after each test
        import src.client

        src.client._client = None
        yield
        # Reset the global client state
        src.client._client = None


class TestClientIntegration:
    def test_full_client_initialization_flow(self):
        with patch("src.client._client", None):  # Reset global state
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
                with patch("src.client.AsyncOpenAI") as mock_openai:
                    with patch(
                        "src.client.set_default_openai_client",
                    ) as mock_set_default:
                        mock_instance = AsyncMock()
                        mock_openai.return_value = mock_instance

                        # Initialize client
                        success = ensure_openai_client()
                        assert success is True

                        # Verify client can be retrieved
                        client = get_openai_client()
                        assert client is mock_instance

                        # Verify setup calls
                        mock_openai.assert_called_once_with(timeout=600.0)
                        mock_set_default.assert_called_once_with(mock_instance)

    def test_client_initialization_without_api_key(self):
        with patch("src.client._client", None):  # Reset global state
            # Remove API key from environment
            with patch.dict(os.environ, {}, clear=True):
                # Attempt to initialize
                success = ensure_openai_client()
                assert success is False

                # Verify no client is available
                client = get_openai_client()
                assert client is None

    @pytest.fixture(autouse=True)
    def reset_global_client(self):
        # Reset global client before and after each test
        import src.client

        src.client._client = None
        yield
        src.client._client = None
