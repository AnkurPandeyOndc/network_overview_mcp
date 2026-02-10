"""Role-based table access control."""

from ondc_mcp.db.schema_registry import SchemaRegistry, registry as default_registry


class RoleAccess:
    """Check whether a role can access specific tables."""

    def __init__(self, schema_registry: SchemaRegistry | None = None):
        self.registry = schema_registry or default_registry

    def get_allowed_tables(self, role: str) -> list[str]:
        """Return list of table names accessible by the given role."""
        roles = self.registry.roles
        role_config = roles.get(role)
        if role_config is None:
            # Default: all tables
            return self.registry.get_table_names()
        return role_config.get("allowed_tables", [])

    def can_access_table(self, role: str, table_name: str) -> bool:
        allowed = self.get_allowed_tables(role)
        return table_name in allowed

    def check_tables(self, role: str, table_names: list[str]) -> list[str]:
        """Return list of tables the role is NOT allowed to access."""
        allowed = set(self.get_allowed_tables(role))
        return [t for t in table_names if t not in allowed]


# Module-level singleton
role_access = RoleAccess()
