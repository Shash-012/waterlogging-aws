"""A5: build contract Replay JSON for each event in data/ground_truth/events.json.

Frames run hourly from 18 h before the first report to 6 h after it (a dry event uses
its own start/end). Each frame sees only what was known at that hour: the latest ECMWF
run usable then (see core/functions/score/rain.py) and rain that had already fallen.

Writes data/replay/<event_id>.json and data/replay/index.json, prints per-event metrics.
Usage: python scripts/replay/build_replay.py [--params model/params.json] [--out data/replay]
"""
import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "model"))
sys.path.insert(0, str(ROOT / "scripts" / "replay"))
sys.path.insert(0, str(ROOT / "core" / "functions" / "score"))
import rain  # noqa: E402
import rain_cache  # noqa: E402
from wlew_model import load_params, score_snapshot  # noqa: E402
from wlew_model.risk import iso, parse_iso  # noqa: E402

UTC = timezone.utc
IST = timedelta(hours=5, minutes=30)
GT = ROOT / "data" / "ground_truth"
HOTSPOTS = json.loads((ROOT / "data" / "hotspots" / "hotspots_contract.json").read_text(encoding="utf-8"))
FLAG = ("HIGH", "CRITICAL")


def ist_to_utc(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M").replace(tzinfo=UTC) - IST


def frame_window(event, reports):
    if event["kind"] == "dry" or not reports:
        return parse_iso(event["start"]), parse_iso(event["end"])
    first = min(ist_to_utc(r["first_report_ist"]) for r in reports)
    first = first.replace(minute=0, second=0, microsecond=0)
    return first - timedelta(hours=18), first + timedelta(hours=6)


def frames_for(start, end, p):
    past = rain_cache.historical((start - timedelta(days=1)).replace(hour=0), end)
    frames, runs_used = [], []
    t = start
    while t <= end:
        run_start, run = rain_cache.usable_run(t)
        runs_used.append(iso(run_start) if run_start else None)
        series = {}
        for h in HOTSPOTS:
            key = rain_cache.cell_key(h["hotspot_id"])
            series[h["hotspot_id"]] = rain.replay_hourly(t, past[key], run[key] if run else {},
                                                          p["rain"]["window_hours"])
        frames.append(score_snapshot(HOTSPOTS, series, t, p, mode="replay"))
        t += timedelta(hours=1)
    return frames, runs_used


def metrics(frames, ground_truth):
    first_flag = {}
    for fr in frames:
        for h in fr["hotspots"]:
            if h["level"] in FLAG:
                first_flag.setdefault(h["hotspot_id"], parse_iso(fr["as_of"]))
    leads, per_spot = [], []
    for g in ground_truth:
        ff, rep = first_flag.get(g["hotspot_id"]), parse_iso(g["first_report_at"])
        lead = (rep - ff).total_seconds() / 3600 if ff is not None and ff < rep else None
        if lead is not None:
            leads.append(lead)
        per_spot.append({"hotspot_id": g["hotspot_id"], "first_flag": iso(ff) if ff else None,
                         "first_report_at": g["first_report_at"],
                         "lead_hours": round(lead, 1) if lead is not None else None})
    reported = {g["hotspot_id"] for g in ground_truth}
    m = {"spots_reported": len(reported), "flagged_before_report": len(leads),
         "median_lead_hours": round(statistics.median(leads), 1) if leads else None,
         "unconfirmed_flags": len(set(first_flag) - reported)}
    return m, per_spot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", type=Path, default=ROOT / "model" / "params.json")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "replay")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    p = load_params(args.params)
    events = json.loads((GT / "events.json").read_text(encoding="utf-8"))["events"]
    args.out.mkdir(parents=True, exist_ok=True)
    index, summary = [], []
    for ev in events:
        if args.only and ev["event_id"] not in args.only:
            continue
        reports = ev.get("reports", [])
        start, end = frame_window(ev, reports)
        frames, runs_used = frames_for(start, end, p)
        ground_truth = [{"hotspot_id": r["hotspot_id"], "first_report_at": iso(ist_to_utc(r["first_report_ist"])),
                         "source_url": r["source_url"], "note": r["note"]} for r in reports]
        m, per_spot = metrics(frames, ground_truth)
        replay = {"event_id": ev["event_id"], "title_en": ev["title_en"], "kind": ev["kind"],
                  "start": frames[0]["as_of"], "end": frames[-1]["as_of"], "frame_count": len(frames),
                  "frames": frames, "ground_truth": ground_truth, "metrics": m}
        (args.out / f"{ev['event_id']}.json").write_text(json.dumps(replay, ensure_ascii=False) + "\n",
                                                          encoding="utf-8")
        index.append({k: replay[k] for k in ("event_id", "title_en", "kind", "start", "end", "frame_count")})
        city = [f["city"]["status"] for f in frames]
        first_high = next((f["as_of"] for f in frames if any(h["level"] in FLAG for h in f["hotspots"])), None)
        left_standby = next((f["as_of"] for f in frames if f["city"]["status"] != "STANDBY"), None)
        summary.append({"event_id": ev["event_id"], "kind": ev["kind"], "metrics": m, "per_spot": per_spot,
                        "max_rain_trigger": max(f["city"]["rain_trigger_max"] for f in frames),
                        "max_risk": max(h["risk"] for f in frames for h in f["hotspots"]),
                        "city_left_standby": left_standby, "first_high": first_high,
                        "all_low": all(h["level"] == "LOW" for f in frames for h in f["hotspots"]),
                        "statuses": sorted(set(city)), "runs_used": sorted({r for r in runs_used if r}),
                        "frames_without_run": runs_used.count(None)})
    if not args.only:
        (args.out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    for s in summary:
        print(f"{s['event_id']} {s['kind']:5} {s['metrics']} max_rt={s['max_rain_trigger']} max_risk={s['max_risk']} "
              f"left_standby={s['city_left_standby']} first_high={s['first_high']} all_low={s['all_low']} "
              f"no_run_frames={s['frames_without_run']}")
        for ps in s["per_spot"]:
            print(f"    {ps}")


if __name__ == "__main__":
    main()
