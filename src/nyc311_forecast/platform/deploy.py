"""Idempotent contract table deployment through an existing SQL warehouse."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep

from nyc311_forecast.config import Config
from nyc311_forecast.platform.sql_templates import render_sql


def ddl_statements(path: Path, *, catalog: str, schema: str) -> list[str]:
    sql = render_sql(path, catalog=catalog, schema=schema)
    without_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    statements = [part.strip() for part in without_comments.split(";") if part.strip()]
    if len(statements) != 10 or any(
        not part.startswith("CREATE TABLE IF NOT EXISTS") for part in statements
    ):
        raise ValueError("Expected exactly ten contract CREATE TABLE statements")
    return statements


def view_statements(path: Path, *, catalog: str, schema: str) -> list[str]:
    sql = render_sql(path, catalog=catalog, schema=schema)
    without_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    statements = [part.strip() for part in without_comments.split(";") if part.strip()]
    if len(statements) != 5 or any(
        not part.startswith("CREATE OR REPLACE VIEW") for part in statements
    ):
        raise ValueError("Expected exactly five contract CREATE OR REPLACE VIEW statements")
    return statements


def deploy_tables(api, config: Config, ddl_path: Path, *, timeout_seconds: int = 120) -> list[dict]:
    from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout, StatementState

    if not config.catalog or not config.schema or not config.warehouse_id:
        raise ValueError("catalog, schema and warehouse_id are required")
    results: list[dict] = []
    for statement in ddl_statements(ddl_path, catalog=config.catalog, schema=config.schema):
        table_name = statement.split("(", 1)[0].split()[-1]
        started = monotonic()
        response = api.execute_statement(
            statement=statement,
            warehouse_id=config.warehouse_id,
            wait_timeout="30s",
            on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
        )
        query_id = response.statement_id
        while response.status and response.status.state in (
            StatementState.PENDING,
            StatementState.RUNNING,
        ):
            if monotonic() - started >= timeout_seconds:
                results.append({"table": table_name, "query_id": query_id, "status": "timeout"})
                return results
            sleep(2)
            response = api.get_statement(query_id)
        state = response.status.state if response.status else None
        item = {
            "table": table_name,
            "query_id": query_id,
            "status": str(state),
            "wall_seconds": monotonic() - started,
            "checked_at_utc": datetime.now(UTC).isoformat(),
        }
        results.append(item)
        if state != StatementState.SUCCEEDED:
            error = response.status.error if response.status else None
            item["safe_error_message"] = (
                error.message.splitlines()[0] if error and error.message else "no detail"
            )
            return results
    return results


def deploy_views(api, config: Config, view_path: Path, *, timeout_seconds: int = 120) -> list[dict]:
    from databricks.sdk.service.sql import ExecuteStatementRequestOnWaitTimeout, StatementState

    if not config.catalog or not config.schema or not config.warehouse_id:
        raise ValueError("catalog, schema and warehouse_id are required")
    results: list[dict] = []
    for statement in view_statements(view_path, catalog=config.catalog, schema=config.schema):
        view_name = statement.split(" AS\n", 1)[0].split()[-1]
        started = monotonic()
        response = api.execute_statement(
            statement=statement,
            warehouse_id=config.warehouse_id,
            wait_timeout="30s",
            on_wait_timeout=ExecuteStatementRequestOnWaitTimeout.CONTINUE,
        )
        query_id = response.statement_id
        while response.status and response.status.state in (
            StatementState.PENDING,
            StatementState.RUNNING,
        ):
            if monotonic() - started >= timeout_seconds:
                results.append({"view": view_name, "query_id": query_id, "status": "timeout"})
                return results
            sleep(2)
            response = api.get_statement(query_id)
        state = response.status.state if response.status else None
        item = {
            "view": view_name,
            "query_id": query_id,
            "status": str(state),
            "wall_seconds": monotonic() - started,
            "checked_at_utc": datetime.now(UTC).isoformat(),
        }
        results.append(item)
        if state != StatementState.SUCCEEDED:
            error = response.status.error if response.status else None
            item["safe_error_message"] = (
                error.message.splitlines()[0] if error and error.message else "no detail"
            )
            return results
    return results
