import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "functions" / "score"))
import rain  # noqa: E402

UTC = timezone.utc


def test_run_start_uses_latest_run_six_hours_back():
    assert rain.run_start_for(datetime(2026, 8, 25, 10, tzinfo=UTC)) == datetime(2026, 8, 25, 0, tzinfo=UTC)
    assert rain.run_start_for(datetime(2026, 8, 25, 11, tzinfo=UTC)) == datetime(2026, 8, 25, 0, tzinfo=UTC)
    assert rain.run_start_for(datetime(2026, 8, 25, 12, tzinfo=UTC)) == datetime(2026, 8, 25, 6, tzinfo=UTC)
    assert rain.run_start_for(datetime(2026, 8, 25, 3, tzinfo=UTC)) == datetime(2026, 8, 24, 18, tzinfo=UTC)


def test_replay_hourly_never_reads_the_future_from_observed_rain():
    t = datetime(2026, 8, 25, 10, tzinfo=UTC)
    past = {t + timedelta(hours=h): 100.0 + h for h in range(-30, 30)}  # "what fell", incl. the future
    run = {t + timedelta(hours=h): 1.0 for h in range(-6, 30)}           # what the usable run forecast
    hourly = rain.replay_hourly(t, past, run)
    assert set(hourly) == {t + timedelta(hours=h) for h in range(-23, 7)}
    assert all(hourly[t + timedelta(hours=h)] == 1.0 for h in range(1, 7))   # future = issued forecast only
    assert hourly[t] == 100.0 and hourly[t - timedelta(hours=23)] == 77.0     # past = what fell


def test_series_parses_lists_and_nulls():
    payload = [{"hourly": {"time": ["2026-08-25T00:00", "2026-08-25T01:00"], "precipitation": [None, 2.5]}}]
    (s,) = rain._series(payload)
    assert s == {datetime(2026, 8, 25, 0, tzinfo=UTC): 0.0, datetime(2026, 8, 25, 1, tzinfo=UTC): 2.5}
