#!/usr/bin/env python3
"""
forwarder/forwarder_ctl.py
==========================
One CLI to run the WXO OTLP Forwarder on AWS Lambda.

  1. deploy   Deploy / update the forwarder as a Lambda (Function URL)
  2. wxo      Set WXO details (tenant, export URL, API key, environment)
  3. agent    Map platform agents -> WXO agents (add / remove / list / import)
  4. auth     Optional: manage the token callers must present (off by default)

Settings live in AWS SSM Parameter Store, so changes (2-4) take effect within ~60s
with NO redeploy.

Examples:
  ./src/forwarder/forwarder_ctl.py deploy --region us-east-1
  ./src/forwarder/forwarder_ctl.py wxo set --tenant-id T --export-url U --api-key K --environment live
  ./src/forwarder/forwarder_ctl.py agent add customer-bot 61e315a1-0749-49fc-9972-fd92068fd881 --display-name "Support"
  ./src/forwarder/forwarder_ctl.py agent import config/agent_map.json
  ./src/forwarder/forwarder_ctl.py wxo set          # no flags: reads WXO_TENANT_ID, WXO_OTEL_EXPORT_URL,
                                                # ENVIRONMENT_NAME, API_KEY, TOKEN_URL from the environment
  ./src/forwarder/forwarder_ctl.py agent import     # no file: reads WXO_AGENT_MAP from the environment
  ./src/forwarder/forwarder_ctl.py agent list

Requires: AWS CLI authenticated.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import secrets
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PARAM = os.environ.get("SSM_SETTINGS_PATH", "/wxo-agent/settings")
AGENT_MAP_PARAM = os.environ.get("SSM_AGENT_MAP_PATH", "/wxo-agent/agent_map")
DEFAULT_TOKEN_URL = "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token"


# ── AWS helpers ──────────────────────────────────────────────────────────────
def aws(args: list[str], region: str, check: bool = True) -> str:
    cmd = ["aws", *args, "--region", region, "--output", "json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        sys.exit(f"✗ {' '.join(cmd[:4])}...\n{res.stderr.strip()}")
    return res.stdout if res.returncode == 0 else ""


def ssm_get(name: str, region: str) -> dict:
    out = aws(["ssm", "get-parameter", "--name", name, "--with-decryption"], region, check=False)
    return json.loads(json.loads(out)["Parameter"]["Value"]) if out else {}


def ssm_put(name: str, value: dict, region: str) -> None:
    aws(["ssm", "put-parameter", "--name", name, "--type", "SecureString",
         "--tier", "Intelligent-Tiering", "--overwrite", "--value", json.dumps(value)], region)


# ── 1. deploy ────────────────────────────────────────────────────────────────
def build_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ("forwarder.py", "lambda_function.py"):
            z.write(os.path.join(HERE, f), f)
    return buf.getvalue()


def cmd_deploy(a) -> None:
    name, region = a.function_name, a.region
    role_name = f"{name}-role"
    env = json.dumps({"Variables": {
        "SSM_SETTINGS_PATH": SETTINGS_PARAM,
        "SSM_AGENT_MAP_PATH": AGENT_MAP_PARAM,
    }})
    zip_path = os.path.join(HERE, ".function.zip")
    with open(zip_path, "wb") as f:
        f.write(build_zip())
    zip_arg = f"fileb://{zip_path}"

    try:
        exists = bool(aws(["lambda", "get-function", "--function-name", name], region, check=False))
        if exists:
            print(f"Updating Lambda '{name}'...")
            aws(["lambda", "update-function-code", "--function-name", name, "--zip-file", zip_arg], region)
            aws(["lambda", "wait", "function-updated", "--function-name", name], region, check=False)
            aws(["lambda", "update-function-configuration", "--function-name", name, "--environment", env], region)
        else:
            print(f"Creating IAM role '{role_name}'...")
            trust = json.dumps({"Version": "2012-10-17", "Statement": [{
                "Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]})
            out = aws(["iam", "get-role", "--role-name", role_name], region, check=False)
            if not out:
                out = aws(["iam", "create-role", "--role-name", role_name, "--assume-role-policy-document", trust], region)
                time.sleep(10)  # IAM propagation
            role_arn = json.loads(out)["Role"]["Arn"]
            aws(["iam", "attach-role-policy", "--role-name", role_name, "--policy-arn",
                 "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"], region)
            ssm_policy = json.dumps({"Version": "2012-10-17", "Statement": [{
                "Effect": "Allow", "Action": ["ssm:GetParameter"],
                "Resource": [f"arn:aws:ssm:{region}:*:parameter{p}" for p in (SETTINGS_PARAM, AGENT_MAP_PARAM)]}]})
            aws(["iam", "put-role-policy", "--role-name", role_name, "--policy-name", "wxo-forwarder-ssm",
                 "--policy-document", ssm_policy], region)

            print(f"Creating Lambda '{name}'...")
            aws(["lambda", "create-function", "--function-name", name, "--runtime", "python3.12",
                 "--handler", "lambda_function.lambda_handler", "--role", role_arn, "--timeout", "30",
                 "--memory-size", "256", "--zip-file", zip_arg, "--environment", env], region)
            aws(["lambda", "wait", "function-active-v2", "--function-name", name], region, check=False)

            aws(["lambda", "create-function-url-config", "--function-name", name, "--auth-type", "NONE"], region)
            aws(["lambda", "add-permission", "--function-name", name, "--statement-id", "FunctionURLAllowPublic",
                 "--action", "lambda:InvokeFunctionUrl", "--principal", "*",
                 "--function-url-auth-type", "NONE"], region)
            aws(["lambda", "add-permission", "--function-name", name, "--statement-id", "FunctionURLInvoke",
                 "--action", "lambda:InvokeFunction", "--principal", "*", "--invoked-via-function-url"],
                region, check=False)
    finally:
        os.remove(zip_path)

    url = json.loads(aws(["lambda", "get-function-url-config", "--function-name", name], region))["FunctionUrl"]
    endpoint = url.rstrip('/')
    print(f"\n✓ Forwarder deployed.")
    print(f"  Endpoint: {endpoint}")
    print("  Auth: optional, off by default. Enable with FORWARDER_AUTH_TOKEN in config/claude.env, "
          "or: forwarder_ctl.py auth rotate")
    print("  Next: 'wxo set', 'agent add'  (no redeploy needed)")


# ── auth ─────────────────────────────────────────────────────────────────────
def cmd_auth(a) -> None:
    s = ssm_get(SETTINGS_PARAM, a.region)
    if a.action == "rotate":
        s["auth_token"] = secrets.token_urlsafe(32)
    elif a.action == "set":
        s["auth_token"] = a.token
    elif a.action == "disable":
        s.pop("auth_token", None)
    if a.action != "show":
        ssm_put(SETTINGS_PARAM, s, a.region)
    token = s.get("auth_token")
    print(f"Auth token: {token}" if token else "Auth DISABLED — anyone with the URL can post traces.")


# ── 3. wxo ───────────────────────────────────────────────────────────────────
def cmd_wxo(a) -> None:
    s = ssm_get(SETTINGS_PARAM, a.region)
    if a.action == "set":
        # Flags win; otherwise read the same env vars used in config/claude.env
        env = os.environ.get
        updates = {"tenant_id": a.tenant_id or env("WXO_TENANT_ID"),
                   "otel_export_url": a.export_url or env("WXO_OTEL_EXPORT_URL"),
                   "api_key": a.api_key or env("API_KEY"),
                   "token_url": a.token_url or env("TOKEN_URL"),
                   "environment": a.environment or env("ENVIRONMENT_NAME"),
                   # CPD mode (WXO_DEPLOYMENT_MODE=cpd): username/password login, no tenant / API key
                   "deployment_mode": env("WXO_DEPLOYMENT_MODE"),
                   "cpd_host_url": env("CPD_HOST_URL"), "cpd_username": env("CPD_USERNAME"),
                   "cpd_password": env("CPD_PASSWORD"), "cpd_instance_id": env("CPD_INSTANCE_ID"),
                   "cpd_namespace": env("CPD_NAMESPACE"), "cpd_verify_tls": env("CPD_VERIFY_TLS")}
        s.update({k: v for k, v in updates.items() if v})
        s.setdefault("token_url", DEFAULT_TOKEN_URL)
        ssm_put(SETTINGS_PARAM, s, a.region)
        print("✓ WXO details saved.")
    shown = {k: ("****" if k in ("api_key", "auth_token", "cpd_password") and v else v) for k, v in s.items()}
    print(json.dumps(shown, indent=2))


# ── 4. agent ─────────────────────────────────────────────────────────────────
def cmd_agent(a) -> None:
    m = ssm_get(AGENT_MAP_PARAM, a.region)
    if a.action == "add":
        entry = {"wxo_agent_id": a.wxo_agent_id}
        if a.display_name:
            entry["wxo_display_name"] = a.display_name
        if a.environment:
            entry["environment"] = a.environment
        m[a.platform_agent] = entry
    elif a.action == "remove":
        m.pop(a.platform_agent, None)
    elif a.action == "import":
        if a.file:
            with open(a.file, encoding="utf-8") as f:
                m.update(json.load(f))
        else:  # no file given: read WXO_AGENT_MAP from the environment
            m.update(json.loads(os.environ["WXO_AGENT_MAP"]))
    if a.action != "list":
        ssm_put(AGENT_MAP_PARAM, m, a.region)
    print(f"Agent mappings ({len(m)}):")
    for k, v in m.items():
        v = {"wxo_agent_id": v} if isinstance(v, str) else v
        print(f"  {k} -> {v.get('wxo_agent_id') or v.get('agent_id')}")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser(description="WXO OTLP Forwarder control CLI")
    p.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    # --region is also accepted after the subcommand (SUPPRESS keeps the top-level value if omitted)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--region", default=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("deploy", parents=[common], help="Deploy/update the forwarder Lambda")
    d.add_argument("--function-name", default=os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or "wxo-otlp-forwarder-claude")
    d.set_defaults(fn=cmd_deploy)

    t = sub.add_parser("auth", parents=[common], help="Manage the token callers must present")
    t.add_argument("action", choices=["show", "rotate", "set", "disable"])
    t.add_argument("token", nargs="?", help="Token value (for set)")
    t.set_defaults(fn=cmd_auth)

    w = sub.add_parser("wxo", parents=[common], help="Set/show WXO details")
    w.add_argument("action", choices=["set", "show"])
    w.add_argument("--tenant-id")
    w.add_argument("--export-url")
    w.add_argument("--api-key")
    w.add_argument("--token-url")
    w.add_argument("--environment", choices=["draft", "live"])
    w.set_defaults(fn=cmd_wxo)

    g = sub.add_parser("agent", parents=[common], help="Map platform agents to WXO agents")
    g.add_argument("action", choices=["add", "remove", "list", "import"])
    g.add_argument("platform_agent", nargs="?", help="Platform agent id / service.name / model name")
    g.add_argument("wxo_agent_id", nargs="?", help="WXO agent UUID (for add)")
    g.add_argument("--display-name")
    g.add_argument("--environment", choices=["draft", "live"])
    g.add_argument("--file", help="JSON file (for import)")
    g.set_defaults(fn=cmd_agent)

    a = p.parse_args()
    if a.cmd == "auth" and a.action == "set" and not a.token:
        p.error("auth set <token>")
    if a.cmd == "agent":
        if a.action == "add" and not (a.platform_agent and a.wxo_agent_id):
            p.error("agent add <platform_agent> <wxo_agent_id>")
        if a.action == "remove" and not a.platform_agent:
            p.error("agent remove <platform_agent>")
        if a.action == "import":
            a.file = a.file or a.platform_agent
            if not a.file and not os.environ.get("WXO_AGENT_MAP"):
                p.error("agent import <file.json>, or export WXO_AGENT_MAP='{...}'")
    a.fn(a)


if __name__ == "__main__":
    main()
