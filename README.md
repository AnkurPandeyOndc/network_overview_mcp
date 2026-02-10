# ONDC Analytics MCP Server

A governed [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that gives LLMs safe, read-only access to ONDC e-commerce analytics data in PostgreSQL.

## What it does

The server exposes **4 MCP tools** that an LLM (Claude, etc.) can call to explore and query ONDC order data:

| Tool | Description |
|------|-------------|
| `get_schema` | Returns table definitions, column types, domain/category mappings, and NP types |
| `get_data_freshness` | Returns the latest `order_date` per table |
| `run_safe_sql` | Validates and executes a read-only SQL query with safety guardrails |
| `search_docs` | Searches indexed ONDC documents (RAG skeleton, no docs indexed yet) |

### SQL safety guardrails

Every query passed to `run_safe_sql` is validated before execution:

- Only `SELECT` statements allowed (no INSERT/UPDATE/DELETE/DROP)
- `SELECT *` is rejected — explicit column names required
- `WHERE` clause with `order_date` filter is mandatory
- `LIMIT` is auto-injected (default 1000) or capped if too high
- Only tables defined in `schema/tables.yaml` are accessible
- JOINs require an `ON` clause on allowed columns only
- Multi-statement queries are rejected
- All queries run in a read-only transaction with a statement timeout

### Role-based access

Two roles are defined in `schema/tables.yaml`:

- **analyst** — access to both tables
- **viewer** — access to `model_for_all_domain` only

## Database schema

Schema: `opendata_nodata`

**`model_for_all_domain`** — Order counts by domain, category, and network participant

| Column | Type | Description |
|--------|------|-------------|
| order_date | date | Order date |
| buyer_np | varchar | Buyer network participant name |
| seller_np | varchar | Seller network participant name |
| category | varchar | Product/service category |
| domain | varchar | Business domain (Retail B2C, Logistics, etc.) |
| np_type | varchar | Network participant type: Inter NP, Intra NP, or null |
| orders | int4 | Number of orders |

**`model_for_all_domain_pincode`** — Order counts by domain and city

| Column | Type | Description |
|--------|------|-------------|
| order_date | date | Order date |
| domain | varchar | Business domain |
| delivery_city | varchar | City where order is delivered |
| seller_city | varchar | City where seller is located |
| orders | int8 | Number of orders |

### Domains

Finance, Home Services, Logistics, Public Transport, Retail B2B, Retail B2C, Retail Voucher, Ride Hailing

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- PostgreSQL (remote or local)
- Redis (optional — can be disabled)

## Setup

```bash
cd ondc-analytics-mcp
poetry install
```

### Configuration

Copy the example env file and fill in your database credentials:

```bash
cp .env.example .env
```

`.env` variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_HOST` | `localhost` | PostgreSQL host |
| `DATABASE_PORT` | `5432` | PostgreSQL port |
| `DATABASE_NAME` | `ondc_analytics` | Database name |
| `DATABASE_USER` | `ondc` | Database user |
| `DATABASE_PASSWORD` | `ondc_secret` | Database password |
| `DATABASE_SCHEMA` | `opendata_nodata` | Schema name |
| `DATABASE_URL` | *(auto-built)* | Full connection URL — set this to override individual vars |
| `REDIS_ENABLED` | `true` | Set to `false` to disable Redis caching entirely |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `TRANSPORT` | `stdio` | Transport mode: `stdio` or `http` |
| `MAX_QUERY_ROWS` | `1000` | Maximum rows returned per query |
| `QUERY_TIMEOUT_SECONDS` | `30` | SQL statement timeout |
| `LOG_LEVEL` | `INFO` | Logging level |
| `AUDIT_LOG_PATH` | `logs/audit.jsonl` | Path to audit log file |

## Running the server

### Option 1: stdio mode (for Claude Desktop / MCP Inspector)

```bash
poetry run python -m ondc_mcp.server
```

Or use the MCP Inspector for interactive testing:

```bash
poetry run mcp dev src/ondc_mcp/server.py
```

### Option 2: HTTP mode (streamable-http on port 8000)

```bash
TRANSPORT=http poetry run python -m ondc_mcp.server
```

### Option 3: Docker Compose (full stack with local Postgres + Redis)

```bash
docker compose up --build
```

This starts:
- PostgreSQL 16 (seeded with sample data via `schema/init.sql`)
- Redis 7
- MCP server on port 8000

To run only Postgres and Redis (and run the server locally):

```bash
docker compose up postgres redis
```

## Connecting to Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ondc-analytics": {
      "command": "poetry",
      "args": ["run", "python", "-m", "ondc_mcp.server"],
      "cwd": "/path/to/ondc-analytics-mcp",
      "env": {
        "DATABASE_HOST": "your-db-host",
        "DATABASE_PORT": "5432",
        "DATABASE_NAME": "your-db-name",
        "DATABASE_USER": "your-db-user",
        "DATABASE_PASSWORD": "your-db-password",
        "REDIS_ENABLED": "false"
      }
    }
  }
}
```

Once connected, Claude will see all 4 tools and can answer analytics questions like:
- "What were the top domains by order count yesterday?"
- "Show me Retail B2C orders by category for the last week"
- "Compare order volumes between Bangalore and Delhi"

## Example queries

**Valid query:**
```sql
SELECT domain, SUM(orders) AS total_orders
FROM opendata_nodata.model_for_all_domain
WHERE order_date = '2026-02-08'
GROUP BY domain
LIMIT 10
```

**Rejected — DROP TABLE:**
```sql
DROP TABLE opendata_nodata.model_for_all_domain
-- Error: "Only SELECT statements are allowed, got: Drop"
```

**Rejected — SELECT \*:**
```sql
SELECT * FROM opendata_nodata.model_for_all_domain WHERE order_date = '2026-02-08'
-- Error: "SELECT * is not allowed. Please specify explicit column names."
```

**Rejected — no date filter:**
```sql
SELECT domain FROM opendata_nodata.model_for_all_domain
-- Error: "A WHERE clause with an order_date filter is required"
```

## Audit logging

Every tool call and SQL query is logged to `logs/audit.jsonl`. Each entry includes:

- `timestamp`
- `user_id`, `role`
- `raw_sql`, `validated_sql`
- `status` (success / rejected)
- `rejection_reasons`
- `execution_time_ms`
- `row_count`

## Running tests

```bash
poetry run pytest tests/ -v
```

37 tests covering SQL validator rules, schema registry, role access, and RAG skeleton. No database or Redis required.

## Project structure

```
ondc-analytics-mcp/
  src/ondc_mcp/
    server.py              # MCP server entry point, tool registration
    config.py              # Environment-based configuration
    db/
      connection.py        # asyncpg connection pool, read-only execution
      schema_registry.py   # Loads table metadata from tables.yaml
    validation/
      sql_validator.py     # SQL AST validation via sqlglot
    security/
      role_access.py       # Role-based table access control
      query_logger.py      # Audit logging
    cache/
      redis_cache.py       # Redis caching with graceful degradation
    tools/
      sql_tool.py          # run_safe_sql implementation
      schema_tool.py       # get_schema implementation
      freshness_tool.py    # get_data_freshness implementation
      rag_tool.py          # search_docs skeleton
    rag/
      ingestion.py         # Document ingestion (skeleton)
      search.py            # Document search (skeleton)
  schema/
    tables.yaml            # Table metadata, domains, roles
    init.sql               # Seed data for local development
  tests/
    test_sql_validator.py  # 22 SQL validation tests
    test_tools.py          # 15 schema, role, RAG tests
  docker-compose.yml
  Dockerfile
  pyproject.toml
```
