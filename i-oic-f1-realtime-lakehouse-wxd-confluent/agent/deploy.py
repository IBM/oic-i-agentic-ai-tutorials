"""Deploy the F1 Race Analyst to watsonx Orchestrate with the ADK.

    python agent/deploy.py

What it does, in order (each step prints the ADK command it runs):
1. Activates your Orchestrate environment.
2. Stores the watsonx.data MCP credentials in a key-value connection. Each key becomes an
   HTTP header on every call Orchestrate makes to the MCP server.
3. Adds the watsonx.data MCP server as a remote toolkit, importing only read-only tools.
4. Imports the knowledge base.
5. Renders the agent YAML from .env, imports it and deploys it to the live environment.
"""

import base64
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from lakehouse import config  # noqa: E402

CONNECTION = "wxd_mcp"
TOOLKIT = "watsonx_data"
TOOLS = ["watsonxdata-list-schemas", "watsonxdata-list-tables", "watsonxdata-describe-table",
         "watsonxdata-execute-select"]
ORCH = os.getenv("ORCH", str(HERE.parent / ".venv" / "bin" / "orchestrate"))


def run(args: list[str], secret: str | None = None, check: bool = True) -> int:
    shown = " ".join(shlex.quote(a) for a in args)
    print("$ orchestrate " + (shown.replace(secret, "****") if secret else shown))
    rc = subprocess.run([ORCH, *args]).returncode
    if check and rc:
        sys.exit(rc)
    return rc


def must_exist(kind: str, name: str) -> None:
    """The ADK can log an import error and still exit 0, so check the result explicitly."""
    out = subprocess.run([ORCH, kind, "list"], capture_output=True, text=True,
                         env={**os.environ, "COLUMNS": "300"}).stdout
    if name not in out:
        sys.exit(f"{kind} '{name}' was not created; see the error above")


def listed(kind: str, name: str) -> bool:
    out = subprocess.run([ORCH, kind, "list"], capture_output=True, text=True,
                         env={**os.environ, "COLUMNS": "300"}).stdout
    return name in out


def main() -> None:
    s = config.load()
    env_name = os.getenv("WXO_ENV_NAME", "f1-tutorial")
    url, key = os.environ["WXO_INSTANCE_URL"], os.environ["WXO_API_KEY"]

    if not listed("env", env_name):
        run(["env", "add", "-n", env_name, "-u", url, "--type", "ibm_iam"])
    run(["env", "activate", env_name, "--api-key", key], secret=key)

    basic = "Basic " + base64.b64encode(f"{s.wxd_user}:{s.api_key}".encode()).decode()
    if not listed("connections", CONNECTION):
        run(["connections", "add", "-a", CONNECTION])
    for env in ("draft", "live"):
        run(["connections", "configure", "-a", CONNECTION, "--env", env, "--type", "team", "--kind", "key_value"],
            check=False)
        run(["connections", "set-credentials", "-a", CONNECTION, "--env", env,
             "-e", f"authorization={basic}", "-e", f"authinstanceid={s.wxd_crn}"], secret=basic)

    run(["toolkits", "remove", "-n", TOOLKIT], check=False)
    run(["toolkits", "add", "--kind", "mcp", "--name", TOOLKIT,
         "--description", "IBM watsonx.data: discover schemas and run read-only Presto SQL",
         "--url", f"{s.wxd_host}/api/v1/watsonxdata/mcp", "--transport", "streamable_http",
         "--tools", ",".join(TOOLS), "--app-id", CONNECTION])

    run(["knowledge-bases", "import", "-f", str(HERE / "knowledge_base" / "f1_lakehouse_guide.yaml")])
    must_exist("knowledge-bases", "f1_lakehouse_guide")

    rendered = (HERE / "f1_race_analyst.yaml.tmpl").read_text() \
        .replace("{{CATALOG}}", s.catalog).replace("{{PRESTO_ENGINE}}", s.presto_engine) \
        .replace("{{TOOLKIT}}", TOOLKIT)
    out = HERE / "f1_race_analyst.yaml"
    out.write_text(rendered)
    run(["agents", "import", "-f", str(out)])
    must_exist("agents", "f1_race_analyst")
    # Imported agents are drafts. Deploy publishes the agent so it appears in the chat UI.
    run(["agents", "deploy", "--name", "f1_race_analyst"])
    print("\nDone. Open watsonx Orchestrate, select F1 Race Analyst and ask a question.")


if __name__ == "__main__":
    main()
