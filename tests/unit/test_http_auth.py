"""Test OAuth authentication for HTTP server."""

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from agent_kit.api.http.auth import _get_jwks, verify_oauth_token


@pytest.fixture
def mock_oidc_discovery() -> dict[str, Any]:
    """Mock OIDC discovery document."""
    return {
        "issuer": "https://accounts.google.com",
        "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
        "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_endpoint": "https://oauth2.googleapis.com/token",
    }


@pytest.fixture
def mock_jwks() -> dict[str, Any]:
    """Mock JWKS (JSON Web Key Set)."""
    return {"keys": [{"kty": "RSA", "use": "sig", "kid": "test-key-id", "n": "test-modulus", "e": "AQAB"}]}


@pytest.fixture
def mock_valid_token_claims() -> dict[str, Any]:
    """Mock valid token claims."""
    return {
        "iss": "https://accounts.google.com",
        "aud": "test-client-id",
        "email": "user@example.com",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }


@pytest.mark.asyncio
async def test_get_jwks_fetches_and_caches(mock_oidc_discovery: dict[str, Any], mock_jwks: dict[str, Any]) -> None:
    """JWKS are fetched from discovery and cached."""
    issuer = "https://accounts.google.com"

    with (
        patch("agent_kit.api.http.auth._fetch_oidc_discovery", return_value=mock_oidc_discovery) as mock_disco,
        patch("agent_kit.api.http.auth._fetch_jwks", return_value=mock_jwks) as mock_fetch_jwks,
    ):
        # First call should fetch
        jwks1 = await _get_jwks(issuer)
        assert jwks1 == mock_jwks
        mock_disco.assert_called_once()
        mock_fetch_jwks.assert_called_once()

        # Second call should use cache
        mock_disco.reset_mock()
        mock_fetch_jwks.reset_mock()
        jwks2 = await _get_jwks(issuer)
        assert jwks2 == mock_jwks
        mock_disco.assert_not_called()
        mock_fetch_jwks.assert_not_called()


@pytest.mark.asyncio
async def test_verify_oauth_token_success(
    mock_oidc_discovery: dict[str, Any], mock_jwks: dict[str, Any], mock_valid_token_claims: dict[str, Any]
) -> None:
    """Valid token is verified and returns email."""
    issuer = "https://accounts.google.com"
    client_id = "test-client-id"
    token = "mock-jwt-token"

    mock_claims = MagicMock()
    mock_claims.get.return_value = "user@example.com"
    mock_claims.validate.return_value = None

    with (
        patch("agent_kit.api.http.auth._get_jwks", return_value=mock_jwks),
        patch("agent_kit.api.http.auth.JsonWebToken.decode", return_value=mock_claims),
    ):
        email = await verify_oauth_token(token, issuer, client_id)
        assert email == "user@example.com"


@pytest.mark.asyncio
async def test_verify_oauth_token_missing_email(mock_jwks: dict[str, Any]) -> None:
    """Token without email claim raises 401."""
    issuer = "https://accounts.google.com"
    client_id = "test-client-id"
    token = "mock-jwt-token"

    mock_claims = MagicMock()
    mock_claims.get.return_value = None  # No email
    mock_claims.validate.return_value = None

    with (
        patch("agent_kit.api.http.auth._get_jwks", return_value=mock_jwks),
        patch("agent_kit.api.http.auth.JsonWebToken.decode", return_value=mock_claims),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await verify_oauth_token(token, issuer, client_id)
        assert exc_info.value.status_code == 401
        assert "email" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_verify_oauth_token_invalid_signature(mock_jwks: dict[str, Any]) -> None:
    """Token with invalid signature raises 401."""
    from authlib.jose.errors import BadSignatureError

    issuer = "https://accounts.google.com"
    client_id = "test-client-id"
    token = "invalid-jwt-token"

    with (
        patch("agent_kit.api.http.auth._get_jwks", return_value=mock_jwks),
        patch("agent_kit.api.http.auth.JsonWebToken.decode", side_effect=BadSignatureError("Invalid signature")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await verify_oauth_token(token, issuer, client_id)
        assert exc_info.value.status_code == 401


@pytest.fixture
def auth_test_app(test_registry: Any, test_session_store: Any) -> Any:
    """Test FastAPI app with auth enabled."""
    from agent_kit.api.http.rest import create_rest_routes
    from agent_kit.config.models import HttpConfig
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    # Create minimal FastAPI app
    app = FastAPI(title="Test API with Auth")

    # Store config in app state
    http_config = HttpConfig(
        enabled=True,
        auth_enabled=True,
        oauth_issuer="https://accounts.google.com",
        oauth_client_id="test-client-id",
        rest_api=True,
        mcp_http=False,
    )

    # Add CORS
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
    )

    # Store state
    app.state.session_store = test_session_store
    app.state.registry = test_registry
    app.state.http_config = http_config

    # Exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Any, exc: HTTPException) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # Create and include REST router
    rest_router = create_rest_routes(test_registry, test_session_store)
    app.include_router(rest_router)

    return app


@pytest.fixture
def auth_client(auth_test_app: Any) -> TestClient:
    """Test client with auth-enabled app."""
    return TestClient(auth_test_app, raise_server_exceptions=False)


def test_protected_endpoints_require_auth(auth_client: TestClient, auth_test_app: Any) -> None:
    """Protected endpoints return 401 without auth token."""
    # Mock get_config to return our test app's config
    with patch(
        "agent_kit.api.http.auth.get_config",
        return_value=MagicMock(interfaces=MagicMock(http=auth_test_app.state.http_config)),
    ):
        # Session endpoints
        response = auth_client.post("/api/v1/sessions")
        assert response.status_code == 401

        response = auth_client.get("/api/v1/sessions/test-id")
        assert response.status_code == 401

        response = auth_client.delete("/api/v1/sessions/test-id")
        assert response.status_code == 401

        # Agent execution endpoint
        response = auth_client.post("/api/v1/hello", json={"query": "test"})
        assert response.status_code == 401


def test_public_endpoints_work_without_auth(auth_client: TestClient) -> None:
    """Public endpoints work without auth token."""
    # Health endpoint
    response = auth_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Info endpoint
    response = auth_client.get("/api/v1/info")
    assert response.status_code == 200
    assert "agents" in response.json()


def test_protected_endpoints_work_with_valid_token(
    auth_client: TestClient, auth_test_app: Any, mock_jwks: dict[str, Any], mock_valid_token_claims: dict[str, Any]
) -> None:
    """Protected endpoints work with valid auth token."""
    token = "mock-valid-jwt-token"

    mock_claims = MagicMock()
    mock_claims.get.return_value = "user@example.com"
    mock_claims.validate.return_value = None

    with (
        patch(
            "agent_kit.api.http.auth.get_config",
            return_value=MagicMock(interfaces=MagicMock(http=auth_test_app.state.http_config)),
        ),
        patch("agent_kit.api.http.auth._get_jwks", return_value=mock_jwks),
        patch("agent_kit.api.http.auth.JsonWebToken.decode", return_value=mock_claims),
    ):
        # Create session with auth
        response = auth_client.post("/api/v1/sessions", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 201
        assert "session_id" in response.json()


def test_auth_disabled_allows_all_requests(test_registry: Any, test_session_store: Any) -> None:
    """When auth is disabled, all requests work without tokens."""
    from agent_kit.api.http.rest import create_rest_routes
    from agent_kit.config.models import HttpConfig
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    http_config = HttpConfig(enabled=True, auth_enabled=False, rest_api=True, mcp_http=False)

    # Create minimal FastAPI app
    app = FastAPI(title="Test API No Auth")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
    )
    app.state.session_store = test_session_store
    app.state.registry = test_registry
    app.state.http_config = http_config

    rest_router = create_rest_routes(test_registry, test_session_store)
    app.include_router(rest_router)

    client = TestClient(app)

    # Mock get_config to return config with auth disabled
    with patch("agent_kit.api.http.auth.get_config", return_value=MagicMock(interfaces=MagicMock(http=http_config))):
        # All endpoints should work without token
        response = client.post("/api/v1/sessions")
        assert response.status_code == 201

        response = client.get("/api/v1/health")
        assert response.status_code == 200


def test_invalid_bearer_token_format(auth_client: TestClient, auth_test_app: Any) -> None:
    """Invalid bearer token format returns 401."""
    with patch(
        "agent_kit.api.http.auth.get_config",
        return_value=MagicMock(interfaces=MagicMock(http=auth_test_app.state.http_config)),
    ):
        # Missing 'Bearer ' prefix
        response = auth_client.post("/api/v1/sessions", headers={"Authorization": "invalid-token"})
        assert response.status_code == 401

        # Empty authorization header
        response = auth_client.post("/api/v1/sessions", headers={"Authorization": ""})
        assert response.status_code == 401
