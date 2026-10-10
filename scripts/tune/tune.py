"""A5: tune rain parameters on two storm days, check on the others; tune susceptibility weights.

Protocol (fixed before looking at results):
- Train events: 2024-06-28 and 2024-07-31. Held out: 2026-08-07 and 2026-08-25. Control: 2026-09-10.
- Rain grid: i0 in {3,4,5}, i1 in {20,25,30,40}, a_sat in {40,60,80}, k in {0.5,1,1.5}; window stays 6 h.
- Objective on train events: flagged_before_report - 0.2 * unconfirmed_flags, summed.
  Hard constraint: the dry control stays all LOW. Ties go to the set closest to the v1 defaults.
- Susceptibility weights (step 0.05, summing to 1, each >= 0.1): maximise how many reported
  spots across all storm events land in the top 10 by susceptibility. Ties -> closest to v1.
Rain inputs per frame are computed once from the cached issued forecasts (no hindsight).
Prints the leaderboard; writes nothing unless --write.
"""
import argparse
import itertools
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "replay"))
sys.path.insert(0, str(ROOT / "model"))
import build_replay as br  # noqa: E402
from wlew_model import load_params  # noqa: E402
from wlew_model.risk import level, rain_trigger, risk  # noqa: E402

TRAIN = ["2024-06-28", "2024-07-31"]
HELD_OUT = ["2026-08-07", "2026-08-25"]
DRY = "2026-09-10"
V1 = load_params(ROOT / "model" / "params.json")


def event_inputs(ev):
    """Per frame: (as_of, {hotspot_id: (I, A)}), using v1's 6 h window (the window is not tuned)."""
    start, end = br.frame_window(ev, ev.get("reports", []))
    frames, _ = br.frames_for(start, end, V1)
    return [(br.parse_iso(f["as_of"]), {h["hotspot_id"]: (h["intensity_mm_h"], h["rain_24h_mm"]) for h in f["hotspots"]})
            for f in frames]


def evaluate(p, inputs, sus, ground_truth):
    first_flag = {}
    for as_of, spots in inputs:
        for hid, (i, a) in spots.items():
            if level(risk(rain_trigger(i, a, p), sus[hid]), p) in ("HIGH", "CRITICAL"):
                first_flag.setdefault(hid, as_of)
    leads = [(g["t"] - first_flag[g["hotspot_id"]]).total_seconds() / 3600
             for g in ground_truth if g["hotspot_id"] in first_flag and first_flag[g["hotspot_id"]] < g["t"]]
    reported = {g["hotspot_id"] for g in ground_truth}
    return {"flagged": len(leads), "reported": len(reported), "unconfirmed": len(set(first_flag) - reported),
            "median_lead": round(sorted(leads)[len(leads) // 2], 1) if leads else None, "any_flag": bool(first_flag)}


def with_rain(base, i0, i1, a_sat, k):
    p = json.loads(json.dumps(base))
    p["rain"].update(i0_mm_h=i0, i1_mm_h=i1, a_sat_mm=a_sat, k=k)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write the chosen params to model/params.json")
    args = ap.parse_args()
    events = {e["event_id"]: e for e in json.loads((br.GT / "events.json").read_text(encoding="utf-8"))["events"]}
    hotspots = br.HOTSPOTS
    sus = {h["hotspot_id"]: h["susceptibility"] for h in hotspots}
    inputs = {eid: event_inputs(ev) for eid, ev in events.items()}
    truth = {eid: [{"hotspot_id": r["hotspot_id"], "t": br.ist_to_utc(r["first_report_ist"])} for r in ev.get("reports", [])]
             for eid, ev in events.items()}

    # --- rain parameters ---
    r1 = V1["rain"]
    results = []
    for i0, i1, a_sat, k in itertools.product([3.0, 4.0, 5.0], [20.0, 25.0, 30.0, 40.0], [40.0, 60.0, 80.0], [0.5, 1.0, 1.5]):
        p = with_rain(V1, i0, i1, a_sat, k)
        if evaluate(p, inputs[DRY], sus, [])["any_flag"]:
            continue
        train = [evaluate(p, inputs[e], sus, truth[e]) for e in TRAIN]
        score = sum(t["flagged"] - 0.2 * t["unconfirmed"] for t in train)
        dist = abs(i0 - r1["i0_mm_h"]) / 5 + abs(i1 - r1["i1_mm_h"]) / 30 + abs(a_sat - r1["a_sat_mm"]) / 60 + abs(k - r1["k"])
        results.append((score, -dist, (i0, i1, a_sat, k), train))
    results.sort(reverse=True)
    print("rain leaderboard (score = flagged - 0.2*unconfirmed on train events):")
    for score, nd, params, train in results[:8]:
        print(f"  {score:6.2f} i0,i1,a_sat,k={params} train={[(t['flagged'], t['reported'], t['unconfirmed']) for t in train]}")
    v1_train = [evaluate(V1, inputs[e], sus, truth[e]) for e in TRAIN]
    print(f"  v1 defaults: score={sum(t['flagged'] - 0.2 * t['unconfirmed'] for t in v1_train):.2f} "
          f"train={[(t['flagged'], t['reported'], t['unconfirmed']) for t in v1_train]}")
    best = results[0][2]
    chosen = with_rain(V1, *best)
    for name, p in (("v1 defaults", V1), (f"tuned {best}", chosen)):
        print(f"{name}:")
        for e in TRAIN + HELD_OUT + [DRY]:
            r = evaluate(p, inputs[e], sus, truth[e])
            tag = "train" if e in TRAIN else "held-out" if e in HELD_OUT else "dry"
            print(f"    {e} [{tag}] flagged {r['flagged']}/{r['reported']} unconfirmed {r['unconfirmed']} "
                  f"median_lead {r['median_lead']} any_flag {r['any_flag']}")

    # --- susceptibility weights ---
    reported = [g["hotspot_id"] for e in TRAIN + HELD_OUT for g in truth[e]]
    w1 = V1["susceptibility"]
    best_w = None
    for wh in [x / 20 for x in range(2, 17)]:
        for wl in [x / 20 for x in range(2, 17)]:
            wc = round(1 - wh - wl, 2)
            if wc < 0.1 - 1e-9:
                continue
            s = {h["hotspot_id"]: wh * h["factors"]["history"] + wl * h["factors"]["low_lying"] + wc * h["factors"]["catchment"]
                 for h in hotspots}
            top10 = set(sorted(s, key=lambda x: -s[x])[:10])
            hits = sum(1 for r in reported if r in top10)
            dist = math.dist((wh, wl, wc), (w1["w_history"], w1["w_low_lying"], w1["w_catchment"]))
            cand = (hits, -dist, (wh, wl, wc))
            best_w = max(best_w, cand) if best_w else cand
    s1 = {h["hotspot_id"]: h["susceptibility"] for h in hotspots}
    v1_hits = sum(1 for r in reported if r in set(sorted(s1, key=lambda x: -s1[x])[:10]))
    print(f"susceptibility weights: v1 {tuple(w1.values())} puts {v1_hits}/{len(reported)} reports in the top 10; "
          f"best {best_w[2]} puts {best_w[0]}/{len(reported)}")

    if args.write:
        out = json.loads(json.dumps(chosen))
        out["susceptibility"] = dict(zip(("w_history", "w_low_lying", "w_catchment"), best_w[2]))
        (ROOT / "model" / "params.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        print("wrote model/params.json", out)


if __name__ == "__main__":
    main()
