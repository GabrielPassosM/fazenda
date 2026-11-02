from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.application.templating import format_date, format_peso
from app.infrastructure.database import get_db
from app.main import app


def test_health_check_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert "environment" in payload


def test_health_check_returns_503_on_db_error() -> None:
    broken_db = MagicMock()
    broken_db.execute.side_effect = OperationalError("SELECT 1", {}, Exception("db down"))

    def override_broken_db():
        yield broken_db

    app.dependency_overrides[get_db] = override_broken_db
    try:
        with TestClient(app) as c:
            response = c.get("/health")
            assert response.status_code == 503
            assert "Database connection failed" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_get_db_generator_closes_session(monkeypatch) -> None:
    mock_session = MagicMock()
    monkeypatch.setattr("app.infrastructure.database.SessionLocal", lambda: mock_session)

    gen = get_db()
    session = next(gen)
    assert session is mock_session
    gen.close()
    mock_session.close.assert_called_once()


def test_templating_filters_none_values() -> None:
    assert format_date(None) == "—"
    assert format_peso(None) == "—"


def test_list_animais_empty_state(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Animais do Rebanho" in response.text
    assert "Nenhum animal encontrado" in response.text
