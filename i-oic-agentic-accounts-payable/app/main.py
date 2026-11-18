"""FastAPI app for the Agentic Accounts Payable demo.

    uvicorn app.main:app --reload --port 8000
"""

import threading
import time
from collections import Counter
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, mail, pipeline, store
from scripts.demo_data import INVOICES, OTHER_DOCUMENTS, RECEIPTS, employee_email

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Agentic Accounts Payable · watsonx Orchestrate", version="3.0.0")
store.init()


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# ---- status & overview --------------------------------------------------------------------
_status_cache: dict = {"at": 0.0, "value": None}


@app.get("/api/status")
def status():
    if time.time() - _status_cache["at"] > 60 or not _status_cache["value"]:
        def probe(fn):
            try:
                return fn()
            except Exception as exc:
                return {"connected": False, "error": str(exc)[:160]}
        _status_cache["value"] = {
            "wxo": probe(pipeline.wxo.ping),
            "odoo": probe(pipeline.odoo.ping),
            "gmail": {"connected": mail.configured(), "user": config.GMAIL_USER},
        }
        _status_cache["at"] = time.time()
    return _status_cache["value"]


def _sync():
    try:
        pipeline.sync_from_erp()
    except Exception:
        pass  # the dashboard must render even when Odoo is unreachable


@app.get("/api/overview")
def overview():
    _sync()
    docs = store.all_docs()
    done = [d for d in docs if d["status"] not in ("processing", "failed")]
    touchless = [d for d in done if d["status"] in ("posted", "verified", "received")]
    open_ex = [d for d in docs if d["status"] == "exception"]
    blocked = [d for d in docs if d["status"] == "blocked"]
    tds = sum(((d["controls"] or {}).get("tds") or {}).get("amount") or 0
              for d in docs if d["status"] in ("posted", "approved"))
    reasons = Counter(c.get("label", c["title"]) for d in docs if d["status"] in ("exception", "blocked", "approved", "rejected")
                      for c in (d["controls"] or {}).get("checks", [])
                      if c["status"] == "fail" and (d["status"] != "blocked" or c["code"].startswith("DUP-")))
    cycles = [d["meta"].get("cycle_seconds") for d in done if d["meta"].get("cycle_seconds")]
    return {
        "processed": len(done),
        "in_flight": sum(d["status"] == "processing" for d in docs),
        "touchless_rate": round(len(touchless) / len(done) * 100) if done else 0,
        "value_processed": round(sum(d["total"] or 0 for d in done), 2),
        "open_exceptions": len(open_ex),
        "value_on_hold": round(sum(d["total"] or 0 for d in open_ex), 2),
        "duplicates_blocked": len(blocked),
        "value_protected": round(sum(d["total"] or 0 for d in blocked), 2),
        "tds_deducted": tds,
        "avg_cycle_seconds": round(sum(cycles) / len(cycles), 1) if cycles else None,
        "exception_reasons": reasons.most_common(8),
        "status_counts": Counter(d["status"] for d in docs),
        "by_type": Counter(d["meta"].get("doc_type") or "pending" for d in docs),
    }


# ---- documents ----------------------------------------------------------------------------
def _summary(d: dict) -> dict:
    c = d["controls"] or {}
    return {k: d[k] for k in ("id", "created_at", "source", "file_name", "status", "stage", "vendor",
                              "invoice_number", "invoice_date", "total", "error")} | {
        "doc_type": d["meta"].get("doc_type", ""),
        "po": (c.get("po") or {}).get("name"),
        "issues": [x.get("label", x["title"]) for x in c.get("checks", []) if x["status"] == "fail"],
        "erp_ref": _erp_ref(d["erp"] or {}),
    }


def _erp_ref(erp: dict) -> str:
    if erp.get("bill"):
        return erp["bill"].get("name") or f"Draft bill #{erp['bill']['id']}"
    if erp.get("expense"):
        return f"Expense #{erp['expense']['id']}"
    return (erp.get("receipt") or {}).get("name", "")


@app.get("/api/documents")
def list_documents():
    _sync()
    return [_summary(d) for d in store.all_docs()]


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int):
    doc = store.get(doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


ACCEPTED_TYPES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@app.post("/api/documents")
async def create_document(file: UploadFile | None = File(None), sample: str | None = Form(None),
                          submitted_by: str = Form("")):
    if file and file.filename:
        if Path(file.filename).suffix.lower() not in ACCEPTED_TYPES:
            raise HTTPException(400, f"{file.filename}: unsupported file type. Use PDF, PNG, JPG or TIFF.")
        try:
            return pipeline.submit(await file.read(), file.filename, "upload", {"sender": submitted_by} if submitted_by else {})
        except pipeline.UnreadableDocument as exc:
            raise HTTPException(400, str(exc))
    if sample:
        path = next((p for p in config.SAMPLES_DIR.iterdir() if p.name == Path(sample).name), None)
        if not path:
            raise HTTPException(404, f"Sample {sample} not found")
        spec = next((r for r in RECEIPTS if r["file"] == path.stem), None)
        return pipeline.submit(path.read_bytes(), path.name, "sample",
                               {"sender": employee_email(spec["submitted_by"])} if spec else {})
    raise HTTPException(400, "Upload a file or choose a sample")


@app.get("/api/documents/{doc_id}/preview")
def document_preview(doc_id: int):
    doc = store.get(doc_id)
    if not doc or not doc["preview_path"]:
        raise HTTPException(404)
    return FileResponse(doc["preview_path"], media_type="image/png")


@app.get("/api/documents/{doc_id}/file")
def document_file(doc_id: int):
    doc = store.get(doc_id)
    if not doc:
        raise HTTPException(404)
    return FileResponse(doc["file_path"], filename=doc["file_name"])


def _action(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception as exc:
        raise HTTPException(502, str(exc)[:300])


@app.post("/api/documents/{doc_id}/approve")
def approve(doc_id: int, body: dict = Body(default={})):
    return _action(pipeline.approve, doc_id, body.get("resolution", "as_invoiced"), body.get("note", ""))


@app.post("/api/documents/{doc_id}/reject")
def reject(doc_id: int, body: dict = Body(default={})):
    return _action(pipeline.reject, doc_id, body.get("reason") or "Rejected by AP reviewer",
                   bool(body.get("email_vendor")), body.get("body", ""))


@app.get("/api/documents/{doc_id}/vendor-email")
def vendor_email(doc_id: int):
    return pipeline.vendor_email_draft(doc_id) | {"gmail_configured": mail.configured()}


@app.post("/api/documents/{doc_id}/vendor-email")
def send_vendor_email(doc_id: int, body: dict = Body(...)):
    return _action(pipeline.email_supplier, doc_id, body.get("to", ""), body.get("subject", ""), body.get("body", ""))


@app.get("/api/samples")
def samples():
    kinds = [("supplier_invoice", INVOICES), ("expense_receipt", RECEIPTS), (None, OTHER_DOCUMENTS)]
    return [{"file": next((p.name for p in config.SAMPLES_DIR.glob(f"{i['file']}.*")), ""), "scenario": i["scenario"],
             "number": i.get("number") or i.get("po", ""), "kind": kind or i["kind"]}
            for kind, items in kinds for i in items]


@app.post("/api/inbox/poll")
def poll_inbox():
    docs = _action(pipeline.poll_inbox)
    return {"count": len(docs), "documents": [_summary(d) for d in docs]}


@app.post("/api/reset")
def reset():
    return {"bills_removed": _action(pipeline.reset)}


# ---- assistant ------------------------------------------------------------------------------
AGENTS = {"copilot": config.WXO_COPILOT_AGENT, "supplier": config.WXO_SUPPLIER_AGENT}


@app.get("/api/controls")
def controls():
    return _action(pipeline.wxo.controls)


@app.post("/api/chat")
def chat(body: dict = Body(...)):
    agent = AGENTS.get(body.get("agent", "copilot"), config.WXO_COPILOT_AGENT)
    return _action(pipeline.wxo.chat, agent, body.get("message", ""), body.get("thread_id"))


# ---- background inbox polling ---------------------------------------------------------------
def _inbox_loop():
    while True:
        time.sleep(config.GMAIL_POLL_SECONDS)
        try:
            pipeline.poll_inbox()
        except Exception:
            pass


if config.GMAIL_POLL_SECONDS and mail.configured():
    threading.Thread(target=_inbox_loop, daemon=True).start()


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/api/build")
def build():
    """Changes whenever the UI files change; open tabs reload themselves instead of running stale code."""
    return {"build": int(max((STATIC / f).stat().st_mtime for f in ("index.html", "app.js", "app.css")))}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})
