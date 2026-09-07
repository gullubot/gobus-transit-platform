import uuid
from datetime import datetime, timezone, timedelta, date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import engine
from app.db.seed import (
    ORG_ID,
    VEH_IDS,
    STOP_IDS,
    RS_IDS,
    ROUTE_R1_ID,
    ROUTE_R2_ID,
    SVC_AC4B_ID,
    SVC_SD5_ID,
    FARE_CONFIG_ID,
    seed_dev_data,
)
from app.main import app
from app.models.enums import Direction, TripStatus
from app.models.route import Stop, RouteStop
from app.models.service import Service, ServiceSchedule
from app.models.state import BusCurrentState
from app.models.trip import Trip

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed():
    """Ensure database has seed data before each test."""
    with Session(engine) as session:
        session.execute(text("DELETE FROM bus_current_state"))
        session.commit()
        seed_dev_data(session)


def _get_stops():
    res = client.get(f"/api/passenger/stops?organization_id={ORG_ID}")
    assert res.status_code == 200
    stops = res.json()
    stop_cc = next(s for s in stops if "City Center" in s["name"] or "CC" in s["stop_code"])
    stop_kp = next(s for s in stops if "Knowledge Park" in s["name"] or "KP" in s["stop_code"])
    stop_tp = next(s for s in stops if "Tech Park" in s["name"] or "TP" in s["stop_code"])
    stop_ap = next(s for s in stops if "Airport" in s["name"] or "AP" in s["stop_code"])
    stop_rs = next(s for s in stops if "Railway Station" in s["name"] or "RS" in s["stop_code"])
    return stop_cc, stop_kp, stop_tp, stop_ap, stop_rs


def test_01_today_active_live_bus():
    """1. today + active live bus: Returns LIVE mode with authoritative nearest bus"""
    cc, _, tp, _, _ = _get_stops()
    v1 = VEH_IDS["PNB005234"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=180,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["availability_mode"] == "LIVE"
    assert srv["departure_mode"] == "LIVE_DEPARTURE"
    assert srv["arrival_mode"] == "LIVE_ETA"
    assert srv["active_buses_count"] == 1
    assert srv["nearest_bus"] is not None
    assert srv["nearest_bus"]["vehicle_id"] == str(v1)
    assert srv["relative_wait_seconds"] == 180
    assert "Arriving in 3 min" in srv["relative_message"]


def test_02_today_no_active_bus_later_schedule():
    """2. today + no active bus + later schedule: Fallback to earliest scheduled departure"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=04:00:00"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["availability_mode"] == "SCHEDULED"
    assert srv["departure_mode"] == "SCHEDULED_DEPARTURE"
    assert srv["arrival_mode"] == "SCHEDULED_ARRIVAL"
    assert srv["active_buses_count"] == 0
    assert srv["nearest_bus"] is None
    assert srv["departure_timestamp"] is not None
    assert srv["relative_wait_seconds"] is not None


def test_03_today_before_first_service():
    """3. today before first service: returns first real service with relative wait"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Seed early morning schedule from 06:00 to 22:00
    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(6, 0),
            end_time=time(22, 0),
            typical_interval_minutes=30,
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=05:00:00"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["availability_mode"] == "SCHEDULED"
    # First service arrives at CC at 06:00 (departure at CC)
    assert srv["departure_timestamp"] is not None
    assert "06:00:00" in srv["departure_timestamp"]
    assert srv["relative_wait_seconds"] == 3600
    assert srv["relative_message"] == "Departs in 1 hr"


def test_04_today_between_services():
    """4. today between services: returns the next scheduled departure"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(8, 0),
            end_time=time(20, 0),
            typical_interval_minutes=20,
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    # Search at 08:25 -> next departure is at 08:40
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=08:25:00"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["availability_mode"] == "SCHEDULED"
    assert "08:40:00" in srv["departure_timestamp"]
    assert srv["relative_wait_seconds"] == 15 * 60
    assert srv["relative_message"] == "Starts in 15 min"


def test_05_today_after_last_service():
    """5. today after last service: returns UNAVAILABLE state"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(8, 0),
            end_time=time(18, 0),
            typical_interval_minutes=20,
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    # Search at 21:00 -> after last service 18:00
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=21:00:00"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["availability_mode"] == "UNAVAILABLE"
    assert srv["departure_timestamp"] is None


def test_06_future_date_schedule():
    """6. future date schedule: uses actual schedule for future date"""
    cc, _, tp, _, _ = _get_stops()
    future_date = (datetime.now(timezone.utc) + timedelta(days=5)).date()
    future_str = future_date.strftime("%Y-%m-%d")

    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(7, 0),
            end_time=time(21, 0),
            typical_interval_minutes=30,
            days_of_week=[future_date.weekday()],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={future_str}&search_time=08:00:00"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["availability_mode"] == "SCHEDULED"
    assert srv["departure_timestamp"] is not None
    assert "08:00:00" in srv["departure_timestamp"]


def test_07_future_date_with_no_service():
    """7. future date with no service: truthful unavailable state"""
    cc, _, tp, _, _ = _get_stops()
    future_date = (datetime.now(timezone.utc) + timedelta(days=5)).date()
    future_str = future_date.strftime("%Y-%m-%d")

    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        # Schedule only runs on weekday 0 (Monday), assume future_date is different
        other_day = (future_date.weekday() + 1) % 7
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(7, 0),
            end_time=time(21, 0),
            typical_interval_minutes=30,
            days_of_week=[other_day],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={future_str}&search_time=08:00:00"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["availability_mode"] == "UNAVAILABLE"


def test_08_live_eta_rendering():
    """8. live ETA rendering: relative message says Arriving in X min"""
    cc, _, tp, _, _ = _get_stops()
    v1 = VEH_IDS["PNB005234"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=420,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["relative_message"] == "Arriving in 7 min"


def test_09_scheduled_relative_wait():
    """9. scheduled relative wait: relative message says Starts in X min"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(10, 0),
            end_time=time(20, 0),
            typical_interval_minutes=30,
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=09:42:00"
    )
    assert res.status_code == 200
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["relative_message"] == "Starts in 18 min"
    assert srv["relative_wait_seconds"] == 18 * 60


def test_10_changing_requested_time_changes_relative_wait():
    """10. changing requested time changes relative wait dynamically"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(10, 0),
            end_time=time(20, 0),
            typical_interval_minutes=60,
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    # Search at 09:30 -> 30 min wait
    res1 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=09:30:00"
    )
    s1 = next(s for s in res1.json() if s["service_id"] == str(SVC_AC4B_ID))
    assert s1["relative_wait_seconds"] == 1800
    assert s1["relative_message"] == "Starts in 30 min"

    # Search at 09:50 -> 10 min wait
    res2 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=09:50:00"
    )
    s2 = next(s for s in res2.json() if s["service_id"] == str(SVC_AC4B_ID))
    assert s2["relative_wait_seconds"] == 600
    assert s2["relative_message"] == "Starts in 10 min"


def test_11_no_fabricated_bus():
    """11. no fabricated bus: nearest_bus is None when no actual vehicle is live"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["nearest_bus"] is None
    assert srv["active_buses_count"] == 0


def test_12_no_fabricated_eta():
    """12. no fabricated ETA: if eta_status is UNAVAILABLE, eta_seconds is None"""
    cc, _, tp, _, _ = _get_stops()
    v1 = VEH_IDS["PNB005234"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=None,
            eta_status="UNAVAILABLE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    srv = next(s for s in res.json() if s["service_id"] == str(SVC_AC4B_ID))
    # Bus exists but has UNAVAILABLE eta, so it falls back to schedule
    assert srv["nearest_bus"] is None or srv["nearest_bus"]["eta_seconds"] is None


def test_13_ac_filtering():
    """13. AC filtering: filter_by=AC returns only AC services"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&filter_by=AC"
    )
    data = res.json()
    assert len(data) > 0
    assert all(s["is_ac"] is True for s in data)


def test_14_non_ac_filtering():
    """14. Non-AC filtering: filter_by=NON_AC returns only Non-AC services"""
    _, _, _, ap, rs = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={ap['id']}&destination_id={rs['id']}&filter_by=NON_AC"
    )
    data = res.json()
    assert len(data) > 0
    assert all(s["is_ac"] is False for s in data)


def test_15_direct_filtering():
    """15. Direct filtering: filter_by=DIRECT returns direct services"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&filter_by=DIRECT"
    )
    data = res.json()
    assert all(s["is_direct"] is True for s in data)


def test_16_lowest_price_sorting():
    """16. lowest-price sorting: sort_by=LOWEST_PRICE orders ascending by fare"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&sort_by=LOWEST_PRICE"
    )
    data = res.json()
    fares = [s["fare"] for s in data if s["fare"] is not None]
    assert fares == sorted(fares)


def test_17_quickest_sorting():
    """17. quickest sorting: sort_by=QUICKEST orders ascending by journey duration"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&sort_by=QUICKEST"
    )
    data = res.json()
    durations = [s["journey_duration_seconds"] for s in data if s["journey_duration_seconds"] is not None]
    assert durations == sorted(durations)


def test_18_earliest_departure_sorting():
    """18. earliest departure sorting: sort_by=EARLIEST_DEPARTURE orders by departure_timestamp"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&sort_by=EARLIEST_DEPARTURE"
    )
    data = res.json()
    deps = [s["departure_timestamp"] for s in data if s["departure_timestamp"] is not None]
    assert deps == sorted(deps)


def test_19_multi_factor_best_match_ranking():
    """19. multi-factor Best Match ranking: computes ranking_score and orders descending"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&sort_by=BEST_MATCH"
    )
    data = res.json()
    avail = [s for s in data if s["availability_mode"] != "UNAVAILABLE"]
    if len(avail) > 1:
        scores = [s["ranking_score"] for s in avail if s["ranking_score"] is not None]
        assert scores == sorted(scores, reverse=True)


def test_20_accurate_visible_result_count():
    """20. accurate visible result count: returned list matches actual qualifying items"""
    cc, _, tp, _, _ = _get_stops()
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    data = res.json()
    assert len(data) == 1
    assert data[0]["service_code"] == "AC4B"


def test_21_accurate_en_route_count():
    """21. accurate en-route count: only counts real live active buses"""
    cc, _, tp, _, _ = _get_stops()
    v1 = VEH_IDS["PNB005234"]
    v2 = VEH_IDS["PNB005781"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=200,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        b2 = BusCurrentState(
            vehicle_id=v2,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=500,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.add(b2)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["active_buses_count"] == 2


def test_22_zero_en_route_future_scheduled_services():
    """22. zero en-route + future scheduled services: future search always has active_buses_count = 0"""
    cc, _, tp, _, _ = _get_stops()
    v1 = VEH_IDS["PNB005234"]
    # Add an active bus for today
    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=200,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    # Search for tomorrow
    tomorrow_str = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={tomorrow_str}"
    )
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["active_buses_count"] == 0
    assert srv["nearest_bus"] is None


def test_23_searched_segment_vs_absolute_route():
    """23. searched segment vs absolute route endpoints are distinct"""
    cc, kp, tp, _, _ = _get_stops()
    # Search KP -> TP (sub-segment of CC -> TP route)
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={kp['id']}&destination_id={tp['id']}"
    )
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["searched_origin"] == kp["name"]
    assert srv["searched_destination"] == tp["name"]
    assert srv["absolute_origin"] == cc["name"]
    assert srv["absolute_destination"] == tp["name"]


def test_24_fare_correctness():
    """24. fare correctness: matches distance slab authoritative fare"""
    cc, _, tp, _, _ = _get_stops()
    # CC (0.0km) to TP (5.2km) = 5.2 km -> matches 5.0km+ slab = ₹20.0
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    data = res.json()
    srv = next(s for s in data if s["service_id"] == str(SVC_AC4B_ID))
    assert srv["fare"] == 20.0


def test_25_swap_triggers_fresh_results():
    """25. swap triggers fresh results with reversed direction B_TO_A"""
    cc, _, tp, _, _ = _get_stops()
    res_fwd = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    assert res_fwd.json()[0]["direction"] == "A_TO_B"

    res_rev = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={tp['id']}&destination_id={cc['id']}"
    )
    assert res_rev.json()[0]["direction"] == "B_TO_A"


def test_26_date_change_triggers_fresh_results():
    """26. date change triggers fresh results for requested date"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    next_week_str = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")

    res1 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}"
    )
    res2 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={next_week_str}"
    )
    assert res1.status_code == 200
    assert res2.status_code == 200


def test_27_time_change_triggers_fresh_results():
    """27. time change triggers fresh results with different departure timing"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    res1 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=08:00:00"
    )
    res2 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=14:00:00"
    )
    s1 = res1.json()[0]
    s2 = res2.json()[0]
    assert s1["departure_timestamp"] != s2["departure_timestamp"]


def test_28_filter_no_match_empty_state():
    """28. filter-no-match empty state: filter_by with no matches returns empty list"""
    cc, _, tp, _, _ = _get_stops()
    # AC4B is AC, filtering by NON_AC should yield empty list
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&filter_by=NON_AC"
    )
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_29_no_services_found_empty_state():
    """29. no-services-found empty state: stops not connected by any service yield empty list"""
    cc, _, _, ap, _ = _get_stops()
    # CC is on R1, AP is on R2 (no direct service connecting CC to AP)
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={ap['id']}"
    )
    assert res.status_code == 200
    assert len(res.json()) == 0


def test_30_no_more_buses_today_empty_state():
    """30. no-more-buses-today empty state: all schedules in past marked UNAVAILABLE"""
    cc, _, tp, _, _ = _get_stops()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with Session(engine) as session:
        session.execute(text("DELETE FROM service_schedules WHERE service_id = :sid"), {"sid": SVC_AC4B_ID})
        sch = ServiceSchedule(
            id=uuid.uuid4(),
            service_id=SVC_AC4B_ID,
            direction=Direction.A_TO_B,
            start_time=time(6, 0),
            end_time=time(12, 0),
            typical_interval_minutes=30,
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            status="ACTIVE",
        )
        session.add(sch)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={today_str}&search_time=23:00:00"
    )
    assert res.status_code == 200
    srv = res.json()[0]
    assert srv["availability_mode"] == "UNAVAILABLE"


def test_31_service_specific_journey_duration():
    """31. service-specific journey duration: calculated from route stops nominal travel time"""
    cc, kp, tp, _, _ = _get_stops()
    # CC (300s) -> TP (1200s) = 900s (15 min)
    res1 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    assert res1.json()[0]["journey_duration_seconds"] == 900

    # KP (900s) -> TP (1200s) = 300s (5 min)
    res2 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={kp['id']}&destination_id={tp['id']}"
    )
    assert res2.json()[0]["journey_duration_seconds"] == 300


def test_32_no_double_counting_live_eta():
    """32. no double-counting live ETA: arrival is departure + segment duration"""
    cc, _, tp, _, _ = _get_stops()
    v1 = VEH_IDS["PNB005234"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=240,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    srv = res.json()[0]
    dep = datetime.fromisoformat(srv["departure_timestamp"])
    arr = datetime.fromisoformat(srv["arrival_timestamp"])
    duration = (arr - dep).total_seconds()
    assert duration == srv["journey_duration_seconds"]


def test_33_future_search_does_not_leak_todays_live_buses():
    """33. future search does not leak today's live buses"""
    cc, _, tp, _, _ = _get_stops()
    v1 = VEH_IDS["PNB005234"]

    with Session(engine) as session:
        b1 = BusCurrentState(
            vehicle_id=v1,
            service_id=SVC_AC4B_ID,
            direction="A_TO_B",
            state="LIVE",
            eta_seconds=120,
            eta_status="LIVE",
            last_observed_at=datetime.now(timezone.utc),
            last_received_at=datetime.now(timezone.utc),
        )
        session.add(b1)
        session.commit()

    future_str = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    res = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}&search_date={future_str}"
    )
    srv = res.json()[0]
    assert srv["availability_mode"] == "SCHEDULED"
    assert srv["active_buses_count"] == 0
    assert srv["nearest_bus"] is None


def test_34_stable_deterministic_ordering():
    """34. stable deterministic ordering: multiple identical queries yield identical candidate order"""
    cc, _, tp, _, _ = _get_stops()
    res1 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    res2 = client.get(
        f"/api/passenger/services/search?organization_id={ORG_ID}&origin_id={cc['id']}&destination_id={tp['id']}"
    )
    assert [s["service_id"] for s in res1.json()] == [s["service_id"] for s in res2.json()]
