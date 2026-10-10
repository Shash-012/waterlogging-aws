#!/usr/bin/env python3
"""Regenerate contract fixtures instead of hand-editing them.

Usage: python contract/tools/regen_fixtures.py [--api CORE_API_URL]

1. contract/fixtures/live/: the real set. Replays and error shapes come from
   handoff/samples-a/; with --api, health, hotspots, the latest snapshot, the
   pump plan, the replay list and the replays are fetched fresh from the core
   API (snapshot and pump plan in the same call so their run_id matches).
   params.json is model/params.json. Checked by `validate.py --real`.
2. contract/fixtures/replay_2026-09-10.json: a synthetic dry replay built from
   snapshot_dry.json, so fixtures mode can show the dry control (requests-b #1).

The synthetic set (12 spots, the worked example, the synthetic 25 Aug storm)
is otherwise left alone: the frontend and ops tests are written against it.
"""
import argparse
import json
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contract" / "fixtures"
LIVE = FIXTURES / "live"
SAMPLES = ROOT / "handoff" / "samples-a"
REAL_REPLAYS = ["2024-06-28", "2026-08-25", "2026-09-10"]  # headline storm, honest miss, dry control

DRY_EVENT = "2026-09-10"
DRY_FRAMES = 18


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, doc, indent=1):
    Path(path).write_text(json.dumps(doc, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def get(api, route):
    req = urllib.request.Request(api.rstrip("/") + route, headers={"User-Agent": "wlew-regen-fixtures"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def regen_live(api):
    LIVE.mkdir(exist_ok=True)
    dump(LIVE / "params.json", load(ROOT / "model" / "params.json"), indent=2)
    for name in ("error_404_hotspot.json", "error_400_pumps.json"):
        dump(LIVE / name, load(SAMPLES / name))
    if api:
        docs = {
            "health.json": get(api, "/health"),
            "hotspots.json": get(api, "/hotspots"),
            "hotspot_DL-001.json": get(api, "/hotspots/DL-001"),
            "snapshot_live.json": get(api, "/scores/latest"),
            "pump_plan.json": get(api, "/pumps?count=6"),
            "replay_index.json": get(api, "/replays"),
        }
        if docs["pump_plan.json"]["run_id"] != docs["snapshot_live.json"]["run_id"]:  # the hour turned mid-fetch
            docs["snapshot_live.json"] = get(api, "/scores/latest")
            docs["pump_plan.json"] = get(api, "/pumps?count=6")
        for event_id in REAL_REPLAYS:
            docs[f"replay_{event_id}.json"] = get(api, f"/replays/{event_id}")
    else:
        docs = {
            "health.json": load(SAMPLES / "health.json"),
            "hotspots.json": load(SAMPLES / "hotspots.json"),
            "hotspot_DL-001.json": load(SAMPLES / "hotspot_DL-001.json"),
            "snapshot_live.json": load(SAMPLES / "scores_latest.json"),
            "pump_plan.json": load(SAMPLES / "pumps_count6.json"),
            "replay_index.json": load(SAMPLES / "replays.json"),
        }
        for event_id in REAL_REPLAYS:
            docs[f"replay_{event_id}.json"] = load(SAMPLES / f"replay_{event_id}.json")
    for name, doc in docs.items():
        dump(LIVE / name, doc)
    print(f"wrote {len(docs) + 3} files to {LIVE.relative_to(ROOT)}")


def regen_dry_replay():
    dry = load(FIXTURES / "snapshot_dry.json")
    start = datetime(2026, 9, 10, tzinfo=timezone.utc)
    frames = []
    for i in range(DRY_FRAMES):
        t = (start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        frames.append({**dry, "run_id": t, "as_of": t, "mode": "replay"})
    summary = {
        "event_id": DRY_EVENT,
        "title_en": "Dry monsoon-break day, 10 Sep 2026 (synthetic fixture)",
        "kind": "dry",
        "start": frames[0]["as_of"],
        "end": frames[-1]["as_of"],
        "frame_count": DRY_FRAMES,
    }
    replay = {**summary, "frames": frames, "ground_truth": [],
              "metrics": {"spots_reported": 0, "flagged_before_report": 0, "median_lead_hours": None,
                          "unconfirmed_flags": 0}}
    dump(FIXTURES / f"replay_{DRY_EVENT}.json", replay, indent=2)
    index = [e for e in load(FIXTURES / "replay_index.json") if e["event_id"] != DRY_EVENT] + [summary]
    dump(FIXTURES / "replay_index.json", index, indent=2)
    print(f"wrote contract/fixtures/replay_{DRY_EVENT}.json and its replay_index.json entry")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", help="core API URL; without it, everything comes from handoff/samples-a/")
    args = ap.parse_args()
    regen_live(args.api)
    regen_dry_replay()


if __name__ == "__main__":
    main()
