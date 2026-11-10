"""
wire_agent.py  —  Wire Azure AI Foundry agents with WXO tracing
==============================================================

Deploys a single Azure Function App that polls the Log Analytics workspace
(AppGenAIContent & AppDependencies tables) every 5 seconds and forwards
spans to WXO Agent Analytics.

No changes to the agents themselves. One Function App covers ALL agents
(prompt and hosted) in the workspace simultaneously.

Steps:
  1. Create / verify Storage Account
  2. Create / verify Linux Consumption Function App
  3. Assign Managed Identity + grant Monitoring Reader on Log Analytics
  4. Merge WXO_AGENT_MAP into Function App settings & blob storage
  5. Publish function_app.py code via `func` CLI

Usage
-----
    cd wxo-external-agent-tracing

    # Deploy / update the Function App
    ./azure.sh
    ./azure.sh --publish-only   # skip resource creation, update code/settings
    ./azure.sh --dry-run
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

# =============================================================================
# ── Configuration ─────────────────────────────────────────────────────────────
# =============================================================================

SUBSCRIPTION     = os.environ.get("AZURE_SUBSCRIPTION_ID", "<your-azure-subscription-id>")
RESOURCE_GROUP   = os.environ.get("AZURE_RESOURCE_GROUP",  "<your-resource-group>")
AZURE_LOCATION   = os.environ.get("AZURE_LOCATION",        "eastus")
ACCOUNT          = os.environ.get("AZURE_ACCOUNT",         "<your-ai-foundry-account>")
PROJECT          = os.environ.get("AZURE_PROJECT",         "<your-ai-foundry-project>")
PROJECT_ENDPOINT = f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"

LOG_ANALYTICS_WORKSPACE_ID   = os.environ.get("LOG_ANALYTICS_WORKSPACE_ID",   "")
LOG_ANALYTICS_WORKSPACE_NAME = os.environ.get("LOG_ANALYTICS_WORKSPACE_NAME", "")
FUNCTION_APP_NAME            = os.environ.get("FUNCTION_APP_NAME",            "wxo-foundry-prompt-tracer")
STORAGE_ACCOUNT_NAME         = os.environ.get("STORAGE_ACCOUNT_NAME",         "")

WXO_AGENT_MAP_RAW            = os.environ.get("WXO_AGENT_MAP", "{}")

# WXO credentials — read from env vars (populated from config/azure.env).
_WXO_MODE            = "cpd" if os.environ.get("WXO_DEPLOYMENT_MODE", "cloud").strip().lower() == "cpd" else "cloud"
_CPD_HOST_URL        = os.environ.get("CPD_HOST_URL", "").rstrip("/")
_CPD_USERNAME        = os.environ.get("CPD_USERNAME", "")
_CPD_PASSWORD        = os.environ.get("CPD_PASSWORD", "")
_CPD_INSTANCE_ID     = os.environ.get("CPD_INSTANCE_ID", "")
_CPD_NAMESPACE       = os.environ.get("CPD_NAMESPACE", "")
_CPD_VERIFY_TLS      = os.environ.get("CPD_VERIFY_TLS", "false")

def extract_tenant_id(export_url: str = "") -> str:
    url = export_url or os.environ.get("WXO_OTEL_EXPORT_URL", "")
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return ""

if _WXO_MODE == "cpd":
    _WXO_TENANT_ID       = ""
    _WXO_API_KEY         = ""
    _WXO_TOKEN_URL       = ""
    _WXO_OTEL_EXPORT_URL = (os.environ.get("CPD_EXPORT_URL") or os.environ.get("WXO_OTEL_EXPORT_URL")
                            or (f"{_CPD_HOST_URL}/{_CPD_NAMESPACE}/instances/{_CPD_INSTANCE_ID}/v1/agentops-v3/traces"
                                if _CPD_HOST_URL and _CPD_NAMESPACE and _CPD_INSTANCE_ID else ""))
else:
    _WXO_OTEL_EXPORT_URL = os.environ.get("WXO_OTEL_EXPORT_URL", "https://api.watson-orchestrate.ibm.com/instances/<your-wxo-instance-id>/v1/orchestrate/inject/traces")
    _WXO_TENANT_ID       = extract_tenant_id(_WXO_OTEL_EXPORT_URL) or os.environ.get("WXO_TENANT_ID", "<your-wxo-tenant-id>")
    _WXO_API_KEY         = os.environ.get("API_KEY",           "<your-wxo-api-key>")
    _WXO_TOKEN_URL       = os.environ.get("TOKEN_URL",         "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token")
_WXO_ENVIRONMENT     = os.environ.get("ENVIRONMENT_NAME",  "draft")


def _wxo_auth_settings(overrides=None) -> dict:
    """Mode-specific WXO auth settings to inject into the Function App.

    cloud → {WXO_OTEL_EXPORT_URL, WXO_API_KEY, WXO_TOKEN_URL, WXO_TENANT_ID}
    cpd   → {WXO_DEPLOYMENT_MODE, WXO_OTEL_EXPORT_URL, CPD_*}  (no tenant / API key)
    """
    o = overrides or {}
    if _WXO_MODE == "cpd":
        return {
            "WXO_DEPLOYMENT_MODE": "cpd",
            "WXO_OTEL_EXPORT_URL": o.get("wxo_otel_export_url") or _WXO_OTEL_EXPORT_URL,
            "CPD_HOST_URL":        _CPD_HOST_URL,
            "CPD_USERNAME":        _CPD_USERNAME,
            "CPD_PASSWORD":        _CPD_PASSWORD,
            "CPD_INSTANCE_ID":     _CPD_INSTANCE_ID,
            "CPD_NAMESPACE":       _CPD_NAMESPACE,
            "CPD_VERIFY_TLS":      _CPD_VERIFY_TLS,
        }
    export_url = o.get("wxo_otel_export_url") or _WXO_OTEL_EXPORT_URL
    tenant_id  = o.get("wxo_tenant_id") or o.get("tenant_id") or extract_tenant_id(export_url) or _WXO_TENANT_ID
    return {
        "WXO_OTEL_EXPORT_URL": export_url,
        "WXO_API_KEY":         o.get("wxo_api_key")         or _WXO_API_KEY,
        "WXO_TOKEN_URL":       o.get("wxo_token_url")       or _WXO_TOKEN_URL,
        "WXO_TENANT_ID":       tenant_id,
    }


# =============================================================================
# ── Shared helpers ─────────────────────────────────────────────────────────────
# =============================================================================

def _ok(msg: str) -> None:   print(f"  ✓  {msg}")
def _info(msg: str) -> None: print(f"  ·  {msg}")
def _err(msg: str) -> None:  print(f"  ✗  {msg}")
def _head(msg: str) -> None: print(f"\n{'═'*60}\n  {msg}\n{'═'*60}")


def _az_login_if_service_principal() -> None:
    """Non-interactive `az login` for CI / unattended runs (no browser, no MFA).

    Runs only when AZURE_CLIENT_ID, AZURE_CLIENT_SECRET and AZURE_TENANT_ID are
    all set; otherwise the existing `az login` session is used unchanged.
    """
    client_id     = os.environ.get("AZURE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("AZURE_CLIENT_SECRET", "").strip()
    tenant_id     = os.environ.get("AZURE_TENANT_ID", "").strip()
    if not (client_id and client_secret and tenant_id):
        return
    _info("Service principal credentials detected — running `az login --service-principal`")
    result = subprocess.run(
        ["az", "login", "--service-principal",
         "-u", client_id, "-p", client_secret, "--tenant", tenant_id,
         "--output", "none"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        _info(f"az login --service-principal failed, falling back to existing az login session:\n{result.stderr.strip()}")
        return
    _ok("Logged in to Azure as service principal")


def _az(args: list[str], capture: bool = False) -> str:
    """Run an `az` CLI command. Returns stdout if capture=True."""
    cmd = ["az"] + args
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True,
                            capture_output=capture,
                            check=False)
    if result.returncode != 0 and not capture:
        _err(f"az command failed: {' '.join(cmd)}")
        sys.exit(1)
    return result.stdout.strip() if capture else ""


# =============================================================================
# ── Function App Deployment Steps ─────────────────────────────────────────────
# =============================================================================

def _validate_config() -> None:
    """Abort with helpful message if required vars are missing."""
    required = {
        "AZURE_SUBSCRIPTION_ID":        SUBSCRIPTION,
        "AZURE_RESOURCE_GROUP":         RESOURCE_GROUP,
        "AZURE_LOCATION":               AZURE_LOCATION,
        "STORAGE_ACCOUNT_NAME":         STORAGE_ACCOUNT_NAME,
        "FUNCTION_APP_NAME":            FUNCTION_APP_NAME,
        "LOG_ANALYTICS_WORKSPACE_ID":   LOG_ANALYTICS_WORKSPACE_ID,
        "LOG_ANALYTICS_WORKSPACE_NAME": LOG_ANALYTICS_WORKSPACE_NAME,
        "ENVIRONMENT_NAME":             _WXO_ENVIRONMENT,
    }
    if _WXO_MODE == "cpd":
        required.update({
            "CPD_HOST_URL":    _CPD_HOST_URL,
            "CPD_USERNAME":    _CPD_USERNAME,
            "CPD_PASSWORD":    _CPD_PASSWORD,
            "CPD_INSTANCE_ID": _CPD_INSTANCE_ID,
            "CPD_NAMESPACE":   _CPD_NAMESPACE,
        })
    else:
        required.update({
            "WXO_TENANT_ID":       _WXO_TENANT_ID,
            "API_KEY":             _WXO_API_KEY,
            "TOKEN_URL":           _WXO_TOKEN_URL,
            "WXO_OTEL_EXPORT_URL": _WXO_OTEL_EXPORT_URL,
        })
    missing = [k for k, v in required.items() if not v or v.startswith("<")]
    if missing:
        for m in missing:
            _err(f"{m} is not set in config.env")
        print("\n  Edit config.env and re-run.")
        sys.exit(1)


def _step1_storage() -> None:
    _head("Step 1/5 — Storage account")
    exists = _az([
        "storage", "account", "show",
        "--name", STORAGE_ACCOUNT_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--query", "name", "-o", "tsv",
    ], capture=True)
    if exists:
        _ok(f"Storage account already exists: {STORAGE_ACCOUNT_NAME}")
    else:
        _az([
            "storage", "account", "create",
            "--name", STORAGE_ACCOUNT_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--location", AZURE_LOCATION,
            "--sku", "Standard_LRS",
            "--output", "none",
        ])
        _ok(f"Storage account created: {STORAGE_ACCOUNT_NAME}")


def _step2_function_app() -> None:
    _head("Step 2/5 — Function App")
    exists = _az([
        "functionapp", "show",
        "--name", FUNCTION_APP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--query", "name", "-o", "tsv",
    ], capture=True)
    if exists:
        _ok(f"Function App already exists: {FUNCTION_APP_NAME}")
    else:
        _az([
            "functionapp", "create",
            "--name", FUNCTION_APP_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--storage-account", STORAGE_ACCOUNT_NAME,
            "--consumption-plan-location", AZURE_LOCATION,
            "--runtime", "python",
            "--runtime-version", "3.11",
            "--functions-version", "4",
            "--os-type", "Linux",
            "--assign-identity",
            "--output", "none",
        ])
        _ok(f"Function App created: {FUNCTION_APP_NAME}")


def _ensure_function_app_running() -> None:
    """Start the Function App if it is stopped.

    Test teardown stops the app to save cost; publishing to a stopped app fails with
    'Error calling sync triggers (BadRequest/TooManyRequests)'.
    """
    state = _az([
        "functionapp", "show",
        "--name", FUNCTION_APP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--query", "state", "-o", "tsv",
    ], capture=True)
    if state == "Running":
        _ok(f"Function App is running: {FUNCTION_APP_NAME}")
        return
    _info(f"Function App state is '{state}' — starting it")
    _az([
        "functionapp", "start",
        "--name", FUNCTION_APP_NAME,
        "--resource-group", RESOURCE_GROUP,
    ])
    _ok(f"Function App started: {FUNCTION_APP_NAME}")
    time.sleep(30)  # let the host come up before app settings / publish


def _step3_role_assignment() -> None:
    _head("Step 3/5 — Managed Identity + Monitoring Reader role")

    principal = _az([
        "functionapp", "identity", "show",
        "--name", FUNCTION_APP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--query", "principalId", "-o", "tsv",
    ], capture=True)

    if not principal:
        _info("Assigning system identity to Function App...")
        _az([
            "functionapp", "identity", "assign",
            "--name", FUNCTION_APP_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--output", "none",
        ])
        principal = _az([
            "functionapp", "identity", "show",
            "--name", FUNCTION_APP_NAME,
            "--resource-group", RESOURCE_GROUP,
            "--query", "principalId", "-o", "tsv",
        ], capture=True)

    _ok(f"Managed identity principal: {principal}")

    workspace_scope = _az([
        "monitor", "log-analytics", "workspace", "show",
        "--workspace-name", LOG_ANALYTICS_WORKSPACE_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--query", "id", "-o", "tsv",
    ], capture=True)

    role_exists = _az([
        "role", "assignment", "list",
        "--assignee", principal,
        "--role", "Monitoring Reader",
        "--scope", workspace_scope,
        "--query", "[0].id", "-o", "tsv",
    ], capture=True)

    if role_exists:
        _ok("Monitoring Reader role already assigned")
    else:
        _az([
            "role", "assignment", "create",
            "--assignee", principal,
            "--role", "Monitoring Reader",
            "--scope", workspace_scope,
            "--output", "none",
        ])
        _ok("Monitoring Reader role assigned on Log Analytics workspace")


def _step4_app_settings() -> None:
    _head("Step 4/5 — Function App settings (merge WXO_AGENT_MAP)")

    existing_raw = _az([
        "functionapp", "config", "appsettings", "list",
        "--name", FUNCTION_APP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--query", "[?name=='WXO_AGENT_MAP'].value",
        "-o", "tsv",
    ], capture=True)

    # Merge existing map in Azure with the local WXO_AGENT_MAP from config.env
    merged: dict = {}
    for raw in (existing_raw, WXO_AGENT_MAP_RAW):
        if raw and raw.strip():
            try:
                merged.update(json.loads(raw))
            except json.JSONDecodeError:
                pass
    final_map = json.dumps(merged)

    appinsights_conn = _az([
        "monitor", "app-insights", "component", "list",
        "--resource-group", RESOURCE_GROUP,
        "--query", "[0].connectionString",
        "-o", "tsv",
    ], capture=True)
    if not appinsights_conn:
        _info("APPLICATIONINSIGHTS_CONNECTION_STRING not found — Function App logs will go to stdout only")
    else:
        _ok(f"App Insights connection string fetched (key={appinsights_conn[:30]}...)")

    settings = [
        f"LOG_ANALYTICS_WORKSPACE_ID={LOG_ANALYTICS_WORKSPACE_ID}",
        f"PROJECT_ENDPOINT={PROJECT_ENDPOINT}",   # authoritative token usage via GET /responses/{id}
        *[f"{k}={v}" for k, v in _wxo_auth_settings().items()],
        f"WXO_ENVIRONMENT_NAME={_WXO_ENVIRONMENT}",
        f"WXO_AGENT_MAP={final_map}",
        f"WXO_AGENT_ID={os.environ.get('WXO_AGENT_ID', '')}",
        f"WXO_AGENT_DISPLAY_NAME={os.environ.get('WXO_AGENT_DISPLAY_NAME', '')}",
    ]
    if appinsights_conn:
        settings.append(f"APPLICATIONINSIGHTS_CONNECTION_STRING={appinsights_conn}")

    _az([
        "functionapp", "config", "appsettings", "set",
        "--name", FUNCTION_APP_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--settings", *settings,
        "--output", "none",
    ])
    _ok(f"App settings configured (merged WXO_AGENT_MAP: {final_map})")
    _upload_agent_map_blob(final_map)


def _upload_agent_map_blob(final_map: str) -> None:
    """
    Publish the merged agent map to blob storage (azure-webjobs-hosts/wxo-cursor/agent_map.json).
    function_app.py re-reads it on every poll, so Function App instances that started before
    this deploy still route traces by the CURRENT map instead of the one in their frozen env.
    The storage key is passed via env vars so it never appears in the printed command.
    """
    keys = _az([
        "storage", "account", "keys", "list",
        "--account-name", STORAGE_ACCOUNT_NAME,
        "--resource-group", RESOURCE_GROUP,
        "--query", "[0].value", "-o", "tsv",
    ], capture=True)
    if not keys:
        _err(f"Could not read a key for storage account {STORAGE_ACCOUNT_NAME} — agent map blob NOT updated")
        sys.exit(1)

    blob_name = "wxo-cursor/agent_map.json"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write(final_map)
        tmp_path = fh.name
    try:
        env = {**os.environ, "AZURE_STORAGE_ACCOUNT": STORAGE_ACCOUNT_NAME, "AZURE_STORAGE_KEY": keys}
        for args in (
            ["az", "storage", "container", "create", "--name", "azure-webjobs-hosts", "--output", "none"],
            ["az", "storage", "blob", "upload", "--container-name", "azure-webjobs-hosts",
             "--name", blob_name, "--file", tmp_path, "--overwrite", "true", "--output", "none"],
        ):
            result = subprocess.run(args, text=True, capture_output=True, env=env)
            if result.returncode != 0:
                _err(f"agent map blob update failed: {result.stderr.strip()[:500]}")
                sys.exit(1)
    finally:
        os.unlink(tmp_path)
    _ok(f"Agent map published to blob azure-webjobs-hosts/{blob_name}")


def _step5_publish(attempts: int = 3) -> None:
    _head("Step 5/5 — Publish function code")
    azure_dir = Path(__file__).parent
    last_exit = 1
    for attempt in range(1, attempts + 1):
        result = subprocess.run(
            ["func", "azure", "functionapp", "publish", FUNCTION_APP_NAME, "--python"],
            cwd=str(azure_dir),
            text=True,
        )
        if result.returncode == 0:
            return
        last_exit = result.returncode
        if attempt < attempts:
            _info(f"`func` publish failed (exit {result.returncode}), retrying in 30s [{attempt}/{attempts}]")
            time.sleep(30)
    _err(f"`func` publish failed after {attempts} attempts (exit {last_exit})")
    sys.exit(1)


def flow_deploy(publish_only: bool = False) -> None:
    """Deploy / update the Azure Function App tracer."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  WXO Azure Foundry Agent Tracing (Function App Poller)       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Subscription : {SUBSCRIPTION}")
    print(f"  Resource Grp : {RESOURCE_GROUP}")
    print(f"  Location     : {AZURE_LOCATION}")
    print()
    print("  ┌─────────────────────────────────────────────────────────────┐")
    print("  │  Config (from config.env)                                   │")
    print("  ├─────────────────────────────────────────────────────────────┤")
    print(f"  │  FUNCTION_APP_NAME   : {FUNCTION_APP_NAME:<37}│")
    print(f"  │  STORAGE_ACCOUNT     : {STORAGE_ACCOUNT_NAME:<37}│")
    print(f"  │  LOG_ANALYTICS_WS    : {LOG_ANALYTICS_WORKSPACE_ID:<37}│")
    print(f"  │  Traces ALL agents   : {'in this workspace automatically':<37}│")
    print("  └─────────────────────────────────────────────────────────────┘")
    print()

    _validate_config()

    # Set subscription
    subprocess.run(
        ["az", "account", "set", "--subscription", SUBSCRIPTION],
        check=True, capture_output=True,
    )

    if publish_only:
        _head("--publish-only: skipping infra creation, updating settings + code")
        _ensure_function_app_running()
        _step4_app_settings()
    else:
        _step1_storage()
        _step2_function_app()
        _ensure_function_app_running()
        _step3_role_assignment()
        _step4_app_settings()

    _step5_publish()

    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Done — WXO Azure Foundry agent tracing deployed.            ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Function App : {FUNCTION_APP_NAME}")
    print(f"  Traces       : all agents in workspace {LOG_ANALYTICS_WORKSPACE_ID}")
    print( "  Poll interval: every 15 seconds")
    print()
    print("  Stream logs:")
    print(f"    func azure functionapp logstream {FUNCTION_APP_NAME}")
    print()
    print("  To redeploy code only (skip resource creation):")
    print("    python3 wire_agent.py --publish-only")
    print()


# =============================================================================
# ── Main ──────────────────────────────────────────────────────────────────────
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wire_agent.py",
        description=(
            "Wire Azure AI Foundry agents with WXO tracing.\n\n"
            "  Deploys/updates the Azure Function App that polls Log Analytics\n"
            "  every 5s and forwards spans to WXO (covers prompt & hosted agents).\n"
            "  Agent input: WXO_AGENT_MAP in config/azure.env (or config.env)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--publish-only", action="store_true",
        help="Skip resource creation; only update settings and republish function code",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would happen without making any changes",
    )

    args = parser.parse_args()

    # ── Banner ─────────────────────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  WXO Azure Foundry Agent Tracing                             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    if args.dry_run:
        print("  --dry-run: would deploy Azure Function App tracer.")
        print(f"    Function App : {FUNCTION_APP_NAME}")
        print(f"    Resource Grp : {RESOURCE_GROUP}")
        print(f"    Log Analytics: {LOG_ANALYTICS_WORKSPACE_ID}")
        print(f"    publish-only : {args.publish_only}")
        print()
        print("  No changes made.")
        return

    # ── Azure auth (service principal if configured, else existing `az login`) ─
    _az_login_if_service_principal()

    # ── Dispatch ───────────────────────────────────────────────────────────────
    flow_deploy(publish_only=args.publish_only)


if __name__ == "__main__":
    main()
