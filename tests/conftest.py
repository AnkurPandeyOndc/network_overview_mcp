"""Test fixtures and configuration."""

import os
from pathlib import Path

import pytest

from ondc_mcp.db.schema_registry import SchemaRegistry
from ondc_mcp.validation.sql_validator import SQLValidator


@pytest.fixture
def schema_registry():
    """Schema registry loaded from the project's tables.yaml."""
    config_path = str(Path(__file__).parent.parent / "schema" / "tables.yaml")
    reg = SchemaRegistry(config_path=config_path)
    reg.load()
    return reg


@pytest.fixture
def sql_validator(schema_registry):
    """SQL validator with test schema registry."""
    return SQLValidator(schema_registry=schema_registry)
