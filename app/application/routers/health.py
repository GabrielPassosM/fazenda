from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.application.schemas import HealthResponse
from app.domain.core.config import settings
from app.infrastructure.database import get_db

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Verifica a saúde da aplicação e conectividade com o banco de dados",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {exc}",
        ) from exc

    return HealthResponse(
        status="ok",
        database="connected",
        environment=settings.ENVIRONMENT,
    )

