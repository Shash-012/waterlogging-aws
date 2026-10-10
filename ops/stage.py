"""Stage send_alert for `sam build`.

Copies functions/send_alert plus ops/templates, ops/config and the contract's hotspot
fixture (used when CoreApiUrl is "fixtures") into ops/build/send_alert/.

Usage: python ops/stage.py
"""
import shutil
from pathlib import Path

OPS = Path(__file__).resolve().parent
OUT = OPS / "build" / "send_alert"

shutil.rmtree(OUT, ignore_errors=True)
shutil.copytree(OPS / "functions" / "send_alert", OUT, ignore=shutil.ignore_patterns("__pycache__"))
shutil.copytree(OPS / "templates", OUT / "templates")
shutil.copytree(OPS / "config", OUT / "config")
shutil.copy(OPS.parent / "contract" / "fixtures" / "hotspots.json", OUT / "hotspots_fixture.json")
print(f"staged {OUT.relative_to(OPS.parent)}")
