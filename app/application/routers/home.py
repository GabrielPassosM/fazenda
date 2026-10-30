from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.domain.core.config import settings

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["Home"])


@router.get("/", response_class=HTMLResponse, summary="Página inicial SSR")
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "app_name": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
        },
    )


@router.get("/htmx/ping", response_class=HTMLResponse, summary="Fragmento dinâmico HTMX de teste")
def htmx_ping() -> HTMLResponse:
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    html_fragment = f"""
    <div class="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900 shadow-xs transition-all">
        <div class="flex items-center gap-2 font-semibold">
            <span class="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Conexão HTMX ativa!
        </div>
        <p class="mt-1 text-emerald-700">
            Fragmento HTML renderizado no servidor sem recarregar a página às <code class="font-mono font-bold">{now}</code>.
        </p>
    </div>
    """
    return HTMLResponse(content=html_fragment)

