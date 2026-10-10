"""Stage model/wlew_model and model/params.json as a Lambda layer in core/build/layer/python/."""
import shutil
from pathlib import Path

CORE = Path(__file__).resolve().parent
MODEL = CORE.parent / "model"
DEST = CORE / "build" / "layer" / "python"

shutil.rmtree(DEST.parent, ignore_errors=True)
shutil.copytree(MODEL / "wlew_model", DEST / "wlew_model", ignore=shutil.ignore_patterns("__pycache__"))
shutil.copy2(MODEL / "params.json", DEST / "params.json")
print(f"staged {DEST}")
