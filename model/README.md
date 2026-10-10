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

## Replays, tuning and results (A5)

Rebuild with:

    python scripts/replay/build_replay.py   # data/replay/<event_id>.json, index.json, summary.json
    python scripts/tune/tune.py             # prints the leaderboard; add --write to freeze params

### Ground truth

`data/ground_truth/events.json` lists four storms and one dry control day: 37 reports across 26 distinct hotspots. Each report has a source URL. The raw research is in `research_ground_truth.json`.

**The report times are publication times, not first sightings.** We found no timestamped Traffic Police posts or live-blog entries. Each "first report" is the publication time of the earliest article that names the spot, so it's a late bound. Every lead time below is measured against that late bound and overstates the real warning. Some articles were published the next day: on 31 Jul 2024 and 7 Aug 2026, several leads of more than 20 h come from that and shouldn't be read as real warning. Only one rain-start time was stated: 28 Jun 2024 at about 03:00 IST.

Frames run hourly from 18 h before the first report to 6 h after it, 25 frames per event. The dry day runs from 2026-09-09 18:00 to 2026-09-10 18:00 UTC.

### Tuning protocol (fixed before the runs)

- **Rain parameters.** Grid: i0 {3,4,5}, i1 {20,25,30,40}, a_sat {40,60,80}, k {0.5,1,1.5}; the 6 h window is not tuned. Trained on 28 Jun 2024 and 31 Jul 2024; 7 Aug 2026 and 25 Aug 2026 are held out. The objective is flagged-before-report − 0.2 × unconfirmed flags, with a hard rule that the dry day stays all LOW.
- **Weights.** Chosen to maximise how many reported spots land in the top 10 by susceptibility, using the reports from all four storms. The roadmap gives no split for this, so the weights are not independently tested.

**Frozen as v1:** i0 4.0 (was 5.0) and i1 20.0 (was 30.0); a_sat 60 and k 1.0 unchanged. Weights: history 0.45, low-lying 0.40, catchment 0.15 (was 0.40 / 0.35 / 0.25). The level and city thresholds are unchanged. With the weights, 14 of the 37 reports fall on top-10 spots, up from 9.

### Results with v1 (real numbers, misses included)

| Event | Role | Reported | Flagged HIGH before report | Median lead (upper bound) | Unconfirmed flags | Notes |
|---|---|---|---|---|---|---|
| 28 Jun 2024 | train | 14 | 3 (Tilak Bridge, ITO, Pragati Maidan) | 10.6 h | 7 | The city left STANDBY at 21:30 IST on 27 Jun. First HIGH at 23:30 IST, about 3.5 h before the stated 03:00 rain start. Missed: Minto Bridge, Moolchand, Dhaula Kuan and 8 more. Peak risk 0.49. Before tuning: 0 flagged. |
| 31 Jul 2024 | train | 8 | 3 (Pragati Maidan, Patparganj, Jangpura) | 23.1 h | 24 | ITO and Connaught Place went HIGH at 19:30 IST, 17 min after the first article (19:13), so they don't count. The city left STANDBY in the same frame as the first HIGH, 11:30 IST. Leads are inflated by next-day articles. |
| 7 Aug 2026 | held out | 8 | 2 (ITO, Badarpur) | 27.5 h | 27 | Flags started at 05:30 IST on 7 Aug, but the reports are 8 Aug articles, so the leads mean little. Many unconfirmed flags. |
| 25 Aug 2026 | held out (headline) | 7 | **0, a miss** | — | 0 | ECMWF IFS 9 km never forecast the burst: at most 4.1 mm/h in any issued run, against the reported 72 mm in under 2 h. The city reached ALERT (rain trigger 0.45), but peak risk was 0.16 (WATCH). It's kept as an honest miss and not tuned toward. |
| 10 Sep 2026 | dry control | 0 | 0 | — | 0 | Every spot LOW and the city on STANDBY in all 25 frames. |

- **Warning time.** At least one storm day (28 Jun 2024) flagged spots more than an hour before the first report and before the stated rain start, so the "at least an hour of warning" bar is met. Given the publication-time caveat, all lead times are upper bounds.
- **Unconfirmed flags.** They are high on the two heavy 2024/2026 days (24 and 27 of 69 spots). That means flagged with no report found. It isn't proof of a false alarm, because news covers only a few spots per storm.
- **Main limit.** The 9 km model resolution, together with forecasts that miss convective bursts, limits the system more than the formula does. On 25 Aug the model simply didn't see the storm.
