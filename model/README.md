# wlew_model: the risk engine

Pure Python with no AWS imports. It implements the formulas in `contract/CONTRACT.md`: rain trigger, susceptibility, risk, level, city status, pump plan and `score_snapshot()`. Parameters come from `params.json`. Run the tests with `make -C core test`.

## Rain inputs (A4)

- **Model.** Live scoring and replays both use the ECMWF IFS 9 km model through Open-Meteo (`models=ecmwf_ifs`), so thresholds tuned on replays carry over to live scoring. Open-Meteo returns this model in hourly steps for the horizons we use (48 h or less). Each value is the precipitation of the preceding hour in mm, which is already mm/h, so no conversion is applied. The series change from hour to hour; they aren't 3-hourly blocks spread out.
- **Live.** `core/functions/score/rain.py` `live_rain()` makes one batched call with `past_hours=24` and `forecast_hours=8`. The 69 hotspots fall in 16 model cells (`data/hotspots/model_cells.json`), and each cell is fetched once. Five consecutive calls took 0.75–0.94 s, against a target of under 5 s. Requests retry with exponential backoff on network errors, 429 and 5xx.
- **Replays.** A frame at hour t uses only what was known at t:
  - I, for hours t+1 to t+6, comes from the latest ECMWF run that started at or before t − 6 h (runs start at 00, 06, 12 and 18 UTC), as that run issued it, via Open-Meteo's Single Runs API.
  - The current hour and A (the 24 h ending at t) come from the historical-forecast endpoint, i.e. rain that had already fallen.
  - A unit test checks that no value after t is ever read from the historical series.
- **Caching.** Every pull is cached in `data/replay/cache/` (see `scripts/replay/rain_cache.py`).
- **Caveat.** The "historical" series is Open-Meteo's archive of the model's own short-range forecasts, not rain-gauge data. It is the same model as the forecasts, which keeps the inputs consistent, but on convective days it can be far below what gauges recorded.
