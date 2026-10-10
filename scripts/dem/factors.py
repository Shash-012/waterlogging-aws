"""A2 step 2: susceptibility factors per hotspot from the Delhi DEM (contract/CONTRACT.md).

LowLying  d = mean raw-DEM elevation in a 150-400 m ring minus the median of the 3x3
          cells at the spot; L = clip(d / 3 m, 0, 1); underpasses get max(L, 0.9).
          Uses the RAW DEM: filling depressions would erase the dips that flood.
Catchment A_c (km2) = D8 flow accumulation on a pit-filled, depression-filled,
          flat-resolved DEM (pysheds), read at the highest-accumulation cell within
          60 m; C = clip(log10(A_c / 0.01) / log10(500), 0, 1).
History   H = clip(flood_seasons / 5, 0, 1).

Writes data/factors/delhi_factors.csv, data/factors/low_lying.png and
data/factors/catchment.png, and prints the A2 "done when" checks.
"""
import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from pyproj import Transformer  # noqa: E402
from pysheds.grid import Grid  # noqa: E402
from scipy import ndimage  # noqa: E402

if not hasattr(np, "in1d"):  # pysheds 0.4 still calls np.in1d, removed in numpy 2.4
    np.in1d = np.isin

ROOT = Path(__file__).resolve().parents[2]
DEM = ROOT / "data" / "dem" / "delhi_dem_utm43.tif"
HOTSPOTS = ROOT / "data" / "hotspots" / "delhi_hotspots.json"
OUT = ROOT / "data" / "factors"
PARAMS = ROOT / "model" / "params.json"
CELL = 30.0
RING = (150.0, 400.0)
SNAP_M = 60.0


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ring_kernel():
    r = int(math.ceil(RING[1] / CELL))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1] * CELL
    d = np.hypot(xx, yy)
    return ((d >= RING[0]) & (d <= RING[1])).astype("float64")


def ring_mean(z, valid):
    """Mean of valid cells in the 150-400 m annulus around every cell (for the map)."""
    k = ring_kernel()
    zs = ndimage.convolve(np.where(valid, z, 0.0), k, mode="constant")
    n = ndimage.convolve(valid.astype("float64"), k, mode="constant")
    with np.errstate(invalid="ignore", divide="ignore"):
        return zs / n


def accumulation_km2():
    cache = DEM.with_name("acc_km2.npy")
    if cache.exists() and cache.stat().st_mtime > DEM.stat().st_mtime:
        return np.load(cache)
    grid = Grid.from_raster(str(DEM))
    dem = grid.read_raster(str(DEM))
    pit = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit)
    inflated = grid.resolve_flats(flooded)
    fdir = grid.flowdir(inflated, routing="d8")
    acc = grid.accumulation(fdir, routing="d8")
    km2 = np.asarray(acc, dtype="float64") * CELL * CELL / 1e6
    np.save(cache, km2)
    return km2


def main():
    with rasterio.open(DEM) as src:
        z = src.read(1).astype("float64")
        transform, crs = src.transform, src.crs
    valid = z > -9999
    z_nan = np.where(valid, z, np.nan)
    acc = accumulation_km2()
    acc[~valid] = np.nan

    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    hotspots = json.loads(HOTSPOTS.read_text(encoding="utf-8"))
    w = json.loads(PARAMS.read_text(encoding="utf-8"))["susceptibility"] if PARAMS.exists() else \
        {"w_history": 0.40, "w_low_lying": 0.35, "w_catchment": 0.25}

    rk = ring_kernel().astype(bool)
    r = rk.shape[0] // 2
    snap = int(math.ceil(SNAP_M / CELL))
    rows = []
    for h in hotspots:
        x, y = to_utm.transform(h["lon"], h["lat"])
        row, col = rasterio.transform.rowcol(transform, x, y)
        centre = np.nanmedian(z_nan[row - 1:row + 2, col - 1:col + 2])
        window = z_nan[row - r:row + r + 1, col - r:col + r + 1]
        d = round(float(np.nanmean(window[rk]) - centre), 2)  # published value; factors derive from it
        L = clip(d / 3.0)
        if h["site_type"] == "underpass":
            L = max(L, 0.9)
        best = 0.0
        for dr in range(-snap, snap + 1):
            for dc in range(-snap, snap + 1):
                if math.hypot(dr, dc) * CELL <= SNAP_M and np.isfinite(acc[row + dr, col + dc]):
                    best = max(best, acc[row + dr, col + dc])
        best = round(float(best), 4)
        C = clip(math.log10(best / 0.01) / math.log10(500)) if best > 0 else 0.0
        H = clip(h["flood_seasons"] / 5)
        Hr, Lr, Cr = round(H, 3), round(L, 3), round(C, 3)
        sus = round(w["w_history"] * Hr + w["w_low_lying"] * Lr + w["w_catchment"] * Cr, 3)
        rows.append({"hotspot_id": h["hotspot_id"], "name_en": h["name_en"], "site_type": h["site_type"],
                     "elevation_m": round(float(centre), 1), "relative_depth_m": d,
                     "catchment_km2": best, "flood_seasons": h["flood_seasons"],
                     "history": Hr, "low_lying": Lr, "catchment": Cr, "susceptibility": sus})

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "delhi_factors.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

    # Contract Hotspot records (contract/schemas/hotspot.schema.json) for the API and seeding.
    by_id = {r_["hotspot_id"]: r_ for r_ in rows}
    contract = []
    for h in hotspots:
        r_ = by_id[h["hotspot_id"]]
        contract.append({
            "hotspot_id": h["hotspot_id"], "name_en": h["name_en"], "name_hi": h["name_hi"],
            "lat": h["lat"], "lon": h["lon"], "site_type": h["site_type"], "ward": h["ward"],
            "importance": h["importance"], "elevation_m": r_["elevation_m"],
            "relative_depth_m": r_["relative_depth_m"], "catchment_km2": r_["catchment_km2"],
            "flood_seasons": h["flood_seasons"],
            "factors": {"history": r_["history"], "low_lying": r_["low_lying"], "catchment": r_["catchment"]},
            "susceptibility": r_["susceptibility"],
            "avoid_en": h["avoid_en"], "avoid_hi": h["avoid_hi"],
            "diversion_en": h["diversion_en"], "diversion_hi": h["diversion_hi"], "sources": h["sources"]})
    (ROOT / "data" / "hotspots" / "hotspots_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Maps for the README: relative depth (ring mean - cell) and log10 upstream area, spots overlaid.
    xs, ys = zip(*[to_utm.transform(h["lon"], h["lat"]) for h in hotspots])
    extent = (transform.c, transform.c + transform.a * z.shape[1], transform.f + transform.e * z.shape[0], transform.f)
    rel = ring_mean(z, valid) - z
    rel[~valid] = np.nan
    for name, data, cmap, label, vmin, vmax in (
            ("low_lying.png", rel, "RdBu", "Ring mean (150-400 m) minus cell elevation, m", -3, 3),
            ("catchment.png", np.log10(np.where(acc > 0, acc, np.nan)), "Blues", "log10 upstream area, km2", -3, 2.7)):
        fig, ax = plt.subplots(figsize=(8, 7.5), dpi=110)
        im = ax.imshow(data, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        ax.scatter(xs, ys, s=14, c="black", edgecolors="white", linewidths=0.6)
        ax.set_title(f"Delhi {label} (Copernicus GLO-30)", fontsize=9)
        ax.set_xlabel("UTM 43N easting (m)")
        ax.set_ylabel("northing (m)")
        fig.colorbar(im, ax=ax, shrink=0.8)
        fig.tight_layout()
        fig.savefig(OUT / name)
        plt.close(fig)

    # A2 "done when" checks
    areas = [r_["catchment_km2"] for r_ in rows if r_["catchment_km2"] > 0]
    print(f"catchment span: {min(areas):.4f} - {max(areas):.1f} km2 "
          f"({math.log10(max(areas) / min(areas)):.1f} orders of magnitude)")
    bad = [r_["name_en"] for r_ in rows if r_["site_type"] == "underpass" and r_["low_lying"] < 0.9]
    print("underpasses with L < 0.9:", bad or "none")
    ranked = sorted(rows, key=lambda r_: -r_["susceptibility"])
    third = len(ranked) // 3
    for i, r_ in enumerate(ranked, 1):
        print(f"{i:3d} {'*' if i <= third else ' '} {r_['hotspot_id']} {r_['name_en'][:40]:40} "
              f"sus={r_['susceptibility']:.3f} H={r_['history']:.2f} L={r_['low_lying']:.2f} "
              f"C={r_['catchment']:.2f} d={r_['relative_depth_m']:+.2f}m Ac={r_['catchment_km2']}")


if __name__ == "__main__":
    main()
