from fastapi.testclient import TestClient
from starlette.requests import Request

from app.application.routers.auth import _get_client_ip
from app.domain.core.config import settings
from app.domain.core.security import (
    SESSION_COOKIE_NAME,
    LoginRateLimiter,
    create_session_token,
    login_rate_limiter,
    sanitize_next_url,
    verify_access_password,
    verify_session_token,
)


def test_verify_access_password() -> None:
    assert verify_access_password(settings.ACCESS_PASSWORD) is True
    assert verify_access_password("senha-errada") is False
    assert verify_access_password("") is False


def test_session_token_lifecycle(monkeypatch) -> None:
    token = create_session_token(expires_days=1, now=1000)
    assert verify_session_token(token, now=1000) is True
    assert verify_session_token(token, now=1000 + 86399) is True
    # Expirado
    assert verify_session_token(token, now=1000 + 86400) is False

    # Token vazio ou malformado
    assert verify_session_token(None) is False
    assert verify_session_token("") is False
    assert verify_session_token("apenas-uma-parte") is False
    assert verify_session_token("nao-numero.nonce.sig") is False
    assert verify_session_token("9999999999..sig") is False

    # Assinatura adulterada
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.00000000000000000000"
    assert verify_session_token(tampered, now=1000) is False

    # Alterar ACCESS_PASSWORD invalida tokens emitidos anteriormente
    monkeypatch.setattr(settings, "ACCESS_PASSWORD", "nova-senha-secreta")
    assert verify_session_token(token, now=1000) is False


def test_sanitize_next_url() -> None:
    assert sanitize_next_url(None) == "/"
    assert sanitize_next_url("") == "/"
    assert sanitize_next_url("/pastos") == "/pastos"
    assert sanitize_next_url("/animais?fazenda=tiziu") == "/animais?fazenda=tiziu"
    assert sanitize_next_url("https://evil.com") == "/"
    assert sanitize_next_url("//evil.com") == "/"
    assert sanitize_next_url("/\\evil.com") == "/"
    assert sanitize_next_url("/login") == "/"
    assert sanitize_next_url("/logout") == "/"


def test_login_rate_limiter_unit() -> None:
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
    ip = "192.168.1.50"

    assert limiter.is_blocked(ip, now=100.0) is False
    limiter.record_failure(ip, now=100.0)
    limiter.record_failure(ip, now=110.0)
    assert limiter.is_blocked(ip, now=120.0) is False

    limiter.record_failure(ip, now=120.0)
    assert limiter.is_blocked(ip, now=130.0) is True

    # Após a janela de 60s expirar para a primeira tentativa, desbloqueia
    assert limiter.is_blocked(ip, now=161.0) is False

    # Após todas expirarem, remove a chave da memória
    assert limiter.is_blocked(ip, now=200.0) is False

    limiter.record_failure(ip, now=210.0)
    limiter.reset(ip)
    assert limiter.is_blocked(ip, now=210.0) is False

    limiter.record_failure(ip, now=220.0)
    limiter.clear_all()
    assert limiter.is_blocked(ip, now=220.0) is False


def test_get_client_ip_variants() -> None:
    scope_forwarded = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
        "client": ("127.0.0.1", 8000),
    }
    assert _get_client_ip(Request(scope_forwarded)) == "203.0.113.10"

    scope_no_client = {
        "type": "http",
        "headers": [],
        "client": None,
    }
    assert _get_client_ip(Request(scope_no_client)) == "unknown"


def test_unauthenticated_redirect_and_htmx_redirect(client: TestClient) -> None:
    client.cookies.clear()

    # Rota raiz redireciona para /login sem query string desnecessária
    r_root = client.get("/", follow_redirects=False)
    assert r_root.status_code == 303
    assert r_root.headers["location"] == "/login"

    # Rota interna com query string preserva o destino em ?next=
    r_pastos = client.get("/pastos?msg=ok", follow_redirects=False)
    assert r_pastos.status_code == 303
    assert r_pastos.headers["location"] == "/login?next=%2Fpastos%3Fmsg%3Dok"

    # Requisição HTMX não autenticada recebe 401 + HX-Redirect
    r_htmx = client.get(
        "/htmx/animal-lookup?fazenda=tiziu&numero=10",
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert r_htmx.status_code == 401
    assert r_htmx.headers["HX-Redirect"] == "/login"

    # Endpoint /health permanece público para o Docker healthcheck
    r_health = client.get("/health")
    assert r_health.status_code == 200


def test_login_and_logout_flow(client: TestClient) -> None:
    login_rate_limiter.clear_all()
    client.cookies.clear()

    # Exibe tela de login
    page = client.get("/login")
    assert page.status_code == 200
    assert "Senha de acesso" in page.text

    # Senha incorreta retorna 401
    bad = client.post(
        "/login",
        data={"senha": "errada", "next_url": "/pastos"},
        follow_redirects=False,
    )
    assert bad.status_code == 401
    assert "Senha de acesso incorreta." in bad.text

    # Senha correta autentica, define cookie HttpOnly e redireciona para next_url
    good = client.post(
        "/login",
        data={"senha": settings.ACCESS_PASSWORD, "next_url": "/pastos"},
        follow_redirects=False,
    )
    assert good.status_code == 303
    assert good.headers["location"] == "/pastos"
    assert SESSION_COOKIE_NAME in good.cookies

    # Acessar /login já estando logado redireciona direto para o sistema
    already_logged = client.get("/login?next=/pastos", follow_redirects=False)
    assert already_logged.status_code == 303
    assert already_logged.headers["location"] == "/pastos"

    # Logout limpa o cookie e redireciona para /login
    logout_resp = client.post("/logout", follow_redirects=False)
    assert logout_resp.status_code == 303
    assert logout_resp.headers["location"] == "/login"


def test_login_rate_limiting_blocks_after_max_attempts(client: TestClient) -> None:
    login_rate_limiter.clear_all()
    client.cookies.clear()

    for _ in range(login_rate_limiter.max_attempts):
        resp = client.post("/login", data={"senha": "errada"})
        assert resp.status_code == 401

    blocked = client.post("/login", data={"senha": settings.ACCESS_PASSWORD})
    assert blocked.status_code == 429
    assert "Muitas tentativas incorretas" in blocked.text
    login_rate_limiter.clear_all()

