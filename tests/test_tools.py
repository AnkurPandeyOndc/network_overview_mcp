"""Tests for MCP tools (unit-level, no DB required)."""

import pytest

from ondc_mcp.tools.rag_tool import search_docs
from ondc_mcp.db.schema_registry import SchemaRegistry
from ondc_mcp.security.role_access import RoleAccess


class TestSchemaRegistry:
    def test_load_tables(self, schema_registry):
        tables = schema_registry.get_table_names()
        assert "model_for_all_domain" in tables
        assert "model_for_all_domain_pincode" in tables

    def test_schema_name(self, schema_registry):
        assert schema_registry.schema_name == "opendata_nodata"

    def test_domain_categories(self, schema_registry):
        dc = schema_registry.domain_categories
        assert "Retail B2C" in dc
        assert "Grocery" in dc["Retail B2C"]

    def test_np_types(self, schema_registry):
        assert "Inter NP" in schema_registry.np_types
        assert "Intra NP" in schema_registry.np_types

    def test_date_column(self, schema_registry):
        assert schema_registry.get_date_column("model_for_all_domain") == "order_date"

    def test_require_date_filter(self, schema_registry):
        assert schema_registry.requires_date_filter("model_for_all_domain")

    def test_allowed_join_columns(self, schema_registry):
        cols = schema_registry.get_allowed_join_columns("model_for_all_domain")
        assert "order_date" in cols
        assert "domain" in cols

    def test_get_schema_description(self, schema_registry):
        desc = schema_registry.get_schema_description()
        assert desc["schema"] == "opendata_nodata"
        assert "model_for_all_domain" in desc["tables"]
        assert "domain_categories" in desc
        assert "np_types" in desc

    def test_full_table_name(self, schema_registry):
        assert (
            schema_registry.get_full_table_name("model_for_all_domain")
            == "opendata_nodata.model_for_all_domain"
        )


class TestRoleAccess:
    def test_analyst_has_both_tables(self, schema_registry):
        ra = RoleAccess(schema_registry=schema_registry)
        tables = ra.get_allowed_tables("analyst")
        assert "model_for_all_domain" in tables
        assert "model_for_all_domain_pincode" in tables

    def test_viewer_has_one_table(self, schema_registry):
        ra = RoleAccess(schema_registry=schema_registry)
        tables = ra.get_allowed_tables("viewer")
        assert "model_for_all_domain" in tables
        assert "model_for_all_domain_pincode" not in tables

    def test_unknown_role_gets_all_tables(self, schema_registry):
        ra = RoleAccess(schema_registry=schema_registry)
        tables = ra.get_allowed_tables("unknown_role")
        assert len(tables) == 2

    def test_check_denied_tables(self, schema_registry):
        ra = RoleAccess(schema_registry=schema_registry)
        denied = ra.check_tables("viewer", ["model_for_all_domain_pincode"])
        assert "model_for_all_domain_pincode" in denied

    def test_check_allowed_tables(self, schema_registry):
        ra = RoleAccess(schema_registry=schema_registry)
        denied = ra.check_tables("analyst", ["model_for_all_domain"])
        assert len(denied) == 0


class TestSearchDocs:
    @pytest.mark.asyncio
    async def test_search_docs_skeleton(self):
        result = await search_docs("test query")
        assert result["status"] == "success"
        assert result["results"] == []
        assert "No documents indexed" in result["message"]
