import httpx
import uuid
import datetime
from typing import List, Dict, Any, Optional

class SimulatorClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=timeout)
        self.device_id = str(uuid.uuid4()) # Ephemeral device ID for simulator

    def _headers(self) -> Dict[str, str]:
        headers = {"X-Device-Id": self.device_id}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def close(self):
        await self.client.aclose()

    async def login(self, username: str, password: str) -> bool:
        response = await self.client.post(
            f"{self.base_url}/api/auth/operator/login",
            json={"employee_code": username, "password": password},
        )
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            return True
        return False

    async def get_service_route(self, service_id: str) -> Dict[str, Any]:
        """Discovers the route details for a given service."""
        # 1. Get organization ID for Kolkata
        org_resp = await self.client.get(f"{self.base_url}/api/passenger/organizations")
        org_resp.raise_for_status()
        orgs = org_resp.json()
        if not orgs:
            raise ValueError("No organizations found")
        org_id = orgs[0]["id"]
        for o in orgs:
            if "Kolkata" in o["name"]:
                org_id = o["id"]
                break

        # 2. Get service details
        detail_resp = await self.client.get(
            f"{self.base_url}/api/passenger/services/{service_id}?organization_id={org_id}",
            headers=self._headers()
        )
        detail_resp.raise_for_status()
        return detail_resp.json()

    async def get_my_assignment(self) -> Dict[str, Any]:
        """Gets the operator's current active trip assignment."""
        response = await self.client.get(
            f"{self.base_url}/api/operator/me/assignment",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def start_trip(self, trip_id: str) -> Dict[str, Any]:
        """Starts a tracking session for a trip."""
        response = await self.client.post(
            f"{self.base_url}/api/trips/{trip_id}/start",
            headers=self._headers()
        )
        response.raise_for_status()
        return response.json()

    async def end_trip(self, trip_id: str) -> Dict[str, Any]:
        """Ends the tracking session."""
        response = await self.client.post(
            f"{self.base_url}/api/trips/{trip_id}/end",
            headers=self._headers()
        )
        if response.status_code != 200:
            pass # ignore errors on end
        return response.json() if response.status_code == 200 else {}

    async def send_telemetry_batch(self, session_id: str, packets: List[Dict[str, Any]]) -> bool:
        """Sends a batch of telemetry packets."""
        payload = {
            "session_id": session_id,
            "packets": packets
        }
        response = await self.client.post(
            f"{self.base_url}/api/tracking/batch",
            json=payload,
            headers=self._headers()
        )
        return response.status_code == 200

    async def send_crowding_report(self, vehicle_id: str, level: str, observed_at: str) -> bool:
        """Submits a crowding report."""
        payload = {
            "report_id": str(uuid.uuid4()),
            "vehicle_id": vehicle_id,
            "level": level,
            "observed_at": observed_at
        }
        response = await self.client.post(
            f"{self.base_url}/api/crowding/reports",
            json=payload,
            headers=self._headers()
        )
        return response.status_code == 200
