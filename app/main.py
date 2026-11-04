from fastapi import Depends, FastAPI

from app.application.routers import animais, auth, health, pastos, pesagens
from app.domain.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="0.1.0",
    )

    application.add_exception_handler(
        auth.AuthenticationRequiredError,
        auth.auth_exception_handler,
    )

    protected = [Depends(auth.require_auth)]

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(animais.router, dependencies=protected)
    application.include_router(pastos.router, dependencies=protected)
    application.include_router(pesagens.router, dependencies=protected)

    return application


app = create_app()
