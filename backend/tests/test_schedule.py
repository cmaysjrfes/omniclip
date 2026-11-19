from datetime import datetime, timedelta

from app.agents.schedule_optimizer import next_publish_times, rank_slots


def _uploads(hour: int, vpd: float, n: int = 10):
    base = datetime(2026, 10, 5, hour)  # a Monday, UTC
    return [{"published_at": (base + timedelta(days=7 * i)).isoformat() + "+00:00", "views_per_day": vpd}
            for i in range(n)]


def test_rank_slots_prefers_high_performing_hours_in_local_time():
    uploads = _uploads(22, 50_000, n=3) + _uploads(9, 500, n=3)  # Oct 5-19: all inside EDT
    slots = rank_slots(uploads, [], tz="America/New_York")
    assert (slots[0]["weekday"], slots[0]["hour"]) == (0, 18)  # 22:00 UTC = 18:00 EDT Monday


def test_own_data_overrides_prior_with_enough_samples():
    uploads = _uploads(22, 50_000) + _uploads(9, 500)
    own = ([{"published_at": u["published_at"], "views_48h": 900_000} for u in _uploads(9, 0, n=20)]
           + [{"published_at": u["published_at"], "views_48h": 1_000} for u in _uploads(22, 0, n=20)])
    slots = rank_slots(uploads, own, tz="UTC")
    assert (slots[0]["weekday"], slots[0]["hour"]) == (0, 9)


def test_next_publish_times_respects_daily_cap_and_spacing():
    slots = [{"weekday": d, "hour": h, "minute": 0, "score": 90} for d in range(7) for h in (9, 10, 13, 18, 21)]
    times = next_publish_times(slots, tz="UTC", count=6, after=datetime(2026, 11, 2, 0), posts_per_day=2,
                               min_gap_hours=3)
    assert len(times) == 6
    days = [t.date() for t in times]
    assert all(days.count(d) <= 2 for d in days)
    for a, b in zip(times, times[1:]):
        assert (b - a) >= timedelta(hours=3)
