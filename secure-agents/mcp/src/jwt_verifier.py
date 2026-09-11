import logging
import os
from typing import Dict, Optional
import jwt
from contextvars import ContextVar

from fastmcp.server.auth.providers.jwt import JWTVerifier
from config import get_config

# Configure logging
# Configure logging level from .env (default to INFO)
LOG_LEVEL = get_config().log_level.upper()
# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.getLevelNamesMapping().get(LOG_LEVEL))

# Context variable to store the JWT token across SSE requests
_jwt_token_context: ContextVar[Optional[str]] = ContextVar("jwt_token", default=None)

# Global token storage for SSE sessions (keyed by user 'sub' claim)
# This persists across async contexts and allows token retrieval during tool calls
_global_token_storage: Dict[str, str] = {}


class LoggingJWTVerifier(JWTVerifier):
    """Extended JWTVerifier with detailed request logging and token caching for SSE."""

    def __init__(self, *args, **kwargs):
        """Initialize with logging."""
        super().__init__(*args, **kwargs)
        logger.info("=== LoggingJWTVerifier initialized ===")
        logger.info(f"JWKS URI: {kwargs.get('jwks_uri', 'N/A')}")
        logger.info(f"Issuer: {kwargs.get('issuer', 'N/A')}")
        logger.info(f"Audience: {kwargs.get('audience', 'N/A')}")

    async def __call__(
        self, headers: Dict[str, str], body: Optional[bytes] = None
    ) -> Optional[Dict]:
        """Verify JWT token with detailed logging of incoming request."""
        # Log all incoming headers (mask sensitive data)
        logger.info("=== Incoming MCP Request ===")
        logger.info("All Headers:")
        for header_name, header_value in headers.items():
            if header_name.lower() in ["authorization", "cookie"]:
                # Log authorization header but mask the token
                if header_name.lower() == "authorization":
                    if header_value.startswith("Bearer "):
                        token_preview = (
                            header_value[:27] + "..." + header_value[-10:]
                            if len(header_value) > 37
                            else header_value
                        )
                        logger.info(f"  {header_name}: {token_preview}")
                    else:
                        logger.info(
                            f"  {header_name}: [NOT A BEARER TOKEN - VALUE: {header_value[:50]}]"
                        )
                else:
                    logger.info(f"  {header_name}: [REDACTED]")
            else:
                logger.info(f"  {header_name}: {header_value}")

        # Log request body if present (for debugging streamable-http transport)
        if body:
            try:
                import json

                body_str = (
                    body.decode("utf-8") if isinstance(body, bytes) else str(body)
                )
                logger.info(f"Request body length: {len(body_str)}")
                logger.info(f"Request body preview (first 200 chars): {body_str[:200]}")

                # Try to parse as JSON to see structure
                try:
                    body_json = json.loads(body_str)
                    logger.info(f"Request body keys: {list(body_json.keys())}")

                    # Check if token is in body
                    if "token" in body_json:
                        logger.info("Found 'token' field in request body!")
                    if "authorization" in body_json:
                        logger.info("Found 'authorization' field in request body!")
                    if "headers" in body_json:
                        logger.info(
                            f"Found 'headers' field in request body with keys: {list(body_json.get('headers', {}).keys())}"
                        )
                except json.JSONDecodeError:
                    logger.info("Request body is not valid JSON")
            except Exception as e:
                logger.error(f"Error logging request body: {e}")
        else:
            logger.info("No request body present")

        # Get authorization header (case-insensitive lookup)
        auth_header = next(
            (v for k, v in headers.items() if k.lower() == "authorization"), ""
        )
        logger.info(f"Authorization header present: {bool(auth_header)}")
        logger.info(f"Authorization header length: {len(auth_header)}")

        is_bearer = auth_header.startswith("Bearer ")
        logger.info(f"Is Bearer token: {is_bearer}")

        if not is_bearer and auth_header:
            logger.warning(
                f"Authorization header does not start with 'Bearer '. Header starts with: '{auth_header[:20]}'"
            )

        # Extract and store the token in context for later use
        if is_bearer:
            token = auth_header.split(" ")[1]
            _jwt_token_context.set(token)
            logger.info(f"✓ Stored JWT token in ContextVar (length: {len(token)})")

            # Also store in global storage keyed by 'sub' claim for SSE persistence
            logger.info("=== Storing Token in Global Storage for SSE ===")
            try:
                token_data = decode_jwt_token(token)
                sub = token_data.get("sub")
                if sub:
                    _global_token_storage[sub] = token
                    logger.info("✓ Stored JWT token in global storage")
                    logger.info(f"  User (sub): {sub}")
                    logger.info(f"  Token length: {len(token)}")
                    logger.info(
                        f"  Total tokens in storage: {len(_global_token_storage)}"
                    )
                    logger.info(f"  Storage keys: {list(_global_token_storage.keys())}")
                else:
                    logger.warning(
                        "✗ Token does not contain 'sub' claim - cannot store globally"
                    )
            except Exception as e:
                logger.error(
                    f"✗ Could not extract 'sub' from token for global storage: {e}"
                )
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")

        # Call parent class verification
        try:
            result = await super().__call__(headers)
            logger.info("JWT verification successful")
            return result
        except Exception as e:
            logger.error(f"JWT verification failed: {type(e).__name__}: {str(e)}")
            raise


def get_jwt_verifier() -> LoggingJWTVerifier:
    """Create JWT verifier from environment variables with logging.

    Returns:
        LoggingJWTVerifier: Configured JWT verifier instance with logging
    """
    jwks_uri = os.getenv("JWKS_URI")
    jwt_issuer = os.getenv("JWT_ISSUER")
    jwt_audience = os.getenv("JWT_AUDIENCE")

    if not all([jwks_uri, jwt_issuer, jwt_audience]):
        raise ValueError(
            "Missing required JWT configuration: JWKS_URI, JWT_ISSUER, JWT_AUDIENCE must be set in environment"
        )

    logger.info(f"Configuring JWT verifier with issuer: {jwt_issuer}")
    logger.info(f"JWT audience: {jwt_audience}")
    logger.info(f"JWKS URI: {jwks_uri}")

    return LoggingJWTVerifier(
        jwks_uri=jwks_uri,
        issuer=jwt_issuer,
        audience=jwt_audience,
        algorithm="RS256",  # Standard for Azure AD / Microsoft Entra ID
    )


async def get_jwt_token_from_request() -> str:
    """
    Extract JWT token from context variable, global storage, or HTTP headers.

    For SSE transport, FastMCP's JWT verifier may not be called for each tool call,
    so we need to extract the token directly from HTTP headers as a fallback.

    Returns:
        str: The JWT token if found

    Raises:
        ValueError: If no JWT token is found
    """
    logger.info("=" * 60)
    logger.info("=== EXTRACTING JWT TOKEN FROM REQUEST ===")
    logger.info("=" * 60)

    # First try context variable (works for non-SSE or same async context)
    logger.info("Step 1: Checking ContextVar...")
    cached_token = _jwt_token_context.get()
    if cached_token:
        logger.info("✓ Found JWT token in ContextVar")
        logger.info(f"  Token length: {len(cached_token)}")
        logger.info(f"  Token preview: {cached_token[:20]}...{cached_token[-10:]}")
        logger.info("=" * 60)
        return cached_token
    else:
        logger.info("✗ ContextVar is empty (expected for SSE tool calls)")

    # For SSE, try to get from global storage
    logger.info("Step 2: Checking Global Token Storage...")
    logger.info(f"  Tokens in storage: {len(_global_token_storage)}")
    logger.info(f"  Storage keys (users): {list(_global_token_storage.keys())}")

    if len(_global_token_storage) == 1:
        # If there's only one token stored, use it (common case for single user)
        sub = list(_global_token_storage.keys())[0]
        token = _global_token_storage[sub]
        logger.info("✓ Found single token in global storage")
        logger.info(f"  User (sub): {sub}")
        logger.info(f"  Token length: {len(token)}")
        logger.info(f"  Token preview: {token[:20]}...{token[-10:]}")
        logger.info("=" * 60)
        return token
    elif len(_global_token_storage) > 1:
        # Multiple users - use the most recently added token
        sub = list(_global_token_storage.keys())[-1]
        token = _global_token_storage[sub]
        logger.warning(
            f"⚠ Multiple tokens in storage ({len(_global_token_storage)}), using most recent"
        )
        logger.warning(f"  User (sub): {sub}")
        logger.warning(f"  Token length: {len(token)}")
        logger.warning(f"  All users: {list(_global_token_storage.keys())}")
        logger.info("=" * 60)
        return token

    # Fallback: Try to extract token from HTTP headers (for SSE)
    logger.info("Step 3: Attempting to extract from HTTP Headers...")
    logger.info("  (This is a fallback for SSE when verifier wasn't called)")

    try:
        from fastmcp.server.dependencies import get_http_headers

        headers = get_http_headers()

        logger.info(f"  Headers type: {type(headers)}")
        logger.info(f"  Headers count: {len(headers)}")
        logger.info(f"  All header keys: {list(headers.keys())}")

        # Log all headers (mask sensitive ones)
        logger.info("  All headers:")
        for key, value in headers.items():
            if key.lower() in ["authorization", "cookie"]:
                if key.lower() == "authorization" and value.startswith("Bearer "):
                    logger.info(f"    {key}: Bearer {value[7:27]}...{value[-10:]}")
                else:
                    logger.info(f"    {key}: [REDACTED]")
            else:
                logger.info(f"    {key}: {value}")

        # Get authorization header (case-insensitive lookup)
        auth_header = next(
            (v for k, v in headers.items() if k.lower() == "authorization"), None
        )

        if auth_header:
            logger.info("  ✓ Authorization header found")
            logger.info(
                f"    Starts with 'Bearer ': {auth_header.startswith('Bearer ')}"
            )

            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
                logger.info("  ✓ Extracted JWT token from HTTP headers")
                logger.info(f"    Token length: {len(token)}")
                logger.info(f"    Token preview: {token[:20]}...{token[-10:]}")

                # Store it in global storage for future use
                try:
                    token_data = decode_jwt_token(token)
                    sub = token_data.get("sub")
                    if sub:
                        _global_token_storage[sub] = token
                        logger.info(
                            f"    ✓ Stored token in global storage for user: {sub}"
                        )
                    else:
                        logger.warning("    ⚠ Token has no 'sub' claim")
                except Exception as e:
                    logger.warning(f"    ⚠ Could not store token: {e}")

                logger.info("=" * 60)
                return token
            else:
                logger.error("  ✗ Authorization header doesn't start with 'Bearer '")
                logger.error(f"    Header value: {auth_header[:50]}")
        else:
            logger.error("  ✗ No Authorization header found in headers")

    except Exception as e:
        logger.error(f"  ✗ Error accessing HTTP headers: {type(e).__name__}: {e}")
        import traceback

        logger.error(f"  Traceback:\n{traceback.format_exc()}")

    # No token found anywhere
    logger.error("=" * 60)
    logger.error("✗ NO JWT TOKEN FOUND IN ANY LOCATION!")
    logger.error("  Checked:")
    logger.error("    1. ContextVar (empty)")
    logger.error(f"    2. Global Storage ({len(_global_token_storage)} tokens)")
    logger.error("    3. HTTP Headers (see above)")
    logger.error("=" * 60)
    raise ValueError("No JWT token found - authentication required")


def decode_jwt_token(token: str) -> Dict:
    """
    Decode JWT token without verification to extract claims.
    This is used for getting basic token information like subject claim
    without full validation.

    Args:
        token (str): JWT token string

    Returns:
        Dict: Decoded token claims

    Raises:
        ValueError: If token is invalid or cannot be decoded
    """
    try:
        # Decode without verification for internal use
        claims = jwt.decode(token, options={"verify_signature": False})
        return claims
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid JWT token: {str(e)}")
    except Exception as e:
        raise ValueError(f"Error decoding token: {str(e)}")
