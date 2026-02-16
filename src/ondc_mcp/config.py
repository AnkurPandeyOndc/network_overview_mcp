"""Application configuration via environment variables."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Individual DB connection variables (preferred)
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "ondc_analytics"
    database_user: str = "ondc"
    database_password: str = "ondc_secret"
    database_schema: str = "opendata_nodata"

    # Composite URL — auto-built from individual vars if not set explicitly
    database_url: str = ""

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url:
            self.database_url = (
                f"postgresql://{self.database_user}:{self.database_password}"
                f"@{self.database_host}:{self.database_port}/{self.database_name}"
            )
        return self

    transport: str = "stdio"  # "stdio" or "http"
    host: str = "0.0.0.0"
    port: int = 8000

    max_query_rows: int = 1000
    query_timeout_seconds: int = 30

    log_level: str = "INFO"
    audit_log_path: str = "logs/audit.jsonl"

    # Rate limiting
    rate_limit_per_minute: int = 30

    # Security monitoring
    security_monitor_enabled: bool = True
    security_alert_log_path: str = "logs/security_alerts.jsonl"

    schema_config_path: str = str(
        Path(__file__).resolve().parent.parent.parent / "schema" / "tables.yaml"
    )

    # Cache TTLs in seconds
    cache_query_ttl: int = 300  # 5 minutes
    cache_schema_ttl: int = 3600  # 1 hour

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
