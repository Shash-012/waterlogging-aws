"""Contract tests against a deployed core API: pytest core/tests/contract --api $CORE_API_URL"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "contract" / "tools"))
import validate as contract  # noqa: E402

SCHEMAS, REGISTRY = contract.load_registry()
PARAMS = json.loads((ROOT / "model" / "params.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def api(request):
    url = request.config.getoption("--api")
    if not url:
        pytest.skip("pass --api <CoreApiUrl> to run contract tests")
    return url.rstrip("/")


def get(api, path):
    try:
        with urllib.request.urlopen(api + path, timeout=30) as r:
            return r.status, json.loads(r.read().decode("utf-8")), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8")), dict(e.headers)


def assert_valid(doc, schema):
    errors = [f"{list(e.absolute_path)}: {e.message}"
              for e in Draft202012Validator(SCHEMAS[schema], registry=REGISTRY).iter_errors(doc)]
    assert errors == [], errors[:5]


def no_contract_errors(fn, *args):
    contract.errors.clear()
    fn(*args)
    assert contract.errors == [], contract.errors[:5]


@pytest.fixture(scope="session")
def hotspots(api):
    status, body, _ = get(api, "/hotspots")
    assert status == 200
    return body


def test_health(api):
    status, body, _ = get(api, "/health")
    assert status == 200
    assert_valid(body, "health.schema.json")
    assert body["ok"] is True and body["latest_run_id"]


def test_hotspots_list(hotspots):
    assert_valid(hotspots, "hotspot_list.schema.json")
    assert len(hotspots) >= 50
    no_contract_errors(contract.check_hotspots, "GET /hotspots", hotspots, PARAMS)


def test_hotspot_by_id(api, hotspots):
    status, body, _ = get(api, f"/hotspots/{hotspots[0]['hotspot_id']}")
    assert status == 200
    assert_valid(body, "hotspot.schema.json")
    assert body == hotspots[0]


def test_unknown_hotspot_is_contract_error(api):
    status, body, _ = get(api, "/hotspots/DL-999")
    assert status == 404
    assert_valid(body, "error.schema.json")


def test_scores_latest(api, hotspots):
    status, snap, _ = get(api, "/scores/latest")
    assert status == 200
    assert_valid(snap, "snapshot.schema.json")
    assert snap["mode"] == "live" and len(snap["hotspots"]) == len(hotspots)
    no_contract_errors(contract.check_snapshot, "GET /scores/latest", snap, PARAMS,
                       {h["hotspot_id"]: h for h in hotspots})


@pytest.mark.parametrize("count", [0, 6, 50])
def test_pumps(api, hotspots, count):
    status, plan, _ = get(api, f"/pumps?count={count}")
    assert status == 200
    assert_valid(plan, "pump_plan.schema.json")
    _, snap, _ = get(api, "/scores/latest")
    if plan["run_id"] == snap["run_id"]:
        assert plan == contract.expected_pump_plan(snap, count, {h["hotspot_id"]: h for h in hotspots})


@pytest.mark.parametrize("bad", ["51", "-1", "six"])
def test_pumps_rejects_bad_count(api, bad):
    status, body, _ = get(api, f"/pumps?count={bad}")
    assert status == 400
    assert_valid(body, "error.schema.json")


def test_replays(api, hotspots):
    status, index, _ = get(api, "/replays")
    assert status == 200
    assert_valid(index, "replay_index.schema.json")
    assert {r["kind"] for r in index} == {"storm", "dry"}
    by_id = {h["hotspot_id"]: h for h in hotspots}
    for entry in index:
        status, rep, _ = get(api, f"/replays/{entry['event_id']}")
        assert status == 200, entry["event_id"]
        assert_valid(rep, "replay.schema.json")
        no_contract_errors(contract.check_replay, entry["event_id"], rep, PARAMS, by_id, index)


def test_unknown_replay_is_contract_error(api):
    status, body, _ = get(api, "/replays/1999-01-01")
    assert status == 404
    assert_valid(body, "error.schema.json")


def test_cors_allows_localhost(api):
    req = urllib.request.Request(api + "/health", headers={"Origin": "http://localhost:5173"})
    with urllib.request.urlopen(req, timeout=30) as r:
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
