from datetime import date
from decimal import Decimal
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.domain.core.config import settings
from app.domain.models.enums import CategoriaAnimalEnum, FazendaEnum, StatusAnimalEnum

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def format_date(value: date | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d/%m/%Y")


def format_peso(value: Decimal | float | None) -> str:
    if value is None:
        return "—"
    formatted = f"{Decimal(str(value)):,.2f}"
    # Formatação padrão brasileiro: 1.234,56
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{formatted} kg"


templates.env.filters["format_date"] = format_date
templates.env.filters["format_peso"] = format_peso
templates.env.globals["app_name"] = settings.APP_NAME
templates.env.globals["FazendaEnum"] = FazendaEnum
templates.env.globals["CategoriaAnimalEnum"] = CategoriaAnimalEnum
templates.env.globals["StatusAnimalEnum"] = StatusAnimalEnum

