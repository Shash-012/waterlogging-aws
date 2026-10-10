"""Open-Meteo rain clients (stdlib only, so the scoring Lambda needs no dependencies).

All series use the ECMWF IFS 9 km model (models=ecmwf_ifs) so thresholds tuned on replays
carry over to live scoring. Open-Meteo reports `precipitation` at time T as the total of the
preceding hour, in mm, which is already mm/h for hourly steps.

Returned series are {datetime (UTC, on the hour): mm} per point, in the order given.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SINGLE_RUNS_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
MODEL = "ecmwf_ifs"
RUN_HOURS = (0, 6, 12, 18)
RUN_LAG_HOURS = 6  # a run is usable 4-6 h after it starts; frame t uses the latest run started <= t-6h
USER_AGENT = "wlew-ews/0.1 (+https://github.com/Shash-012/waterlogging-aws)"


def get_json(url, params, retries=4, backoff_s=1.0, timeout_s=20):
    """GET with retries and exponential backoff on network errors, 429 and 5xx."""
    full = url + "?" + urllib.parse.urlencode(params, safe=",:")
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500 or attempt == retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(backoff_s * 2 ** attempt)
    raise RuntimeError("unreachable")


def _coords(points):
    return {"latitude": ",".join(f"{p[0]:.5f}" for p in points),
            "longitude": ",".join(f"{p[1]:.5f}" for p in points)}


def _series(payload):
    items = payload if isinstance(payload, list) else [payload]
    out = []
    for item in items:
        h = item["hourly"]
        out.append({datetime.strptime(t, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc): (v or 0.0)
                    for t, v in zip(h["time"], h["precipitation"])})
    return out


def live_rain(points):
    """One batched forecast call: the past 24 h and the next 8 h for every point.

    Pass each spot's model grid cell (data/hotspots/model_cells.json) rather than its own
    coordinates: spots sharing a 9 km cell are fetched once, which keeps the call near 1 s.
    """
    unique = list(dict.fromkeys(points))
    params = {**_coords(unique), "hourly": "precipitation", "models": MODEL, "timezone": "UTC",
              "past_hours": 24, "forecast_hours": 8}
    by_point = dict(zip(unique, _series(get_json(FORECAST_URL, params))))
    return [by_point[p] for p in points]


def run_start_for(frame_time):
    """Latest ECMWF run (00/06/12/18 UTC) that started at or before frame_time - RUN_LAG_HOURS."""
    t = frame_time - timedelta(hours=RUN_LAG_HOURS)
    return t.replace(hour=t.hour - t.hour % 6, minute=0, second=0, microsecond=0)


def run_forecast(points, run_start, hours=48):
    """The forecast exactly as issued by one ECMWF run (Open-Meteo Single Runs API)."""
    params = {**_coords(points), "hourly": "precipitation", "models": MODEL, "timezone": "UTC",
              "run": run_start.strftime("%Y-%m-%dT%H:%M"), "forecast_hours": hours}
    return _series(get_json(SINGLE_RUNS_URL, params))


def historical(points, start_date, end_date):
    """Rain that fell, as Open-Meteo's archived ECMWF short-range series (for A, the 24 h total)."""
    params = {**_coords(points), "hourly": "precipitation", "models": MODEL, "timezone": "UTC",
              "start_date": start_date.strftime("%Y-%m-%d"), "end_date": end_date.strftime("%Y-%m-%d")}
    return _series(get_json(HISTORICAL_URL, params))


def replay_hourly(frame_time, past, run, window_hours=6):
    """Rain known at frame_time for one point, ready for wlew_model.rain_inputs.

    Hours up to and including frame_time (rain that has already fallen) come from the
    historical series; the next window_hours come from the run that was usable then.
    Nothing after frame_time is taken from the historical series.
    """
    hourly = {frame_time - timedelta(hours=h): past.get(frame_time - timedelta(hours=h), 0.0) for h in range(24)}
    for h in range(1, window_hours + 1):
        t = frame_time + timedelta(hours=h)
        hourly[t] = run.get(t, 0.0)
    return hourly
