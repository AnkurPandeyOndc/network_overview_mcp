"""SQL AST validation using sqlglot.

Enforces:
- Only SELECT statements
- No SELECT *
- Required date filter on order_date
- LIMIT enforcement (auto-inject if missing)
- Only allowed tables and schema
- Join validation (ON clause required, only allowed columns)
- No Cartesian joins
"""

from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

from ondc_mcp.db.schema_registry import SchemaRegistry, registry as default_registry


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    sanitized_sql: str = ""


class SQLValidator:
    def __init__(self, schema_registry: SchemaRegistry | None = None):
        self.registry = schema_registry or default_registry

    def validate(self, sql: str, role: str = "") -> ValidationResult:
        errors: list[str] = []
        unrestricted = self.registry.role_unrestricted_select(role)

        # Parse
        try:
            parsed = sqlglot.parse(sql, dialect="postgres")
        except sqlglot.errors.ParseError as e:
            return ValidationResult(valid=False, errors=[f"SQL parse error: {e}"])

        if not parsed:
            return ValidationResult(valid=False, errors=["Empty SQL statement"])

        # Only single statement allowed (skipped for unrestricted roles)
        if not unrestricted and len(parsed) > 1:
            errors.append("Only single SQL statements are allowed")
            return ValidationResult(valid=False, errors=errors)

        # Rule: Only SELECT — always enforced regardless of role
        for stmt in parsed:
            if not isinstance(stmt, (exp.Select, exp.Union)):
                errors.append(
                    f"Only SELECT statements are allowed, got: {type(stmt).__name__}"
                )
        if errors:
            return ValidationResult(valid=False, errors=errors)

        # Unrestricted roles: multi-statement passes through as-is (no further checks)
        if unrestricted and len(parsed) > 1:
            return ValidationResult(valid=True, errors=[], sanitized_sql=sql)

        statement = parsed[0]

        # Remaining rules skipped entirely for unrestricted roles
        if not unrestricted:
            tables_found = self._extract_tables(statement)
            self._check_allowed_tables(tables_found, errors)
            self._check_no_star(statement, errors)
            self._check_date_filter(statement, tables_found, errors)
            self._check_joins(statement, errors)

        if errors:
            return ValidationResult(valid=False, errors=errors)

        # Auto-inject LIMIT if missing
        sanitized = self._ensure_limit(statement)

        return ValidationResult(
            valid=True,
            errors=[],
            sanitized_sql=sanitized.sql(dialect="postgres"),
        )

    def _check_no_star(self, stmt: exp.Select, errors: list[str]) -> None:
        for select_expr in stmt.find_all(exp.Star):
            errors.append(
                "SELECT * is not allowed. Please specify explicit column names."
            )
            return

    def _extract_tables(self, stmt: exp.Select) -> list[str]:
        """Extract bare table names from the query, excluding CTE aliases."""
        # CTE names (e.g. monthly_orders, pivoted) are referenced as exp.Table
        # nodes in the main query body but are not real tables — exclude them.
        cte_names = {cte.alias for cte in stmt.find_all(exp.CTE)}
        return [
            table.name
            for table in stmt.find_all(exp.Table)
            if table.name not in cte_names
        ]

    def _check_allowed_tables(
        self, tables: list[str], errors: list[str]
    ) -> None:
        allowed = set(self.registry.get_table_names())
        schema_name = self.registry.schema_name

        for table_node in tables:
            bare_name = table_node
            if bare_name not in allowed:
                errors.append(
                    f"Table '{bare_name}' is not allowed. "
                    f"Allowed tables: {', '.join(sorted(allowed))}"
                )

    def _check_date_filter(
        self,
        stmt: exp.Select,
        tables: list[str],
        errors: list[str],
    ) -> None:
        """Ensure all tables that require date filters have order_date in WHERE."""
        tables_needing_date = set()
        for t in tables:
            if self.registry.requires_date_filter(t):
                tables_needing_date.add(t)

        if not tables_needing_date:
            return

        # Check if WHERE clause references order_date
        where = stmt.find(exp.Where)
        if where is None:
            errors.append(
                "A WHERE clause with an order_date filter is required for: "
                + ", ".join(sorted(tables_needing_date))
            )
            return

        date_columns_referenced = set()
        for col in where.find_all(exp.Column):
            if col.name == "order_date":
                date_columns_referenced.add("order_date")

        if "order_date" not in date_columns_referenced:
            errors.append(
                "WHERE clause must include a filter on 'order_date'. "
                "This is required for tables: "
                + ", ".join(sorted(tables_needing_date))
            )

    def _check_joins(self, stmt: exp.Select, errors: list[str]) -> None:
        """Check join conditions: ON clause required, allowed columns only."""
        for join in stmt.find_all(exp.Join):
            on_clause = join.args.get("on")
            if on_clause is None:
                errors.append(
                    "All JOINs must have an ON clause. Cartesian joins are not allowed."
                )
                continue

            # Check join columns against allowed list
            join_columns = set()
            for col in on_clause.find_all(exp.Column):
                join_columns.add(col.name)

            # Get all tables in the query and their allowed join columns
            all_allowed_join_cols = set()
            for table in stmt.find_all(exp.Table):
                allowed = self.registry.get_allowed_join_columns(table.name)
                all_allowed_join_cols.update(allowed)

            if all_allowed_join_cols:
                disallowed = join_columns - all_allowed_join_cols
                if disallowed:
                    errors.append(
                        f"Join on columns {disallowed} is not allowed. "
                        f"Allowed join columns: {sorted(all_allowed_join_cols)}"
                    )

    def _ensure_limit(self, stmt: exp.Select) -> exp.Select:
        """Inject LIMIT if not present."""
        max_rows = self.registry._data.get("max_rows", None)
        from ondc_mcp.config import settings
        limit_val = max_rows or settings.max_query_rows

        existing_limit = stmt.find(exp.Limit)
        if existing_limit is None:
            stmt = stmt.limit(limit_val)
        else:
            # Enforce max even if user specified a higher limit
            limit_expr = existing_limit.args.get("expression")
            if limit_expr and isinstance(limit_expr, exp.Literal):
                try:
                    user_limit = int(limit_expr.this)
                    if user_limit > limit_val:
                        existing_limit.args["expression"] = exp.Literal.number(
                            limit_val
                        )
                except (ValueError, TypeError):
                    pass
        return stmt
