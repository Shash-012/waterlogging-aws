import itertools
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "model"))
sys.path.insert(0, str(ROOT / "contract" / "tools"))

import validate as contract  # noqa: E402
from wlew_model import (  # noqa: E402
    city_status, effective_intensity, level, load_params, pump_plan, rain_inputs, rain_trigger, risk,
    score_snapshot, susceptibility,
)

P = load_params()  # tuned model/params.json (A5)
P_CONTRACT = load_params(ROOT / "contract" / "fixtures" / "params.json")  # contract defaults
T0 = datetime(2026, 10, 9, 14, tzinfo=timezone.utc)
FIXTURES = ROOT / "contract" / "fixtures"
HOTSPOTS = json.loads((ROOT / "data" / "hotspots" / "hotspots_contract.json").read_text(encoding="utf-8"))
SCHEMAS, REGISTRY = contract.load_registry()


def schema_errors(doc, name):
    return list(Draft202012Validator(SCHEMAS[name], registry=REGISTRY).iter_errors(doc))


def contract_errors(fn, *args):
    contract.errors.clear()
    fn(*args)
    return list(contract.errors)


def test_worked_example():
    """The contract's worked example, with the contract's default parameters."""
    p = P_CONTRACT
    assert effective_intensity(14.0, 30.0, p) == pytest.approx(21.0)
    rt = rain_trigger(14.0, 30.0, p)
    assert rt == 0.64
    sus = susceptibility(0.8, 0.9, 0.72, p)
    assert sus == 0.815
    rk = risk(rt, sus)
    assert rk == 0.522
    assert level(rk, p) == "HIGH"
    assert city_status(rt, p) == "ALERT"


def test_levels_and_city_thresholds():
    assert [level(x, P) for x in (0.0, 0.149, 0.15, 0.349, 0.35, 0.599, 0.6, 1.0)] == \
        ["LOW", "LOW", "WATCH", "WATCH", "HIGH", "HIGH", "CRITICAL", "CRITICAL"]
    assert [city_status(x, P) for x in (0.0, 0.001, 0.4, 0.75)] == ["STANDBY", "RAIN_WATCH", "ALERT", "SEVERE"]


def test_dry_day_is_zero_and_standby():
    snap = score_snapshot(HOTSPOTS, {}, T0, P)
    assert snap["city"] == {"status": "STANDBY", "rain_trigger_max": 0.0, "spots_raining": 0}
    assert all(h["risk"] == 0 and h["level"] == "LOW" and h["peak_at"] is None for h in snap["hotspots"])


def test_more_rain_never_lowers_risk():
    rng = random.Random(7)
    for _ in range(2000):
        i, a, sus = rng.uniform(0, 60), rng.uniform(0, 150), rng.uniform(0, 1)
        di, da = rng.uniform(0, 10), rng.uniform(0, 30)
        assert rain_trigger(i + di, a + da, P) >= rain_trigger(i, a, P)
        assert risk(rain_trigger(i + di, a + da, P), sus) >= risk(rain_trigger(i, a, P), sus)


def test_rain_inputs_window_and_24h():
    hourly = {T0 + timedelta(hours=h): v for h, v in [(-30, 50), (-23, 4), (-1, 6), (0, 2), (3, 14), (6, 9), (7, 40)]}
    i, a, peak = rain_inputs(hourly, T0, P)
    assert i == 14 and peak == T0 + timedelta(hours=3)  # hour +7 is outside the 6 h window
    assert a == 12  # -23, -1 and 0 are inside the 24 h ending now; -30 is not


def rainy_inputs(seed):
    rng = random.Random(seed)
    rain = {}
    for h in HOTSPOTS:
        burst = rng.choice([0, 0, 5, 12, 25, 45])
        rain[h["hotspot_id"]] = {T0 + timedelta(hours=k): max(0.0, rng.gauss(burst / 3, 2)) if burst else 0.0
                                 for k in range(-23, 7)}
    return rain


@pytest.mark.parametrize("seed", range(5))
def test_snapshots_validate_against_contract(seed):
    snap = score_snapshot(HOTSPOTS, rainy_inputs(seed), T0, P)
    assert schema_errors(snap, "snapshot.schema.json") == []
    by_id = {h["hotspot_id"]: h for h in HOTSPOTS}
    assert contract_errors(contract.check_snapshot, "snap", snap, P, by_id) == []
    replay = score_snapshot(HOTSPOTS, rainy_inputs(seed), T0, P, mode="replay")
    assert replay["mode"] == "replay" and schema_errors(replay, "snapshot.schema.json") == []


def test_pump_plan_matches_contract_fixture():
    snap = json.loads((FIXTURES / "snapshot_live.json").read_text(encoding="utf-8"))
    hotspots = json.loads((FIXTURES / "hotspots.json").read_text(encoding="utf-8"))
    importance = {h["hotspot_id"]: h["importance"] for h in hotspots}
    want = json.loads((FIXTURES / "pump_plan.json").read_text(encoding="utf-8"))
    assert pump_plan(snap, 6, importance) == want


@pytest.mark.parametrize("count", [0, 1, 3, 6, 50])
def test_pump_plan_edge_counts(count):
    snap = score_snapshot(HOTSPOTS, rainy_inputs(1), T0, P)
    importance = {h["hotspot_id"]: h["importance"] for h in HOTSPOTS}
    plan = pump_plan(snap, count, importance)
    assert schema_errors(plan, "pump_plan.schema.json") == []
    assert sum(a["pumps"] for a in plan["assignments"]) <= count
    high = [h for h in snap["hotspots"] if h["level"] in ("HIGH", "CRITICAL")]
    if count == 0:
        assert plan["assignments"] == [] and len(plan["unassigned"]) == len(high)
    if count >= 2 * len(snap["hotspots"]):  # more pumps than spots: nobody HIGH+ is left out
        assert plan["unassigned"] == []
    assert plan == contract.expected_pump_plan(snap, count, {h["hotspot_id"]: h for h in HOTSPOTS})


def test_pump_plan_tie_break_on_importance():
    snap = {"run_id": "r", "hotspots": [
        {"hotspot_id": "DL-002", "level": "HIGH", "risk": 0.5},
        {"hotspot_id": "DL-001", "level": "HIGH", "risk": 0.5},
        {"hotspot_id": "DL-003", "level": "CRITICAL", "risk": 0.61},
        {"hotspot_id": "DL-004", "level": "WATCH", "risk": 0.2}]}
    plan = pump_plan(snap, 3, {"DL-001": 1.0, "DL-002": 0.3, "DL-003": 0.3, "DL-004": 1.0})
    assert [(a["hotspot_id"], a["pumps"]) for a in plan["assignments"]] == [("DL-003", 1), ("DL-001", 1), ("DL-002", 1)]
    plan = pump_plan(snap, 2, {"DL-001": 1.0, "DL-002": 0.3, "DL-003": 0.3, "DL-004": 1.0})
    assert [u["hotspot_id"] for u in plan["unassigned"]] == ["DL-002"]


def test_hotspot_records_obey_formulas():
    assert schema_errors(HOTSPOTS, "hotspot_list.schema.json") == []
    assert contract_errors(contract.check_hotspots, "hotspots", HOTSPOTS, P) == []
    minto = next(h for h in HOTSPOTS if h["name_en"] == "Minto Bridge underpass")
    assert minto["hotspot_id"] == "DL-001"


def test_params_shape_matches_contract():
    assert schema_errors(P, "params.schema.json") == []
    assert list(itertools.accumulate([P["levels"]["watch"], P["levels"]["high"], P["levels"]["critical"]], max)) == \
        [P["levels"]["watch"], P["levels"]["high"], P["levels"]["critical"]]


def test_model_has_no_aws_imports():
    for path in (ROOT / "model" / "wlew_model").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "boto3" not in text and "botocore" not in text, path


def test_replays_validate_against_contract():
    replay_dir = ROOT / "data" / "replay"
    index = json.loads((replay_dir / "index.json").read_text(encoding="utf-8"))
    assert schema_errors(index, "replay_index.schema.json") == []
    by_id = {h["hotspot_id"]: h for h in HOTSPOTS}
    kinds = set()
    for entry in index:
        rep = json.loads((replay_dir / f"{entry['event_id']}.json").read_text(encoding="utf-8"))
        kinds.add(rep["kind"])
        assert schema_errors(rep, "replay.schema.json") == [], entry["event_id"]
        assert contract_errors(contract.check_replay, entry["event_id"], rep, P, by_id, index) == []
    assert kinds == {"storm", "dry"}
