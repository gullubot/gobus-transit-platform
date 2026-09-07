"""
Transit Platform — Service-Day Manifest Ingestion & Generation.

BUILD 4 Phase 5B: Sanitized manifest loader importing planned trips, vehicle duties,
and operator mappings with strict validation and zero credential leakage.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

FORBIDDEN_SECRET_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "jwt",
    "secret",
    "authorization",
    "bearer",
}


@dataclass
class ServiceDayManifest:
    """Sanitized manifest representing an operational service day."""
    service_date: str
    timezone: str
    vehicles: List[Dict[str, Any]]
    operators: List[Dict[str, Any]]
    trips: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_date": self.service_date,
            "timezone": self.timezone,
            "metadata": self.metadata,
            "vehicles": self.vehicles,
            "operators": self.operators,
            "trips": self.trips,
        }

    def save(self, filepath: Union[str, Path]) -> None:
        """Exports manifest to JSON file."""
        p = Path(filepath)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


def _check_no_secrets(obj: Any, path: str = "") -> None:
    """Recursively validates that no secret or credential keys exist."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_SECRET_KEYS:
                raise ValueError(f"Security violation: forbidden credential key '{k}' found in manifest at '{path}'")
            _check_no_secrets(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _check_no_secrets(item, f"{path}[{idx}]")


def load_manifest(source: Union[str, Path, Dict[str, Any]]) -> ServiceDayManifest:
    """
    Loads and validates a ServiceDayManifest from a file path or dictionary.
    """
    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Service day manifest not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    elif isinstance(source, dict):
        data = source
    else:
        raise TypeError(f"Expected file path or dict, got {type(source)}")

    # 1. Security check: Reject any credentials
    _check_no_secrets(data)

    # 2. Schema check: Required top-level fields
    for required in ("service_date", "vehicles", "operators", "trips"):
        if required not in data:
            raise ValueError(f"Manifest missing required field: '{required}'")

    if not isinstance(data["vehicles"], list) or len(data["vehicles"]) == 0:
        raise ValueError("Manifest 'vehicles' must be a non-empty list")

    if not isinstance(data["operators"], list) or len(data["operators"]) == 0:
        raise ValueError("Manifest 'operators' must be a non-empty list")

    if not isinstance(data["trips"], list) or len(data["trips"]) == 0:
        raise ValueError("Manifest 'trips' must be a non-empty list")

    # 3. Validate each trip has minimum required identifiers
    for idx, t in enumerate(data["trips"]):
        for tf in ("trip_id", "service_id", "route_id", "vehicle_id", "operator_code", "direction", "planned_start"):
            if tf not in t:
                raise ValueError(f"Trip at index {idx} missing required field '{tf}'")

    return ServiceDayManifest(
        service_date=data["service_date"],
        timezone=data.get("timezone", "Asia/Kolkata"),
        vehicles=data["vehicles"],
        operators=data["operators"],
        trips=data["trips"],
        metadata=data.get("metadata", {}),
    )


def create_default_manifest(service_date: str = "2026-09-03") -> ServiceDayManifest:
    """
    Generates a realistic full-day manifest based on real GoBus database inventory
    discovered during Phase 5A audit (Route SD5, R1, R2, across all 4 vehicles).
    """
    vehicles = [
        {"vehicle_id": "8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e", "vehicle_number": "WB04-DEMO-001", "vehicle_type": "AC_BUS"},
        {"vehicle_id": "50000000-0000-0000-0000-000000000001", "vehicle_number": "PNB005234", "vehicle_type": "BUS"},
        {"vehicle_id": "50000000-0000-0000-0000-000000000002", "vehicle_number": "PNB005781", "vehicle_type": "BUS"},
        {"vehicle_id": "50000000-0000-0000-0000-000000000003", "vehicle_number": "PNB006421", "vehicle_type": "MINI_BUS"},
    ]

    operators = [
        {"operator_code": "O-001", "operator_name": "Demo Operator 1"},
        {"operator_code": "O-002", "operator_name": "Relief Operator 2"},
        {"operator_code": "O-003", "operator_name": "Evening Operator 3"},
        {"operator_code": "DRV001", "operator_name": "Demo Driver 1"},
        {"operator_code": "DRV002", "operator_name": "Relief Driver 2"},
        {"operator_code": "DRV003", "operator_name": "Evening Driver 3"},
        {"operator_code": "DRV004", "operator_name": "Feeder Driver 4"},
    ]

    trips = [
        # ── Bus 1 (WB04-DEMO-001): Route SD5 (Sonarpur <-> Kharibaria, 29.45 km) ───────────
        {
            "trip_id": "42c1eb19-f580-49e4-a052-1eba1b478e60",
            "service_id": "1fc2351a-2902-570c-a664-632414aa46ac",
            "service_code": "SD5",
            "route_id": "fefc79a0-69ed-5092-bc0c-ff88e45e3c6c",
            "route_code": "SD5",
            "vehicle_id": "8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e",
            "vehicle_number": "WB04-DEMO-001",
            "operator_code": "O-001",
            "direction": "A_TO_B",
            "planned_start": f"{service_date}T05:30:00+05:30",
            "planned_end": f"{service_date}T06:35:00+05:30",
        },
        {
            "trip_id": "42c1eb19-f580-49e4-a052-1eba1b478e61",
            "service_id": "1fc2351a-2902-570c-a664-632414aa46ac",
            "service_code": "SD5",
            "route_id": "fefc79a0-69ed-5092-bc0c-ff88e45e3c6c",
            "route_code": "SD5",
            "vehicle_id": "8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e",
            "vehicle_number": "WB04-DEMO-001",
            "operator_code": "O-002",
            "direction": "B_TO_A",
            "planned_start": f"{service_date}T06:50:00+05:30",
            "planned_end": f"{service_date}T07:55:00+05:30",
        },
        {
            "trip_id": "42c1eb19-f580-49e4-a052-1eba1b478e62",
            "service_id": "1fc2351a-2902-570c-a664-632414aa46ac",
            "service_code": "SD5",
            "route_id": "fefc79a0-69ed-5092-bc0c-ff88e45e3c6c",
            "route_code": "SD5",
            "vehicle_id": "8360c3dd-1995-4c69-bce6-5e1d9f4c8e6e",
            "vehicle_number": "WB04-DEMO-001",
            "operator_code": "O-003",
            "direction": "A_TO_B",
            "planned_start": f"{service_date}T08:15:00+05:30",
            "planned_end": f"{service_date}T09:20:00+05:30",
        },
        # ── Bus 2 (PNB005234): Route R1 (City Center <-> Tech Park, 5.2 km) ──────────────
        {
            "trip_id": "90000000-0000-0000-0000-000000000001",
            "service_id": "40000000-0000-0000-0000-000000000001",
            "service_code": "AC4B",
            "route_id": "20000000-0000-0000-0000-000000000001",
            "route_code": "R1",
            "vehicle_id": "50000000-0000-0000-0000-000000000001",
            "vehicle_number": "PNB005234",
            "operator_code": "DRV001",
            "direction": "A_TO_B",
            "planned_start": f"{service_date}T06:00:00+05:30",
            "planned_end": f"{service_date}T06:25:00+05:30",
        },
        {
            "trip_id": "90000000-0000-0000-0000-000000000011",
            "service_id": "40000000-0000-0000-0000-000000000001",
            "service_code": "AC4B",
            "route_id": "20000000-0000-0000-0000-000000000001",
            "route_code": "R1",
            "vehicle_id": "50000000-0000-0000-0000-000000000001",
            "vehicle_number": "PNB005234",
            "operator_code": "DRV002",
            "direction": "B_TO_A",
            "planned_start": f"{service_date}T06:35:00+05:30",
            "planned_end": f"{service_date}T07:00:00+05:30",
        },
        # ── Bus 3 (PNB005781): Route R1 (Staggered AC4B Headway) ──────────────────────────
        {
            "trip_id": "90000000-0000-0000-0000-000000000002",
            "service_id": "40000000-0000-0000-0000-000000000001",
            "service_code": "AC4B",
            "route_id": "20000000-0000-0000-0000-000000000001",
            "route_code": "R1",
            "vehicle_id": "50000000-0000-0000-0000-000000000002",
            "vehicle_number": "PNB005781",
            "operator_code": "DRV003",
            "direction": "A_TO_B",
            "planned_start": f"{service_date}T06:15:00+05:30",
            "planned_end": f"{service_date}T06:40:00+05:30",
        },
        # ── Bus 4 (PNB006421): Route R2 (Airport Shuttle, 4.8 km) ─────────────────────────
        {
            "trip_id": "90000000-0000-0000-0000-000000000003",
            "service_id": "40000000-0000-0000-0000-000000000002",
            "service_code": "SD5-SHUTTLE",
            "route_id": "20000000-0000-0000-0000-000000000002",
            "route_code": "R2",
            "vehicle_id": "50000000-0000-0000-0000-000000000003",
            "vehicle_number": "PNB006421",
            "operator_code": "DRV004",
            "direction": "A_TO_B",
            "planned_start": f"{service_date}T06:30:00+05:30",
            "planned_end": f"{service_date}T06:55:00+05:30",
        },
    ]

    return ServiceDayManifest(
        service_date=service_date,
        timezone="Asia/Kolkata",
        vehicles=vehicles,
        operators=operators,
        trips=trips,
        metadata={
            "description": "GoBus Transit Platform — Kolkata Full-Fleet Demonstration Manifest",
            "generated_by": "Phase 5B Service Day Engine",
        },
    )
