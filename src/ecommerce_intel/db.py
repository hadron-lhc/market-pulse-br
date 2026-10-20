"""PostgreSQL connection helpers."""

from __future__ import annotations

import logging

import psycopg

from .config import Settings, load_settings

log = logging.getLogger(__name__)


def connect(settings: Settings | None = None) -> psycopg.Connection:
    """Open a connection to the configured database (autocommit off)."""
    settings = settings or load_settings()
    return psycopg.connect(settings.dsn)


def ensure_database(settings: Settings | None = None) -> None:
    """Create the target database if it does not exist yet."""
    settings = settings or load_settings()
    try:
        with psycopg.connect(settings.admin_dsn, autocommit=True) as admin:
            exists = admin.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (settings.dbname,)
            ).fetchone()
            if not exists:
                admin.execute(f'CREATE DATABASE "{settings.dbname}"')
                log.info("Created database %s", settings.dbname)
            else:
                log.info("Database %s already exists", settings.dbname)
    except psycopg.OperationalError as exc:
        raise SystemExit(
            f"Cannot connect to PostgreSQL at {settings.host}:{settings.port} "
            f"as user {settings.user}: {exc}\n"
            "Start the database (make db-up) or fix PG* settings in .env"
        ) from exc
