import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"


def _load_private_key() -> str:
    """
    Load YOUR private key from environment variable (base64 encoded PEM).
    This key is used to SIGN JWT tokens sent to Watson Orchestrate.
    Falls back to file system for backward compatibility.
    """
    if settings.JWT_PRIVATE_KEY_BASE64:
        # Decode base64 to get PEM string
        return base64.b64decode(settings.JWT_PRIVATE_KEY_BASE64).decode("utf-8")

    # Fallback to file system (deprecated)
    import os

    keys_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keys")
    private_key_path = os.path.join(keys_dir, "private.pem")

    if os.path.exists(private_key_path):
        with open(private_key_path) as f:
            return f.read()

    raise ValueError(
        "JWT_PRIVATE_KEY_BASE64 environment variable not set and no private.pem file found. "
        "Please set JWT_PRIVATE_KEY_BASE64 in your .env file."
    )


def _load_wxo_public_key() -> rsa.RSAPublicKey:
    """
    Load WATSON ORCHESTRATE's public key from environment variable (base64 encoded PEM).
    This key is used to ENCRYPT the user payload that WXO will decrypt.
    Falls back to file system for backward compatibility.
    """
    pem_data: bytes

    if settings.WXO_PUBLIC_KEY_BASE64:
        # Decode base64 to get PEM bytes
        pem_data = base64.b64decode(settings.WXO_PUBLIC_KEY_BASE64)
    else:
        # Fallback to file system (deprecated)
        import os

        keys_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "keys")
        wxo_public_key_path = os.path.join(keys_dir, "wxo_public.pem")

        if os.path.exists(wxo_public_key_path):
            with open(wxo_public_key_path, "rb") as f:
                pem_data = f.read()
        else:
            raise ValueError(
                "WXO_PUBLIC_KEY_BASE64 environment variable not set and no wxo_public.pem file found. "
                "Please set WXO_PUBLIC_KEY_BASE64 in your .env file."
            )

    # Load and validate the public key
    public_key = serialization.load_pem_public_key(pem_data, backend=default_backend())

    if not isinstance(public_key, rsa.RSAPublicKey):
        raise ValueError("Key is not an RSA public key")

    return public_key


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def decode_jwt_token(
    token_string: str,
) -> tuple[dict | None, dict | None, str | None]:
    """Decode JWT token and return header, payload, and error message"""
    try:
        parts = token_string.split(".")
        if len(parts) != 3:
            return None, None, "Invalid JWT token format"

        header = json.loads(base64.urlsafe_b64decode(parts[0] + "==").decode("utf-8"))
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8"))

        return header, payload, None
    except Exception as e:
        return None, None, f"Error decoding token: {str(e)}"


def encrypt_user_payload(user_payload: dict) -> str:
    """
    Encrypt user payload using WxO public key with chunked encryption.
    Returns base64 encoded encrypted data.
    """
    try:
        # Load WxO public key from environment or file
        wxo_public_key = _load_wxo_public_key()

        # Calculate max chunk size for RSA encryption
        key_size = wxo_public_key.key_size // 8  # Convert bits to bytes
        # OAEP padding overhead: 2 * hash_length + 2
        max_chunk_size = key_size - 2 * hashes.SHA256().digest_size - 2

        # Convert payload to JSON string and then to bytes
        payload_json = json.dumps(user_payload)
        payload_bytes = payload_json.encode("utf-8")

        # Encrypt in chunks
        encrypted_chunks = []
        offset = 0

        while offset < len(payload_bytes):
            # Get the next chunk
            chunk = payload_bytes[offset : offset + max_chunk_size]

            # Encrypt this chunk
            encrypted_chunk = wxo_public_key.encrypt(
                chunk,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            encrypted_chunks.append(encrypted_chunk)
            offset += max_chunk_size

        # Concatenate all encrypted chunks
        encrypted_data = b"".join(encrypted_chunks)

        # Return base64 encoded encrypted data
        return base64.b64encode(encrypted_data).decode("utf-8")
    except Exception as e:
        raise Exception(f"Error encrypting user payload: {str(e)}")


def create_wxo_jwt_token(
    sso_token: str | None = None,
    user_name: str | None = None,
    custom_user_id: str | None = None,
) -> str:
    """
    Create a JWT token signed with the private key for Watson Orchestrate.
    Includes encrypted user_payload with SSO token and user information.

    Args:
        sso_token: Optional SSO token (IBM Verify access token) to include in encrypted payload
        user_name: Optional user name extracted from IBM Verify token
        custom_user_id: Optional custom user ID extracted from IBM Verify token

    Returns the signed JWT token string.
    """
    try:
        # Load the private key from environment or file
        private_key_pem = _load_private_key()

        # Extract user info from SSO token if provided
        user_info = {}
        if sso_token:
            _, token_payload, error = decode_jwt_token(sso_token)
            if token_payload and not error:
                user_info = token_payload
                # Extract common OIDC claims
                if not user_name:
                    user_name = (
                        token_payload.get("name")
                        or token_payload.get("preferred_username")
                        or token_payload.get("email")
                    )
                if not custom_user_id:
                    custom_user_id = token_payload.get("sub") or token_payload.get(
                        "user_id"
                    )

        # Use extracted or provided values, with sensible defaults if extraction fails
        final_user_id = custom_user_id or "unknown-user"
        final_user_name = user_name or "Unknown User"

        # Create JWT payload with actual user data
        now = datetime.now(timezone.utc)
        payload = {
            "sub": final_user_name,  # Subject - user identifier from IBM Verify
            "woUserId": final_user_name,  # Watson Orchestrate user ID
            "woTenantId": settings.WXO_TENANT_ID,  # Watson Orchestrate tenant ID
            "iat": now,  # Issued at
            "exp": now + timedelta(hours=24),  # Expiration time (24 hours)
            "iss": "products-web-app",  # Issuer
        }

        # Create user_payload with SSO token and user data
        user_payload = {
            "name": final_user_name,
            "custom_user_id": final_user_id,
        }

        # Add SSO token (IBM Verify access token) if provided
        if sso_token:
            user_payload["sso_token"] = sso_token
            # Add additional user info from IBM Verify token
            if user_info:
                user_payload["email"] = user_info.get("email")
                user_payload["email_verified"] = user_info.get("email_verified")
                user_payload["iss"] = user_info.get("iss")  # IBM Verify issuer

        print("THIS IS YOUR PAYLOAD AGAIAAAIAAIAIAIAINA")
        print(payload)
        print(user_payload)

        # Try to encrypt the user_payload using WxO public key
        try:
            encrypted_payload = encrypt_user_payload(user_payload)
            payload["user_payload"] = encrypted_payload
        except Exception as encrypt_error:
            # Log error but continue without encrypted payload
            print(f"Failed to encrypt user_payload: {str(encrypt_error)}")
            raise  # Re-raise to ensure we don't send invalid tokens

        # Sign the JWT with RS256 algorithm using the PEM string
        token = jwt.encode(payload, private_key_pem, algorithm="RS256")

        return token
    except Exception as e:
        raise Exception(f"Error creating JWT token: {str(e)}")
