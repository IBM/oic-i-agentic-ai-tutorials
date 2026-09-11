from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
import os
from typing import List, Dict

# ===================================================
# Okta JWT verification
# ===================================================

OKTA_ISSUER = os.getenv(
    "OIDC_ISSUER",
    "https://trial-1234567.okta.com/oauth2/default"
)

OKTA_AUDIENCE = os.getenv(
    "OIDC_AUDIENCE",
    "api://default"
)

auth = JWTVerifier(
    jwks_uri=f"{OKTA_ISSUER}/v1/keys",
    issuer=OKTA_ISSUER,
    audience=OKTA_AUDIENCE,
    algorithm="RS256",
    required_scopes=["mcp.read"]
)

# ===================================================
# MCP Server
# ===================================================

mcp = FastMCP(
    name="HR MCP Server",
    version="1.0.0",
    host="localhost",
    port=8080,
    stateless_http=True,
    auth=auth
)

# ===================================================
# TOOL 1 — GENERAL TOOLS
# ===================================================

@mcp.tool(description="Returns a list of company office locations")
async def get_office_locations() -> List[Dict]:
    return [
        {"office_name": "HQ", "city": "New York", "country": "USA"},
        {"office_name": "Tech Hub", "city": "Austin", "country": "USA"},
        {"office_name": "EU Office", "city": "London", "country": "UK"},
    ]


@mcp.tool(description="Returns the logged-in employee leave balance")
async def get_leave_balance() -> Dict:
    return {
        "annual_leave": 12,
        "sick_leave": 5,
        "used_leaves": 6,
        "remaining_leaves": 11
    }


@mcp.tool(description="Returns upcoming company holidays")
async def get_holidays() -> List[Dict]:
    return [
        {"name": "New Year", "date": "2026-01-01"},
        {"name": "Republic Day", "date": "2026-01-26"},
        {"name": "Holi", "date": "2026-03-04"},
        {"name": "Good Friday", "date": "2026-04-03"},
        {"name": "Ambedkar Jayanti", "date": "2026-04-14"},
        {"name": "Labour Day", "date": "2026-05-01"},
        {"name": "Eid al-Adha (Bakrid)", "date": "2026-06-17"},
        {"name": "Independence Day (India)", "date": "2026-08-15"},
        {"name": "Ganesh Chaturthi", "date": "2026-09-11"},
        {"name": "Gandhi Jayanti", "date": "2026-10-02"},
        {"name": "Dussehra", "date": "2026-10-20"},
        {"name": "Diwali", "date": "2026-11-08"},
        {"name": "Christmas", "date": "2026-12-25"},
    ]



# ===================================================
# ADMIN TOOLS
# ===================================================

@mcp.tool(description="Returns the employee salary in USD")
async def get_employee_salary() -> Dict:
    return {
        "salary_usd": 85000,
        "currency": "USD"
    }


@mcp.tool(description="Fetches team dashboard summary")
async def get_team_summary_dashboard() -> Dict:
    return {
        "team_name": "Engineering Team",
        "total_members": 25,
        "present_today": 21,
        "on_leave_today": 3,
        "working_remote_today": 1,
        "new_joiners_this_month": 2,
        "upcoming_joiners_next_week": 1,
        "average_attendance_percentage": 94,
        "open_positions": 3,
        "upcoming_holidays": 3
    }




# ===================================================
# Run Server
# ===================================================

if __name__ == "__main__":
    print("Starting HR MCP Server on http://localhost:8080/mcp ...")
    mcp.run(transport="streamable-http")
