"""Load the fantasy-league app database into PostgreSQL (Neon).

    python postgres/load.py
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

with psycopg.connect(os.environ["NEON_PG_URL"]) as conn:
    conn.execute((ROOT / "postgres" / "fantasy_league.sql").read_text())
    for table in ("fantasy_managers", "driver_prices", "fantasy_picks"):
        n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n} rows")
