"""Configuration loaded from environment variables (.env supported, never committed)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    user: str
    password: str | None
    dbname: str
    data_dir: Path

    @property
    def dsn(self) -> str:
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"user={self.user}",
            f"dbname={self.dbname}",
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)

    @property
    def admin_dsn(self) -> str:
        """DSN for the maintenance database used to create the target database."""
        return self.dsn.replace(f"dbname={self.dbname}", "dbname=postgres")


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    data_dir = Path(_env("DATA_DIR", "data"))
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir
    return Settings(
        host=_env("PGHOST", "localhost"),
        port=int(_env("PGPORT", "5432")),
        user=_env("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD") or None,
        dbname=_env("PGDATABASE", "olist_analytics"),
        data_dir=data_dir,
    )
