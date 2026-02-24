"""Load and expose table metadata from tables.yaml."""

from pathlib import Path
from typing import Any

import yaml

from ondc_mcp.config import settings


class SchemaRegistry:
    """Loads tables.yaml and provides metadata lookups."""

    def __init__(self, config_path: str | None = None):
        self._config_path = config_path or settings.schema_config_path
        self._data: dict[str, Any] = {}
        self._loaded = False

    def load(self) -> None:
        path = Path(self._config_path)
        with open(path) as f:
            self._data = yaml.safe_load(f)
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @property
    def schema_name(self) -> str:
        self._ensure_loaded()
        return self._data["schema"]

    @property
    def tables(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._data.get("tables", {})

    @property
    def domain_categories(self) -> dict[str, list[str]]:
        self._ensure_loaded()
        return self._data.get("domain_categories", {})

    @property
    def np_types(self) -> list[str]:
        self._ensure_loaded()
        return self._data.get("np_types", [])

    @property
    def roles(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._data.get("roles", {})

    def get_table_names(self) -> list[str]:
        return list(self.tables.keys())

    def get_table_info(self, table_name: str) -> dict[str, Any] | None:
        return self.tables.get(table_name)

    def get_allowed_join_columns(self, table_name: str) -> list[str]:
        info = self.get_table_info(table_name)
        if info is None:
            return []
        return info.get("allowed_join_columns", [])

    def requires_date_filter(self, table_name: str) -> bool:
        info = self.get_table_info(table_name)
        if info is None:
            return False
        return info.get("require_date_filter", False)

    def role_unrestricted_select(self, role: str) -> bool:
        """Return True if the role may run any SELECT without shape restrictions."""
        return self.roles.get(role, {}).get("unrestricted_select", False)

    def get_date_column(self, table_name: str) -> str | None:
        info = self.get_table_info(table_name)
        if info is None:
            return None
        return info.get("date_column")

    def get_full_table_name(self, table_name: str) -> str:
        return f"{self.schema_name}.{table_name}"

    def get_schema_description(self) -> dict[str, Any]:
        """Return full schema info suitable for LLM context."""
        self._ensure_loaded()
        result = {
            "schema": self.schema_name,
            "tables": {},
            "domain_categories": self.domain_categories,
            "np_types": self.np_types,
        }
        for name, info in self.tables.items():
            result["tables"][name] = {
                "description": info["description"],
                "columns": info["columns"],
                "date_column": info.get("date_column"),
                "require_date_filter": info.get("require_date_filter", False),
            }
        return result


# Module-level singleton
registry = SchemaRegistry()
