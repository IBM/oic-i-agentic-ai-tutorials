"""SQLite document store. Odoo is the system of record for vendors, POs and bills; this keeps
the processing artefacts (extraction, bounding boxes, control results, timeline) for the UI."""

import json
import sqlite3
import threading
from datetime import datetime, timezone

from app.config import DATA_DIR

DB_PATH = DATA_DIR / "ap_agent.db"
JSON_COLS = ("extraction", "controls", "erp", "timeline", "meta")
_lock = threading.Lock()


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT, updated_at TEXT,
                source TEXT, file_name TEXT, file_path TEXT, preview_path TEXT,
                status TEXT, stage TEXT, error TEXT,
                vendor TEXT, invoice_number TEXT, invoice_date TEXT, total REAL,
                extraction TEXT, controls TEXT, erp TEXT, timeline TEXT, meta TEXT
            )""")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r) -> dict:
    d = dict(r)
    for k in JSON_COLS:
        d[k] = json.loads(d[k]) if d.get(k) else ({} if k != "timeline" else [])
    return d


def create(**fields) -> dict:
    fields.setdefault("timeline", [])
    fields.update(created_at=_now(), updated_at=_now())
    cols = list(fields)
    vals = [json.dumps(fields[k]) if k in JSON_COLS else fields[k] for k in cols]
    with _lock, _conn() as c:
        cur = c.execute(f"INSERT INTO documents ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
    return get(cur.lastrowid)


def update(doc_id: int, **fields) -> dict:
    fields["updated_at"] = _now()
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = [json.dumps(v) if k in JSON_COLS else v for k, v in fields.items()]
    with _lock, _conn() as c:
        c.execute(f"UPDATE documents SET {sets} WHERE id = ?", [*vals, doc_id])
    return get(doc_id)


def log(doc_id: int, step: str, status: str, detail: str = "", duration_ms: float | None = None, **extra) -> None:
    """Append (or update, by step key) an entry on the document's processing timeline."""
    doc = get(doc_id)
    timeline = [t for t in doc["timeline"] if t["step"] != step]
    timeline.append({"step": step, "status": status, "detail": detail, "duration_ms": duration_ms,
                     "at": _now(), **extra})
    update(doc_id, timeline=timeline)


def get(doc_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    return _row(r) if r else None


def all_docs() -> list[dict]:
    with _conn() as c:
        return [_row(r) for r in c.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()]


def clear() -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM documents")
        c.execute("DELETE FROM sqlite_sequence WHERE name = 'documents'")
