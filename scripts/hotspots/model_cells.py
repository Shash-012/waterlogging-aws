"""A4: map every hotspot to its ECMWF IFS 9 km grid cell as Open-Meteo resolves it.

Writes data/hotspots/model_cells.json ({hotspot_id: [lat, lon]}). The live scorer and the
replay builder query these cell centres, so spots sharing a cell are fetched once.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core" / "functions" / "score"))
import rain  # noqa: E402

hotspots = json.loads((ROOT / "data" / "hotspots" / "hotspots_contract.json").read_text(encoding="utf-8"))
params = {**rain._coords([(h["lat"], h["lon"]) for h in hotspots]), "hourly": "precipitation",
          "models": rain.MODEL, "timezone": "UTC", "past_hours": 1, "forecast_hours": 1}
resp = rain.get_json(rain.FORECAST_URL, params)
cells = {h["hotspot_id"]: [round(r["latitude"], 6), round(r["longitude"], 6)] for h, r in zip(hotspots, resp)}
(ROOT / "data" / "hotspots" / "model_cells.json").write_text(json.dumps(cells, indent=1) + "\n", encoding="utf-8")
print(f"{len(cells)} hotspots -> {len({tuple(c) for c in cells.values()})} model cells")
