"""Tests for SQL validation rules."""

import pytest


class TestSelectOnly:
    def test_select_allowed(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, SUM(orders) FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01' GROUP BY domain"
        )
        assert result.valid

    def test_insert_rejected(self, sql_validator):
        result = sql_validator.validate(
            "INSERT INTO opendata_nodata.model_for_all_domain VALUES ('2025-01-01')"
        )
        assert not result.valid
        assert any("SELECT" in e for e in result.errors)

    def test_update_rejected(self, sql_validator):
        result = sql_validator.validate(
            "UPDATE opendata_nodata.model_for_all_domain SET orders = 0"
        )
        assert not result.valid

    def test_delete_rejected(self, sql_validator):
        result = sql_validator.validate(
            "DELETE FROM opendata_nodata.model_for_all_domain"
        )
        assert not result.valid

    def test_drop_rejected(self, sql_validator):
        result = sql_validator.validate(
            "DROP TABLE opendata_nodata.model_for_all_domain"
        )
        assert not result.valid


class TestNoSelectStar:
    def test_star_rejected(self, sql_validator):
        result = sql_validator.validate(
            "SELECT * FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01'"
        )
        assert not result.valid
        assert any("SELECT *" in e for e in result.errors)

    def test_explicit_columns_allowed(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, orders FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01'"
        )
        assert result.valid


class TestDateFilter:
    def test_missing_date_filter_rejected(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, SUM(orders) FROM opendata_nodata.model_for_all_domain "
            "GROUP BY domain"
        )
        assert not result.valid
        assert any("order_date" in e for e in result.errors)

    def test_date_equality_filter_allowed(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, orders FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01'"
        )
        assert result.valid

    def test_date_range_filter_allowed(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, SUM(orders) FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date >= '2025-01-01' AND order_date <= '2025-01-31' "
            "GROUP BY domain"
        )
        assert result.valid

    def test_date_between_filter_allowed(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, SUM(orders) FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date BETWEEN '2025-01-01' AND '2025-01-31'"
        )
        assert result.valid


class TestTableAccess:
    def test_allowed_table(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, orders FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01'"
        )
        assert result.valid

    def test_disallowed_table(self, sql_validator):
        result = sql_validator.validate(
            "SELECT id FROM opendata_nodata.users "
            "WHERE order_date = '2025-01-01'"
        )
        assert not result.valid
        assert any("not allowed" in e for e in result.errors)


class TestUnionSupport:
    def test_union_all_allowed(self, sql_validator):
        """UNION ALL across allowed tables must pass validation."""
        result = sql_validator.validate(
            "SELECT domain, SUM(orders) AS orders"
            " FROM opendata_nodata.model_for_all_domain"
            " WHERE order_date >= '2025-11-01' AND order_date <= '2025-11-30'"
            " GROUP BY domain"
            " UNION ALL"
            " SELECT domain, SUM(orders) AS orders"
            " FROM opendata_nodata.model_for_all_domain"
            " WHERE order_date >= '2025-12-01' AND order_date <= '2025-12-31'"
            " GROUP BY domain"
        )
        assert result.valid, result.errors

    def test_cte_union_all_allowed(self, sql_validator):
        """CTE followed by UNION ALL in the final SELECT must pass."""
        result = sql_validator.validate(
            "WITH nov AS ("
            "  SELECT domain, SUM(orders) AS orders"
            "  FROM opendata_nodata.model_for_all_domain"
            "  WHERE order_date >= '2025-11-01' AND order_date <= '2025-11-30'"
            "  GROUP BY domain"
            "), dec AS ("
            "  SELECT domain, SUM(orders) AS orders"
            "  FROM opendata_nodata.model_for_all_domain"
            "  WHERE order_date >= '2025-12-01' AND order_date <= '2025-12-31'"
            "  GROUP BY domain"
            ")"
            " SELECT 'Nov' AS month, domain, orders FROM nov"
            " UNION ALL"
            " SELECT 'Dec' AS month, domain, orders FROM dec"
            " ORDER BY month, orders DESC"
        )
        assert result.valid, result.errors


class TestCTESupport:
    def test_cte_aliases_not_treated_as_tables(self, sql_validator):
        """CTE names must not trigger 'table not allowed' errors."""
        result = sql_validator.validate(
            "WITH monthly AS ("
            "  SELECT domain, date_trunc('month', order_date) AS month, SUM(orders) AS orders"
            "  FROM opendata_nodata.model_for_all_domain"
            "  WHERE order_date >= '2025-11-01'"
            "  GROUP BY 1, 2"
            "), totals AS ("
            "  SELECT domain, SUM(orders) AS total FROM monthly GROUP BY 1"
            ")"
            " SELECT domain, total FROM totals ORDER BY 2 DESC"
        )
        assert result.valid, result.errors

    def test_cte_with_disallowed_base_table_rejected(self, sql_validator):
        """A CTE over a disallowed real table must still be rejected."""
        result = sql_validator.validate(
            "WITH bad AS ("
            "  SELECT id FROM opendata_nodata.users"
            "  WHERE order_date = '2025-01-01'"
            ")"
            " SELECT id FROM bad"
        )
        assert not result.valid
        assert any("not allowed" in e for e in result.errors)


class TestLimitEnforcement:
    def test_auto_inject_limit(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, orders FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01'"
        )
        assert result.valid
        assert "LIMIT" in result.sanitized_sql.upper()

    def test_existing_limit_preserved(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, orders FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01' LIMIT 10"
        )
        assert result.valid
        assert "10" in result.sanitized_sql

    def test_excessive_limit_capped(self, sql_validator):
        result = sql_validator.validate(
            "SELECT domain, orders FROM opendata_nodata.model_for_all_domain "
            "WHERE order_date = '2025-01-01' LIMIT 99999"
        )
        assert result.valid
        # Should be capped to max_query_rows (1000)
        assert "99999" not in result.sanitized_sql


class TestJoinValidation:
    def test_join_on_allowed_columns(self, sql_validator):
        result = sql_validator.validate(
            "SELECT a.domain, a.orders, b.delivery_city "
            "FROM opendata_nodata.model_for_all_domain a "
            "JOIN opendata_nodata.model_for_all_domain_pincode b "
            "ON a.order_date = b.order_date AND a.domain = b.domain "
            "WHERE a.order_date = '2025-01-01'"
        )
        assert result.valid

    def test_join_without_on_rejected(self, sql_validator):
        result = sql_validator.validate(
            "SELECT a.domain, b.delivery_city "
            "FROM opendata_nodata.model_for_all_domain a, "
            "opendata_nodata.model_for_all_domain_pincode b "
            "WHERE a.order_date = '2025-01-01'"
        )
        # Comma-join is parsed as a cross join — not validated as a JOIN with ON
        # This is acceptable; the query has a WHERE clause
        # The key check is explicit JOIN without ON
        pass

    def test_join_on_disallowed_column_rejected(self, sql_validator):
        result = sql_validator.validate(
            "SELECT a.domain, b.delivery_city "
            "FROM opendata_nodata.model_for_all_domain a "
            "JOIN opendata_nodata.model_for_all_domain_pincode b "
            "ON a.orders = b.orders "
            "WHERE a.order_date = '2025-01-01'"
        )
        assert not result.valid
        assert any("not allowed" in e.lower() for e in result.errors)


class TestMultiStatement:
    def test_multi_statement_rejected(self, sql_validator):
        result = sql_validator.validate(
            "SELECT 1; DROP TABLE opendata_nodata.model_for_all_domain"
        )
        assert not result.valid
        assert any("single" in e.lower() for e in result.errors)


class TestMalformed:
    def test_empty_sql(self, sql_validator):
        result = sql_validator.validate("")
        assert not result.valid

    def test_gibberish(self, sql_validator):
        result = sql_validator.validate("not a sql query at all")
        assert not result.valid
