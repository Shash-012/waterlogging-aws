"""Risk = RainTrigger x Susceptibility, levels, city status, pump plan and snapshots.

All functions are pure; parameters are the dict shape of model/params.json.
Rounding follows the contract: scores to 3 decimals, rain to 0.1 mm(/h), and every
derived number is computed from the rounded value it is published next to, so a
snapshot can be re-checked from its own fields.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

PARAMS_PATH = Path(__file__).resolve().parent.parent / "params.json"
LEVEL_ORDER = {"LOW": 0, "WATCH": 1, "HIGH": 2, "CRITICAL": 3}


def load_params(path=PARAMS_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _r3(x):
    return round(x + 0.0, 3)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def effective_intensity(intensity_mm_h, rain_24h_mm, p):
    r = p["rain"]
    return intensity_mm_h * (1 + r["k"] * min(rain_24h_mm / r["a_sat_mm"], 1))


def rain_trigger(intensity_mm_h, rain_24h_mm, p):
    r = p["rain"]
    ieff = effective_intensity(intensity_mm_h, rain_24h_mm, p)
    return _r3(_clip((ieff - r["i0_mm_h"]) / (r["i1_mm_h"] - r["i0_mm_h"])))


def susceptibility(history, low_lying, catchment, p):
    w = p["susceptibility"]
    return _r3(w["w_history"] * history + w["w_low_lying"] * low_lying + w["w_catchment"] * catchment)


def risk(rain_trigger_value, susceptibility_value):
    return _r3(rain_trigger_value * susceptibility_value)


def level(risk_value, p):
    lv = p["levels"]
    if risk_value >= lv["critical"]:
        return "CRITICAL"
    if risk_value >= lv["high"]:
        return "HIGH"
    if risk_value >= lv["watch"]:
        return "WATCH"
    return "LOW"


def city_status(rain_trigger_max, p):
    if rain_trigger_max >= p["city"]["severe"]:
        return "SEVERE"
    if rain_trigger_max >= p["city"]["alert"]:
        return "ALERT"
    return "RAIN_WATCH" if rain_trigger_max > 0 else "STANDBY"


def rain_inputs(hourly, as_of, p):
    """I, A and peak_at for one spot at hour `as_of`.

    hourly: {datetime (UTC, on the hour): precipitation mm in that hour}. For live runs this
    is the forecast plus past_days; for replays the caller supplies, for each hour, only
    values that were known at `as_of` (issued forecasts), so nothing here peeks ahead.
    I = max over the current hour and the next window_hours; A = sum over the 24 h ending
    at the current hour (missing hours count as 0).
    """
    window = p["rain"]["window_hours"]
    ahead = [(as_of + timedelta(hours=h), hourly.get(as_of + timedelta(hours=h), 0.0) or 0.0)
             for h in range(window + 1)]
    peak_t, intensity = max(ahead, key=lambda tv: (tv[1], -tv[0].timestamp()))
    rain_24h = sum(hourly.get(as_of - timedelta(hours=h), 0.0) or 0.0 for h in range(24))
    return intensity, rain_24h, (peak_t if intensity > 0 else None)


def score_snapshot(hotspots, rain, as_of, p, mode="live", run_id=None):
    """Contract Snapshot. hotspots: contract Hotspot records; rain: {hotspot_id: hourly dict}."""
    rows = []
    for h in hotspots:
        intensity, rain_24h, peak = rain_inputs(rain.get(h["hotspot_id"], {}), as_of, p)
        intensity, rain_24h = round(intensity, 1), round(rain_24h, 1)
        rt = rain_trigger(intensity, rain_24h, p)
        sus = h["susceptibility"]
        rk = risk(rt, sus)
        rows.append({
            "hotspot_id": h["hotspot_id"], "rank": 0, "level": level(rk, p), "risk": rk,
            "rain_trigger": rt, "susceptibility": sus,
            "intensity_mm_h": intensity, "rain_24h_mm": rain_24h,
            "effective_intensity_mm_h": round(effective_intensity(intensity, rain_24h, p), 1),
            "peak_at": iso(peak) if peak else None,
        })
    rows.sort(key=lambda r: (-r["risk"], -r["susceptibility"], r["hotspot_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    rt_max = max((r["rain_trigger"] for r in rows), default=0.0)
    return {
        "run_id": run_id or iso(as_of), "as_of": iso(as_of), "mode": mode, "params_version": p["version"],
        "city": {"status": city_status(rt_max, p), "rain_trigger_max": rt_max,
                 "spots_raining": sum(1 for r in rows if r["intensity_mm_h"] > 0)},
        "hotspots": rows,
    }


def pump_plan(snapshot, count, importance):
    """Contract pump plan. importance: {hotspot_id: 1.0 | 0.6 | 0.3}.

    Sort by level (CRITICAL first), risk, importance, all descending. One pump to each
    HIGH/CRITICAL spot; then a second to CRITICAL spots; then one to WATCH spots.
    HIGH-or-above spots without a pump are listed as unassigned.
    """
    spots = sorted(snapshot["hotspots"], reverse=True,
                   key=lambda h: (LEVEL_ORDER[h["level"]], h["risk"], importance.get(h["hotspot_id"], 0.0)))
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
        "run_id": snapshot["run_id"], "pumps_available": count,
        "assignments": [{"hotspot_id": h["hotspot_id"], "pumps": pumps[h["hotspot_id"]],
                         "level": h["level"], "risk": h["risk"]} for h in spots if h["hotspot_id"] in pumps],
        "unassigned": [{"hotspot_id": h["hotspot_id"], "level": h["level"], "risk": h["risk"]}
                       for h in spots if h["level"] in ("HIGH", "CRITICAL") and h["hotspot_id"] not in pumps],
    }


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
