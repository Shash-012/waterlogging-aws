"""A4: disk-cached replay rain pulls (data/replay/cache/), so replays rebuild offline.

Each ECMWF run (Single Runs API) and each historical date range is fetched once for the
16 model cells and saved as JSON: {"lat,lon": {"YYYY-MM-DDTHH:MM": mm}}.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "functions" / "score"))
import rain  # noqa: E402

CACHE = ROOT / "data" / "replay" / "cache"
CELLS = json.loads((ROOT / "data" / "hotspots" / "model_cells.json").read_text(encoding="utf-8"))
POINTS = sorted({tuple(v) for v in CELLS.values()})


def _key(p):
    return f"{p[0]:.6f},{p[1]:.6f}"


def _load(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: {datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc): v for t, v in s.items()}
            for k, s in raw.items()}


def _save(path, series_list):
    CACHE.mkdir(parents=True, exist_ok=True)
    raw = {_key(p): {t.strftime("%Y-%m-%dT%H:%M"): v for t, v in sorted(s.items())}
           for p, s in zip(POINTS, series_list)}
    path.write_text(json.dumps(raw, separators=(",", ":")) + "\n", encoding="utf-8")


def run(run_start, hours=48):
    path = CACHE / f"run_{run_start:%Y%m%dT%H}.json"
    if not path.exists():
        _save(path, rain.run_forecast(POINTS, run_start, hours))
    return _load(path)


def historical(start_date, end_date):
    path = CACHE / f"hist_{start_date:%Y%m%d}_{end_date:%Y%m%d}.json"
    if not path.exists():
        _save(path, rain.historical(POINTS, start_date, end_date))
    return _load(path)


def cell_key(hotspot_id):
    return _key(tuple(CELLS[hotspot_id]))
