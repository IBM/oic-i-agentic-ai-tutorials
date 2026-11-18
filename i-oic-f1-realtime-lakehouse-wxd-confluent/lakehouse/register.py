"""Register external data sources in watsonx.data and attach them to the Presto engine.

    python -m lakehouse register kafka      # Confluent topic  -> catalog kafka_live
    python -m lakehouse register postgres   # Neon PostgreSQL  -> catalog fantasy_pg

The same can be done in the console: Infrastructure manager > Add component > Data source.
Attaching a catalog makes Presto reload its catalogs, which takes a minute or two.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import certifi
import requests
from pathlib import Path

from .wxd import WatsonxData

KAFKA_CATALOG = "kafka_live"
PG_CATALOG = "fantasy_pg"


def _post(w: WatsonxData, path: str, body: dict) -> requests.Response:
    h = {"Authorization": f"Bearer {w.token()}", "AuthInstanceId": w.s.wxd_crn}
    return requests.post(f"{w.s.wxd_host}/lakehouse/api/v3{path}", headers=h, json=body, timeout=180)


def _existing(w: WatsonxData, catalog: str) -> dict | None:
    regs = w._api("GET", "/database_registrations").json().get("database_registrations", [])
    return next((r for r in regs if r.get("associated_catalog", {}).get("catalog_name") == catalog), None)


def _register(w: WatsonxData, body: dict) -> None:
    catalog = body["associated_catalog"]["catalog_name"]
    if _existing(w, catalog):
        print(f"Data source for catalog {catalog} already registered")
    else:
        r = _post(w, "/database_registrations", body)
        if r.status_code >= 300:
            raise SystemExit(f"Registration failed ({r.status_code}): {r.text[:400]}")
        print(f"Registered {body['display_name']} as catalog {catalog} (id {r.json()['id']})")
    attach(w, catalog)


def attach(w: WatsonxData, catalog: str) -> None:
    """Associate a catalog with the Presto engine and wait until Presto can see it."""
    for _ in range(10):
        cat = next(c for c in w._api("GET", "/catalogs").json()["catalogs"] if c["name"] == catalog)
        if w.s.presto_engine in (cat.get("associated_engines") or []):
            break
        _post(w, f"/presto_engines/{w.s.presto_engine}/catalogs", {"catalog_names": [catalog]})
        time.sleep(20)
    print(f"Catalog {catalog} attached to {w.s.presto_engine}; waiting for Presto to load it", end="", flush=True)
    for _ in range(40):
        try:
            if any(r[0] == catalog for r in w.sql("SHOW CATALOGS")[1]):
                print(" … ready")
                return
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(15)
    raise SystemExit(f"\nPresto has not loaded {catalog} yet; try again in a few minutes")


def register_kafka(w: WatsonxData) -> None:
    s = w.s
    host, port = s.kafka_bootstrap.rsplit(":", 1)
    _register(w, {
        "display_name": "confluent-f1",
        "type": "kafka",
        "description": "Confluent Cloud: live 2026 race results",
        "associated_catalog": {"catalog_name": KAFKA_CATALOG, "catalog_type": "kafka"},
        "connection": {
            "hostname": host, "port": int(port), "hosts": s.kafka_bootstrap,
            "sasl": True, "sasl_mechanism": "plain",
            "username": s.kafka_key, "password": s.kafka_secret,  # Confluent API key and secret
            "tables": s.kafka_topic,                            # topics exposed as tables
        },
    })


def ca_certificate(label: str = "ISRG Root X1") -> str:
    """The root CA that signs Neon's certificate (Let's Encrypt), from the certifi bundle.

    watsonx.data validates a database's TLS certificate against the CA you upload, even
    when the CA is a public one.
    """
    bundle = Path(certifi.where()).read_text()
    m = re.search(r'# Label: "' + re.escape(label) + r'".*?(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)',
                  bundle, re.S)
    return m.group(1)


def register_postgres(w: WatsonxData, pg_url: str) -> None:
    u = urlparse(pg_url)
    # Use Neon's direct endpoint, not the "-pooler" one: Presto's JDBC connector keeps
    # sessions and prepared statements, which a transaction pooler does not preserve.
    host = u.hostname.replace("-pooler.", ".")
    _register(w, {
        "display_name": "neon-fantasy-league",
        "type": "postgresql",
        "description": "Fantasy-league app database on Neon PostgreSQL",
        "associated_catalog": {"catalog_name": PG_CATALOG, "catalog_type": "postgresql"},
        "connection": {
            "hostname": host, "port": u.port or 5432, "name": u.path.lstrip("/"),  # the database name
            "username": u.username, "password": u.password,
            "ssl": True, "certificate": ca_certificate(), "certificate_extension": "pem",
            "validate_server_certificate": True,
        },
    })
