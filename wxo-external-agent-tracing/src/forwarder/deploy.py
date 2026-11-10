#!/usr/bin/env python3
"""
forwarder/deploy.py
===================
Deploy the OTLP Forwarder for Claude to ONE target and connect Claude to it.

  deploy(target)  create/update the forwarder, push config, read back its URL, then
                  point Claude's OTel destination at that URL            (default)
  sync(target)    push config only, no code redeploy                     (--sync)

Targets (FORWARDER_TARGET in config/claude.env, or --target; asked interactively if unset):
  aws     Lambda + Function URL. Config lives in SSM, picked up within ~60 s.
  azure   Function App. Config lives in App Settings (the app restarts).
  docker  Local container. Config is passed as env (container is recreated).

Inputs:
  config/shared.env   API_KEY, TOKEN_URL
  config/claude.env   WXO_TENANT_ID, WXO_OTEL_EXPORT_URL, ENVIRONMENT_NAME, WXO_AGENT_MAP, FORWARDER_TARGET + settings

Claude step (after deploy):
  ANTHROPIC_ADMIN_API_KEY set  -> the destination is created/updated in Anthropic automatically
                                  (also needs ANTHROPIC_WORKSPACE_ID: ids or 'all').
  ANTHROPIC_ADMIN_API_KEY unset -> nothing is sent; the forwarder endpoint is printed so you can
                                  set it in your Claude OTel settings yourself.

  register-anthropic    Only do the Claude step against an already deployed forwarder.
  unregister-anthropic  Delete the Anthropic destination. Never touches the forwarder.

Normally invoked through:  ./claude.sh [--sync] [--target T] [--dry-run]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "config")
CLAUDE_ENV = os.path.join(CONFIG_DIR, "claude.env")
DEFAULT_TOKEN_URL = "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token"
# Default Lambda name when AWS_LAMBDA_FUNCTION_NAME is unset (the IAM role is "<name>-role").
DEFAULT_LAMBDA_NAME = "wxo-otlp-forwarder-claude"
TARGETS = ("aws", "azure", "docker")
CODE_FILES = ("forwarder.py", "lambda_function.py", "function_app.py", "host.json", "requirements.txt")


class DeployError(Exception):
    """A user-fixable problem (bad config, missing CLI, failed command)."""


# ── Config ───────────────────────────────────────────────────────────────────
def load_env() -> dict:
    """Source config.env or config/{shared,claude}.env with bash and return the resulting environment.

    bash (not a regex parser) so ${VAR} references, quotes and multi-line JSON behave
    exactly as they do when the files are sourced by wire_agent.sh. Values already in
    the process environment win, so a caller can still override anything.
    """
    repo_root = os.path.dirname(os.path.dirname(HERE))
    unified_candidates = [
        os.path.join(repo_root, "config.env"),
        os.path.join(CONFIG_DIR, "config.env"),
        os.path.join(repo_root, ".env"),
    ]
    unified = next((c for c in unified_candidates if os.path.exists(c)), None)

    # Layers, lowest → highest: config.env [claude] < config/shared.env < config/claude.env.
    # Platform-specific files (config/claude.env) take highest precedence.
    merged: dict = {}
    if unified:
        sys.path.insert(0, os.path.join(repo_root, "src", "lib"))
        try:
            from parse_env_section import parse_config
            section = parse_config(unified, "claude")
            for k, v in section.items():
                if not _placeholder(v):
                    merged[k] = v
        except Exception as exc:
            raise DeployError(f"Could not parse {unified}: {exc}")

    files = [os.path.join(CONFIG_DIR, n) for n in ("shared.env", "claude.env")]
    files = [f for f in files if os.path.exists(f)]
    if files:
        script = "set -a\n" + "".join(f'source "{f}"\n' for f in files) + \
            'exec python3 -c "import os, json; print(json.dumps(dict(os.environ)))"'
        res = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                             env={k: v for k, v in os.environ.items()})
        if res.returncode != 0:
            raise DeployError(f"Could not read config files: {res.stderr.strip()}")
        file_env = json.loads(res.stdout)
        for k, v in file_env.items():
            if not _placeholder(v) or _placeholder(merged.get(k, "")):
                merged[k] = v
    # Process env wins over files (lets callers override one value for a single run).
    # With no config files at all (e.g. the integration-test harness) the process env is the only source.
    if not unified and not files:
        return {**merged, **{k: v for k, v in os.environ.items() if v != ""}}
    return {**merged, **{k: v for k, v in os.environ.items() if k in merged and v != ""}}


def _placeholder(v: str) -> bool:
    return not v or "<" in v and ">" in v


CPD_VARS = ("CPD_HOST_URL", "CPD_USERNAME", "CPD_PASSWORD", "CPD_INSTANCE_ID", "CPD_NAMESPACE")


def wxo_mode(env: dict) -> str:
    return "cpd" if (env.get("WXO_DEPLOYMENT_MODE") or "cloud").strip().lower() == "cpd" else "cloud"


def extract_tenant_id(export_url: str) -> str:
    """Extract tenant/instance ID from an OTEL export URL."""
    if export_url:
        m = re.search(r'/instances/([^/?#]+)', export_url)
        if m:
            return m.group(1).strip()
    return ""


def cpd_export_url(env: dict) -> str:
    """Explicit URL wins; otherwise build the CPD agentops traces URL from CPD_*."""
    explicit = env.get("CPD_EXPORT_URL") or env.get("WXO_OTEL_EXPORT_URL") or ""
    if explicit and not _placeholder(explicit):
        return explicit
    host, ns, iid = (env.get(k, "") for k in ("CPD_HOST_URL", "CPD_NAMESPACE", "CPD_INSTANCE_ID"))
    return f"{host.rstrip('/')}/{ns}/instances/{iid}/v1/agentops-v3/traces" if host and ns and iid else ""


def validate(env: dict) -> dict:
    """Check WXO settings; return the parsed agent map."""
    errors = []
    required = CPD_VARS if wxo_mode(env) == "cpd" else ("API_KEY", "WXO_OTEL_EXPORT_URL")
    for var in required:
        if _placeholder(env.get(var, "")):
            errors.append(f"{var} is not set in config.env or config files (WXO_DEPLOYMENT_MODE={wxo_mode(env)})")
    if wxo_mode(env) != "cpd":
        url = env.get("WXO_OTEL_EXPORT_URL", "")
        tid = env.get("WXO_TENANT_ID", "") or extract_tenant_id(url)
        if _placeholder(tid):
            errors.append("Tenant ID could not be extracted from WXO_OTEL_EXPORT_URL (expected '.../instances/<id>/...'). "
                          "Fix the URL, or set WXO_TENANT_ID explicitly.")
    try:
        raw_map = env.get("UNIVERSAL_AGENT_MAP") or env.get("WXO_AGENT_MAP", "") or "{}"
        agent_map = json.loads(raw_map)
        if not isinstance(agent_map, dict) or not agent_map:
            raise ValueError("must be a non-empty JSON object")
    except ValueError as exc:
        errors.append(f"WXO_AGENT_MAP is invalid: {exc}")
        agent_map = {}
    for key, val in agent_map.items():
        agent_id = val if isinstance(val, str) else (val or {}).get("wxo_agent_id") or (val or {}).get("agent_id")
        if _placeholder(str(agent_id or "")):
            errors.append(f"WXO_AGENT_MAP['{key}'] has no real wxo_agent_id")
    if errors:
        raise DeployError("\n".join(f"  ✗ {e}" for e in errors))
    return agent_map


def settings_from(env: dict) -> dict:
    """WXO settings shared by every target (same keys the forwarder reads at runtime)."""
    if wxo_mode(env) == "cpd":
        return {
            "deployment_mode": "cpd",
            "otel_export_url": cpd_export_url(env),
            "environment": env.get("ENVIRONMENT_NAME") or "draft",
            **{k.lower(): env[k] for k in CPD_VARS},
            "cpd_verify_tls": env.get("CPD_VERIFY_TLS") or "false",
        }
    tenant_id = env.get("WXO_TENANT_ID", "") or extract_tenant_id(env.get("WXO_OTEL_EXPORT_URL", ""))
    return {
        "deployment_mode": "cloud",
        "tenant_id": tenant_id,
        "otel_export_url": env.get("WXO_OTEL_EXPORT_URL", ""),
        "environment": env.get("ENVIRONMENT_NAME") or "draft",
        "api_key": env.get("API_KEY", ""),
        "token_url": env.get("TOKEN_URL") or DEFAULT_TOKEN_URL,
    }


def env_vars_from(env: dict) -> dict:
    """Process env vars (Azure app settings / docker env) for the active mode."""
    s = settings_from(env)
    if s["deployment_mode"] == "cpd":
        out = {"WXO_DEPLOYMENT_MODE": "cpd", "WXO_OTEL_EXPORT_URL": s["otel_export_url"],
               "ENVIRONMENT_NAME": s["environment"], "CPD_VERIFY_TLS": s["cpd_verify_tls"]}
        out.update({k: env[k] for k in CPD_VARS})
        return out
    return {"WXO_DEPLOYMENT_MODE": "cloud", "API_KEY": s["api_key"], "TOKEN_URL": s["token_url"],
            "WXO_TENANT_ID": s["tenant_id"], "WXO_OTEL_EXPORT_URL": s["otel_export_url"],
            "ENVIRONMENT_NAME": s["environment"]}


def _run(cmd: list[str], check: bool = True, **kw) -> subprocess.CompletedProcess:
    if not shutil.which(cmd[0]):
        raise DeployError(f"'{cmd[0]}' CLI not found. Install it and re-run.")
    res = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if check and res.returncode != 0:
        raise DeployError(f"{' '.join(cmd[:4])} ... failed:\n{(res.stderr or res.stdout).strip()}")
    return res


def _health(url: str, tries: int = 6) -> bool:
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(3)
    return False


def _diff(old: dict, new: dict) -> str:
    added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
    kept = len(set(new) & set(old))
    return f"{len(new)} agent(s): {len(added)} added {added}, {len(removed)} removed {removed}, {kept} kept/updated"


def _agents(agent_map: dict) -> None:
    for key, val in agent_map.items():
        aid = val if isinstance(val, str) else val.get("wxo_agent_id") or val.get("agent_id")
        print(f"      {key!r:44s} → {aid}")


# ── AWS ──────────────────────────────────────────────────────────────────────
def _aws_ctl():
    sys.path.insert(0, HERE)
    import forwarder_ctl  # noqa: E402
    return forwarder_ctl


def aws_sync(env: dict, agent_map: dict, dry_run: bool) -> None:
    ctl = _aws_ctl()
    region = env.get("AWS_REGION", "us-east-1")
    settings_param = env.get("SSM_SETTINGS_PATH", "/wxo-agent/settings")
    map_param = env.get("SSM_AGENT_MAP_PATH", "/wxo-agent/agent_map")
    ctl.SETTINGS_PARAM, ctl.AGENT_MAP_PARAM = settings_param, map_param

    existing = ctl.ssm_get(map_param, region)
    print(f"  SSM {map_param}: {_diff(existing, agent_map)}")
    if dry_run:
        print("  [dry-run] would write SSM settings + agent map (map is replaced, not merged)")
        return
    current = ctl.ssm_get(settings_param, region)
    current.update(settings_from(env))
    if env.get("FORWARDER_AUTH_TOKEN"):                  # optional; unset leaves any stored token as is
        current["auth_token"] = env["FORWARDER_AUTH_TOKEN"]
    ctl.ssm_put(settings_param, current, region)
    ctl.ssm_put(map_param, agent_map, region)
    print(f"  ✓ Wrote {settings_param} and {map_param} (Lambda picks it up within ~60 s)")
    _agents(agent_map)


def lambda_name(env: dict) -> str:
    """Lambda function name: AWS_LAMBDA_FUNCTION_NAME if set, else the built-in default."""
    name = (env.get("AWS_LAMBDA_FUNCTION_NAME") or "").strip()
    return DEFAULT_LAMBDA_NAME if _placeholder(name) else name


def aws_deploy(env: dict, agent_map: dict, dry_run: bool) -> str:
    ctl = _aws_ctl()
    name = lambda_name(env)
    region = env.get("AWS_REGION", "us-east-1")
    ctl.SETTINGS_PARAM = env.get("SSM_SETTINGS_PATH", "/wxo-agent/settings")
    ctl.AGENT_MAP_PARAM = env.get("SSM_AGENT_MAP_PATH", "/wxo-agent/agent_map")
    print(f"  Lambda {name} in {region}")
    if dry_run:
        exists = bool(ctl.aws(["lambda", "get-function", "--function-name", name], region, check=False))
        print(f"  [dry-run] would {'update' if exists else 'create'} the Lambda, then sync SSM config")
        aws_sync(env, agent_map, dry_run=True)
        return ""

    class A:  # argparse-like namespace for forwarder_ctl.cmd_deploy
        function_name, region = name, env.get("AWS_REGION", "us-east-1")
    ctl.cmd_deploy(A)
    aws_sync(env, agent_map, dry_run=False)
    url = json.loads(ctl.aws(["lambda", "get-function-url-config", "--function-name", name],
                             region))["FunctionUrl"].rstrip("/")
    return url


# ── Azure ────────────────────────────────────────────────────────────────────
def _az_names(env: dict) -> tuple[str, str]:
    app = env.get("AZURE_FUNCTION_APP_NAME", "wxo-otlp-forwarder")
    rg = env.get("AZURE_RESOURCE_GROUP", "wxo-tracing-rg")
    return app, rg


def _az_exists(app: str, rg: str) -> bool:
    return _run(["az", "functionapp", "show", "-n", app, "-g", rg, "-o", "none"], check=False).returncode == 0


def _azure_app_settings(env: dict, agent_map: dict) -> list[dict]:
    values = {
        **env_vars_from(env),
        "WXO_AGENT_MAP": json.dumps(agent_map, separators=(",", ":")),
        "SCM_DO_BUILD_DURING_DEPLOYMENT": "true",
    }
    if env.get("FORWARDER_AUTH_TOKEN"):
        values["FORWARDER_AUTH_TOKEN"] = env["FORWARDER_AUTH_TOKEN"]
    return [{"name": k, "value": v, "slotSetting": False} for k, v in values.items()]


def azure_sync(env: dict, agent_map: dict, dry_run: bool) -> None:
    app, rg = _az_names(env)
    print(f"  Function App {app} (resource group {rg})")
    if dry_run:
        print("  [dry-run] would set App Settings (API_KEY, WXO_*, WXO_AGENT_MAP, ...) — app restarts")
        return
    if not _az_exists(app, rg):
        raise DeployError(f"Function App '{app}' not found in '{rg}'. Run --deploy first.")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        os.chmod(f.name, 0o600)
        json.dump(_azure_app_settings(env, agent_map), f)
    try:
        _run(["az", "functionapp", "config", "appsettings", "set", "-n", app, "-g", rg,
              "--settings", f"@{f.name}", "-o", "none"])
    finally:
        os.remove(f.name)
    print("  ✓ App Settings updated (the app restarts to apply them)")
    _agents(agent_map)


def azure_deploy(env: dict, agent_map: dict, dry_run: bool) -> str:
    app, rg = _az_names(env)
    location, storage = env.get("AZURE_LOCATION", ""), env.get("AZURE_STORAGE_ACCOUNT", "")
    print(f"  Function App {app} (resource group {rg})")
    if dry_run:
        exists = shutil.which("az") and _az_exists(app, rg)
        print(f"  [dry-run] app {'exists: would publish code' if exists else 'missing: would create it, then publish code'}")
        azure_sync(env, agent_map, dry_run=True)
        return ""
    if not _az_exists(app, rg):
        if not location or not storage:
            raise DeployError(f"Function App '{app}' does not exist. To create it set AZURE_LOCATION and "
                              f"AZURE_STORAGE_ACCOUNT in config/claude.env.")
        print("  Creating missing resources (resource group / storage account / Function App) ...")
        # Reuse an existing group/storage account: they may live in another region than the
        # Function App, and `create` with a different location fails.
        if _run(["az", "group", "show", "-n", rg, "-o", "none"], check=False).returncode != 0:
            _run(["az", "group", "create", "-n", rg, "-l", location, "-o", "none"])
        if _run(["az", "storage", "account", "show", "-n", storage, "-g", rg, "-o", "none"],
                check=False).returncode != 0:
            _run(["az", "storage", "account", "create", "-n", storage, "-g", rg, "-l", location,
                  "--sku", "Standard_LRS", "-o", "none"])
        _run(["az", "functionapp", "create", "-n", app, "-g", rg, "--storage-account", storage,
              "--consumption-plan-location", location, "--runtime", "python", "--runtime-version", "3.11",
              "--functions-version", "4", "--os-type", "Linux", "-o", "none"])

    # Settings first so the freshly published code starts with its config.
    azure_sync(env, agent_map, dry_run=False)
    stage = tempfile.mkdtemp(prefix="wxo-fwd-")
    try:
        for fname in ("forwarder.py", "function_app.py", "host.json", "requirements.txt"):
            shutil.copy(os.path.join(HERE, fname), stage)
        print("  Publishing code ...")
        if shutil.which("func"):
            _run(["func", "azure", "functionapp", "publish", app, "--python"], cwd=stage)
        else:
            zip_base = os.path.join(stage, "app")
            shutil.make_archive(zip_base, "zip", stage)
            _run(["az", "functionapp", "deployment", "source", "config-zip", "-g", rg, "-n", app,
                  "--src", zip_base + ".zip", "-o", "none"])
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    host = _run(["az", "functionapp", "show", "-n", app, "-g", rg, "--query", "defaultHostName", "-o", "tsv"]).stdout.strip()
    return f"https://{host}/api"


# ── Docker ───────────────────────────────────────────────────────────────────
def _docker_names(env: dict) -> tuple[str, str, str]:
    return (env.get("DOCKER_IMAGE_NAME", "wxo-otlp-forwarder"),
            env.get("DOCKER_CONTAINER_NAME", "wxo-otlp-forwarder"),
            env.get("OTLP_PORT", "4318"))


def docker_sync(env: dict, agent_map: dict, dry_run: bool) -> None:
    image, container, port = _docker_names(env)
    print(f"  Container {container} (image {image}, host port {port})")
    if dry_run:
        print("  [dry-run] would recreate the container with the new env")
        return
    if _run(["docker", "image", "inspect", image], check=False).returncode != 0:
        raise DeployError(f"Image '{image}' not found. Run --deploy first.")
    values = {
        "PORT": "4318", **env_vars_from(env),
        "WXO_AGENT_MAP": json.dumps(agent_map, separators=(",", ":")),   # one line: --env-file is line based
    }
    if env.get("FORWARDER_AUTH_TOKEN"):
        values["FORWARDER_AUTH_TOKEN"] = env["FORWARDER_AUTH_TOKEN"]
    # env-file (0600, deleted right after) keeps secrets out of `ps` output.
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        os.chmod(f.name, 0o600)
        f.write("".join(f"{k}={v}\n" for k, v in values.items()))
    try:
        _run(["docker", "rm", "-f", container], check=False)
        _run(["docker", "run", "-d", "--name", container, "--restart", "unless-stopped",
              "-p", f"{port}:4318", "--env-file", f.name, image])
    finally:
        os.remove(f.name)
    print(f"  ✓ Container recreated with {len(agent_map)} agent(s)")
    _agents(agent_map)


def docker_deploy(env: dict, agent_map: dict, dry_run: bool) -> str:
    image, container, port = _docker_names(env)
    print(f"  Image {image}, container {container}, host port {port}")
    if dry_run:
        print("  [dry-run] would build the image and (re)start the container")
        docker_sync(env, agent_map, dry_run=True)
        return ""
    print("  Building image ...")
    _run(["docker", "build", "-t", image, "-f", os.path.join(HERE, "Dockerfile"), os.path.dirname(HERE)])
    docker_sync(env, agent_map, dry_run=False)
    return f"http://localhost:{port}"


# ── Entry points ─────────────────────────────────────────────────────────────
_SYNC = {"aws": aws_sync, "azure": azure_sync, "docker": docker_sync}
_DEPLOY = {"aws": aws_deploy, "azure": azure_deploy, "docker": docker_deploy}
_HEALTH = {"aws": "/health", "azure": "/health", "docker": "/health"}


def _choose_target() -> str:
    """Ask where to deploy; only used when no target is configured and a terminal is attached."""
    print("\n  Where should the forwarder be deployed?")
    print("    1) aws     AWS Lambda + Function URL")
    print("    2) azure   Azure Function App")
    print("    3) docker  Local Docker container")
    choice = input("  Enter choice [1-3]: ").strip().lower()
    return {"1": "aws", "2": "azure", "3": "docker"}.get(choice, choice)


def run(action: str, target: str | None = None, dry_run: bool = False,
        claude: bool = False, content_mode: str | None = None) -> int:
    """action: 'deploy' or 'sync'. With claude=True a successful deploy is followed by the Claude step.

    Returns a process exit code.
    """
    try:
        env = load_env()
        target = (target or env.get("FORWARDER_TARGET", "")).strip().lower()
        if not target and sys.stdin.isatty():
            target = _choose_target()
        if target not in TARGETS:
            raise DeployError(f"FORWARDER_TARGET must be one of {', '.join(TARGETS)} "
                              f"(set it in config/claude.env or pass --target). Got: {target or '(empty)'}")
        agent_map = validate(env)

        print(f"\n  {action.upper()} → {target}{'  [dry-run]' if dry_run else ''}")
        if wxo_mode(env) == "cpd":
            print(f"  WXO mode     : cpd ({env['CPD_HOST_URL']}, instance {env['CPD_INSTANCE_ID']})")
        else:
            tenant_disp = env.get("WXO_TENANT_ID", "") or extract_tenant_id(env.get("WXO_OTEL_EXPORT_URL", ""))
            print(f"  WXO tenant   : {tenant_disp}")
        print(f"  Environment  : {env.get('ENVIRONMENT_NAME') or 'draft'}")
        print(f"  Agents       : {len(agent_map)}")
        print(f"  Caller auth  : {'ON (FORWARDER_AUTH_TOKEN)' if env.get('FORWARDER_AUTH_TOKEN') else 'off (optional)'}")
        if target == "aws":
            # Set automatically (config value, else default) so every helper in this run sees the same name.
            src = "default" if _placeholder((env.get("AWS_LAMBDA_FUNCTION_NAME") or "").strip()) else "from config"
            os.environ["AWS_LAMBDA_FUNCTION_NAME"] = env["AWS_LAMBDA_FUNCTION_NAME"] = lambda_name(env)
            print(f"  Lambda name  : {env['AWS_LAMBDA_FUNCTION_NAME']}  ({src})")
        # Apply the target's own env (region, profile, keys) to the CLIs we shell out to.
        for k in ("AWS_REGION", "AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"):
            if env.get(k):
                os.environ[k] = env[k]
        os.environ.setdefault("AWS_DEFAULT_REGION", env.get("AWS_REGION", "us-east-1"))
        print()

        url = ""
        if action == "deploy":
            url = _DEPLOY[target](env, agent_map, dry_run)
            if url and not dry_run:
                ok = _health(url + _HEALTH[target])
                print(f"\n  Forwarder endpoint : {url}")
                print(f"  Health check       : {'ok' if ok else 'no answer yet (cold start? retry in a minute)'}")
        else:
            _SYNC[target](env, agent_map, dry_run)
        print("\n  ✓ Done." if not dry_run else "\n  ✓ Dry-run complete (nothing changed).")
        if action == "deploy" and claude:
            return _connect_claude(env, target, url, dry_run, content_mode)
        return 0
    except DeployError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1


def _connect_claude(env: dict, target: str, url: str, dry_run: bool, content_mode: str | None) -> int:
    """Point Claude's OTel destination at the freshly deployed forwarder.

    With an Anthropic admin key the destination is created/updated automatically; without one
    (or for a non-public URL) the endpoint is printed for the user to set in their Claude OTel settings.
    """
    key = _cfg(env, "ANTHROPIC_ADMIN_API_KEY")
    has_key = bool(key) and not _placeholder(key)
    token = _cfg(env, "FORWARDER_AUTH_TOKEN")
    if has_key and (dry_run or url.startswith("https://")):
        return anthropic_destination("register", target, dry_run, content_mode,
                                     url=url or "(known after deploy)")

    print("\n  ── Claude (Anthropic) OTel setup " + "─" * 30)
    if has_key:
        print(f"  ANTHROPIC_ADMIN_API_KEY is set, but {url or 'the forwarder'} is not a public https:// URL,")
        print("  which Anthropic requires. Not updating Anthropic.")
    else:
        print("  ANTHROPIC_ADMIN_API_KEY is not set, so Claude was not updated automatically.")
    print("  Set this endpoint in your Claude OTel (OpenTelemetry) settings:")
    print(f"    Endpoint : {url or '(deploy first to get the forwarder URL)'}")
    print("    Protocol : http/protobuf  (http/json also works)")
    if token:
        print(f"    Header   : Authorization: Bearer {token}")
    print("  To have this script do it next time, set ANTHROPIC_ADMIN_API_KEY and ANTHROPIC_WORKSPACE_ID.")
    return 0


# ── Anthropic (Claude) telemetry destination ─────────────────────────────────
# Registers the forwarder URL as the org's OTel destination in Anthropic, so Anthropic
# pushes Claude traces to it. Only writes to Anthropic; the forwarder is not changed.
# Display name in the Anthropic Console, and the key used to find/update/delete our destination.
# Override with ANTHROPIC_DESTINATION_NAME; changing it later makes the next run create a new one.
ANTHROPIC_DEST_NAME = "watsonx Orchestrate - Agent Analytics (OTLP forwarder)"


def _cfg(env: dict, name: str) -> str:
    """Shell environment wins (keeps the admin key out of tracked files), then config."""
    return (os.environ.get(name) or env.get(name) or "").strip()


def _forwarder_url(env: dict, target: str) -> str:
    """Public base URL of the deployed forwarder (no /v1/traces; Anthropic appends it)."""
    url = _cfg(env, "FORWARDER_URL")
    if not url:
        if target == "aws":
            name = lambda_name(env)
            out = _aws_ctl().aws(["lambda", "get-function-url-config", "--function-name", name],
                                 env.get("AWS_REGION", "us-east-1"), check=False)
            url = json.loads(out)["FunctionUrl"] if out else ""
        elif target == "azure":
            app, rg = _az_names(env)
            host = _run(["az", "functionapp", "show", "-n", app, "-g", rg,
                         "--query", "defaultHostName", "-o", "tsv"]).stdout.strip()
            url = f"https://{host}/api" if host else ""
    url = url.rstrip("/")
    if url.endswith("/v1/traces"):
        url = url[: -len("/v1/traces")]
    if not url.startswith("https://"):
        raise DeployError("Anthropic needs a public https:// forwarder URL (not localhost/IP).\n"
                          "  Set FORWARDER_URL, or use --target aws|azure.")
    return url


def anthropic_destination(action: str, target: str | None = None, dry_run: bool = False,
                          content_mode: str | None = None, url: str | None = None) -> int:
    """action: 'register' (create or update) or 'unregister' (delete).

    url: forwarder base URL when the caller just deployed it; otherwise it is looked up from the target.
    """
    try:
        env = load_env()
        target = (target or env.get("FORWARDER_TARGET", "")).strip().lower()
        if target not in TARGETS:
            raise DeployError(f"FORWARDER_TARGET must be one of {', '.join(TARGETS)} (or pass --target).")
        for k in ("AWS_REGION", "AWS_PROFILE"):
            if env.get(k):
                os.environ[k] = env[k]
        os.environ.setdefault("AWS_DEFAULT_REGION", env.get("AWS_REGION", "us-east-1"))

        dest_name = _cfg(env, "ANTHROPIC_DESTINATION_NAME") or ANTHROPIC_DEST_NAME
        ws_raw = _cfg(env, "ANTHROPIC_WORKSPACE_ID")
        if not ws_raw or _placeholder(ws_raw):
            raise DeployError("ANTHROPIC_WORKSPACE_ID is not set (wrkspc_... IDs, comma-separated, or 'all').")
        workspaces = ({"type": "all"} if ws_raw.lower() == "all"
                      else {"type": "include", "workspace_ids": [w.strip() for w in ws_raw.split(",") if w.strip()]})
        token = _cfg(env, "FORWARDER_AUTH_TOKEN")
        if action != "register":
            url = ""
        elif url is None:
            url = _forwarder_url(env, target)

        # Content mode: 'content' (full payload) or 'metadata_only'
        cm_raw = (content_mode or _cfg(env, "ANTHROPIC_CONTENT_MODE") or "content").lower().strip()
        cm_val = "metadata_only" if "meta" in cm_raw else "content"

        print(f"\n  {action.upper()}-ANTHROPIC{'  [dry-run]' if dry_run else ''}")
        print(f"  Name          : {dest_name}")
        print(f"  Forwarder URL : {url or '(n/a)'}")
        print(f"  Workspaces    : {ws_raw}")
        print(f"  Content Mode  : {cm_val} ({'full prompt & completions' if cm_val == 'content' else 'metadata only'})")
        print(f"  Auth header   : {'Authorization: Bearer ***' if token else 'none (FORWARDER_AUTH_TOKEN unset)'}")
        if dry_run:
            print("\n  ✓ Dry-run complete (nothing sent to Anthropic).")
            return 0

        key = _cfg(env, "ANTHROPIC_ADMIN_API_KEY")
        if not key or _placeholder(key):
            raise DeployError("ANTHROPIC_ADMIN_API_KEY is not set. Export it in your shell rather than a file:\n"
                              "    export ANTHROPIC_ADMIN_API_KEY=sk-ant-admin...")
        # Private dependency dir: avoids PEP 668 "externally-managed-environment"
        # errors and never touches the system/Homebrew Python.
        deps_dir = os.path.join(os.path.expanduser("~"), ".cache", "wxo-external-agent-tracing", "pydeps")
        if deps_dir not in sys.path:
            sys.path.insert(0, deps_dir)
        try:
            from anthropic import Anthropic
        except ImportError:
            print(f"  Installing the 'anthropic' package into {deps_dir} ...")
            res = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "--target", deps_dir, "anthropic"],
                                 capture_output=True, text=True)
            if res.returncode != 0:
                raise DeployError("Could not install the 'anthropic' package. Install it manually:\n"
                                  "    python3 -m venv .venv && . .venv/bin/activate && pip install -U anthropic\n"
                                  + (res.stderr or res.stdout).strip())
            import importlib
            importlib.invalidate_caches()
            from anthropic import Anthropic
        dests = Anthropic(api_key=key).beta.organization.telemetry_destinations
        existing = next((d for d in dests.list(limit=100) if d.display_name == dest_name), None)

        if action == "unregister":
            if existing:
                dests.delete(existing.id)
                print(f"  ✓ Deleted destination {existing.id}")
            else:
                print("  Nothing to remove: no destination with that name.")
            return 0

        params: dict[str, Any] = {
            "endpoint_url": url,
            "workspaces": workspaces,
            "traces": {"content_mode": cm_val, "enabled": True},
        }
        if token:                      # header values are write-only; omitted = keep the stored one
            params["headers"] = {"authorization": f"Bearer {token}"}
        if existing:
            dest = dests.update(existing.id, **params)
            print(f"  ✓ Updated destination {dest.id}")
        else:
            dest = dests.create(display_name=dest_name, **params)
            print(f"  ✓ Registered destination {dest.id}")
        result = dests.test(dest.id).result
        if result.type == "success":
            print("  ✓ Anthropic test span delivered (forwarder answered 2xx)")
            return 0
        print(f"  ✗ Anthropic test delivery failed: {result.error}", file=sys.stderr)
        return 1
    except DeployError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # Anthropic API errors: show the message, never the key
        print(f"\n  ✗ Anthropic API error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["deploy", "sync", "register-anthropic", "unregister-anthropic"])
    p.add_argument("--target", choices=TARGETS)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--claude", action="store_true",
                   help="with deploy: after deploying, connect Claude (auto-register if ANTHROPIC_ADMIN_API_KEY is set, "
                        "otherwise print the endpoint to set in Claude's OTel settings)")
    p.add_argument("--content-mode", choices=["content", "metadata_only", "full"],
                   help="Claude trace content mode: 'content' (full prompt/completions) or 'metadata_only'")
    a = p.parse_args()
    if a.action.endswith("-anthropic"):
        sys.exit(anthropic_destination(a.action.split("-")[0], a.target, a.dry_run, a.content_mode))
    sys.exit(run(a.action, a.target, a.dry_run, a.claude, a.content_mode))
