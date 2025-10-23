# OAuth/OIDC authentication for HTTP server
# Generic implementation supporting any OAuth provider via OIDC discovery

import logging
import time
from typing import Any

import httpx
from authlib.jose import JsonWebKey, JsonWebToken, JWTClaims
from authlib.jose.errors import JoseError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agent_kit.config import get_config

logger = logging.getLogger(__name__)

# JWKS cache: {issuer: (jwks_data, expiry_time)}
_jwks_cache: dict[str, tuple[dict[str, Any], float]] = {}
JWKS_CACHE_TTL = 3600  # 1 hour


security = HTTPBearer(auto_error=False)


async def _fetch_oidc_discovery(issuer: str) -> dict[str, Any]:
    """Fetch OIDC discovery document from issuer."""
    discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(discovery_url, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch OIDC discovery from {discovery_url}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch OAuth provider configuration"
            )


async def _fetch_jwks(jwks_uri: str) -> dict[str, Any]:
    """Fetch JWKS (JSON Web Key Set) from provider."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(jwks_uri, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch JWKS from {jwks_uri}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to fetch OAuth signing keys"
            )


async def _get_jwks(issuer: str) -> dict[str, Any]:
    """Get JWKS for issuer, using cache if available."""
    now = time.time()

    # Check cache
    if issuer in _jwks_cache:
        jwks_data, expiry = _jwks_cache[issuer]
        if now < expiry:
            return jwks_data

    # Fetch fresh JWKS
    discovery = await _fetch_oidc_discovery(issuer)
    jwks_uri = discovery.get("jwks_uri")
    if not jwks_uri:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="OAuth provider missing jwks_uri")

    jwks_data = await _fetch_jwks(jwks_uri)

    # Cache for 1 hour
    _jwks_cache[issuer] = (jwks_data, now + JWKS_CACHE_TTL)

    return jwks_data


async def verify_oauth_token(token: str, issuer: str, client_id: str) -> str:
    """Verify OAuth/OIDC token and return user email."""
    try:
        # Get JWKS for issuer
        jwks_data = await _get_jwks(issuer)

        # Verify token signature and claims
        jwt = JsonWebToken(["RS256"])
        claims: JWTClaims = jwt.decode(  # type: ignore[reportUnknownMemberType]
            token,
            key=JsonWebKey.import_key_set(jwks_data),
            claims_options={
                "iss": {"essential": True, "value": issuer},
                "aud": {"essential": True, "value": client_id},
            },
        )

        # Validate claims
        claims.validate()  # type: ignore[reportUnknownMemberType]

        # Extract email
        email = claims.get("email")
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing email claim")

        return email

    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except JoseError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    except Exception as e:
        logger.exception(f"Unexpected error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication verification failed"
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> str:
    """FastAPI dependency to extract and verify OAuth token."""
    config = get_config()
    http_config = config.interfaces.http

    # Skip auth if disabled
    if not http_config.auth_enabled:
        return "anonymous"

    # Check for missing credentials
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify required config
    if not http_config.oauth_issuer or not http_config.oauth_client_id:
        logger.error("OAuth authentication enabled but oauth_issuer or oauth_client_id not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Authentication not properly configured"
        )

    # Verify token
    token = credentials.credentials
    return await verify_oauth_token(token, http_config.oauth_issuer, http_config.oauth_client_id)
