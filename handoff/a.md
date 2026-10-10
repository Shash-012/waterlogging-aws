# Agent A handoff: data, model and core backend

Branch `agent-a/core`. Everything below was run from a Windows machine with the `wlew` AWS profile (ap-south-1).

## Core API

**CoreApiUrl: `https://x6klvfqev1.execute-api.ap-south-1.amazonaws.com`** (stack output `CoreApiUrl` of `wlew-core`)

| Route | Notes |
|---|---|
| `GET /health` | `latest_run_id` is the last hourly run |
| `GET /hotspots`, `GET /hotspots/{id}` | 69 Delhi hotspots, contract `Hotspot` records; unknown id gives 404 with the contract error shape |
| `GET /scores/latest` | Latest live `Snapshot` (mode `live`), scored hourly |
| `GET /pumps?count=N` | Pump plan on the latest snapshot; N outside 0–50 or not an integer gives 400. Default N=6 if omitted. |
| `GET /replays`, `GET /replays/{event_id}` | 5 replays (4 storms + 1 dry control), 25 hourly frames each; unknown id gives 404 |

The API is public, GET only, and CORS allows `http://localhost:5173` plus the stack parameter `AllowedOrigin` (redeploy with `sam deploy --parameter-overrides AllowedOrigin=https://<amplify-domain>`). Responses are UTF-8 with Hindi text.

One live response per route is saved in `handoff/samples-a/`, including `error_404_hotspot.json` and `error_400_pumps.json`.

## What's deployed (stack `wlew-core`, every resource tagged `Project=wlew`)

- **HTTP API.** API Gateway HTTP API, with one Python 3.12 arm64 Lambda (`core/functions/api`) for all routes.
- **Scorer.** A scoring Lambda (`core/functions/score`) on EventBridge Scheduler `rate(1 hour)` (SAM `ScheduleV2`, schedule name `wlew-core-hourly-score`). It calls Open-Meteo once for the 16 model cells and scores with `wlew_model`. It writes the snapshot to DynamoDB and updates the `LATEST` pointer item. Each run logs one JSON line to the CloudWatch log group `/wlew/core/score`: `{"event":"scoring_run","run_id":…,"city_status":…,"spots_raining":…,"spots_high_or_above":…,"duration_ms":…}`. Runs take about 1 s.
- **Tables.** DynamoDB `HotspotsTable` (key `hotspot_id`; each item is the contract record plus an internal `model_cell`) and `SnapshotsTable` (key `run_id`; `doc` holds the full snapshot JSON, plus summary attributes for the console; `run_id = "LATEST"` is the pointer; 30-day TTL).
- **Replay bucket.** A private S3 bucket holding `replays/index.json` and `replays/<event_id>.json` (DynamoDB items cap at 400 KB).
- **Model layer.** A Lambda layer `wlew-model` containing `model/wlew_model` and `model/params.json`.
- **Logs.** 30-day retention on `/wlew/core/api` and `/wlew/core/score`.

For the video's AWS shots:
- EventBridge Scheduler → `wlew-core-hourly-score`
- CloudWatch → `/wlew/core/score` (the `scoring_run` lines)
- DynamoDB → SnapshotsTable items (`city_status`, `spots_raining`, `spots_high_or_above` columns)
- API Gateway → HTTP API routes

## Redeploy from scratch

Prerequisites: AWS CLI v2, SAM CLI, Python 3.12, and the profile `wlew` in ap-south-1.

    python -m venv .venv && .venv/Scripts/pip install numpy rasterio pysheds pandas requests jsonschema pytest boto3 matplotlib
    make -C core build PYTHON=../.venv/Scripts/python   # stages model/ into core/build/layer, then sam build
    cd core && sam deploy                               # samconfig.toml: stack wlew-core, ap-south-1, profile wlew
    cd .. && .venv/Scripts/python scripts/seed/seed.py  # 69 hotspots -> DynamoDB, 5 replays -> S3 (names from stack outputs)
    make -C core score                                  # optional: score once now instead of waiting for the hour

On Windows, `make` is `mingw32-make`. `sam` may only be on the PowerShell PATH.

## Test

    make -C core test                                   # 24 unit tests: model, rain client, replays vs contract (no AWS)
    .venv/Scripts/python -m pytest core/tests/contract --api https://x6klvfqev1.execute-api.ap-south-1.amazonaws.com
    make contract-check                                 # Agent C's fixture check still passes on this branch

- The contract tests (14) validate every route against `contract/schemas/`. They re-check hotspot, snapshot and replay numbers with the contract's own formula checks and compare `/pumps` with the contract's pump-plan rule. They also check the 404/400 error shapes and CORS. Result at handoff: **14 passed**.
- The unit tests include the worked example, using the contract's default parameters.

## Rebuild the data

| Step | Command | Output |
|---|---|---|
| A1 hotspots | `python scripts/hotspots/build_hotspots.py data/hotspots/research/*.json --report` | `data/hotspots/delhi_hotspots.json` (see `data/hotspots/README.md`) |
| A2 DEM factors | `python scripts/dem/download_dem.py && python scripts/dem/factors.py` | `data/factors/`, `data/hotspots/hotspots_contract.json` (see `data/factors/README.md`) |
| A4 model cells | `python scripts/hotspots/model_cells.py` | `data/hotspots/model_cells.json` |
| A5 replays | `python scripts/replay/build_replay.py` | `data/replay/*.json` (pulls cached in `data/replay/cache/`) |
| A5 tuning | `python scripts/tune/tune.py [--write]` | leaderboard; `--write` freezes `model/params.json` |

## Final parameters (`model/params.json`, version v1)

    rain: i0 4.0 mm/h, i1 20.0 mm/h, a_sat 60 mm, k 1.0, window 6 h      (contract defaults: i0 5, i1 30)
    susceptibility: w_history 0.45, w_low_lying 0.40, w_catchment 0.15    (defaults: 0.40 / 0.35 / 0.25)
    levels: watch 0.15, high 0.35, critical 0.60; city: alert 0.40, severe 0.75   (unchanged)

The tuning protocol and full results are in `model/README.md`.

## Replay metrics (as served by `/replays/{event_id}`)

| event_id | kind | reported | flagged_before_report | median_lead_hours | unconfirmed_flags | Comment |
|---|---|---|---|---|---|---|
| 2024-06-28 | storm | 14 | 3 | 10.6 | 7 | Best case. First HIGH at 23:30 IST, about 3.5 h before the rain started (03:00 IST). City left STANDBY 2 h before the first HIGH. |
| 2024-07-31 | storm | 8 | 3 | 23.1 | 24 | Lead inflated by next-day articles. City left STANDBY in the same frame as the first HIGH. |
| 2026-08-07 | storm | 8 | 2 | 27.5 | 27 | Lead inflated by next-day articles; many unconfirmed flags. |
| 2026-08-25 | storm | 7 | **0** | null | 0 | **Miss.** ECMWF never forecast the burst (at most 4.1 mm/h issued). City reached ALERT; no spot above WATCH. |
| 2026-09-10 | dry | 0 | 0 | null | 0 | All LOW and STANDBY in every frame. |

At least one storm (28 Jun 2024) gives more than an hour of warning, measured against the first article and against the rain start.

## For Agent B and Agent C (demo)

- **The headline replay is a miss.** The roadmap calls 25 Aug 2026 the best headline replay, and the contract fixture tells a success story for it. The real 25 Aug 2026 replay is a miss. **Suggestion:** use `2024-06-28` as the headline replay, the one where warnings came before the rain. Show 25 Aug as the honest limit: forecasts at 9 km miss short convective bursts. Either way, the "Replay of …" label should follow the selected `event_id`, not a hard-coded date.
- **Report times are article publication times**, so lead times are upper bounds. Every ground-truth `note` ends with `[time: published]`. A UI callout like "Flagged HIGH 10.6 h before the first news report" is accurate. "…before flooding began" is not.
- **The checklist item "city leaves STANDBY before the first spot reaches HIGH"** holds for 2024-06-28 (21:30 vs 23:30 IST) and 2026-08-07. It does not hold for 2024-07-31, where both happen in the same frame. 2026-08-25 never reaches HIGH.
- **`spots_raining`** counts spots with forecast intensity I > 0. I is the maximum over the current hour and the next 6, so it includes rain forecast in the next 6 h.
- **Field values to expect.** `peak_at` is `null` when no rain is forecast. `ward` is always `null` (not collected). The 0–50 `count` limit is enforced server-side.

## Known gaps

1. **The live trigger rarely fires.** It's October, after the monsoon, so the live map will normally be all LOW / STANDBY. Use replays for the demo.
2. **Lead times are measured against publication times** (no timestamped Traffic Police posts were found); see `model/README.md`.
3. **25 Aug 2026 is missed.** That's a forecast-skill limit of ECMWF IFS 9 km for convective bursts, not tuned away.
4. **H is understated.** No 2019 reports were found. Big outlets (HT, TOI, NDTV) blocked automated fetching, so evidence leans on smaller outlets.
5. **GLO-30 is a surface model.** Spots under flyovers or the metro viaduct read deck heights (e.g. Rohtak Road at Mundka, L = 0). Several frequently flooded spots get C = 0 because 30 m drainage lines break at roads. See `data/factors/README.md`.
6. **The rain-start and "historical" rain series** are Open-Meteo's archive of ECMWF short-range output, not gauge data.
7. **The weights were tuned on reports from all four storms**, so they aren't independently tested. The rain parameters were tuned on two storms and held out on two.
8. **The Open-Meteo Single Runs archive is missing some runs**, e.g. 18Z in 2024. The replay then uses the next-older run, never a newer one; see `scripts/replay/rain_cache.py`.
9. **Hourly scoring writes one snapshot item per hour.** Manual invocations in the same hour overwrite that hour's item.
