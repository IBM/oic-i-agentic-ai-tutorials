import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import create_wxo_jwt_token, decode_jwt_token
from app.models import TokenInfoResponse

router = APIRouter()


class WXOJWTRequest(BaseModel):
    """Request model for WXO JWT generation"""

    sso_token: str | None = None
    user_name: str | None = None
    custom_user_id: str | None = None


@router.get("/oauth/config")
def get_oauth_config() -> dict[str, Any]:
    """Get OAuth configuration for frontend"""
    return {
        "client_id": settings.IBM_VERIFY_CLIENT_ID,
        "tenant_id": settings.IBM_VERIFY_TENANT_ID,
        "authorize_url": settings.IBM_VERIFY_AUTHORIZE_URL,
        "redirect_uri": settings.IBM_VERIFY_REDIRECT_URI,
        "scope": settings.IBM_VERIFY_SCOPE,
        "frontend_host": settings.FRONTEND_HOST,
    }


@router.get("/oauth/login")
def oauth_login() -> RedirectResponse:
    """Initiate OAuth login with IBM Verify"""
    if not settings.IBM_VERIFY_AUTHORIZE_URL:
        raise HTTPException(status_code=500, detail="OAuth not configured")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Store state in session (you may want to use a more robust session management)
    # For now, we'll include it in the redirect and verify it on callback

    # Build authorization URL
    auth_params = {
        "client_id": settings.IBM_VERIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.IBM_VERIFY_REDIRECT_URI,
        "scope": settings.IBM_VERIFY_SCOPE,
        "state": state,
    }

    auth_url = f"{settings.IBM_VERIFY_AUTHORIZE_URL}?{urlencode(auth_params)}"
    return RedirectResponse(url=auth_url)


@router.get("/oauth/callback")
def oauth_callback(
    code: str = Query(...),
) -> dict[str, Any]:
    """Handle OAuth callback from IBM Verify"""

    # Exchange code for token
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.IBM_VERIFY_REDIRECT_URI,
        "client_id": settings.IBM_VERIFY_CLIENT_ID,
        "client_secret": settings.IBM_VERIFY_CLIENT_SECRET,
    }

    try:
        response = requests.post(
            settings.IBM_VERIFY_TOKEN_URL, data=token_data, timeout=10
        )

        if response.status_code != 200:
            error_detail = response.text
            raise HTTPException(
                status_code=500, detail=f"Token exchange failed: {error_detail}"
            )

        token = response.json()

        # Decode the access token to get user info
        access_token = token.get("access_token")
        if access_token:
            _, payload, error = decode_jwt_token(access_token)
            if payload:
                token["user_info"] = payload

        return token

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Token exchange timed out")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")


@router.post("/oauth/refresh")
def refresh_token(refresh_token: str) -> dict[str, Any]:
    """Refresh the access token"""
    if not refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token provided")

    refresh_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.IBM_VERIFY_CLIENT_ID,
        "client_secret": settings.IBM_VERIFY_CLIENT_SECRET,
    }

    try:
        response = requests.post(settings.IBM_VERIFY_TOKEN_URL, data=refresh_data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")


@router.post("/oauth/logout")
def logout(
    access_token: str = Query(...), refresh_token: str | None = Query(None)
) -> dict[str, Any]:
    """
    Logout from IBM Verify by revoking the access token and optionally the refresh token.
    This invalidates the tokens on IBM Verify's side.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token provided")

    results = {
        "access_token_revoked": False,
        "refresh_token_revoked": False,
        "errors": [],
    }

    # Revoke access token
    try:
        revoke_data = {
            "token": access_token,
            "token_type_hint": "access_token",
            "client_id": settings.IBM_VERIFY_CLIENT_ID,
            "client_secret": settings.IBM_VERIFY_CLIENT_SECRET,
        }

        response = requests.post(
            settings.IBM_VERIFY_REVOKE_URL, data=revoke_data, timeout=10
        )

        # IBM Verify revocation endpoint returns 200 even if token is already invalid
        if response.status_code == 200:
            results["access_token_revoked"] = True
        else:
            results["errors"].append(f"Access token revocation failed: {response.text}")
    except requests.exceptions.Timeout:
        results["errors"].append("Access token revocation timed out")
    except requests.exceptions.RequestException as e:
        results["errors"].append(f"Access token revocation error: {str(e)}")

    # Revoke refresh token if provided
    if refresh_token:
        try:
            revoke_data = {
                "token": refresh_token,
                "token_type_hint": "refresh_token",
                "client_id": settings.IBM_VERIFY_CLIENT_ID,
                "client_secret": settings.IBM_VERIFY_CLIENT_SECRET,
            }

            response = requests.post(
                settings.IBM_VERIFY_REVOKE_URL, data=revoke_data, timeout=10
            )

            if response.status_code == 200:
                results["refresh_token_revoked"] = True
            else:
                results["errors"].append(
                    f"Refresh token revocation failed: {response.text}"
                )
        except requests.exceptions.Timeout:
            results["errors"].append("Refresh token revocation timed out")
        except requests.exceptions.RequestException as e:
            results["errors"].append(f"Refresh token revocation error: {str(e)}")

    # Return success if at least access token was revoked
    if results["access_token_revoked"]:
        return {
            "success": True,
            "message": "Logged out successfully",
            "details": results,
        }
    else:
        raise HTTPException(
            status_code=500, detail=f"Logout failed: {', '.join(results['errors'])}"
        )


@router.get("/oauth/token-info", response_model=TokenInfoResponse)
def get_token_info(access_token: str = Query(...)) -> TokenInfoResponse:
    """Get information about the current token"""
    if not access_token:
        raise HTTPException(status_code=401, detail="No access token provided")

    header, payload, error = decode_jwt_token(access_token)
    if error or not payload:
        raise HTTPException(status_code=401, detail=f"Token decode error: {error}")

    # Check expiration
    exp_time = payload.get("exp")
    is_valid = True
    status_msg = "Token valid"

    if exp_time:
        current_time = datetime.now(timezone.utc).timestamp()
        if exp_time <= current_time:
            is_valid = False
            status_msg = "Token expired"
        else:
            exp_readable = datetime.fromtimestamp(exp_time, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            status_msg = f"Token valid until {exp_readable}"

    return TokenInfoResponse(
        is_valid=is_valid,
        status_message=status_msg,
        header=header,
        payload=payload,
    )


@router.post("/wxo/jwt")
def generate_wxo_jwt(request_data: WXOJWTRequest) -> dict[str, Any]:
    """Generate a JWT token for Watson Orchestrate with encrypted SSO token"""
    print("THIS IS YOUR REQUEST DATA")
    print(request_data)
    try:
        token = create_wxo_jwt_token(
            sso_token=request_data.sso_token,
            user_name=request_data.user_name,
            custom_user_id=request_data.custom_user_id,
        )

        if not token:
            raise HTTPException(status_code=500, detail="Failed to generate JWT token")

        # Decode token to show payload info
        _, payload, error = decode_jwt_token(token)

        return {
            "token": token,
            "payload": payload,
            "error": error,
            "note": "user_payload is encrypted with WxO public key",
            "has_sso_token": bool(request_data.sso_token),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wxo/config")
def get_wxo_config() -> dict[str, Any]:
    """Get Watson Orchestrate configuration"""
    return {
        "orchestrationID": settings.WXO_ORCHESTRATION_ID,
        "hostURL": settings.WXO_HOST_URL,
        "deploymentPlatform": settings.WXO_DEPLOYMENT_PLATFORM,
        "crn": settings.WXO_CRN,
        "agentId": settings.WXO_AGENT_ID,
        "agentEnvironmentId": settings.WXO_AGENT_ENVIRONMENT_ID,
    }


@router.post("/oauth/introspect")
def introspect_token(access_token: str) -> dict[str, Any]:
    """
    Introspect an IBM Verify access token using the introspection endpoint.
    This validates the token with IBM Verify's servers.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token provided")

    introspect_url = f"{settings.IBM_VERIFY_BASE_URL}/introspect"

    introspect_data = {
        "token": access_token,
        "client_id": settings.IBM_VERIFY_CLIENT_ID,
        "client_secret": settings.IBM_VERIFY_CLIENT_SECRET,
    }

    try:
        response = requests.post(introspect_url, data=introspect_data, timeout=10)

        if response.status_code != 200:
            raise HTTPException(
                status_code=500, detail=f"Token introspection failed: {response.text}"
            )

        introspection_result = response.json()

        # Add decoded token info for comparison
        _, payload, error = decode_jwt_token(access_token)

        return {
            "introspection": introspection_result,
            "decoded_payload": payload,
            "decode_error": error,
            "is_active": introspection_result.get("active", False),
        }
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Token introspection timed out")
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500, detail=f"Token introspection failed: {str(e)}"
        )


@router.post("/oauth/validate-token")
def validate_token_simple(access_token: str) -> dict[str, Any]:
    """
    Simple token validation - checks what the backend actually validates.
    This mimics the get_current_user dependency logic.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token provided")

    result = {
        "token_valid": False,
        "reason": None,
        "user_info": None,
        "token_details": {},
    }

    try:
        # Decode the token (same as get_current_user does)
        _, payload, error = decode_jwt_token(access_token)

        if error or not payload:
            result["reason"] = f"Token decode failed: {error}"
            return result

        # Check expiration (same as get_current_user does)
        import time

        exp = payload.get("exp")
        current_time = time.time()

        result["token_details"] = {
            "exp": exp,
            "exp_readable": datetime.fromtimestamp(exp, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
            if exp
            else None,
            "current_time": current_time,
            "current_time_readable": datetime.fromtimestamp(
                current_time, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "time_until_expiry_seconds": exp - current_time if exp else None,
        }

        if exp and exp < current_time:
            result["reason"] = (
                f"Token expired at {result['token_details']['exp_readable']}"
            )
            return result

        # Extract user info (same as get_current_user does)
        user_id = payload.get("sub", "")
        if not user_id:
            result["reason"] = "Token missing user ID (sub claim)"
            return result

        result["token_valid"] = True
        result["reason"] = "Token is valid"
        result["user_info"] = {
            "id": user_id,
            "email": payload.get("unique_name") or payload.get("email"),
            "full_name": payload.get("name"),
            "preferred_username": payload.get("preferred_username"),
            "unique_name": payload.get("unique_name"),
            "upn": payload.get("upn"),
        }

        return result

    except Exception as e:
        result["reason"] = f"Validation error: {str(e)}"
        return result


@router.post("/oauth/validate-flow")
def validate_complete_flow(access_token: str) -> dict[str, Any]:
    """
    Comprehensive validation endpoint that tests the complete token flow:
    1. Decode IBM Verify token
    2. Introspect with IBM Verify
    3. Generate WXO JWT
    4. Decode WXO JWT

    This helps debug token issues end-to-end.
    """
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token provided")

    result = {
        "step1_ibm_verify_decode": {},
        "step2_ibm_verify_introspect": {},
        "step3_wxo_jwt_generation": {},
        "step4_wxo_jwt_decode": {},
        "overall_status": "unknown",
        "issues": [],
    }

    # Step 1: Decode IBM Verify token
    try:
        header, payload, error = decode_jwt_token(access_token)
        if error or not payload:
            result["step1_ibm_verify_decode"] = {
                "status": "failed",
                "error": error or "No payload returned",
            }
            result["issues"].append(f"IBM Verify token decode failed: {error}")
        else:
            result["step1_ibm_verify_decode"] = {
                "status": "success",
                "header": header,
                "payload": payload,
                "user_id": payload.get("sub") if payload else None,
                "email": payload.get("email") if payload else None,
                "name": payload.get("name") if payload else None,
                "expires_at": payload.get("exp") if payload else None,
            }
    except Exception as e:
        result["step1_ibm_verify_decode"] = {
            "status": "error",
            "error": str(e),
        }
        result["issues"].append(f"IBM Verify token decode error: {str(e)}")

    # Step 2: Introspect with IBM Verify
    try:
        introspect_url = f"{settings.IBM_VERIFY_BASE_URL}/introspect"
        introspect_data = {
            "token": access_token,
            "client_id": settings.IBM_VERIFY_CLIENT_ID,
            "client_secret": settings.IBM_VERIFY_CLIENT_SECRET,
        }
        response = requests.post(introspect_url, data=introspect_data, timeout=10)

        if response.status_code == 200:
            introspection = response.json()
            result["step2_ibm_verify_introspect"] = {
                "status": "success",
                "active": introspection.get("active", False),
                "introspection": introspection,
            }
            if not introspection.get("active"):
                result["issues"].append("IBM Verify reports token is not active")
        else:
            result["step2_ibm_verify_introspect"] = {
                "status": "failed",
                "http_status": response.status_code,
                "error": response.text,
            }
            result["issues"].append(
                f"IBM Verify introspection failed: {response.status_code}"
            )
    except Exception as e:
        result["step2_ibm_verify_introspect"] = {
            "status": "error",
            "error": str(e),
        }
        result["issues"].append(f"IBM Verify introspection error: {str(e)}")

    # Step 3: Generate WXO JWT
    try:
        wxo_token = create_wxo_jwt_token(sso_token=access_token)
        result["step3_wxo_jwt_generation"] = {
            "status": "success",
            "token_length": len(wxo_token),
            "token_preview": f"{wxo_token[:50]}...",
        }
    except Exception as e:
        result["step3_wxo_jwt_generation"] = {
            "status": "error",
            "error": str(e),
        }
        result["issues"].append(f"WXO JWT generation failed: {str(e)}")
        wxo_token = None

    # Step 4: Decode WXO JWT
    if wxo_token:
        try:
            header, payload, error = decode_jwt_token(wxo_token)
            if error or not payload:
                result["step4_wxo_jwt_decode"] = {
                    "status": "failed",
                    "error": error or "No payload returned",
                }
                result["issues"].append(f"WXO JWT decode failed: {error}")
            else:
                result["step4_wxo_jwt_decode"] = {
                    "status": "success",
                    "header": header,
                    "payload": payload,
                    "has_user_payload": "user_payload" in payload if payload else False,
                    "user_id": payload.get("sub") if payload else None,
                    "wo_user_id": payload.get("woUserId") if payload else None,
                    "wo_tenant_id": payload.get("woTenantId") if payload else None,
                    "expires_at": payload.get("exp") if payload else None,
                }
        except Exception as e:
            result["step4_wxo_jwt_decode"] = {
                "status": "error",
                "error": str(e),
            }
            result["issues"].append(f"WXO JWT decode error: {str(e)}")

    # Determine overall status
    if not result["issues"]:
        result["overall_status"] = "success"
    elif len(result["issues"]) <= 2:
        result["overall_status"] = "partial"
    else:
        result["overall_status"] = "failed"

    return result
