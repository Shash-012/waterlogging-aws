#!/usr/bin/env python3
"""Validate every contract fixture against its JSON Schema and the risk formulas.

Usage: python contract/tools/validate.py [--fixtures DIR]

Exits non-zero if any fixture fails its schema, has no schema, or breaks a rule in
contract/CONTRACT.md (risk formulas, levels, city status, ranking, pump plan,
replay metrics, worked example).
"""
import argparse
import fnmatch
import json
import math
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CONTRACT = Path(__file__).resolve().parent.parent
SCHEMAS = CONTRACT / "schemas"

# First matching pattern wins.
FIXTURE_SCHEMAS = [
    ("hotspots.json", "hotspot_list"),
    ("hotspot_*.json", "hotspot"),
    ("snapshot_*.json", "snapshot"),
    ("pump_plan*.json", "pump_plan"),
    ("replay_index.json", "replay_index"),
    ("replay_*.json", "replay"),
    ("alert_request*.json", "alert_request"),
    ("alert_response*.json", "alert_response"),
    ("alert_log*.json", "alert_log"),
    ("health*.json", "health"),
    ("error*.json", "error"),
    ("params.json", "params"),
]

TOL = 0.0015  # scores are rounded to 3 decimals
LEVEL_ORDER = {"LOW": 0, "WATCH": 1, "HIGH": 2, "CRITICAL": 3}

errors = []


def fail(where, msg):
    errors.append(f"{where}: {msg}")


def close(a, b, tol=TOL):
    return a is not None and b is not None and abs(a - b) <= tol


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def parse_time(s):
    return datetime.strptime(s.split(".")[0].rstrip("Z"), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def load_registry():
    registry = Registry()
    schemas = {}
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
        registry = registry.with_resource(path.name, Resource.from_contents(schema))
    return schemas, registry


def schema_for(name):
    for pattern, schema in FIXTURE_SCHEMAS:
        if fnmatch.fnmatch(name, pattern):
            return f"{schema}.schema.json"
    return None


# ---------------------------------------------------------------- risk model

def level_of(risk, p):
    lv = p["levels"]
    if risk >= lv["critical"]:
        return "CRITICAL"
    if risk >= lv["high"]:
        return "HIGH"
    if risk >= lv["watch"]:
        return "WATCH"
    return "LOW"


def city_status_of(rt_max, p):
    if rt_max >= p["city"]["severe"]:
        return "SEVERE"
    if rt_max >= p["city"]["alert"]:
        return "ALERT"
    return "RAIN_WATCH" if rt_max > 0 else "STANDBY"


def check_hotspots(where, hotspots, p):
    w = p["susceptibility"]
    ids = [h["hotspot_id"] for h in hotspots]
    if len(set(ids)) != len(ids):
        fail(where, "duplicate hotspot_id")
    for h in hotspots:
        at = f"{where}[{h['hotspot_id']}]"
        f = h["factors"]
        H = clip(h["flood_seasons"] / 5)
        L = clip(h["relative_depth_m"] / 3.0)
        if h["site_type"] == "underpass":
            L = max(L, 0.9)
        C = clip(math.log10(h["catchment_km2"] / 0.01) / math.log10(500)) if h["catchment_km2"] > 0 else 0.0
        for key, want in (("history", H), ("low_lying", L), ("catchment", C)):
            if not close(f[key], want):
                fail(at, f"factors.{key}={f[key]}, formula gives {want:.3f}")
        sus = w["w_history"] * f["history"] + w["w_low_lying"] * f["low_lying"] + w["w_catchment"] * f["catchment"]
        if not close(h["susceptibility"], sus):
            fail(at, f"susceptibility={h['susceptibility']}, formula gives {sus:.3f}")
    return {h["hotspot_id"]: h for h in hotspots}


def check_snapshot(where, snap, p, hotspots):
    r = p["rain"]
    if snap["params_version"] != p["version"]:
        fail(where, f"params_version {snap['params_version']} != params {p['version']}")
    rows = snap["hotspots"]
    if not rows:
        fail(where, "no hotspots")
        return
    as_of = parse_time(snap["as_of"])
    for i, h in enumerate(rows, 1):
        at = f"{where}[{h['hotspot_id']}]"
        if h["hotspot_id"] not in hotspots:
            fail(at, "unknown hotspot_id")
            continue
        if h["rank"] != i:
            fail(at, f"rank {h['rank']} at position {i}")
        I, A = h["intensity_mm_h"], h["rain_24h_mm"]
        ieff = I * (1 + r["k"] * min(A / r["a_sat_mm"], 1))
        if not close(h["effective_intensity_mm_h"], ieff, 0.051):
            fail(at, f"effective_intensity_mm_h={h['effective_intensity_mm_h']}, formula gives {ieff:.2f}")
        rt = clip((ieff - r["i0_mm_h"]) / (r["i1_mm_h"] - r["i0_mm_h"]))
        if not close(h["rain_trigger"], rt):
            fail(at, f"rain_trigger={h['rain_trigger']}, formula gives {rt:.3f}")
        if not close(h["susceptibility"], hotspots[h["hotspot_id"]]["susceptibility"], 1e-9):
            fail(at, "susceptibility differs from the hotspot record")
        risk = h["rain_trigger"] * h["susceptibility"]
        if not close(h["risk"], risk):
            fail(at, f"risk={h['risk']}, rain_trigger x susceptibility gives {risk:.3f}")
        if h["level"] != level_of(h["risk"], p):
            fail(at, f"level {h['level']} but risk {h['risk']} gives {level_of(h['risk'], p)}")
        for key in ("risk", "rain_trigger", "susceptibility"):
            if round(h[key], 3) != h[key]:
                fail(at, f"{key} not rounded to 3 decimals")
        if h["peak_at"] is None:
            if I > 0:
                fail(at, "peak_at is null but intensity_mm_h > 0")
        elif not as_of <= parse_time(h["peak_at"]) <= as_of + timedelta(hours=r["window_hours"]):
            fail(at, "peak_at outside the current hour and the next window_hours")
    if any(a["risk"] < b["risk"] for a, b in zip(rows, rows[1:])):
        fail(where, "hotspots not sorted by risk, descending")
    rt_max = max(h["rain_trigger"] for h in rows)
    city = snap["city"]
    if not close(city["rain_trigger_max"], rt_max, 1e-9):
        fail(where, f"city.rain_trigger_max={city['rain_trigger_max']}, max over spots is {rt_max}")
    if city["status"] != city_status_of(rt_max, p):
        fail(where, f"city.status {city['status']} but rain_trigger_max {rt_max} gives {city_status_of(rt_max, p)}")
    if city["spots_raining"] > len(rows):
        fail(where, "city.spots_raining exceeds the number of spots")


def expected_pump_plan(snap, count, hotspots):
    spots = sorted(snap["hotspots"], reverse=True,
                   key=lambda h: (LEVEL_ORDER[h["level"]], h["risk"], hotspots[h["hotspot_id"]]["importance"]))
    left, pumps = count, {}
    for h in spots:
        if h["level"] in ("HIGH", "CRITICAL") and left:
            pumps[h["hotspot_id"]] = 1
            left -= 1
    for h in spots:
        if h["level"] == "CRITICAL" and h["hotspot_id"] in pumps and left:
            pumps[h["hotspot_id"]] += 1
            left -= 1
    for h in spots:
        if h["level"] == "WATCH" and left:
            pumps[h["hotspot_id"]] = 1
            left -= 1
    return {
        "run_id": snap["run_id"], "pumps_available": count,
        "assignments": [{"hotspot_id": h["hotspot_id"], "pumps": pumps[h["hotspot_id"]],
                         "level": h["level"], "risk": h["risk"]} for h in spots if h["hotspot_id"] in pumps],
        "unassigned": [{"hotspot_id": h["hotspot_id"], "level": h["level"], "risk": h["risk"]}
                       for h in spots if h["level"] in ("HIGH", "CRITICAL") and h["hotspot_id"] not in pumps],
    }


def check_replay(where, rep, p, hotspots, index):
    frames = rep["frames"]
    if rep["frame_count"] != len(frames):
        fail(where, f"frame_count {rep['frame_count']} != {len(frames)} frames")
    if frames[0]["as_of"] != rep["start"] or frames[-1]["as_of"] != rep["end"]:
        fail(where, "start/end do not match the first/last frame")
    for i, fr in enumerate(frames):
        check_snapshot(f"{where}.frames[{i}]", fr, p, hotspots)
        if i and parse_time(fr["as_of"]) - parse_time(frames[i - 1]["as_of"]) != timedelta(hours=1):
            fail(f"{where}.frames[{i}]", "frames are not hourly")
    if rep["kind"] == "dry":
        for i, fr in enumerate(frames):
            if fr["city"]["status"] != "STANDBY" or any(h["level"] != "LOW" for h in fr["hotspots"]):
                fail(f"{where}.frames[{i}]", "dry replay must be all LOW under STANDBY")

    first_flag = {}
    for fr in frames:
        for h in fr["hotspots"]:
            if h["level"] in ("HIGH", "CRITICAL"):
                first_flag.setdefault(h["hotspot_id"], parse_time(fr["as_of"]))
    leads = []
    for g in rep["ground_truth"]:
        if g["hotspot_id"] not in hotspots:
            fail(where, f"ground_truth names unknown hotspot {g['hotspot_id']}")
        ff, reported = first_flag.get(g["hotspot_id"]), parse_time(g["first_report_at"])
        if ff is not None and ff < reported:
            leads.append((reported - ff).total_seconds() / 3600)
    reported_ids = {g["hotspot_id"] for g in rep["ground_truth"]}
    want = {
        "spots_reported": len(reported_ids),
        "flagged_before_report": len(leads),
        "median_lead_hours": statistics.median(leads) if leads else None,
        "unconfirmed_flags": len(set(first_flag) - reported_ids),
    }
    got = rep["metrics"]
    for key, value in want.items():
        ok = (got[key] is None) == (value is None) and (value is None or close(got[key], value, 0.051))
        if not ok:
            fail(where, f"metrics.{key}={got[key]}, frames and ground_truth give {value}")

    summary = {k: rep[k] for k in ("event_id", "title_en", "kind", "start", "end", "frame_count")}
    if index is not None and summary not in index:
        fail(where, "no matching entry in replay_index.json")


def check_alert(where, alert, hotspots, replays):
    if alert["hotspot_id"] not in hotspots:
        fail(where, f"unknown hotspot {alert['hotspot_id']}")
    if alert["mode"] == "live":
        if alert.get("event_id") is not None:
            fail(where, "live alerts carry event_id null")
        return
    rep = replays.get(alert["event_id"])
    if rep is None:
        return  # the replay may not be a fixture
    frame = next((f for f in rep["frames"] if f["run_id"] == alert["run_id"]), None)
    if frame is None:
        fail(where, f"run_id {alert['run_id']} is not a frame of replay {alert['event_id']}")
        return
    row = next((h for h in frame["hotspots"] if h["hotspot_id"] == alert["hotspot_id"]), None)
    if row and (row["level"], row["risk"], row["peak_at"]) != (alert["level"], alert["risk"], alert["peak_at"]):
        fail(where, "level/risk/peak_at differ from the replay frame")


def check_worked_example(snapshots):
    """I=14, A=30 -> I_eff=21, RainTrigger=0.64; H=0.8, L=0.9, C=0.72 -> 0.815; Risk 0.522 HIGH; city ALERT."""
    for name, snap, hotspots in snapshots:
        for h in snap["hotspots"]:
            f = hotspots.get(h["hotspot_id"], {}).get("factors")
            if (h["intensity_mm_h"], h["rain_24h_mm"]) == (14.0, 30.0) and f and \
                    (f["history"], f["low_lying"], f["catchment"]) == (0.8, 0.9, 0.72):
                got = (h["effective_intensity_mm_h"], h["rain_trigger"], h["susceptibility"], h["risk"], h["level"],
                       snap["city"]["status"])
                if got != (21.0, 0.64, 0.815, 0.522, "HIGH", "ALERT"):
                    fail(name, f"worked example row gives {got}")
                return
    fail("fixtures", "no snapshot contains the worked example (I=14, A=30, H=0.8, L=0.9, C=0.72)")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fixtures", type=Path, default=CONTRACT / "fixtures")
    args = ap.parse_args()

    schemas, registry = load_registry()
    docs = {}
    for path in sorted(args.fixtures.glob("*.json")):
        name = path.name
        schema_name = schema_for(name)
        if schema_name is None or schema_name not in schemas:
            fail(name, "no schema mapped to this fixture (see FIXTURE_SCHEMAS in validate.py)")
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schemas[schema_name], registry=registry)
        problems = sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
        for e in problems:
            fail(name, f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message} [{schema_name}]")
        if not problems:
            docs[name] = doc
        print(f"{'FAIL' if problems else 'ok  '} {name} -> {schema_name}")

    # Semantic checks need a valid params.json and hotspots.json.
    if errors or "params.json" not in docs or "hotspots.json" not in docs:
        if "params.json" not in docs or "hotspots.json" not in docs:
            fail("fixtures", "params.json and hotspots.json are required")
        return report()

    p = docs["params.json"]
    hotspots = check_hotspots("hotspots.json", docs["hotspots.json"], p)
    for name, doc in docs.items():
        if fnmatch.fnmatch(name, "hotspot_*.json") and hotspots.get(doc["hotspot_id"]) != doc:
            fail(name, "differs from its entry in hotspots.json")

    snaps = [(n, d) for n, d in docs.items() if schema_for(n) == "snapshot.schema.json"]
    for name, snap in snaps:
        check_snapshot(name, snap, p, hotspots)
    if not any(s["city"]["status"] == "STANDBY" and all(h["level"] == "LOW" for h in s["hotspots"]) for _, s in snaps):
        fail("fixtures", "need a dry snapshot (every spot LOW, city STANDBY)")
    if len(snaps) and not any(len(s["hotspots"]) == len(hotspots) for _, s in snaps):
        fail("fixtures", "no snapshot covers every hotspot")

    index = docs.get("replay_index.json")
    replays = {}
    for name, doc in docs.items():
        if schema_for(name) == "replay.schema.json":
            check_replay(name, doc, p, hotspots, index)
            replays[doc["event_id"]] = doc

    for name, doc in docs.items():
        if schema_for(name) == "pump_plan.schema.json":
            snap = next((s for _, s in snaps if s["run_id"] == doc["run_id"]), None)
            if snap is None:
                fail(name, f"no snapshot fixture with run_id {doc['run_id']}")
            elif doc != expected_pump_plan(snap, doc["pumps_available"], hotspots):
                fail(name, "does not follow the pump-plan rule; expected "
                     + json.dumps(expected_pump_plan(snap, doc["pumps_available"], hotspots)))
        elif schema_for(name) == "alert_request.schema.json":
            check_alert(name, doc, hotspots, replays)
        elif schema_for(name) == "alert_log.schema.json":
            for i, a in enumerate(doc["alerts"]):
                check_alert(f"{name}.alerts[{i}]", a, hotspots, replays)

    frames = [(f"{n}.frames[{i}]", f) for n, r in docs.items() if schema_for(n) == "replay.schema.json"
              for i, f in enumerate(r["frames"])]
    check_worked_example([(n, s, hotspots) for n, s in snaps + frames])
    return report()


def report():
    if errors:
        print(f"\ncontract-check FAILED ({len(errors)} problem(s)):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("\ncontract-check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
