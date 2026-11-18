"""Replay a 2026 Grand Prix to Confluent Cloud, one result per message.

    python -m streaming.producer --round 1            # publish Round 1 (Australian GP)
    python -m streaming.producer --round 1 --delay 0  # publish without the dramatic pause
    python -m streaming.producer --list               # show the rounds you can replay

Each message is a JSON race-result event keyed by "<season>-<round>-<driver_id>". The key
means a replayed result lands on the same partition as the original, and Silver's MERGE
de-duplicates it, so publishing a round twice is harmless.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from lakehouse import config

STREAM_FILE = config.ROOT / "data" / "stream" / "races_2026.json"


def kafka_conf(s) -> dict:
    return {"bootstrap.servers": s.kafka_bootstrap, "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN", "sasl.username": s.kafka_key, "sasl.password": s.kafka_secret}


def ensure_topic(s) -> None:
    admin = AdminClient(kafka_conf(s))
    if s.kafka_topic in admin.list_topics(timeout=20).topics:
        return
    print(f"Creating topic {s.kafka_topic}")
    for f in admin.create_topics([NewTopic(s.kafka_topic, num_partitions=1, replication_factor=3)]).values():
        f.result()


def to_event(season: int, rnd: int, race: dict, r: dict) -> dict:
    status = r["status"]
    lapped = re.match(r"^\+(\d+) Laps?$", status)
    if status == "Finished":
        position_text, laps = str(r["pos"]), race["laps"]
    elif lapped:
        position_text, laps = str(r["pos"]), race["laps"] - int(lapped.group(1))
    elif status.lower() in ("did not start", "withdrew"):
        position_text, laps = "W", 0
    else:
        position_text, laps = "R", None
    return {
        "season": season, "round": rnd, "session_type": "RACE",
        "race_name": race["race_name"], "race_date": race["date"], "circuit_id": race["circuit_id"],
        "driver_id": r["driver_id"], "constructor_id": r["team"], "car_number": r["num"],
        "grid": r["grid"], "position": r["pos"], "position_text": position_text,
        "points": float(r["points"]), "laps": laps, "status": status,
        "event_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int)
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between finishers")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    season_data = {int(k): v for k, v in json.loads(STREAM_FILE.read_text()).items()}
    if a.list or not a.round:
        for rnd, race in season_data.items():
            print(f"  Round {rnd:>2}  {race['date']}  {race['race_name']}")
        return
    race = season_data[a.round]
    s = config.load()
    ensure_topic(s)
    producer = Producer(kafka_conf(s))
    print(f"🏁 2026 Round {a.round}: {race['race_name']} → topic {s.kafka_topic}")

    def delivered(err, msg):
        if err:
            print(f"  ✗ {msg.key().decode()}: {err}")

    for r in sorted(race["results"], key=lambda x: x["pos"]):
        ev = to_event(2026, a.round, race, r)
        key = f"{ev['season']}-{ev['round']}-{ev['driver_id']}"
        producer.produce(s.kafka_topic, key=key, value=json.dumps(ev), on_delivery=delivered)
        producer.poll(0)
        print(f"  P{ev['position']:<2} {ev['driver_id']:<16} {ev['constructor_id']:<14} "
              f"{ev['points']:>4} pts  {ev['status']}")
        time.sleep(a.delay)
    producer.flush(30)
    print(f"Published {len(race['results'])} results.")


if __name__ == "__main__":
    main()
