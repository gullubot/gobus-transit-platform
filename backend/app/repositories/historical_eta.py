from typing import List, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.intelligence.config import ETA_HISTORICAL_MIN_SAMPLES
from app.models.historical import HistoricalRouteTravel, HistoricalSegmentTravel


def calculate_median_with_mad_filtering(
    samples: List[float], min_samples: int = ETA_HISTORICAL_MIN_SAMPLES
) -> Optional[float]:
    """
    Applies strict MAD-based outlier rejection and calculates final median.
    Follows Phase 6 frozen spec:
    M_initial = median(X)
    abs_deviations = [abs(x - M_initial) for x in X]
    MAD = median(abs_deviations)
    safe_MAD = max(MAD, 1.0)
    X_filtered = [x for x in X if abs(x - M_initial) <= 3 * safe_MAD]
    M_final = median(X_filtered)
    """
    if len(samples) < min_samples:
        return None

    def _median(lst: List[float]) -> float:
        sorted_lst = sorted(lst)
        n = len(sorted_lst)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_lst[mid - 1] + sorted_lst[mid]) / 2.0
        else:
            return sorted_lst[mid]

    m_initial = _median(samples)
    abs_deviations = [abs(x - m_initial) for x in samples]
    mad = _median(abs_deviations)
    safe_mad = max(mad, 1.0)

    filtered_samples = [x for x in samples if abs(x - m_initial) <= 3 * safe_mad]

    if len(filtered_samples) == 0:
        return None

    return _median(filtered_samples)


class HistoricalETARepository:
    def __init__(self, db: Session):
        self.db = db

    def get_historical_segment_baseline(
        self,
        organization_id: str,
        route_id: str,
        direction: str,
        from_stop_id: str,
        to_stop_id: str,
        day_of_week: int,
        time_of_day_bucket: str,
    ) -> Optional[Tuple[int, int]]:
        """
        Returns (median_travel_seconds, median_destination_stop_dwell_seconds)
        """
        row = (
            self.db.query(HistoricalSegmentTravel)
            .filter(
                and_(
                    HistoricalSegmentTravel.organization_id == organization_id,
                    HistoricalSegmentTravel.route_id == route_id,
                    HistoricalSegmentTravel.direction == direction,
                    HistoricalSegmentTravel.from_stop_id == from_stop_id,
                    HistoricalSegmentTravel.to_stop_id == to_stop_id,
                    HistoricalSegmentTravel.day_of_week == day_of_week,
                    HistoricalSegmentTravel.time_of_day_bucket == time_of_day_bucket,
                    HistoricalSegmentTravel.sample_count >= ETA_HISTORICAL_MIN_SAMPLES,
                )
            )
            .first()
        )

        if row:
            return (row.median_travel_seconds, row.median_destination_stop_dwell_seconds)
        return None

    def get_historical_route_baseline(
        self,
        organization_id: str,
        route_id: str,
        direction: str,
        day_of_week: int,
        time_of_day_bucket: str,
    ) -> Optional[int]:
        """
        Returns median_travel_seconds for the complete route traversal.
        """
        row = (
            self.db.query(HistoricalRouteTravel)
            .filter(
                and_(
                    HistoricalRouteTravel.organization_id == organization_id,
                    HistoricalRouteTravel.route_id == route_id,
                    HistoricalRouteTravel.direction == direction,
                    HistoricalRouteTravel.day_of_week == day_of_week,
                    HistoricalRouteTravel.time_of_day_bucket == time_of_day_bucket,
                    HistoricalRouteTravel.sample_count >= ETA_HISTORICAL_MIN_SAMPLES,
                )
            )
            .first()
        )

        if row:
            return row.median_travel_seconds
        return None
