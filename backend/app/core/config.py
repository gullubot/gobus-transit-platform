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

    # Security (placeholder — not implemented in BUILD 0)
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"

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
