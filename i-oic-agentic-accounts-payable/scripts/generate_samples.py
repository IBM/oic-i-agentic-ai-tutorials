"""Render the demo supplier invoices (Indian GST tax invoices) from scripts/demo_data.py.

    python scripts/generate_samples.py   ->  samples/*.pdf (+ one scanned .png)
"""

import hashlib
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402,F401  (puts the apcore engine on the path)

import pypdfium2 as pdfium  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402
from reportlab.graphics import renderPDF  # noqa: E402
from reportlab.graphics.barcode.qr import QrCodeWidget  # noqa: E402
from reportlab.graphics.shapes import Drawing  # noqa: E402
from reportlab.lib.colors import HexColor, black  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from apcore.india import STATE_CODES, amount_in_words, inr, pan_from_gstin  # noqa: E402
from scripts.demo_data import (BUYER, EMPLOYEES, INVOICES, MERCHANTS, OTHER_DOCUMENTS, PRODUCTS,  # noqa: E402
                               PURCHASE_ORDERS, RECEIPTS, vendor)

OUT = Path(__file__).resolve().parent.parent / "samples"
W, H = A4
M = 36
GRID = HexColor("#8d8d8d")
SHADE = HexColor("#f2f2f2")


def state_label(gstin):
    return f"{STATE_CODES[gstin[:2]]} ({gstin[:2]})"


def compute(inv):
    lines = []
    for key, qty, rate in inv["lines"]:
        name, hsn, _kind, uom, gst = PRODUCTS[key]
        lines.append({"desc": name, "hsn": hsn, "qty": qty, "uom": "MT" if uom == "t" else ("Nos" if uom == "Units" else uom),
                      "rate": rate, "amount": round(qty * rate, 2), "gst": gst})
    taxable = round(sum(l["amount"] for l in lines), 2)
    rate = lines[0]["gst"]
    if inv["tax"] == "intra":
        half = round(taxable * rate / 200, 2)
        taxes = [(f"CGST @ {rate / 2:g}%", half), (f"SGST @ {rate / 2:g}%", half)]
    else:
        taxes = [(f"IGST @ {rate:g}%", round(taxable * rate / 100, 2))]
    total = round(taxable + sum(t[1] for t in taxes), 2)
    return lines, taxable, taxes, total


def text(c, x, y, s, size=8, bold=False, color=black, right=False):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    (c.drawRightString if right else c.drawString)(x, y, s)
    c.setFillColor(black)


def draw_invoice(inv, path):
    v = vendor(inv["vendor"])
    po = next(p for p in PURCHASE_ORDERS if p["name"] == inv["po"])
    bank = inv.get("bank_override") or v["bank"]
    lines, taxable, taxes, total = compute(inv)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"Tax Invoice {inv['number']}")
    c.setStrokeColor(GRID)
    c.setLineWidth(0.6)

    # Header
    y = H - M
    text(c, W - M, y - 12, "TAX INVOICE", 15, True, right=True)
    text(c, W - M, y - 24, "Original for Recipient", 7, right=True)
    text(c, M, y - 12, v["name"], 13, True)
    text(c, M, y - 26, f"{v['street']}, {v['city']} - {v['zip']}", 8)
    text(c, M, y - 37, f"GSTIN: {v['gstin']}     PAN: {pan_from_gstin(v['gstin'])}", 8, True)
    text(c, M, y - 48, f"State: {state_label(v['gstin'])}     Email: {v['email']}", 8)
    y -= 60

    # e-Invoice block (IRN + signed QR)
    if inv["irn"]:
        irn = hashlib.sha256(f"{v['gstin']}|{inv['number']}|2026-27".encode()).hexdigest()
        ack = str(int(hashlib.md5(irn.encode()).hexdigest(), 16))[:15]
        c.setFillColor(SHADE); c.rect(M, y - 52, W - 2 * M, 52, stroke=1, fill=1); c.setFillColor(black)
        text(c, M + 6, y - 13, "e-Invoice", 8, True)
        text(c, M + 6, y - 25, f"IRN: {irn}", 7)
        text(c, M + 6, y - 36, f"Ack No: {ack}     Ack Date: {inv['date']} 11:42:08", 7)
        text(c, M + 6, y - 47, "Signed by the Invoice Registration Portal (IRP)", 6, color=GRID)
        qr = QrCodeWidget(f"{v['gstin']}|{BUYER['gstin']}|{inv['number']}|{inv['date']}|{total:.2f}|{irn}")
        b = qr.getBounds(); size = 48
        d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0]); d.add(qr)
        renderPDF.draw(d, c, W - M - size - 2, y - size - 2)
        y -= 60

    # Invoice meta + parties
    box_h = 96
    c.rect(M, y - box_h, W - 2 * M, box_h)
    mid = W / 2
    c.line(mid, y, mid, y - box_h)
    meta = [("Invoice No.", inv["number"]), ("Invoice Date", inv["date"]), ("Buyer's Order No.", po["name"]),
            ("Order Date", po["date"]), ("Payment Terms", "Net 30 days"),
            ("Place of Supply", state_label(BUYER["gstin"])), ("Reverse Charge", "No")]
    for i, (k, val) in enumerate(meta):
        text(c, mid + 8, y - 13 - i * 12, k, 8)
        text(c, mid + 100, y - 13 - i * 12, val, 8, True)
    text(c, M + 8, y - 13, "Bill To / Ship To", 7, color=GRID)
    text(c, M + 8, y - 26, BUYER["name"], 9, True)
    text(c, M + 8, y - 38, BUYER["street"], 8)
    text(c, M + 8, y - 49, f"{BUYER['city']} - {BUYER['zip']}", 8)
    text(c, M + 8, y - 62, f"GSTIN: {BUYER['gstin']}", 8, True)
    text(c, M + 8, y - 74, f"State: {state_label(BUYER['gstin'])}", 8)
    y -= box_h + 10

    # Line items
    cols = [(M, "#", 18), (M + 18, "Description of Goods / Services", 214), (M + 232, "HSN/SAC", 56),
            (M + 288, "Qty", 40), (M + 328, "UoM", 34), (M + 362, "Rate (INR)", 74), (M + 436, "Taxable Value (INR)", W - 2 * M - 436)]
    c.setFillColor(SHADE); c.rect(M, y - 16, W - 2 * M, 16, stroke=1, fill=1); c.setFillColor(black)
    for x, label, _w in cols:
        text(c, x + 4, y - 11, label, 7.5, True)
    y -= 16
    for i, l in enumerate(lines, 1):
        row = [str(i), l["desc"], l["hsn"], f"{l['qty']:g}", l["uom"], inr(l["rate"]), inr(l["amount"])]
        for (x, _label, w), val in zip(cols, row):
            numeric = val is row[5] or val is row[6] or val is row[3]
            text(c, x + w - 4 if numeric else x + 4, y - 14, val, 8, right=numeric)
        c.line(M, y - 20, W - M, y - 20)
        y -= 20
    for x, _l, _w in cols[1:]:
        c.line(x, y, x, y + 20 * len(lines) + 16)
    c.rect(M, y, W - 2 * M, 20 * len(lines) + 16)

    # Tax summary
    y -= 8
    sx = M + 300
    rows = [("Total Taxable Value", taxable)] + taxes
    for label, amt in rows:
        text(c, sx, y - 12, label, 8.5)
        text(c, W - M - 4, y - 12, inr(amt), 8.5, right=True)
        y -= 14
    c.line(sx, y - 2, W - M, y - 2)
    text(c, sx, y - 16, "Total Invoice Value (INR)", 10, True)
    text(c, W - M - 4, y - 16, inr(total), 10, True, right=True)
    y -= 26
    text(c, M, y - 6, f"Amount in words: {amount_in_words(total)}", 8, True)
    y -= 24

    # Bank details
    if inv.get("note"):
        text(c, M, y - 4, inv["note"], 8.5, True, color=HexColor("#da1e28"))
        y -= 16
    c.rect(M, y - 52, 260, 52)
    text(c, M + 8, y - 12, "Bank Details for Remittance", 8, True)
    text(c, M + 8, y - 25, f"Bank: {bank['name']}", 8)
    text(c, M + 8, y - 36, f"A/c No: {bank['account']}", 8)
    text(c, M + 8, y - 47, f"IFSC: {bank['ifsc']}", 8)

    text(c, W - M, y - 12, f"For {v['name']}", 8, True, right=True)
    text(c, W - M, y - 47, "Authorised Signatory", 8, right=True)
    text(c, M, M + 6, "Declaration: We declare that this invoice shows the actual price of the goods/services described "
                      "and that all particulars are true and correct.", 6.5, color=GRID)
    text(c, M, M - 4, "This is a computer-generated invoice. Subject to Mumbai jurisdiction.", 6.5, color=GRID)
    c.showPage()
    c.save()


def make_scan(pdf_path, png_path):
    """Turn a PDF into a slightly skewed, noisy 'scanned' image like an emailed phone scan."""
    page = pdfium.PdfDocument(str(pdf_path))[0]
    img = page.render(scale=150 / 72).to_pil().convert("L")
    img = img.rotate(-0.9, resample=Image.BICUBIC, expand=True, fillcolor=244)
    rnd = random.Random(7)
    px = img.load()
    for _ in range(img.width * img.height // 60):
        x, y = rnd.randrange(img.width), rnd.randrange(img.height)
        px[x, y] = max(0, px[x, y] - rnd.randrange(40, 110))
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    img.save(png_path, optimize=True)


# ---- employee receipts ---------------------------------------------------------------------
def receipt_amounts(r):
    if r["kind"] == "taxi":
        items = [("Trip fare", 1, r["fare"])]
    elif r["kind"] == "hotel":
        items = [(f"Room charges · Executive room", r["nights"], r["rate"])]
    else:
        items = r["items"]
    taxable = round(sum(q * p for _, q, p in items), 2)
    half = round(taxable * r["gst_pct"] / 200, 2)
    return items, taxable, half, round(taxable + 2 * half, 2)


def draw_receipt(r, path):
    m = MERCHANTS[r["merchant"]]
    items, taxable, half, total = receipt_amounts(r)
    wide = r["kind"] == "hotel"
    w, h = (A4[0], A4[1] / 2.4) if wide else (230, 250 + 11 * len(items))
    c = canvas.Canvas(str(path), pagesize=(w, h))
    c.setTitle(f"Receipt {r['number']}")
    x, y = 18, h - 28
    text(c, x, y, m["name"], 11 if wide else 9.5, bold=True); y -= 13
    text(c, x, y, m["address"], 7); y -= 10
    text(c, x, y, f"GSTIN: {m['gstin']}", 7); y -= 16
    title = {"taxi": "TRIP RECEIPT / TAX INVOICE", "hotel": "TAX INVOICE — HOTEL BILL", "restaurant": "BILL / TAX INVOICE"}[r["kind"]]
    text(c, x, y, title, 8.5, bold=True); y -= 13
    meta = [("Receipt No.", r["number"]), ("Date", r["date"])]
    if r["kind"] == "taxi":
        meta.append(("Trip", r["trip"]))
    if r["kind"] == "hotel":
        meta += [("Guest", r["guest"]), ("Stay", f"{r['nights']} nights · check-out {r['date']}")]
    if r["kind"] == "restaurant":
        meta.append(("Covers", str(r["persons"])))
    if r["billed_to_company"]:
        meta += [("Bill to", BUYER["name"]), ("Buyer GSTIN", BUYER["gstin"])]
    for k, v in meta:
        text(c, x, y, f"{k}:", 7, bold=True); text(c, x + (70 if wide else 58), y, v, 7); y -= 10
    y -= 6
    c.setStrokeColor(GRID); c.line(x, y + 4, w - 18, y + 4); y -= 8
    for name, q, p in items:
        text(c, x, y, f"{name}" + (f" x {q:g}" if q != 1 or wide else ""), 7.5)
        text(c, w - 18, y, f"{q * p:,.2f}", 7.5, right=True); y -= 11
    c.line(x, y + 4, w - 18, y + 4); y -= 8
    for k, v in [("Taxable value", taxable), (f"CGST @ {r['gst_pct'] / 2:g}%", half), (f"SGST @ {r['gst_pct'] / 2:g}%", half)]:
        text(c, x, y, k, 7.5); text(c, w - 18, y, f"{v:,.2f}", 7.5, right=True); y -= 11
    text(c, x, y, "TOTAL (INR)", 9, bold=True); text(c, w - 18, y, f"{total:,.2f}", 9, bold=True, right=True); y -= 16
    paid = f"Paid by card XXXX XXXX XXXX {r['card']}" if r["card"] else "Paid by UPI"
    text(c, x, y, paid, 7.5); y -= 14
    text(c, x, y, "Thank you. This is a computer-generated receipt.", 6.5, color=GRID)
    c.showPage(); c.save()


# ---- PO copy, delivery challan, letter ----------------------------------------------------
def _header(c, name, lines, title):
    text(c, M, H - M - 10, name, 13, bold=True)
    for i, l in enumerate(lines):
        text(c, M, H - M - 24 - i * 10, l, 7.5)
    text(c, W - M, H - M - 10, title, 13, bold=True, right=True)


def _table(c, y, head, rows, widths):
    c.setFillColor(SHADE); c.rect(M, y - 4, W - 2 * M, 14, fill=1, stroke=0)
    xs = [M + 4]
    for wd in widths[:-1]:
        xs.append(xs[-1] + wd)
    for xx, hd in zip(xs, head):
        text(c, xx, y, hd, 7.5, bold=True)
    for row in rows:
        y -= 16
        for xx, val in zip(xs, row):
            text(c, xx, y, str(val), 7.5)
    return y


def draw_po_copy(d, path):
    po = next(p for p in PURCHASE_ORDERS if p["name"] == d["po"])
    v = vendor(po["vendor"])
    c = canvas.Canvas(str(path), pagesize=A4); c.setTitle(f"Purchase Order {po['name']}")
    _header(c, BUYER["name"], [BUYER["street"], f"{BUYER['city']} - {BUYER['zip']}", f"GSTIN: {BUYER['gstin']}"], "PURCHASE ORDER")
    y = H - M - 80
    for k, val in [("PO Number", po["name"]), ("PO Date", po["date"]), ("Supplier", v["name"]), ("Supplier GSTIN", v["gstin"])]:
        text(c, M, y, f"{k}:", 8, bold=True); text(c, M + 90, y, val, 8); y -= 12
    rows = []
    total = 0
    for key, qty, rate, _ in po["lines"]:
        name, hsn, _k, uom, _g = PRODUCTS[key]
        rows.append([name, hsn, f"{qty:g}", uom, f"{rate:,.2f}", f"{qty * rate:,.2f}"]); total += qty * rate
    y = _table(c, y - 14, ["Description", "HSN/SAC", "Qty", "UoM", "Rate", "Amount"], rows, [230, 60, 40, 40, 70, 80])
    text(c, W - M, y - 22, f"Total (before GST): {total:,.2f}", 9, bold=True, right=True)
    text(c, M, 150, "Accepted for and on behalf of the supplier", 8, bold=True)
    c.setFont("Helvetica-Oblique", 13); c.setFillColor(HexColor("#1d3c8f")); c.drawString(M + 10, 122, "R. Subramanian"); c.setFillColor(black)
    text(c, M, 108, f"{v['name']} · Signed 2026-10-03", 7.5)
    c.showPage(); c.save()


def draw_challan(d, path):
    v = vendor(d["vendor"])
    c = canvas.Canvas(str(path), pagesize=A4); c.setTitle(f"Delivery Challan {d['number']}")
    _header(c, v["name"], [v["street"], f"{v['city']} - {v['zip']}", f"GSTIN: {v['gstin']}"], "DELIVERY CHALLAN")
    y = H - M - 80
    for k, val in [("Challan No.", d["number"]), ("Date", d["date"]), ("Against PO", d["po"]), ("Consignee", BUYER["name"]),
                   ("Consignee GSTIN", BUYER["gstin"]), ("Vehicle No.", d["vehicle"]), ("Reason", "Supply against PO — balance quantity")]:
        text(c, M, y, f"{k}:", 8, bold=True); text(c, M + 90, y, val, 8); y -= 12
    rows = [[PRODUCTS[k][0], PRODUCTS[k][1], f"{q:g}", "MT" if PRODUCTS[k][3] == "t" else PRODUCTS[k][3]] for k, q in d["lines"]]
    y = _table(c, y - 14, ["Description of goods", "HSN", "Quantity", "UoM"], rows, [300, 80, 80, 60])
    text(c, M, y - 40, "Received the above goods in good condition.", 8)
    text(c, M, y - 70, "Gate entry: GE/TAL/26-27/2291    Stores: ___________", 8)
    c.showPage(); c.save()


def draw_letter(d, path):
    v = vendor(d["vendor"])
    c = canvas.Canvas(str(path), pagesize=A4); c.setTitle("Price revision notice")
    _header(c, v["name"], [v["street"], f"{v['city']} - {v['zip']}"], "")
    y = H - M - 90
    body = ["Date: 2026-10-27", "", f"To: Purchase Department, {BUYER['name']}", "",
            "Subject: Revision of prices for laboratory solvents with effect from 1 November 2026", "",
            "Dear Sir / Madam,", "",
            "Owing to an increase in input costs, the price of Acetonitrile HPLC Grade 2.5 L will be revised to",
            "INR 7,280 per unit for all supplies dispatched on or after 1 November 2026. Other prices are unchanged.",
            "", "We request you to amend open purchase orders accordingly.", "", "Yours faithfully,",
            f"for {v['name']}", "", "Sales Manager"]
    for line in body:
        text(c, M, y, line, 9); y -= 13
    c.showPage(); c.save()


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for inv in INVOICES:
        pdf = OUT / f"{inv['file']}.pdf"
        draw_invoice(inv, pdf)
        if inv.get("scan"):
            make_scan(pdf, OUT / f"{inv['file']}.png")
            pdf.unlink()
        _l, taxable, _t, total = compute(inv)
        print(f"{inv['file']:<48} taxable {inr(taxable):>14}  total {inr(total):>14}  — {inv['scenario']}")
    for r in RECEIPTS:
        pdf = OUT / f"{r['file']}.pdf"
        draw_receipt(r, pdf)
        if r.get("scan"):
            make_scan(pdf, OUT / f"{r['file']}.jpg")
            pdf.unlink()
        print(f"{r['file']:<48} total {inr(receipt_amounts(r)[3]):>14}  — {r['scenario']}")
    draw = {"purchase_order": draw_po_copy, "delivery_challan": draw_challan, "letter": draw_letter}
    for d in OTHER_DOCUMENTS:
        draw[d["kind"]](d, OUT / f"{d['file']}.pdf")
        print(f"{d['file']:<48} — {d['scenario']}")
