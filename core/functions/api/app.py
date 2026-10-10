"""Core read API (HTTP API payload v2). Routes and shapes per contract/CONTRACT.md."""
import json
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from wlew_model import pump_plan

DDB = boto3.resource("dynamodb")
HOTSPOTS = DDB.Table(os.environ.get("HOTSPOTS_TABLE", "hotspots"))
SNAPSHOTS = DDB.Table(os.environ.get("SNAPSHOTS_TABLE", "snapshots"))
S3 = boto3.client("s3")
BUCKET = os.environ.get("REPLAY_BUCKET", "")
INTERNAL_FIELDS = {"model_cell"}  # stored with each hotspot, never part of the contract record
_cache = {}


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _json(status, body, max_age=60):
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json; charset=utf-8", "Cache-Control": f"public, max-age={max_age}"},
            "body": json.dumps(body, ensure_ascii=False)}


def from_ddb(x):
    if isinstance(x, list):
        return [from_ddb(v) for v in x]
    if isinstance(x, dict):
        return {k: from_ddb(v) for k, v in x.items()}
    if isinstance(x, Decimal):
        return int(x) if x == x.to_integral_value() and "." not in str(x) else float(x)
    return x


def _hotspot_record(item):
    return {k: v for k, v in from_ddb(item).items() if k not in INTERNAL_FIELDS}


def all_hotspots():
    items, kwargs = [], {}
    while True:
        page = HOTSPOTS.scan(**kwargs)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return sorted((_hotspot_record(i) for i in items), key=lambda h: h["hotspot_id"])


def latest_snapshot():
    pointer = SNAPSHOTS.get_item(Key={"run_id": "LATEST"}).get("Item")
    if not pointer:
        raise ApiError(404, "no_snapshot", "No scoring run has completed yet")
    item = SNAPSHOTS.get_item(Key={"run_id": pointer["latest_run_id"]}).get("Item")
    if not item:
        raise ApiError(404, "no_snapshot", f"Snapshot {pointer['latest_run_id']} not found")
    return json.loads(item["doc"])


def s3_json(key):
    if key in _cache:
        return _cache[key]
    try:
        body = S3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "AccessDenied", "404"):
            raise ApiError(404, "not_found", f"No such replay object {key}") from e
        raise
    _cache[key] = json.loads(body)
    return _cache[key]


def health(event):
    pointer = SNAPSHOTS.get_item(Key={"run_id": "LATEST"}).get("Item")
    return _json(200, {"ok": True, "latest_run_id": pointer["latest_run_id"] if pointer else None}, 0)


def hotspots(event):
    return _json(200, all_hotspots(), 300)


def hotspot(event):
    hid = event["pathParameters"]["id"]
    item = HOTSPOTS.get_item(Key={"hotspot_id": hid}).get("Item")
    if not item:
        raise ApiError(404, "not_found", f"No hotspot with id {hid}")
    return _json(200, _hotspot_record(item), 300)


def scores_latest(event):
    return _json(200, latest_snapshot())


def pumps(event):
    raw = (event.get("queryStringParameters") or {}).get("count", "6")
    try:
        count = int(raw)
    except ValueError:
        raise ApiError(400, "bad_request", "count must be an integer from 0 to 50") from None
    if not 0 <= count <= 50:
        raise ApiError(400, "bad_request", "count must be an integer from 0 to 50")
    snap = latest_snapshot()
    importance = {h["hotspot_id"]: h["importance"] for h in all_hotspots()}
    return _json(200, pump_plan(snap, count, importance))


def replays(event):
    return _json(200, s3_json("replays/index.json"), 3600)


def replay(event):
    event_id = event["pathParameters"]["event_id"]
    if event_id not in {r["event_id"] for r in s3_json("replays/index.json")}:
        raise ApiError(404, "not_found", f"No replay with event_id {event_id}")
    return _json(200, s3_json(f"replays/{event_id}.json"), 3600)


ROUTES = {
    "GET /health": health,
    "GET /hotspots": hotspots,
    "GET /hotspots/{id}": hotspot,
    "GET /scores/latest": scores_latest,
    "GET /pumps": pumps,
    "GET /replays": replays,
    "GET /replays/{event_id}": replay,
}


def handler(event, context):
    route = ROUTES.get(event.get("routeKey", ""))
    try:
        if route is None:
            raise ApiError(404, "not_found", f"No route {event.get('routeKey')}")
        return route(event)
    except ApiError as e:
        return _json(e.status, {"error": {"code": e.code, "message": e.message}}, 0)
    except Exception as e:  # noqa: BLE001 - always answer in the contract's error shape
        print(json.dumps({"event": "api_error", "route": event.get("routeKey"), "error": repr(e)}))
        return _json(500, {"error": {"code": "internal", "message": "Internal error"}}, 0)
