"""A2 step 1: fetch Copernicus GLO-30 tiles for Delhi, mosaic, clip and reproject to UTM 43N.

Tiles come from the public s3://copernicus-dem-30m bucket (no AWS account needed).
Output (git-ignored): data/dem/delhi_dem_utm43.tif, 30 m cells, EPSG:32643.
"""
import subprocess
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[2]
DEM = ROOT / "data" / "dem"
TILES = ["Copernicus_DSM_COG_10_N28_00_E076_00_DEM", "Copernicus_DSM_COG_10_N28_00_E077_00_DEM"]
BOUNDS = (76.80, 28.40, 77.40, 28.90)  # west, south, east, north
DST_CRS = "EPSG:32643"
OUT = DEM / "delhi_dem_utm43.tif"


def fetch():
    DEM.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in TILES:
        p = DEM / f"{t}.tif"
        if not p.exists():
            subprocess.run(["aws", "s3", "cp", f"s3://copernicus-dem-30m/{t}/{t}.tif", str(p),
                            "--no-sign-request", "--region", "eu-central-1", "--only-show-errors"], check=True)
        paths.append(p)
    return paths


def main():
    srcs = [rasterio.open(p) for p in fetch()]
    mosaic, transform = merge(srcs, bounds=BOUNDS)
    src_crs = srcs[0].crs
    h, w = mosaic.shape[1:]
    dst_transform, dw, dh = calculate_default_transform(src_crs, DST_CRS, w, h, *BOUNDS, resolution=30)
    out = np.full((dh, dw), -9999.0, dtype="float32")
    reproject(mosaic[0], out, src_transform=transform, src_crs=src_crs, dst_transform=dst_transform,
              dst_crs=DST_CRS, resampling=Resampling.bilinear, src_nodata=None, dst_nodata=-9999.0)
    out[out < 150] = -9999.0  # reprojection edge fill; Delhi lies at ~190-330 m
    profile = {"driver": "GTiff", "dtype": "float32", "count": 1, "width": dw, "height": dh, "crs": DST_CRS,
               "transform": dst_transform, "nodata": -9999.0, "compress": "deflate", "tiled": True}
    with rasterio.open(OUT, "w", **profile) as dst:
        dst.write(out, 1)
    valid = out[out > -9999]
    print(f"{OUT.name}: {dw}x{dh} cells, elevation {valid.min():.1f}-{valid.max():.1f} m")


if __name__ == "__main__":
    main()
