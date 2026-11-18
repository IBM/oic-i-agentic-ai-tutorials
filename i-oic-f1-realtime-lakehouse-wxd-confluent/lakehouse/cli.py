"""Command line for the F1 lakehouse.

    python -m lakehouse upload        # raw files + Spark apps -> object storage
    python -m lakehouse bronze        # Spark: raw files -> f1_bronze
    python -m lakehouse silver        # Spark: f1_bronze -> f1_silver (MERGE)
    python -m lakehouse gold          # Presto: f1_silver -> f1_gold
    python -m lakehouse stream        # Spark Structured Streaming: Kafka -> f1_bronze.race_events
    python -m lakehouse refresh       # stream + silver + gold, after a race
    python -m lakehouse counts        # row counts for every medallion table
    python -m lakehouse files f1_silver.results   # the Parquet and metadata files behind a table
    python -m lakehouse register kafka|postgres   # attach a data source to Presto
    python -m lakehouse sql "SELECT ..."
    python -m lakehouse engines [pause|resume]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config
from .wxd import WatsonxData

ROOT = config.ROOT
SPARK_DIR = Path(__file__).parent / "spark"
SQL_DIR = Path(__file__).parent / "sql"


def _print_table(cols, rows, max_rows=50):
    if not cols:
        print("(no result set)")
        return
    rows = [["NULL" if v is None else str(v) for v in r] for r in rows[:max_rows]]
    widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    line = "  ".join(c.ljust(w) for c, w in zip(cols, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))


def cmd_upload(w: WatsonxData, _):
    s = w.s
    raw = ROOT / "data" / "raw"
    files = sorted(p for p in raw.rglob("*") if p.is_file())
    apps = sorted(SPARK_DIR.glob("*.py"))
    jobs = [(p, f"{s.landing_prefix}/{p.relative_to(raw).as_posix()}") for p in files] + \
           [(p, f"{s.apps_prefix}/{p.name}") for p in apps]
    print(f"Uploading {len(files)} raw files to {s.landing_uri}/")
    print(f"Uploading {len(apps)} Spark applications to s3a://{s.landing_bucket}/{s.apps_prefix}/")
    w.token()  # fetch once before the threads share it
    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda job: w.upload(*job), jobs))
    print(f"Done: {len(jobs)} objects uploaded.")


def _run_spark(w: WatsonxData, app: str, args: list[str], **kw) -> None:
    w.upload(SPARK_DIR / app, f"{w.s.apps_prefix}/{app}")  # always run the local version
    app_id = w.submit_spark(f"{w.s.apps_prefix}/{app}", args, name=app.removesuffix(".py"), **kw)
    print(f"Submitted {app} as Spark application {app_id}")
    st = w.wait_spark(app_id)
    print_driver_log(w, app_id, only_ours=True)
    if st.get("state") != "finished":
        print_driver_log(w, app_id, only_ours=False)
        sys.exit(f"Spark application {app_id} ended in state {st.get('state')}.")


def print_driver_log(w: WatsonxData, app_id: str, only_ours: bool) -> None:
    """Print our job's own output, or on failure the errors from the Spark driver log."""
    key = f"spark/{w.s.spark_engine}/logs/{app_id}/spark-driver-0"
    try:
        log = w.read_object(key, bucket=w.s.bucket)
    except Exception:
        print(f"  (driver log not available yet: s3a://{w.s.bucket}/{key})")
        return
    lines = log.splitlines()
    if only_ours:
        keep = [l for l in lines if re.match(r"^(bronze|silver|stream)\.|^[A-Z]+_SUMMARY|^f1_", l)]
    else:
        keep = [l for l in lines if re.search(r"Error|Exception|Traceback|^\s+File ", l) and not l.startswith("\tat ")][-25:]
    for l in keep:
        print("  | " + l[:300])


def cmd_bronze(w: WatsonxData, _):
    s = w.s
    _run_spark(w, "bronze_ingest.py", ["--catalog", s.catalog, "--landing", s.landing_uri,
                                       "--warehouse", s.warehouse, "--schema", s.bronze])
    cmd_counts(w, argparse.Namespace(layer=s.bronze))


def cmd_silver(w: WatsonxData, _):
    s = w.s
    _run_spark(w, "silver_transform.py", ["--catalog", s.catalog, "--warehouse", s.warehouse,
                                          "--bronze", s.bronze, "--silver", s.silver])
    cmd_counts(w, argparse.Namespace(layer=s.silver))


KAFKA_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"


def cmd_stream(w: WatsonxData, _):
    s = w.s
    _run_spark(w, "stream_ingest.py",
               ["--catalog", s.catalog, "--warehouse", s.warehouse, "--topic", s.kafka_topic,
                "--checkpoint", f"s3a://{s.landing_bucket}/{s.checkpoint_prefix}/race_events", "--schema", s.bronze],
               packages=KAFKA_PACKAGE,
               env={"KAFKA_BOOTSTRAP": s.kafka_bootstrap, "KAFKA_API_KEY": s.kafka_key,
                    "KAFKA_API_SECRET": s.kafka_secret})
    _, r = w.sql(f"SELECT count(*) FROM {s.catalog}.{s.bronze}.race_events")
    print(f"{s.bronze}.race_events now holds {r[0][0]} Kafka messages")


def cmd_refresh(w: WatsonxData, a):
    """Race weekend: land new Kafka messages, merge them into Silver, rebuild Gold."""
    t0 = time.time()
    print("▸ 1/3 Stream: Kafka → Bronze"); cmd_stream(w, a)
    print("▸ 2/3 Silver: MERGE"); cmd_silver(w, a)
    print("▸ 3/3 Gold: rebuild"); cmd_gold(w, a)
    print(f"Lakehouse refreshed in {time.time() - t0:.0f}s")


def substitute(w: WatsonxData, text: str) -> str:
    """Fill ${catalog}, ${bronze}, ${silver}, ${gold} and ${warehouse} from .env."""
    for k, v in {"catalog": w.s.catalog, "bronze": w.s.bronze, "silver": w.s.silver,
                 "gold": w.s.gold, "warehouse": w.s.warehouse}.items():
        text = text.replace("${" + k + "}", v)
    return text


def run_sql_file(w: WatsonxData, path: Path, quiet: bool = False):
    """Run every statement in a .sql file; return the last statement's result."""
    text = re.sub(r"--[^\n]*", "", substitute(w, path.read_text()))
    result = ([], [])
    for stmt in (x.strip() for x in text.split(";")):
        if not stmt:
            continue
        head = " ".join(stmt.split())[:90]
        t0 = time.time()
        result = w.sql(stmt)
        if not quiet:
            print(f"  ✓ {head}{'…' if len(stmt) > 90 else ''}  ({time.time() - t0:.1f}s)")
    return result


def cmd_gold(w: WatsonxData, _):
    for f in sorted((SQL_DIR / "gold").glob("*.sql")):
        print(f"▸ {f.name}")
        run_sql_file(w, f)
    cmd_counts(w, argparse.Namespace(layer=w.s.gold))


def cmd_counts(w: WatsonxData, a):
    s = w.s
    layers = [a.layer] if getattr(a, "layer", None) else [s.bronze, s.silver, s.gold]
    rows = []
    for layer in layers:
        try:
            _, tables = w.sql(f"SHOW TABLES FROM {s.catalog}.{layer}")
        except Exception:
            continue
        for (t,) in tables:
            _, r = w.sql(f'SELECT count(*) FROM {s.catalog}.{layer}."{t}"')
            rows.append((f"{layer}.{t}", r[0][0]))
    _print_table(["table", "rows"], rows, max_rows=200)


def cmd_sql(w: WatsonxData, a):
    stmt = a.statement if a.statement != "-" else sys.stdin.read()
    p = Path(stmt)
    if p.suffix == ".sql" and p.exists():
        cols, rows = run_sql_file(w, p, quiet=True)
    else:
        cols, rows = w.sql(substitute(w, stmt))
    _print_table(cols, rows, a.max_rows)


def cmd_files(w: WatsonxData, a):
    """Show the object-storage files behind an Iceberg table, for example f1_silver.results."""
    schema, table = a.table.split(".")
    prefix = f"{schema}/{table}/"
    objs = w.list_objects(prefix, bucket=w.s.bucket)
    data = [o for o in objs if "/data/" in o[0]]
    meta = [o for o in objs if "/metadata/" in o[0]]
    print(f"s3a://{w.s.bucket}/{prefix}")
    print(f"  data/      {len(data):>4} Parquet files, {sum(s for _, s in data) / 1e6:.1f} MB")
    print(f"  metadata/  {len(meta):>4} files (table metadata, manifests and one snapshot list per commit)")
    for k, size in data[-3:] + meta[-3:]:
        print(f"  {size:>8}  {k.removeprefix(prefix)}")


def cmd_logs(w: WatsonxData, a):
    print_driver_log(w, a.app_id, only_ours=False)


def cmd_register(w: WatsonxData, a):
    from . import register
    if a.source == "kafka":
        register.register_kafka(w)
    else:
        url = os.getenv("NEON_PG_URL", "").strip()
        if not url:
            sys.exit("Set NEON_PG_URL in .env to your Neon connection string")
        register.register_postgres(w, url)


def cmd_engines(w: WatsonxData, a):
    if a.action in ("pause", "resume"):
        for e in w.engines():
            try:
                w.set_engine(e["type"], e["id"], a.action)
                print(f"{a.action} requested for {e['type']} engine {e['id']}")
            except RuntimeError as err:
                print(f"{e['id']}: {err}")
    for e in w.engines():
        print(f"{e['type']:<7} {e['id']:<12} {e['status']}")


def main():
    ap = argparse.ArgumentParser(prog="python -m lakehouse")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("upload")
    sub.add_parser("bronze")
    sub.add_parser("silver")
    sub.add_parser("gold")
    sub.add_parser("stream")
    sub.add_parser("refresh")
    lg = sub.add_parser("logs"); lg.add_argument("app_id")
    fl = sub.add_parser("files"); fl.add_argument("table", help="schema.table, for example f1_silver.results")
    c = sub.add_parser("counts"); c.add_argument("layer", nargs="?")
    q = sub.add_parser("sql"); q.add_argument("statement"); q.add_argument("--max-rows", type=int, default=50)
    g = sub.add_parser("register"); g.add_argument("source", choices=["kafka", "postgres"])
    e = sub.add_parser("engines"); e.add_argument("action", nargs="?", choices=["status", "pause", "resume"], default="status")
    a = ap.parse_args()
    w = WatsonxData(config.load())
    globals()[f"cmd_{a.cmd}"](w, a)


if __name__ == "__main__":
    main()
