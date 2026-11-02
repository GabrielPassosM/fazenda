from fastapi import FastAPI

from app.application.routers import animais, health, pastos, pesagens
from app.domain.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="0.1.0",
    )

    application.include_router(health.router)
    application.include_router(animais.router)
    application.include_router(pastos.router)
    application.include_router(pesagens.router)

    return application


app = create_app()
