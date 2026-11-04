import urllib.parse

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.application.templating import templates
from app.domain.core.config import settings
from app.domain.core.security import (
    SESSION_COOKIE_NAME,
    create_session_token,
    login_rate_limiter,
    sanitize_next_url,
    verify_access_password,
    verify_session_token,
)

router = APIRouter(tags=["Autenticação"])


class AuthenticationRequiredError(Exception):
    """Exceção levantada quando uma rota protegida é acessada sem sessão válida."""

    def __init__(self, next_url: str = "/", is_htmx: bool = False) -> None:
        self.next_url = next_url
        self.is_htmx = is_htmx
        super().__init__("Autenticação necessária.")


def require_auth(request: Request) -> None:
    """Dependência FastAPI que exige um cookie de sessão válido."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if verify_session_token(token):
        return

    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    next_path = request.url.path
    if request.method == "GET" and request.url.query:
        next_path = f"{next_path}?{request.url.query}"

    raise AuthenticationRequiredError(next_url=next_path, is_htmx=is_htmx)


def auth_exception_handler(
    request: Request,
    exc: AuthenticationRequiredError,
) -> Response:
    """Redireciona usuários não autenticados para a tela de login (com suporte a HTMX)."""
    if exc.is_htmx:
        return Response(
            status_code=401,
            headers={"HX-Redirect": "/login"},
        )

    safe_next = sanitize_next_url(exc.next_url)
    if safe_next != "/":
        quoted_next = urllib.parse.quote(safe_next, safe="")
        login_url = f"/login?next={quoted_next}"
    else:
        login_url = "/login"

    return RedirectResponse(url=login_url, status_code=303)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.get("/login", response_class=HTMLResponse, summary="Tela de login")
def login_page(
    request: Request,
    next: str | None = Query(None),
) -> Response:
    safe_next = sanitize_next_url(next)
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if verify_session_token(token):
        return RedirectResponse(url=safe_next, status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "next_url": safe_next,
            "error": None,
        },
    )


@router.post("/login", response_class=HTMLResponse, summary="Autenticar com senha de acesso")
def login_submit(
    request: Request,
    senha: str = Form(""),
    next_url: str = Form("/"),
) -> Response:
    safe_next = sanitize_next_url(next_url)
    client_ip = _get_client_ip(request)

    if login_rate_limiter.is_blocked(client_ip):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "next_url": safe_next,
                "error": "Muitas tentativas incorretas. Aguarde alguns minutos e tente novamente.",
            },
            status_code=429,
        )

    if not verify_access_password(senha):
        login_rate_limiter.record_failure(client_ip)
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "next_url": safe_next,
                "error": "Senha de acesso incorreta.",
            },
            status_code=401,
        )

    login_rate_limiter.reset(client_ip)
    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(),
        max_age=settings.SESSION_EXPIRE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT.lower() == "production"),
        path="/",
    )
    return response


@router.post("/logout", summary="Encerrar sessão")
def logout_submit() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return response

