"""POST /alerts: validate, render Hindi + English, send to Telegram, log, dedupe.

The same hotspot, run and mode within 30 minutes returns the earlier alert with
duplicate: true, so a double-click never double-sends. The bot token is read from
SSM at runtime and is never logged.
"""
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DEDUPE_S = 30 * 60
IST = timezone(timedelta(hours=5, minutes=30))

HERE = Path(__file__).resolve().parent
# In Lambda everything sits next to app.py (see ops/stage.py); in tests it comes from the source tree.
OPS = HERE if (HERE / "templates").exists() else HERE.parents[1]
FIXTURE = HERE / "hotspots_fixture.json"
if not FIXTURE.exists():
    FIXTURE = OPS.parent / "contract" / "fixtures" / "hotspots.json"

HOTSPOT_ID = re.compile(r"^[A-Z]{2}-\d{3,}$")
UTC_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
LEVELS = ("LOW", "WATCH", "HIGH", "CRITICAL")
FIELDS = ("hotspot_id", "run_id", "mode", "event_id", "level", "risk", "peak_at")
REQUIRED = ("hotspot_id", "run_id", "mode", "level", "risk", "peak_at")


class HttpError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# --- validation (mirrors contract/schemas/alert_request.schema.json) ---

def validate(body):
    if not isinstance(body, dict):
        raise HttpError(400, "bad_request", "Body must be a JSON object.")
    extra = sorted(set(body) - set(FIELDS))
    if extra:
        raise HttpError(400, "bad_request", f"Unknown field(s): {', '.join(extra)}.")
    missing = [f for f in REQUIRED if f not in body]
    if missing:
        raise HttpError(400, "bad_request", f"Missing field(s): {', '.join(missing)}.")

    def bad(field, what):
        raise HttpError(400, "bad_request", f"{field} must be {what}.")

    if not isinstance(body["hotspot_id"], str) or not HOTSPOT_ID.match(body["hotspot_id"]):
        bad("hotspot_id", "like DL-001")
    if not isinstance(body["run_id"], str) or not UTC_TIME.match(body["run_id"]):
        bad("run_id", "a UTC time ending in Z")
    if body["mode"] not in ("live", "replay"):
        bad("mode", '"live" or "replay"')
    event_id = body.get("event_id")
    if event_id is not None and not isinstance(event_id, str):
        bad("event_id", "a string or null")
    if body["mode"] == "replay" and not event_id:
        bad("event_id", "set for a replay alert")
    if body["level"] not in LEVELS:
        bad("level", "one of " + ", ".join(LEVELS))
    risk = body["risk"]
    if isinstance(risk, bool) or not isinstance(risk, (int, float)) or not 0 <= risk <= 1:
        bad("risk", "a number from 0 to 1")
    peak = body["peak_at"]
    if peak is not None and (not isinstance(peak, str) or not UTC_TIME.match(peak)):
        bad("peak_at", "a UTC time ending in Z, or null")
    return {f: body.get(f) for f in FIELDS}


# --- rendering (ops/templates/) ---

def load_templates():
    t = OPS / "templates"
    labels = json.loads((t / "labels.json").read_text(encoding="utf-8"))
    return {
        lang: {**labels[lang], "text": (t / f"alert_{lang}.txt").read_text(encoding="utf-8").strip()}
        for lang in ("en", "hi")
    }


def parse_utc(s):
    return datetime.strptime(s.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def render(req, hotspot, templates):
    out = {}
    for lang, t in templates.items():
        tag = ""
        if req["mode"] == "replay":
            try:
                d = date.fromisoformat(req["event_id"])
                label = f"{d.day} {t['months'][d.month - 1]} {d.year}"
            except ValueError:
                label = req["event_id"]
            tag = t["replay_tag"].format(date=label)
        peak = ""
        if req["peak_at"]:
            peak = t["peak"].format(time=parse_utc(req["peak_at"]).astimezone(IST).strftime("%H:%M"))
        out[lang] = t["text"].format(
            replay_tag=tag,
            level=t["levels"][req["level"]],
            name=hotspot[f"name_{lang}"],
            risk=f"{req['risk']:.3f}",
            peak=peak,
            avoid=hotspot.get(f"avoid_{lang}") or "",
            diversion=hotspot.get(f"diversion_{lang}") or "",
        ).strip()
    return out["en"], out["hi"]


def route_groups(hotspot_id, routing):
    return routing.get("hotspots", {}).get(hotspot_id) or routing["default"]


# --- the send itself, with every outside dependency passed in ---

def send_alert(req, sent_by, deps):
    """Returns the AlertResponse dict. deps: store, get_hotspot, telegram, now."""
    key = f"{req['hotspot_id']}|{req['run_id']}|{req['mode']}"
    store = deps["store"]
    now = deps["now"]()

    earlier = store.recent(key, now)
    if earlier:
        return {**response_of(earlier), "duplicate": True}

    hotspot = deps["get_hotspot"](req["hotspot_id"])
    if hotspot is None:
        raise HttpError(404, "not_found", f"No hotspot with id {req['hotspot_id']}.")
    text_en, text_hi = render(req, hotspot, deps["templates"])

    if not store.claim(key, now):
        # A send for the same key is in flight (double-click): wait for it and return it.
        for _ in range(20):
            time.sleep(deps.get("poll_s", 0.25))
            earlier = store.recent(key, deps["now"]())
            if earlier:
                return {**response_of(earlier), "duplicate": True}
        raise HttpError(409, "in_progress", "The same alert is being sent; try again in a moment.")

    message = f"{text_en}\n\n{text_hi}"
    deliveries = []
    for group in route_groups(req["hotspot_id"], deps["routing"]):
        deliveries.append({"group": group, "ok": deps["telegram"](group, message)})

    record = {
        **req,
        "alert_id": f"alrt-{now:%Y%m%d%H%M%S}-{req['hotspot_id'].lower().replace('-', '')}-{uuid.uuid4().hex[:6]}",
        "sent_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duplicate": False,
        "text_en": text_en,
        "text_hi": text_hi,
        "deliveries": deliveries,
        "sent_by": sent_by,
    }
    store.add(record)
    if any(d["ok"] for d in deliveries):
        store.finish(key, record, now)
    else:
        store.release(key)  # nothing went out, so let the official retry straight away
    return response_of(record)


def response_of(record):
    keys = ("alert_id", "sent_at", "duplicate", "text_en", "text_hi", "deliveries")
    return {k: record[k] for k in keys}


# --- AWS / network implementations ---

class DynamoStore:
    def __init__(self, table):
        self.table = table

    def recent(self, key, now):
        item = self.table.get_item(Key={"pk": f"DEDUPE#{key}", "sk": "-"}, ConsistentRead=True).get("Item")
        if item and "doc" in item and int(item["claimed_at"]) >= now.timestamp() - DEDUPE_S:
            return json.loads(item["doc"])
        return None

    def claim(self, key, now):
        from botocore.exceptions import ClientError

        ts = int(now.timestamp())
        try:
            self.table.put_item(
                Item={"pk": f"DEDUPE#{key}", "sk": "-", "claimed_at": ts, "expires_at": ts + DEDUPE_S + 3600},
                ConditionExpression="attribute_not_exists(pk) OR claimed_at < :cutoff",
                ExpressionAttributeValues={":cutoff": ts - DEDUPE_S},
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def finish(self, key, record, now):
        self.table.update_item(
            Key={"pk": f"DEDUPE#{key}", "sk": "-"},
            UpdateExpression="SET doc = :d",
            ExpressionAttributeValues={":d": json.dumps(record, ensure_ascii=False)},
        )

    def release(self, key):
        self.table.delete_item(Key={"pk": f"DEDUPE#{key}", "sk": "-"})

    def add(self, record):
        self.table.put_item(
            Item={
                "pk": "ALERT",
                "sk": f"{record['sent_at']}#{record['alert_id']}",
                "hotspot_id": record["hotspot_id"],
                "level": record["level"],
                "mode": record["mode"],
                "sent_by": record["sent_by"],
                "doc": json.dumps(record, ensure_ascii=False),
            }
        )


def hotspot_getter(core_api_url):
    if core_api_url == "fixtures":
        by_id = {h["hotspot_id"]: h for h in json.loads(FIXTURE.read_text(encoding="utf-8"))}
        return by_id.get

    base = core_api_url.rstrip("/")

    def get(hotspot_id):
        url = f"{base}/hotspots/{urllib.parse.quote(hotspot_id)}"
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise HttpError(502, "core_unavailable", f"Core API answered {e.code} for {hotspot_id}.")
        except (urllib.error.URLError, TimeoutError):
            raise HttpError(502, "core_unavailable", "Core API did not answer.")

    return get


_secrets = None


def telegram_sender():
    global _secrets
    if _secrets is None:
        import boto3

        names = [os.environ["BOT_TOKEN_PARAM"], os.environ["GROUPS_PARAM"]]
        got = boto3.client("ssm").get_parameters(Names=names, WithDecryption=True)
        values = {p["Name"]: p["Value"] for p in got["Parameters"]}
        _secrets = {
            "token": values.get(names[0]),
            "groups": json.loads(values.get(names[1], "{}")),
        }

    def send(group, text):
        chat_id = _secrets["groups"].get(group)
        if not _secrets["token"] or chat_id is None:
            log({"event": "telegram_skip", "group": group, "reason": "no token or chat id"})
            return False
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{_secrets['token']}/sendMessage", data=data)
        try:
            with urllib.request.urlopen(req, timeout=6) as r:
                return bool(json.loads(r.read()).get("ok"))
        except Exception as e:  # never log the exception text: the URL holds the token
            status = getattr(e, "code", None)
            log({"event": "telegram_error", "group": group, "error": type(e).__name__, "status": status})
            return False

    return send


def log(obj):
    print(json.dumps(obj, ensure_ascii=False))


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json; charset=utf-8"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def username_of(event):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    return claims.get("cognito:username") or claims.get("username") or claims.get("sub") or "unknown"


_deps = None


def default_deps():
    global _deps
    if _deps is None:
        import boto3

        _deps = {
            "store": DynamoStore(boto3.resource("dynamodb").Table(os.environ["ALERTS_TABLE"])),
            "get_hotspot": hotspot_getter(os.environ.get("CORE_API_URL", "fixtures")),
            "telegram": telegram_sender(),
            "templates": load_templates(),
            "routing": json.loads((OPS / "config" / "routing.json").read_text(encoding="utf-8")),
            "now": lambda: datetime.now(timezone.utc),
        }
    return _deps


def handler(event, context, deps=None):
    try:
        try:
            raw = event.get("body") or ""
            if event.get("isBase64Encoded"):
                import base64

                raw = base64.b64decode(raw).decode("utf-8")
            body = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise HttpError(400, "bad_request", "Body must be valid JSON.")
        req = validate(body)
        sent_by = username_of(event)
        result = send_alert(req, sent_by, deps or default_deps())
        log({
            "event": "alert",
            "alert_id": result["alert_id"],
            "hotspot_id": req["hotspot_id"],
            "mode": req["mode"],
            "level": req["level"],
            "duplicate": result["duplicate"],
            "deliveries": result["deliveries"],
            "sent_by": sent_by,
        })
        return respond(200, result)
    except HttpError as e:
        return respond(e.status, {"error": {"code": e.code, "message": e.message}})
