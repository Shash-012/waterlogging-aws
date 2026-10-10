# Shared contract (becomes contract/CONTRACT.md)

This section is the only thing A and B know about each other's work. It fixes the risk formulas, every JSON shape, both APIs and the deploy names; anything not written here is the owning agent's call.

## Conventions

- AWS region `ap-south-1`, CLI profile `wlew`, stacks `wlew-core` (A) and `wlew-ops` (B), every resource tagged `Project=wlew`.
- Python 3.12 for every Lambda and script; Node 20 for the frontend.
- JSON keys are snake_case. Times are UTC ISO 8601 with `Z`; the UI shows IST. Rain is in mm and mm/h. Scores are floats from 0 to 1, rounded to 3 decimals.
- Errors return an HTTP status plus `{"error": {"code": "...", "message": "..."}}`.
- Both APIs allow CORS from `http://localhost:5173` and the Amplify domain, passed in as the stack parameter `AllowedOrigin`.
- Level colours: LOW grey, WATCH amber, HIGH orange, CRITICAL red, each with its own marker shape so colour isn't the only signal.
- Commit prefixes `core:`, `model:`, `data:`, `ops:`, `ui:`, `demo:`. Push to your own branch at least hourly. No force-push, no history rewrites.

## Risk model

$$\text{Risk} = \text{RainTrigger} \times \text{Susceptibility}$$

$$I_{\text{eff}} = I \times \left(1 + k \cdot \min\left(\frac{A}{A_{\text{sat}}},\, 1\right)\right), \qquad \text{RainTrigger} = \operatorname{clip}\left(\frac{I_{\text{eff}} - I_0}{I_1 - I_0},\; 0,\; 1\right)$$

$$\text{Susceptibility} = w_H H + w_L L + w_C C$$

| Input | Exact definition |
|---|---|
| I (mm/h) | Highest hourly Open-Meteo precipitation over the current hour and the next 6. Counting the current hour lets rain already falling register even when an earlier forecast missed it. |
| A (mm) | Sum of hourly precipitation over the 24 hours ending at the current hour |
| L | d = mean raw-DEM elevation in a ring 150 to 400 m around the spot, minus the median of the 3 × 3 cells at the spot. L = clip(d / 3 m, 0, 1). Underpasses get L = max(L, 0.9), because a 30 m surface model can't see the cut. |
| C | Upstream area A_c (km²) from D8 flow accumulation on a pit-filled, flat-resolved DEM, read at the highest-accumulation cell within 60 m of the spot. C = clip(log10(A_c / 0.01) / log10(500), 0, 1), so 1 hectare maps to 0 and 5 km² to 1. |
| H | n = distinct monsoon seasons, 2019 to 2025, with a documented waterlogging report at the spot; an official prone-points list counts as one. H = clip(n / 5, 0, 1). |
| Importance | 1.0 for arterial roads and emergency routes, 0.6 for major roads, 0.3 for local roads. Pump tie-breaker only. |

Defaults live in `model/params.json`. Agent A may retune the numbers; the shape is fixed, and B never hard-codes a threshold (it colours by the level the API returns).

```json
{
  "version": "v1",
  "rain": {"i0_mm_h": 5.0, "i1_mm_h": 30.0, "a_sat_mm": 60.0, "k": 1.0, "window_hours": 6},
  "susceptibility": {"w_history": 0.40, "w_low_lying": 0.35, "w_catchment": 0.25},
  "levels": {"watch": 0.15, "high": 0.35, "critical": 0.60},
  "city": {"alert": 0.40, "severe": 0.75}
}
```

Levels: LOW below `watch`, WATCH, HIGH, CRITICAL at `critical` and above. City status from the highest rain trigger across spots: STANDBY at 0, RAIN_WATCH above 0, ALERT at `city.alert`, SEVERE at `city.severe`.

Pump plan: sort spots by level (CRITICAL first), then risk, then importance, all descending. Give one pump to each HIGH or CRITICAL spot in that order. With pumps left, give a second to CRITICAL spots in the same order, then one to WATCH spots. HIGH-or-above spots left without a pump are listed as `unassigned`.

Worked example, which must appear in A's unit tests and in C's fixtures: I = 14 mm/h and A = 30 mm give I_eff = 21 and RainTrigger = 0.64. H = 0.8, L = 0.9 and C = 0.72 give Susceptibility = 0.815. Risk = 0.522, level HIGH, city status ALERT.

## Payloads

Hotspot, from `GET /hotspots` and `GET /hotspots/{id}` (example values):

```json
{
  "hotspot_id": "DL-001",
  "name_en": "Minto Bridge underpass",
  "name_hi": "मिंटो ब्रिज अंडरपास",
  "lat": 28.63, "lon": 77.22,
  "site_type": "underpass",
  "ward": null,
  "importance": 1.0,
  "elevation_m": 214.0, "relative_depth_m": 1.4, "catchment_km2": 0.88, "flood_seasons": 4,
  "factors": {"history": 0.8, "low_lying": 0.9, "catchment": 0.72},
  "susceptibility": 0.815,
  "avoid_en": "...", "avoid_hi": "...", "diversion_en": "...", "diversion_hi": "...",
  "sources": ["https://..."]
}
```

`site_type` is one of `underpass`, `road`, `junction`, `colony`.

Snapshot, from `GET /scores/latest`, and the shape of every replay frame:

```json
{
  "run_id": "2026-10-09T14:00:00Z",
  "as_of": "2026-10-09T14:00:00Z",
  "mode": "live",
  "params_version": "v1",
  "city": {"status": "ALERT", "rain_trigger_max": 0.64, "spots_raining": 31},
  "hotspots": [
    {"hotspot_id": "DL-001", "rank": 1, "level": "HIGH", "risk": 0.522,
     "rain_trigger": 0.64, "susceptibility": 0.815,
     "intensity_mm_h": 14.0, "rain_24h_mm": 30.0, "effective_intensity_mm_h": 21.0,
     "peak_at": "2026-10-09T17:00:00Z"}
  ]
}
```

Pump plan, from `GET /pumps?count=6`:

```json
{"run_id": "2026-10-09T14:00:00Z", "pumps_available": 6,
 "assignments": [{"hotspot_id": "DL-001", "pumps": 1, "level": "HIGH", "risk": 0.522}],
 "unassigned": []}
```

Replays, from `GET /replays` (a list) and `GET /replays/{event_id}`. `kind` is `storm` or `dry`; frames use `mode: "replay"`.

```json
{"event_id": "2026-08-25", "title_en": "...", "kind": "storm",
 "start": "...", "end": "...", "frame_count": 24,
 "frames": ["<Snapshot>"],
 "ground_truth": [{"hotspot_id": "DL-001", "first_report_at": "...", "source_url": "https://...", "note": "..."}],
 "metrics": {"spots_reported": 9, "flagged_before_report": 7, "median_lead_hours": 3.0, "unconfirmed_flags": 4}}
```

The list endpoint returns the same objects without `frames`, `ground_truth` and `metrics`.

Alert, `POST /alerts` on the ops API (Cognito JWT required):

```json
{"hotspot_id": "DL-001", "run_id": "2026-10-09T14:00:00Z", "mode": "replay", "event_id": "2026-08-25",
 "level": "HIGH", "risk": 0.522, "peak_at": "2026-10-09T17:00:00Z"}
```

Response; `GET /alerts?limit=50` returns `{"alerts": [...]}` of these, each with the request fields and `sent_by` added:

```json
{"alert_id": "...", "sent_at": "...", "duplicate": false, "text_en": "...", "text_hi": "...",
 "deliveries": [{"group": "traffic-police-demo", "ok": true}, {"group": "rwa-demo", "ok": true}]}
```

## APIs

| API | Route | Returns | Owner |
|---|---|---|---|
| Core (public, GET only) | `GET /health` | `{"ok": true, "latest_run_id": "..."}` | A |
| Core | `GET /hotspots`, `GET /hotspots/{id}` | Hotspot list, one Hotspot | A |
| Core | `GET /scores/latest` | Snapshot | A |
| Core | `GET /pumps?count=N` (N from 0 to 50) | Pump plan | A |
| Core | `GET /replays`, `GET /replays/{event_id}` | Replay list, one replay | A |
| Ops (Cognito JWT) | `POST /alerts` | Alert response | B |
| Ops (Cognito JWT) | `GET /alerts?limit=N` | Alert log | B |

## Deploy wiring

- `wlew-core` outputs `CoreApiUrl`.
- `wlew-ops` takes parameters `CoreApiUrl` and `AllowedOrigin`, and outputs `OpsApiUrl`, `UserPoolId` and `UserPoolClientId`.
- The frontend reads `VITE_CORE_API_URL`, `VITE_OPS_API_URL`, `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID` and `VITE_DATA_SOURCE` (`fixtures` or `live`). With `fixtures`, it reads `contract/fixtures/` and fakes `POST /alerts` locally.
- Secrets live in SSM Parameter Store, never in git: `/wlew/telegram/bot_token` (SecureString) and `/wlew/telegram/groups` (JSON of group key to chat ID).
