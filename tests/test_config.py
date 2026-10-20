"""Unit tests for configuration handling (no database required)."""

from __future__ import annotations

from ecommerce_intel.config import REPO_ROOT, load_settings


def _isolate_env(monkeypatch) -> None:
    """Ignore the repo .env so defaults are observable."""
    monkeypatch.setattr("ecommerce_intel.config.load_dotenv", lambda *a, **k: None)
    for var in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE", "DATA_DIR"):
        monkeypatch.delenv(var, raising=False)


def test_defaults(monkeypatch):
    _isolate_env(monkeypatch)
    settings = load_settings()
    assert settings.host == "localhost"
    assert settings.port == 5432
    assert settings.user == "postgres"
    assert settings.dbname == "olist_analytics"
    assert settings.data_dir == REPO_ROOT / "data"


def test_env_override(monkeypatch):
    monkeypatch.setenv("PGHOST", "/var/run/postgresql")
    monkeypatch.setenv("PGPORT", "5433")
    monkeypatch.setenv("PGUSER", "analyst")
    monkeypatch.setenv("PGPASSWORD", "secret")
    monkeypatch.setenv("PGDATABASE", "other_db")
    settings = load_settings()
    assert settings.host == "/var/run/postgresql"
    assert settings.port == 5433
    assert settings.user == "analyst"
    assert settings.dbname == "other_db"
    assert "password=secret" in settings.dsn
    assert "dbname=postgres" in settings.admin_dsn
    assert "dbname=other_db" not in settings.admin_dsn


def test_relative_data_dir_resolves_to_repo_root(monkeypatch):
    monkeypatch.setattr("ecommerce_intel.config.load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", "data")
    assert load_settings().data_dir == REPO_ROOT / "data"
