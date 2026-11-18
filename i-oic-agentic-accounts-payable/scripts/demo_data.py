"""Single source of truth for the demo world: buyer, vendor master, POs, GRNs and the
supplier invoices that exercise each AP control. Read by setup_odoo.py (ERP side) and
generate_samples.py (document side) so the two can never drift apart.

All companies, GSTINs and bank accounts are fictional.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402,F401  (puts the apcore engine on the path)
from apcore.india import make_gstin  # noqa: E402

BUYER = {
    "name": "Meridian Specialty Chemicals India Pvt. Ltd.",
    "gstin": make_gstin("27", "AAJCM4821K"),
    "street": "Plot D-14, MIDC Taloja Industrial Area",
    "city": "Navi Mumbai",
    "zip": "410208",
    "state": "MH",
    "email": "ap@meridian-chem.example",
}

VENDORS = [
    {
        "key": "sahyadri",
        "name": "Sahyadri Drums & Containers Pvt. Ltd.",
        "gstin": make_gstin("27", "AAHCS7314P"),
        "street": "Gat No. 312, Chakan MIDC Phase II",
        "city": "Pune",
        "zip": "410501",
        "state": "MH",
        "email": "accounts@sahyadri-drums.example",
        "bank": {"name": "HDFC Bank", "account": "50200041873310", "ifsc": "HDFC0001267"},
        "tds": None,
        "einvoice": True,
    },
    {
        "key": "kaveri",
        "name": "Kaveri Process Analytics LLP",
        "gstin": make_gstin("29", "AAQFK2209M"),
        "street": "4th Floor, Prestige Tech Park, Outer Ring Road",
        "city": "Bengaluru",
        "zip": "560103",
        "state": "KA",
        "email": "billing@kaveri-analytics.example",
        "bank": {"name": "ICICI Bank", "account": "002905018842", "ifsc": "ICIC0000029"},
        "tds": "professional",
        "einvoice": False,
    },
    {
        "key": "narmada",
        "name": "Narmada Petrochem Industries Ltd.",
        "gstin": make_gstin("24", "AABCN5532R"),
        "street": "Survey No. 88, GIDC Nandesari",
        "city": "Vadodara",
        "zip": "391340",
        "state": "GJ",
        "email": "receivables@narmada-petro.example",
        "bank": {"name": "State Bank of India", "account": "38472910556", "ifsc": "SBIN0003811"},
        "tds": None,
        "einvoice": True,
    },
    {
        "key": "coromandel",
        "name": "Coromandel Plant Services Pvt. Ltd.",
        "gstin": make_gstin("33", "AAGCC6671D"),
        "street": "No. 21, SIDCO Industrial Estate, Ambattur",
        "city": "Chennai",
        "zip": "600098",
        "state": "TN",
        "email": "finance@coromandel-plant.example",
        "bank": {"name": "Indian Overseas Bank", "account": "176902000004418", "ifsc": "IOBA0001769"},
        "tds": "contract",
        "einvoice": False,
    },
    {
        "key": "konkan",
        "name": "Konkan Lab Supplies Pvt. Ltd.",
        "gstin": make_gstin("27", "AAKCK3307E"),
        "street": "Unit 7, Wagle Industrial Estate, Road No. 16",
        "city": "Thane",
        "zip": "400604",
        "state": "MH",
        "email": "invoices@konkan-lab.example",
        "bank": {"name": "Kotak Mahindra Bank", "account": "8311452907", "ifsc": "KKBK0001402"},
        "tds": None,
        "einvoice": True,
    },
]

# product key -> (name, HSN/SAC, goods|service, uom, gst %)
PRODUCTS = {
    "drum200": ("HDPE Open-Top Drum 200 L (UN-certified)", "39231090", "goods", "Units", 18),
    "gasket": ("Drum Closure & Gasket Kit", "40169390", "goods", "Units", 18),
    "hazop": ("HAZOP & Process Safety Study — Taloja Unit 2", "998399", "service", "Units", 18),
    "siteday": ("On-site Process Safety Consultant (per day)", "998399", "service", "Days", 18),
    "pib": ("Polyisobutylene PIB 1300 (bulk)", "39023000", "goods", "t", 18),
    "amc": ("Quarterly Reactor & Pump AMC (Q3)", "998719", "service", "Units", 18),
    "callout": ("Emergency Breakdown Call-out", "998719", "service", "Units", 18),
    "acn": ("Acetonitrile HPLC Grade 2.5 L", "29269000", "goods", "Units", 18),
    "kf": ("Karl Fischer Reagent 1 L", "38220090", "goods", "Units", 18),
}

# Purchase orders with the quantity physically received / accepted (GRN or service entry).
PURCHASE_ORDERS = [
    {"name": "MSC-PO-26-0147", "vendor": "sahyadri", "date": "2026-10-06",
     "lines": [("drum200", 120, 2450.00, 120), ("gasket", 120, 85.00, 120)]},
    {"name": "MSC-PO-26-0152", "vendor": "kaveri", "date": "2026-09-22",
     "lines": [("hazop", 1, 340000.00, 1), ("siteday", 4, 18000.00, 4)]},
    {"name": "MSC-PO-26-0158", "vendor": "narmada", "date": "2026-10-12",
     "lines": [("pib", 10, 142000.00, 8)]},
    {"name": "MSC-PO-26-0161", "vendor": "coromandel", "date": "2026-10-01",
     "lines": [("amc", 1, 225000.00, 1), ("callout", 3, 15000.00, 3)]},
    {"name": "MSC-PO-26-0166", "vendor": "konkan", "date": "2026-10-20",
     "lines": [("acn", 20, 6800.00, 20), ("kf", 12, 3950.00, 12)]},
]

# What each supplier actually printed on their invoice. Deviations from the PO / vendor
# master are deliberate: each document exercises one family of AP controls.
INVOICES = [
    {
        "file": "01_sahyadri_SDC-26-27-0418",
        "scenario": "Touchless — clean 3-way match",
        "vendor": "sahyadri", "number": "SDC/26-27/0418", "date": "2026-10-28",
        "po": "MSC-PO-26-0147", "tax": "intra", "irn": True,
        "lines": [("drum200", 120, 2450.00), ("gasket", 120, 85.00)],
    },
    {
        "file": "02_kaveri_KPA-26-27-073",
        "scenario": "Touchless — services with TDS (professional fees)",
        "vendor": "kaveri", "number": "KPA/26-27/073", "date": "2026-10-30",
        "po": "MSC-PO-26-0152", "tax": "inter", "irn": False,
        "lines": [("hazop", 1, 340000.00), ("siteday", 4, 18000.00)],
    },
    {
        "file": "03_narmada_NPI-GJ-26-27-1182",
        "scenario": "Exception — GRN shortage (billed 10 t, received 8 t)",
        "vendor": "narmada", "number": "NPI/GJ/26-27/1182", "date": "2026-10-31",
        "po": "MSC-PO-26-0158", "tax": "inter", "irn": True,
        "lines": [("pib", 10, 142000.00)],
    },
    {
        "file": "04_coromandel_CPS-26-27-0291",
        "scenario": "Exception — wrong GST regime + changed bank account",
        "vendor": "coromandel", "number": "CPS/26-27/0291", "date": "2026-11-02",
        "po": "MSC-PO-26-0161", "tax": "intra", "irn": False,
        "bank_override": {"name": "Axis Bank", "account": "917020045678123", "ifsc": "UTIB0004417"},
        "note": "Please note our NEW bank account details below for all future remittances.",
        "lines": [("amc", 1, 225000.00), ("callout", 3, 15000.00)],
    },
    {
        "file": "05_konkan_KLS-26-27-0657",
        "scenario": "Exception — price above PO + missing e-invoice IRN",
        "vendor": "konkan", "number": "KLS/26-27/0657", "date": "2026-11-03",
        "po": "MSC-PO-26-0166", "tax": "intra", "irn": False,
        "lines": [("acn", 20, 7280.00), ("kf", 12, 3950.00)],
    },
    {
        "file": "06_sahyadri_SDC-26-27-0418_resubmitted_scan",
        "scenario": "Blocked — duplicate of invoice 01 (scanned resubmission)",
        "vendor": "sahyadri", "number": "SDC/26-27/0418", "date": "2026-10-28",
        "po": "MSC-PO-26-0147", "tax": "intra", "irn": True, "scan": True,
        "lines": [("drum200", 120, 2450.00), ("gasket", 120, 85.00)],
    },
]


def vendor(key: str) -> dict:
    return next(v for v in VENDORS if v["key"] == key)


# ---- employees, expense receipts and other finance documents ------------------------------------
# card: last 4 digits of the corporate card issued to the employee (None = reimbursed personally).
EMPLOYEES = [
    {"key": "vikram", "name": "Vikram Desai", "job": "Head of Operations", "card": "1094", "manager": None},
    {"key": "ananya", "name": "Ananya Rao", "job": "Process Engineer", "card": "4821", "manager": "vikram"},
    {"key": "rahul", "name": "Rahul Mehta", "job": "Key Account Manager", "card": "7350", "manager": "vikram"},
    {"key": "priya", "name": "Priya Nair", "job": "Plant QA Lead", "card": None, "manager": "vikram"},
]


def employee_email(key: str) -> str:
    return f"{key}@meridian-chem.example"


# Merchants on employee receipts (fictional).
MERCHANTS = {
    "cityride": {"name": "CityRide Mobility Pvt. Ltd.", "gstin": make_gstin("27", "AAICC5520L"),
                 "address": "Kurla West, Mumbai - 400070"},
    "seabreeze": {"name": "Hotel Sabarmati Residency", "gstin": make_gstin("24", "AAFHS4410Q"),
                  "address": "Ashram Road, Ahmedabad - 380009"},
    "coastal": {"name": "The Coastal Kitchen", "gstin": make_gstin("27", "AAKFT8812B"),
                "address": "Lower Parel, Mumbai - 400013"},
}

RECEIPTS = [
    {"file": "07_receipt_cityride_taxi", "scenario": "Expense — company-card taxi within policy",
     "kind": "taxi", "merchant": "cityride", "number": "CR-MUM-26-884213", "date": "2026-11-03",
     "card": "4821", "submitted_by": "ananya", "fare": 612.00, "gst_pct": 5, "billed_to_company": False,
     "trip": "Taloja MIDC → Vashi station · 18.4 km"},
    {"file": "08_receipt_hotel_sabarmati", "scenario": "Expense — hotel above ₹6,000/night, paid personally",
     "kind": "hotel", "merchant": "seabreeze", "number": "HSR/26-27/3318", "date": "2026-11-01",
     "card": None, "submitted_by": "priya", "nights": 2, "rate": 8400.00, "gst_pct": 18, "billed_to_company": True,
     "guest": "Priya Nair (Meridian Specialty Chemicals)"},
    {"file": "09_receipt_coastal_kitchen", "scenario": "Expense — client dinner, GST credit blocked (s.17(5))",
     "kind": "restaurant", "merchant": "coastal", "number": "TCK-11482", "date": "2026-11-02",
     "card": "7350", "submitted_by": "rahul", "persons": 3, "gst_pct": 5, "billed_to_company": False,
     "items": [("Coastal seafood platter", 2, 1450.00), ("Veg thali", 1, 690.00), ("Fresh lime soda", 3, 160.00)]},
    {"file": "10_receipt_cityride_taxi_photo", "scenario": "Blocked — same taxi receipt re-submitted by another employee",
     "kind": "taxi", "merchant": "cityride", "number": "CR-MUM-26-884213", "date": "2026-11-03",
     "card": "4821", "submitted_by": "rahul", "fare": 612.00, "gst_pct": 5, "billed_to_company": False,
     "trip": "Taloja MIDC → Vashi station · 18.4 km", "scan": True},
]

OTHER_DOCUMENTS = [
    {"file": "11_po_copy_MSC-PO-26-0161", "scenario": "Purchase order — supplier-signed copy verified against Odoo",
     "kind": "purchase_order", "po": "MSC-PO-26-0161"},
    {"file": "12_challan_narmada_NPI-DC-1190", "scenario": "Delivery challan — 2 t backorder received (GRN)",
     "kind": "delivery_challan", "po": "MSC-PO-26-0158", "vendor": "narmada", "number": "NPI/DC/26-27/1190",
     "date": "2026-11-04", "vehicle": "GJ-06-AT-4471", "lines": [("pib", 2)]},
    {"file": "13_letter_konkan_price_revision", "scenario": "Unsupported — supplier letter, routed to a person",
     "kind": "letter", "vendor": "konkan"},
]
