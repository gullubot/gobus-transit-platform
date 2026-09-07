"""
Transit Platform — Safe HTTP Client.

Persistent requests.Session wrapper with configurable base URL, timeout,
exception normalization, and strict zero-credential logging.
"""

from typing import Any, Dict, Optional
import requests
from urllib.parse import urljoin

from simulator.core.exceptions import (
    AccountForbiddenError,
    AssignmentNotFoundError,
    AuthenticationError,
    BackendUnavailableError,
    InvalidPayloadError,
    RateLimitExceededError,
    SimulatorError,
    TripSessionError,
)
from simulator.utils.logging import get_logger

logger = get_logger("http")


class GoBusHttpClient:
    """Thread-safe persistent HTTP client for GoBus backend communication."""

    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GoBus-Simulator/1.0",
            "Accept": "application/json",
        })

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        path = path.lstrip("/")
        return f"{self.base_url}/{path}"

    def check_health(self) -> Dict[str, Any]:
        """Verifies backend reachability via GET /api/health."""
        try:
            url = self._build_url("/api/health")
            response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 404:
                url = self._build_url("/health")
                response = self.session.get(url, timeout=self.timeout)
            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    return {"status": "ok", "raw": response.text}
            raise SimulatorError(
                f"Health check failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Backend unreachable at {self.base_url}: {e}")
            raise BackendUnavailableError(f"Cannot connect to GoBus backend at {self.base_url}: {e}")

    def get(
        self,
        path: str,
        token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Performs an authenticated GET request with error handling."""
        return self._request("GET", path, token=token, headers=headers, params=params)

    def post(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Performs an authenticated POST request with error handling."""
        return self._request("POST", path, json_data=json_data, token=token, headers=headers)

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self._build_url(path)
        req_headers = dict(headers or {})
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        if json_data is not None:
            req_headers["Content-Type"] = "application/json"

        try:
            logger.debug(f"{method} {url}")
            response = self.session.request(
                method=method,
                url=url,
                json=json_data,
                headers=req_headers,
                params=params,
                timeout=self.timeout,
            )
            return self._handle_response(response)
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout for {method} {url}")
            raise BackendUnavailableError(f"Request to {url} timed out after {self.timeout}s: {e}")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error for {method} {url}")
            raise BackendUnavailableError(f"Could not connect to {url}: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed for {method} {url}: {e}")
            raise SimulatorError(f"HTTP error for {url}: {e}")

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Normalizes HTTP status codes into domain-specific exceptions."""
        status = response.status_code

        # Attempt to extract error detail from JSON
        detail = ""
        body_json = None
        try:
            body_json = response.json()
            if isinstance(body_json, dict):
                detail = body_json.get("detail", "")
        except Exception:
            detail = response.text

        if 200 <= status < 300:
            if body_json is not None:
                return body_json
            return {"status": "ok", "raw": response.text}

        logger.warning(f"HTTP {status}: {detail or response.reason}")

        if status == 401:
            raise AuthenticationError(detail or "Invalid credentials or token expired", status_code=status, details=body_json)
        elif status == 403:
            raise AccountForbiddenError(detail or "Access forbidden for this account/role", status_code=status, details=body_json)
        elif status == 404:
            raise AssignmentNotFoundError(detail or "Resource or assignment not found", status_code=status, details=body_json)
        elif status == 422:
            raise InvalidPayloadError(f"Validation error: {detail}", status_code=status, details=body_json)
        elif status == 429:
            raise RateLimitExceededError(detail or "Rate limit exceeded", status_code=status, details=body_json)
        elif status == 400:
            raise TripSessionError(detail or "Bad request", status_code=status, details=body_json)
        else:
            raise SimulatorError(f"HTTP {status}: {detail or response.reason}", status_code=status, details=body_json)

    def close(self) -> None:
        """Closes the underlying requests session."""
        self.session.close()
