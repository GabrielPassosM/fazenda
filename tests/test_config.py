import pytest
from app.domain.core.config import Settings


def test_settings_assemble_database_url_from_individual_vars():
    settings = Settings(
        POSTGRES_USER="myuser",
        POSTGRES_PASSWORD="mypassword",
        POSTGRES_HOST="dbhost",
        POSTGRES_PORT=5433,
        POSTGRES_DB="custom_db",
        DATABASE_URL="",
    )
    assert (
        settings.DATABASE_URL
        == "postgresql+psycopg://myuser:mypassword@dbhost:5433/custom_db"
    )


def test_settings_default_values():
    settings = Settings(DATABASE_URL="")
    assert (
        settings.DATABASE_URL
        == "postgresql+psycopg://postgres:postgres@localhost:5432/fazenda_db"
    )


def test_settings_explicit_database_url_normalization():
    settings_postgres = Settings(
        DATABASE_URL="postgres://user:pass@host:5432/db"
    )
    assert (
        settings_postgres.DATABASE_URL
        == "postgresql+psycopg://user:pass@host:5432/db"
    )

    settings_postgresql = Settings(
        DATABASE_URL="postgresql://user:pass@host:5432/db"
    )
    assert (
        settings_postgresql.DATABASE_URL
        == "postgresql+psycopg://user:pass@host:5432/db"
    )

