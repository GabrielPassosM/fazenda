from fastapi.testclient import TestClient


def test_health_check_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "connected"
    assert "environment" in payload


def test_home_page_renders_html_and_htmx(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "hx-get=\"/htmx/ping\"" in response.text


def test_htmx_ping_fragment(client: TestClient) -> None:
    response = client.get("/htmx/ping")
    assert response.status_code == 200
    assert "Conexão HTMX ativa!" in response.text

