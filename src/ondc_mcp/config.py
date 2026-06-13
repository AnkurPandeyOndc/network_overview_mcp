"""Application configuration via environment variables."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "prod"

    # Production DB connection variables
    prod_db_host: str = ""
    prod_db_port: int = 5432
    prod_db_database: str = ""
    prod_db_user: str = ""
    prod_db_password: str = ""

    # Staging DB connection variables
    stage_db_host: str = ""
    stage_db_port: int = 5432
    stage_db_database: str = ""
    stage_db_user: str = ""
    stage_db_password: str = ""

    # Composite URL — auto-built from individual vars if not set explicitly
    database_url: str = ""

    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if not self.database_url:
            if self.app_env.lower() == "stage":
                self.database_url = (
                    f"postgresql://{self.stage_db_user}:{self.stage_db_password}"
                    f"@{self.stage_db_host}:{self.stage_db_port}/{self.stage_db_database}"
                )
            else:
                self.database_url = (
                    f"postgresql://{self.prod_db_user}:{self.prod_db_password}"
                    f"@{self.prod_db_host}:{self.prod_db_port}/{self.prod_db_database}"
                )
        return self

    transport: str = "stdio"  # "stdio" or "http"
    host: str = "0.0.0.0"
    port: int = 8000

    max_query_rows: int = 1000
    query_timeout_seconds: int = 600

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
