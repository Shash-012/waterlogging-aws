import json
from datetime import datetime, timedelta, timezone

import pytest
from conftest import load_app

app = load_app("send_alert")

T0 = datetime(2026, 8, 25, 7, 5, tzinfo=timezone.utc)
EVENT = {"requestContext": {"authorizer": {"jwt": {"claims": {"cognito:username": "test-official"}}}}}


class MemoryStore:
    """Same behaviour as DynamoStore, in memory."""

    def __init__(self):
        self.locks, self.log = {}, []

    def recent(self, key, now):
        lock = self.locks.get(key)
        if lock and "doc" in lock and lock["claimed_at"] >= now.timestamp() - app.DEDUPE_S:
            return lock["doc"]
        return None

    def claim(self, key, now):
        lock = self.locks.get(key)
        if lock and lock["claimed_at"] >= now.timestamp() - app.DEDUPE_S:
            return False
        self.locks[key] = {"claimed_at": now.timestamp()}
        return True

    def finish(self, key, record, now):
        self.locks[key]["doc"] = record

    def release(self, key):
        self.locks.pop(key, None)

    def add(self, record):
        self.log.append(record)


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


@pytest.fixture
def deps(fixture):
    hotspots = {h["hotspot_id"]: h for h in fixture("hotspots")}
    sent = []

    def telegram(group, text):
        sent.append((group, text))
        return True

    return {
        "store": MemoryStore(),
        "get_hotspot": hotspots.get,
        "telegram": telegram,
        "templates": app.load_templates(),
        "routing": json.loads((app.OPS / "config" / "routing.json").read_text(encoding="utf-8")),
        "now": Clock(),
        "poll_s": 0,
        "sent": sent,
    }


def post(body, deps, event=EVENT):
    res = app.handler({**event, "body": body if isinstance(body, str) else json.dumps(body)}, None, deps)
    return res["statusCode"], json.loads(res["body"])


def test_replay_alert_renders_both_languages_and_reaches_both_groups(deps, fixture, schema_check):
    status, body = post(fixture("alert_request"), deps)
    assert status == 200
    schema_check("alert_response", body)
    assert body["duplicate"] is False
    # peak_at 11:00Z is 16:30 IST
    assert body["text_en"].startswith(
        "[Replay · 25 Aug 2026] HIGH waterlogging risk at Minto Bridge underpass (risk 0.368), peak expected 16:30 IST. "
    )
    assert body["text_hi"].startswith("[रीप्ले · 25 अगस्त 2026] मिंटो ब्रिज अंडरपास पर जलभराव का उच्च खतरा (जोखिम 0.368), चरम लगभग 16:30 IST. ")
    h = {x["hotspot_id"]: x for x in fixture("hotspots")}["DL-001"]
    assert body["text_en"].endswith(f"{h['avoid_en']} {h['diversion_en']}")
    assert body["text_hi"].endswith(f"{h['avoid_hi']} {h['diversion_hi']}")

    assert body["deliveries"] == [{"group": "traffic-police-demo", "ok": True}, {"group": "rwa-demo", "ok": True}]
    assert [g for g, _ in deps["sent"]] == ["traffic-police-demo", "rwa-demo"]
    assert all(text == f"{body['text_en']}\n\n{body['text_hi']}" for _, text in deps["sent"])

    (record,) = deps["store"].log
    schema_check("alert_record", record)
    assert record["sent_by"] == "test-official"
    schema_check("alert_log", {"alerts": [record]})


def test_live_alert_has_no_replay_tag_and_handles_no_peak(deps, fixture):
    req = {**fixture("alert_request"), "mode": "live", "event_id": None, "peak_at": None, "level": "CRITICAL"}
    status, body = post(req, deps)
    assert status == 200
    assert body["text_en"].startswith("CRITICAL waterlogging risk at Minto Bridge underpass (risk 0.368). ")
    assert "गंभीर खतरा (जोखिम 0.368). " in body["text_hi"]
    assert "Replay" not in body["text_en"] and "रीप्ले" not in body["text_hi"]


def test_double_click_within_30_minutes_returns_the_earlier_alert(deps, fixture):
    _, first = post(fixture("alert_request"), deps)
    deps["now"].t = T0 + timedelta(minutes=29)
    status, second = post(fixture("alert_request"), deps)
    assert status == 200
    assert second == {**first, "duplicate": True}
    assert len(deps["sent"]) == 2  # one message per group, sent once
    assert len(deps["store"].log) == 1

    # Another run is a new alert; so is the same run after 30 minutes.
    _, other_run = post({**fixture("alert_request"), "run_id": "2026-08-25T08:00:00Z"}, deps)
    assert other_run["duplicate"] is False
    deps["now"].t = T0 + timedelta(minutes=31)
    _, later = post(fixture("alert_request"), deps)
    assert later["duplicate"] is False and later["alert_id"] != first["alert_id"]


def test_failed_send_is_logged_but_can_be_retried_at_once(deps, fixture):
    deps["telegram"] = lambda group, text: False
    _, body = post(fixture("alert_request"), deps)
    assert body["deliveries"] == [{"group": "traffic-police-demo", "ok": False}, {"group": "rwa-demo", "ok": False}]
    deps["telegram"] = lambda group, text: True
    _, retry = post(fixture("alert_request"), deps)
    assert retry["duplicate"] is False and all(d["ok"] for d in retry["deliveries"])
    assert len(deps["store"].log) == 2


def test_concurrent_send_waits_for_the_first(deps, fixture):
    store = deps["store"]
    _, first = post(fixture("alert_request"), deps)
    key = "DL-001|2026-08-25T07:00:00Z|replay"
    doc = store.locks[key].pop("doc")  # as if the first send hasn't finished yet
    calls = {"n": 0}
    real_recent = store.recent

    def recent(k, now):
        calls["n"] += 1
        if calls["n"] == 3:
            store.locks[key]["doc"] = doc
        return real_recent(k, now)

    store.recent = recent
    _, second = post(fixture("alert_request"), deps)
    assert second == {**first, "duplicate": True}


def test_routing_per_hotspot(deps, fixture):
    deps["routing"] = {"default": ["traffic-police-demo", "rwa-demo"], "hotspots": {"DL-001": ["rwa-demo"]}}
    _, body = post(fixture("alert_request"), deps)
    assert body["deliveries"] == [{"group": "rwa-demo", "ok": True}]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"risk": 1.5}, "risk"),
        ({"risk": True}, "risk"),
        ({"level": "SEVERE"}, "level"),
        ({"hotspot_id": "dl-1"}, "hotspot_id"),
        ({"run_id": "2026-08-25 07:00"}, "run_id"),
        ({"event_id": None}, "event_id"),
        ({"mode": "test"}, "mode"),
        ({"extra": 1}, "Unknown field"),
        ({"peak_at": "soon"}, "peak_at"),
    ],
)
def test_bad_requests_get_400_in_the_contract_error_shape(deps, fixture, schema_check, change, message):
    status, body = post({**fixture("alert_request"), **change}, deps)
    assert status == 400
    schema_check("error", body)
    assert message in body["error"]["message"]
    assert deps["sent"] == []


def test_missing_field_and_bad_json(deps, fixture):
    req = fixture("alert_request")
    del req["risk"]
    assert post(req, deps)[0] == 400
    status, body = post("{not json", deps)
    assert status == 400 and body["error"]["code"] == "bad_request"


def test_unknown_hotspot_is_404(deps, fixture, schema_check):
    status, body = post({**fixture("alert_request"), "hotspot_id": "DL-999"}, deps)
    assert status == 404
    schema_check("error", body)
    assert deps["sent"] == []


def test_fixture_mode_reads_the_packed_hotspot_list():
    get = app.hotspot_getter("fixtures")
    assert get("DL-001")["name_en"] == "Minto Bridge underpass"
    assert get("DL-999") is None
