"""
Transit Platform — Application Configuration.

Loads settings from environment variables / .env file.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Application
    app_env: str = "development"
    app_name: str = "transit-backend"
    app_version: str = "0.1.0"

    # Database
    database_url: str = "postgresql://transit:transit_dev_password@localhost:5432/transit_platform"

    # Security
    jwt_secret: str = "transit_dev_jwt_secret_key_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours for daily shift

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.app_env != "development" and self.jwt_secret == "transit_dev_jwt_secret_key_change_in_production":
            raise ValueError("JWT_SECRET must be explicitly set for production/demo environments. Do not use the development fallback.")

    # Routing Provider
    routing_provider: str = "osrm"
    osrm_base_url: str = "https://router.project-osrm.org"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
