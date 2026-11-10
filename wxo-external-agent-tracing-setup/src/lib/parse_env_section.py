#!/usr/bin/env python3
"""
parse_env_section.py  —  Helper to extract platform sections from config.env

Supports section headers like [aws], [azure], [claude], [vertex], [salesforce]
and provides:
  - 'sh': outputs bash export statements
  - 'json': outputs JSON
  - 'status': prints a terminal table showing readiness across all platforms
  - 'show': displays formatted key-value pairs for a specific platform
"""

import json
import os
import re
import sys


def extract_tenant_id(url: str) -> str:
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return ""


def _populate_tenant_id(d: dict) -> None:
    if isinstance(d, dict):
        url = d.get("WXO_OTEL_EXPORT_URL", "")
        tid = d.get("WXO_TENANT_ID", "")
        if (not tid or "<" in tid) and url and "<" not in url:
            extracted = extract_tenant_id(url)
            if extracted:
                d["WXO_TENANT_ID"] = extracted


def parse_config(file_path: str, target_section: str = None) -> dict:
    if not os.path.exists(file_path):
        # Fallback: check if directory or config/ has modular files
        if os.path.isdir("config"):
            file_path = "config"
        else:
            return {}

    if os.path.isdir(file_path):
        sections = {}
        for fname in os.listdir(file_path):
            if fname.endswith(".env") and not fname.endswith(".example"):
                sec_name = fname[:-4].lower()
                sec_file = os.path.join(file_path, fname)
                sections[sec_name] = parse_config(sec_file)
        if target_section:
            sec_k = target_section.strip().lower()
            merged = {}
            for base in ("shared", "global", "default"):
                if base in sections:
                    merged.update(sections[base])
            if sec_k in sections:
                merged.update(sections[sec_k])
            return merged
        return sections

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_sections = bool(re.search(r"^\s*\[\s*[A-Za-z0-9_-]+\s*\]", content, re.MULTILINE))

    sections: dict[str, dict[str, str]] = {}
    current_sec = "global"
    sections[current_sec] = {}

    current_key = None
    current_val_lines = []
    in_multiline_quote = None
    brace_depth = 0

    def save_current():
        nonlocal current_key, current_val_lines, in_multiline_quote, brace_depth
        if current_key and current_sec:
            val = "\n".join(current_val_lines).strip()
            if (val.startswith("'") and val.endswith("'") and len(val) >= 2) or (
                val.startswith('"') and val.endswith('"') and len(val) >= 2
            ):
                val = val[1:-1]
            sections[current_sec][current_key] = val
        current_key = None
        current_val_lines = []
        in_multiline_quote = None
        brace_depth = 0

    for line in content.splitlines():
        stripped = line.strip()

        # Match section header: e.g. [claude], [aws]
        m_sec = re.match(r"^\s*\[\s*([A-Za-z0-9_-]+)\s*\]", stripped)
        if m_sec:
            save_current()
            current_sec = m_sec.group(1).lower()
            if current_sec not in sections:
                sections[current_sec] = {}
            continue

        if not current_sec:
            continue

        if not current_key:
            if not stripped or stripped.startswith("#"):
                continue

            # Check single line quoted: e.g. export FOO="bar" # comment
            m_single = re.match(r'''^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(['"])(.*?)\2(?:\s*#.*)?$''', line)
            if m_single:
                sections[current_sec][m_single.group(1)] = m_single.group(3)
                continue

            # Check single line unquoted: e.g. export FOO=bar # comment
            m_unquoted = re.match(r'''^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^{}'"][^\s#]*)(?:\s*#.*)?$''', line)
            if m_unquoted:
                sections[current_sec][m_unquoted.group(1)] = m_unquoted.group(2)
                continue

            m_kv = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
            if m_kv:
                k = m_kv.group(1)
                v = m_kv.group(2).strip()
                current_key = k
                current_val_lines = [v]

                if v.startswith("'"):
                    in_multiline_quote = "'"
                elif v.startswith('"'):
                    in_multiline_quote = '"'
                elif v.startswith("{") or v.startswith("["):
                    open_b = v.count("{") + v.count("[")
                    close_b = v.count("}") + v.count("]")
                    if open_b == close_b and open_b > 0:
                        save_current()
                    else:
                        brace_depth = open_b - close_b
                else:
                    save_current()
        else:
            current_val_lines.append(line)
            if in_multiline_quote:
                if stripped.endswith(in_multiline_quote):
                    save_current()
            elif brace_depth > 0:
                open_b = stripped.count("{") + stripped.count("[")
                close_b = stripped.count("}") + stripped.count("]")
                brace_depth += open_b - close_b
                if brace_depth <= 0:
                    save_current()

    save_current()

    if not has_sections:
        res = sections.get("global", {})
        _populate_tenant_id(res)
        return res

    if target_section:
        target_sec = target_section.strip().lower()
        merged = {}
        for base in ("global", "shared", "default"):
            if base in sections:
                merged.update(sections[base])
        if target_sec in sections:
            merged.update(sections[target_sec])
        _populate_tenant_id(merged)
        return merged

    for sec_data in sections.values():
        _populate_tenant_id(sec_data)
    return sections


def _platform_cmd(p_key: str) -> str:
    """Entrypoint command for a platform (azure/claude have dedicated scripts)."""
    return f"./{p_key}.sh" if p_key in ("azure", "claude") else f"./wire_agent.sh --{p_key}"


def print_status(file_path: str):
    all_sec = parse_config(file_path)
    platforms = [
        ("claude", "Claude (OTLP Forwarder: Docker/Lambda/Azure)"),
        ("aws", "AWS AgentCore / Bedrock"),
        ("azure", "Azure AI Foundry"),
        ("vertex", "Vertex AI / Reasoning Engine"),
        ("salesforce", "Salesforce Agentforce"),
    ]

    print("\n╔════════════════════════════════════════════════════════════════════════════════════╗")
    print("║                   WXO Tracing Platform Configuration Status                        ║")
    print("╚════════════════════════════════════════════════════════════════════════════════════╝\n")
    print(f"  {'Platform':<13} {'Status':<14} {'Tenant ID':<22} {'Agent Map':<14} {'Command'}")
    print(f"  {'-'*11:<13} {'-'*12:<14} {'-'*20:<22} {'-'*12:<14} {'-'*22}")

    for p_key, _ in platforms:
        sec = all_sec.get(p_key, {})
        if not sec:
            print(f"  {p_key:<13} {'✗ Missing':<14} {'-':<22} {'-':<14} {_platform_cmd(p_key)}")
            continue

        # Platform section overrides global/shared/default values (same as parse_config)
        merged = {}
        for base in ("global", "shared", "default"):
            merged.update(all_sec.get(base, {}))
        merged.update(sec)

        def _set(name):
            val = merged.get(name, "")
            return bool(val) and "<" not in val

        mode = (merged.get("WXO_DEPLOYMENT_MODE") or "cloud").strip().lower()
        if mode == "cpd":
            iid = merged.get("CPD_INSTANCE_ID", "")
            tid_disp = "cpd:" + (iid[:15] if iid and "<" not in iid else "(unset)")
            required = ["CPD_HOST_URL", "CPD_USERNAME", "CPD_PASSWORD", "CPD_INSTANCE_ID", "CPD_NAMESPACE"]
            configured = all(_set(n) for n in required)
        else:
            url = merged.get("WXO_OTEL_EXPORT_URL", "")
            tid = merged.get("WXO_TENANT_ID", "") or extract_tenant_id(url)
            tid_disp = "(unset)" if not tid or "<" in tid else (tid[:19] + "..." if len(tid) > 20 else tid)
            configured = all(_set(n) for n in ("API_KEY", "WXO_OTEL_EXPORT_URL")) and bool(tid and "<" not in tid)

        if configured:
            status_disp = "✓ Configured"
        else:
            status_disp = "✗ Incomplete"

        agents = 0
        try:
            m = json.loads(sec.get("WXO_AGENT_MAP", "{}"))
            agents = len(m)
        except Exception:
            pass
        map_disp = f"✓ {agents} agent(s)" if agents > 0 else "✗ None"

        print(f"  {p_key:<13} {status_disp:<14} {tid_disp:<22} {map_disp:<14} {_platform_cmd(p_key)}")

    print("\n  Quick Commands:")
    print("    • Run a platform     : ./claude.sh | ./azure.sh | ./wire_agent.sh --<aws|vertex|salesforce>")
    print("    • Dry-run test       : append --dry-run to any of the above")
    print("    • View configuration : ./wire_agent.sh --show <platform>")
    print("    • Edit configuration : edit config.env\n")


def print_show(file_path: str, section: str):
    sec_data = parse_config(file_path, section)
    if not sec_data:
        print(f"  ✗ Section [{section}] not found in {file_path}")
        return

    print(f"\nConfiguration for [{section}] in {file_path}:\n")
    for k, v in sec_data.items():
        if k == "WXO_AGENT_MAP":
            print(f"  {k}:")
            try:
                parsed_json = json.loads(v)
                for map_k, map_v in parsed_json.items():
                    print(f"    • {map_k}: {map_v}")
            except Exception:
                print(f"    {v}")
        elif "KEY" in k or "SECRET" in k or "PASSWORD" in k:
            masked = v[:6] + "..." + v[-4:] if len(v) > 12 else ("*" * len(v) if v else "(empty)")
            print(f"  {k:<28} = {masked}")
        else:
            print(f"  {k:<28} = {v}")
    print("")


def is_unset(value: str) -> bool:
    """True for empty values and whole-value '<placeholders>' (JSON objects are never placeholders)."""
    v = (value or "").strip()
    return not v or ("<" in v and ">" in v and not v.startswith("{"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    cfg_file = sys.argv[1]
    sec = sys.argv[2] if len(sys.argv) > 2 else ""
    out_mode = sys.argv[3] if len(sys.argv) > 3 else "json"

    if sec == "--status" or out_mode == "status":
        print_status(cfg_file)
        sys.exit(0)

    if out_mode == "show" or sec.startswith("--show"):
        target = sys.argv[3] if len(sys.argv) > 3 else (sec.replace("--show=", "") if "=" in sec else "claude")
        print_show(cfg_file, target)
        sys.exit(0)

    data = parse_config(cfg_file, sec if sec else None)

    if out_mode == "sh":
        for var_name, var_val in data.items():
            escaped = var_val.replace("'", "'\"'\"'")
            print(f"export {var_name}='{escaped}'")
    elif out_mode == "sh-layered":
        # Like 'sh', but an empty/placeholder value never overwrites a value that an
        # earlier layer (config/shared.env, config/<platform>.env) already set.
        for var_name, var_val in data.items():
            escaped = var_val.replace("'", "'\"'\"'")
            if is_unset(var_val):
                print(f"[ -n \"${{{var_name}:-}}\" ] || export {var_name}='{escaped}'")
            else:
                print(f"export {var_name}='{escaped}'")
    else:
        print(json.dumps(data, indent=2))
