"""India statutory helpers: GSTIN, IFSC, IRN validation and the GST/TDS rule tables.

Pure functions with no I/O, shared by the controls engine, the sample generator and
the Odoo seed script. The same GSTIN checksum is re-implemented inline inside the
watsonx Orchestrate flow script node (which cannot import project modules).
"""

import re

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
IRN_RE = re.compile(r"^[0-9a-f]{64}$")

STATE_CODES = {
    "24": "Gujarat",
    "27": "Maharashtra",
    "29": "Karnataka",
    "33": "Tamil Nadu",
    "07": "Delhi",
    "06": "Haryana",
    "09": "Uttar Pradesh",
    "36": "Telangana",
    "19": "West Bengal",
}

# GST 2.0 slabs (effective 22 Sep 2025): 5% merit, 18% standard, 40% de-merit.
GST_SLABS = (0.0, 5.0, 18.0, 40.0)

# TDS natures under the Income-tax Act, 2025 (s.393), mapped to the legacy 1961 sections
# AP teams still talk in. Rates/thresholds are demo defaults — confirm with tax before go-live.
TDS_RULES = {
    "professional": {
        "label": "Professional fees",
        "section": "393(1) Sl.6(iii)(b)",
        "legacy": "194J(b)",
        "rate": 10.0,
        "threshold_single": 50000.0,
        "odoo_tax": "10% TDS 393(1) SI.6(iii) D(b) PROF P",
    },
    "technical": {
        "label": "Fees for technical services",
        "section": "393(1) Sl.6(iii)(a)",
        "legacy": "194J(a)",
        "rate": 2.0,
        "threshold_single": 50000.0,
        "odoo_tax": "2% TDS 393(1) SI.6(iii) D(a) TECH P",
    },
    "contract": {
        "label": "Contract work",
        "section": "393(1) Sl.6(i)(b)",
        "legacy": "194C",
        "rate": 2.0,
        "threshold_single": 30000.0,
        "odoo_tax": "2% TDS 393(1) SI.6(i) D(b) CONT OTH P",
    },
    "goods": {
        "label": "Purchase of goods",
        "section": "393(1) Sl.8(ii)",
        "legacy": "194Q",
        "rate": 0.1,
        "threshold_aggregate": 5000000.0,
        "odoo_tax": "0.1% TDS 393(1) SI.8(ii) GOODS P",
    },
}

# Odoo partner tags used as the vendor-master source of truth for AP policy.
TAG_TDS_PREFIX = "TDS: "
TAG_EINVOICE = "E-invoice applicable"


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = GSTIN_CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def make_gstin(state_code: str, pan: str, entity: str = "1") -> str:
    base = f"{state_code}{pan}{entity}Z"
    return base + gstin_checksum(base)


def validate_gstin(gstin: str) -> tuple[bool, str]:
    g = (gstin or "").strip().upper()
    if not g:
        return False, "GSTIN missing"
    if not GSTIN_RE.match(g):
        return False, f"GSTIN '{g}' is not in the 15-character GSTIN format"
    if g[:2] not in STATE_CODES and not (1 <= int(g[:2]) <= 38):
        return False, f"GSTIN '{g}' has an invalid state code {g[:2]}"
    if gstin_checksum(g[:14]) != g[14]:
        return False, f"GSTIN '{g}' fails the check-digit test"
    return True, "Valid format and check digit"


def pan_from_gstin(gstin: str) -> str:
    g = (gstin or "").strip().upper()
    return g[2:12] if len(g) == 15 else ""


def state_of(gstin: str) -> str:
    code = (gstin or "")[:2]
    return STATE_CODES.get(code, code)


def nearest_slab(rate: float) -> float:
    return min(GST_SLABS, key=lambda s: abs(s - rate))


def inr(amount: float) -> str:
    """Format a number in the Indian digit grouping, e.g. 1675600 -> '16,75,600.00'."""
    neg = amount < 0
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return ("-" if neg else "") + whole + "." + frac


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
         "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen",
         "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def _three(n: int) -> str:
    h, r = divmod(n, 100)
    return ((_ONES[h] + " Hundred" + (" " if r else "")) if h else "") + (_two(r) if r else "")


def amount_in_words(amount: float) -> str:
    n = int(round(amount))
    if n == 0:
        return "Rupees Zero Only"
    parts = []
    for div, name in ((10000000, "Crore"), (100000, "Lakh"), (1000, "Thousand")):
        q, n = divmod(n, div)
        if q:
            parts.append(f"{_three(q) if q >= 100 else _two(q)} {name}")
    if n:
        parts.append(_three(n))
    return "Rupees " + " ".join(parts) + " Only"
