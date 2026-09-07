import uuid
import pytest
from datetime import date, timedelta
from app.services.fare_service import FareCalculationService, FareCalculationError


def test_validate_slabs_success():
    slabs = [
        {"min_distance_km": 0.0, "max_distance_km": 2.0, "fare_amount": 10},
        {"min_distance_km": 2.0, "max_distance_km": 5.0, "fare_amount": 15},
        {"min_distance_km": 5.0, "max_distance_km": None, "fare_amount": 20},
    ]
    # Should not raise
    FareCalculationService.validate_slabs(slabs)


def test_validate_slabs_starts_non_zero():
    slabs = [
        {"min_distance_km": 1.0, "max_distance_km": 2.0, "fare_amount": 10},
    ]
    with pytest.raises(ValueError, match="first fare slab must start at 0.0 km"):
        FareCalculationService.validate_slabs(slabs)


def test_validate_slabs_gap():
    slabs = [
        {"min_distance_km": 0.0, "max_distance_km": 2.0, "fare_amount": 10},
        {"min_distance_km": 2.5, "max_distance_km": 5.0, "fare_amount": 15},
    ]
    with pytest.raises(ValueError, match="Slab gap or overlap detected"):
        FareCalculationService.validate_slabs(slabs)


def test_validate_slabs_overlap():
    slabs = [
        {"min_distance_km": 0.0, "max_distance_km": 3.0, "fare_amount": 10},
        {"min_distance_km": 2.0, "max_distance_km": 5.0, "fare_amount": 15},
    ]
    with pytest.raises(ValueError, match="Slab gap or overlap detected"):
        FareCalculationService.validate_slabs(slabs)


def test_validate_slabs_multiple_open_ended():
    slabs = [
        {"min_distance_km": 0.0, "max_distance_km": None, "fare_amount": 10},
        {"min_distance_km": 2.0, "max_distance_km": None, "fare_amount": 15},
    ]
    with pytest.raises(ValueError, match="Only the final slab can be open-ended"):
        FareCalculationService.validate_slabs(slabs)


def test_validate_slabs_negative():
    slabs = [
        {"min_distance_km": 0.0, "max_distance_km": 2.0, "fare_amount": -5},
    ]
    with pytest.raises(ValueError, match="fare_amount cannot be negative"):
        FareCalculationService.validate_slabs(slabs)

