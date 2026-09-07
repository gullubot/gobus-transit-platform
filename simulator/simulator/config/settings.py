"""
Transit Platform — Simulator Configuration.

Loads environment variables, validates settings, and provides multi-operator support
without storing passwords in plain representations or logs.
"""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import List, Optional


def _load_env_file(env_path: Path) -> None:
    """Lightweight fallback .env loader when python-dotenv is not installed."""
    if not env_path.is_file():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = val


# Attempt to load .env from current directory or simulator root
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    _load_env_file(Path.cwd() / ".env")
    _load_env_file(Path(__file__).resolve().parent.parent.parent / ".env")


@dataclass
class OperatorCredentials:
    """Credentials for a single simulated bus operator."""
    employee_code: str
    password: str
    name: Optional[str] = None
    direction: Optional[str] = "A_TO_B"

    def __repr__(self) -> str:
        return f"OperatorCredentials(employee_code={self.employee_code!r}, password='***', direction={self.direction!r})"


@dataclass
class Settings:
    """Global configuration settings for the GoBus Simulator."""
    backend_url: str = field(
        default_factory=lambda: os.getenv("GOBUS_BACKEND_URL", "http://localhost:8000").rstrip("/")
    )
    operator_employee_code: str = field(
        default_factory=lambda: os.getenv("GOBUS_OPERATOR_EMPLOYEE_CODE", "")
    )
    operator_password: str = field(
        default_factory=lambda: os.getenv("GOBUS_OPERATOR_PASSWORD", "")
    )
    request_timeout: float = field(
        default_factory=lambda: float(os.getenv("GOBUS_REQUEST_TIMEOUT", "10.0"))
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("GOBUS_LOG_LEVEL", "INFO").upper()
    )
    operators_file: Optional[str] = field(
        default_factory=lambda: os.getenv("GOBUS_OPERATORS_CONFIG")
    )
    operators: List[OperatorCredentials] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Normalize backend url
        self.backend_url = self.backend_url.rstrip("/")
        if not self.backend_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid backend URL: {self.backend_url}. Must start with http:// or https://")

        if self.request_timeout <= 0:
            raise ValueError(f"Request timeout must be greater than 0, got {self.request_timeout}")

        # Populate operator list
        if self.operators_file and os.path.exists(self.operators_file):
            try:
                with open(self.operators_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.operators = [
                            OperatorCredentials(
                                employee_code=item.get("employee_code", ""),
                                password=item.get("password", ""),
                                name=item.get("name"),
                                direction=item.get("direction", "A_TO_B"),
                            )
                            for item in data
                            if item.get("employee_code") and item.get("password")
                        ]
            except Exception as e:
                import logging
                logging.getLogger("simulator").warning(f"Failed to load operators file {self.operators_file}: {e}")

        # Fallback to single operator from environment if operators list is empty
        if not self.operators and self.operator_employee_code and self.operator_password:
            self.operators = [
                OperatorCredentials(
                    employee_code=self.operator_employee_code,
                    password=self.operator_password,
                    name="Default Operator",
                    direction="A_TO_B",
                )
            ]

    def get_primary_operator(self) -> Optional[OperatorCredentials]:
        """Returns the primary operator credentials."""
        if self.operators:
            return self.operators[0]
        if self.operator_employee_code and self.operator_password:
            return OperatorCredentials(
                employee_code=self.operator_employee_code,
                password=self.operator_password,
            )
        return None

    def __repr__(self) -> str:
        return (
            f"Settings(backend_url={self.backend_url!r}, "
            f"request_timeout={self.request_timeout}, "
            f"log_level={self.log_level!r}, "
            f"operators_count={len(self.operators)})"
        )


_settings_instance: Optional[Settings] = None


def get_settings(reload: bool = False) -> Settings:
    """Returns a singleton or refreshed instance of Settings."""
    global _settings_instance
    if _settings_instance is None or reload:
        _settings_instance = Settings()
    return _settings_instance
