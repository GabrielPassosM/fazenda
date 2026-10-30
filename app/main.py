from fastapi import FastAPI

from app.application.routers import health, home
from app.domain.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="0.1.0",
    )

    application.include_router(health.router)
    application.include_router(home.router)

    return application


app = create_app()

