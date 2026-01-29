from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.auth.providers.jwt import JWTVerifier
from typing import List, Dict
import os
import logging
import jwt

# ===================================================
# Logging (Code Engine friendly)
# ===================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)

# ===================================================
# Okta JWT Configuration
# ===================================================
OKTA_ISSUER = os.environ.get(
    "OIDC_ISSUER",
    "https://trial-3373486.okta.com/oauth2/default"
)

OKTA_AUDIENCE = os.environ.get(
    "OIDC_AUDIENCE",
    "api://default"
)

auth = JWTVerifier(
    jwks_uri=f"{OKTA_ISSUER}/v1/keys",
    issuer=OKTA_ISSUER,
    audience=OKTA_AUDIENCE,
    algorithm="RS256",
    required_scopes=["mcp.read"],
)

# ===================================================
# FastMCP Server (Code Engine Ready)
# ===================================================
mcp = FastMCP(
    name="HR MCP Server",
    version="0.1.0",
    host="0.0.0.0",                       
    port=int(os.environ.get("PORT", 8080)),  
    stateless_http=True,
    auth=auth,
)

# ===================================================
# HR Tools
# ===================================================
@mcp.tool(description="Returns a list of company office locations")
def get_office_locations() -> List[Dict]:
    logging.info("get_office_locations tool called")

    return [
        {"office_name": "HQ", "city": "New York", "country": "USA"},
        {"office_name": "Tech Hub", "city": "Austin", "country": "USA"},
        {"office_name": "EU Office", "city": "London", "country": "UK"},
    ]


@mcp.tool(description="Returns the employee salary in USD")
def get_employee_salary() -> Dict:
    logging.info("get_employee_salary tool called")

    headers = get_http_headers()
    auth_header = headers.get("authorization", "")

    if not auth_header.startswith("Bearer "):
        return {"error": "Missing authorization token"}

    token = auth_header.replace("Bearer ", "")

    # JWT already validated by JWTVerifier
    claims = jwt.decode(token, options={"verify_signature": False})

    is_manager = claims.get("is_manager", False)

    if not is_manager:
        return {
            "error": "You do not have permission to view the salary since you are not a manager."
        }

    return {"salary": 20000, "currency": "USD"}

# ===================================================
# Run Server
# ===================================================
if __name__ == "__main__":
    logging.info("Starting MCP Server on IBM Code Engine")
    mcp.run(transport="streamable-http")
