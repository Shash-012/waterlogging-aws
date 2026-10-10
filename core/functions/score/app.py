"""Hourly scorer: Open-Meteo rain -> wlew_model.score_snapshot -> DynamoDB (+ LATEST pointer).

Triggered by EventBridge Scheduler rate(1 hour). Logs one structured JSON line per run.
"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3

import rain
from wlew_model import load_params, score_snapshot

DDB = boto3.resource("dynamodb")
HOTSPOTS = DDB.Table(os.environ.get("HOTSPOTS_TABLE", "hotspots"))
SNAPSHOTS = DDB.Table(os.environ.get("SNAPSHOTS_TABLE", "snapshots"))
KEEP_DAYS = 30


def from_ddb(x):
    if isinstance(x, list):
        return [from_ddb(v) for v in x]
    if isinstance(x, dict):
        return {k: from_ddb(v) for k, v in x.items()}
    if isinstance(x, Decimal):
        return int(x) if x == x.to_integral_value() and "." not in str(x) else float(x)
    return x


def load_hotspots():
    items, kwargs = [], {}
    while True:
        page = HOTSPOTS.scan(**kwargs)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            return [from_ddb(i) for i in items]
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def run(now=None):
    started = time.perf_counter()
    p = load_params()
    as_of = (now or datetime.now(timezone.utc)).replace(minute=0, second=0, microsecond=0)
    hotspots = sorted(load_hotspots(), key=lambda h: h["hotspot_id"])
    cells = [tuple(h["model_cell"]) for h in hotspots]
    series = rain.live_rain(cells)
    snap = score_snapshot(hotspots, {h["hotspot_id"]: s for h, s in zip(hotspots, series)}, as_of, p, mode="live")
    high = sum(1 for h in snap["hotspots"] if h["level"] in ("HIGH", "CRITICAL"))
    expires = int((as_of + timedelta(days=KEEP_DAYS)).timestamp())
    SNAPSHOTS.put_item(Item={
        "run_id": snap["run_id"], "as_of": snap["as_of"], "city_status": snap["city"]["status"],
        "rain_trigger_max": Decimal(str(snap["city"]["rain_trigger_max"])),
        "spots_raining": snap["city"]["spots_raining"], "spots_high_or_above": high,
        "params_version": snap["params_version"], "doc": json.dumps(snap, ensure_ascii=False),
        "expires_at": expires,
    })
    SNAPSHOTS.put_item(Item={"run_id": "LATEST", "latest_run_id": snap["run_id"], "as_of": snap["as_of"]})
    log = {"event": "scoring_run", "run_id": snap["run_id"], "city_status": snap["city"]["status"],
           "rain_trigger_max": snap["city"]["rain_trigger_max"], "spots_raining": snap["city"]["spots_raining"],
           "spots_high_or_above": high, "spots": len(snap["hotspots"]),
           "duration_ms": round((time.perf_counter() - started) * 1000)}
    print(json.dumps(log))
    return log


def handler(event, context):
    return run()
