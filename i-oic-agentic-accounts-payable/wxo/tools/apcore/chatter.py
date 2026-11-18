"""The agent's control log as an Odoo chatter note: one line per check, failures first, so it reads well in the
narrow chatter column."""

import html

ICON = {"fail": "❌", "warn": "⚠️", "info": "ℹ️", "pass": "✅"}
ORDER = list(ICON)


def note(title: str, checks: list[dict], extra: str = "") -> str:
    lines = "".join(f"<li>{ICON[c['status']]} <b>{html.escape(c['code'])}</b> {html.escape(c['title'])}"
                    f"<br/><small>{html.escape(c['detail'])}</small></li>"
                    for c in sorted(checks, key=lambda c: ORDER.index(c["status"])))
    passed = sum(c["status"] == "pass" for c in checks)
    return (f"<p><b>AP agent (watsonx Orchestrate flow)</b> — {title}</p>{extra}"
            f"<p>{passed} of {len(checks)} controls passed</p><ul>{lines}</ul>")
