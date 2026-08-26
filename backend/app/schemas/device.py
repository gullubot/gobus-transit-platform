"""
Transit Platform — Device Schemas.

BUILD 2: Device validation and representation schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceResponse(BaseModel):
    """Device representation."""

    id: uuid.UUID
    device_name: str
    platform: str
    status: str
    organization_id: uuid.UUID
    last_seen_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
