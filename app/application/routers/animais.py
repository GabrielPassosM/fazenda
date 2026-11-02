from datetime import date
from decimal import Decimal, InvalidOperation
import urllib.parse
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.application.schemas.animal import AnimalCreate, AnimalUpdate
from app.application.templating import templates
from app.domain.models.enums import CategoriaAnimalEnum, FazendaEnum, StatusAnimalEnum
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.repositories.pasto_repository import PastoRepository
from app.domain.use_cases.animal_use_cases import (
    create_animal,
    delete_animal,
    update_animal,
)
from app.domain.use_cases.exceptions import DomainError, NotFoundError
from app.infrastructure.database import get_db

router = APIRouter(tags=["Animais"])


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", ".")
    if not cleaned:
        return None
    return Decimal(cleaned)


def _parse_date(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None
    return date.fromisoformat(value.strip())


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if value is None or not value.strip():
        return None
    return uuid.UUID(value.strip())


@router.get("/", response_class=HTMLResponse, summary="Listagem paginada de animais")
@router.get("/animais", response_class=HTMLResponse, include_in_schema=False)
def list_animais(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    q: str | None = Query(None),
    fazenda: str | None = Query(None),
    categoria: str | None = Query(None),
    status: str | None = Query(None),
    pasto_id: str | None = Query(None),
    msg: str | None = Query(None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    fazenda_enum = FazendaEnum(fazenda) if fazenda in FazendaEnum._value2member_map_ else None
    categoria_enum = (
        CategoriaAnimalEnum(categoria)
        if categoria in CategoriaAnimalEnum._value2member_map_
        else None
    )
    status_param = StatusAnimalEnum.ATIVO.value if status is None else status
    status_enum = (
        StatusAnimalEnum(status_param)
        if status_param in StatusAnimalEnum._value2member_map_
        else None
    )
    try:
        pasto_uuid = _parse_uuid(pasto_id)
    except ValueError:
        pasto_uuid = None

    repo = AnimalRepository(db)
    pasto_repo = PastoRepository(db)
    paginated = repo.list_paginated(
        page=page,
        page_size=page_size,
        q=q,
        fazenda=fazenda_enum,
        categoria=categoria_enum,
        status=status_enum,
        pasto_id=pasto_uuid,
    )

    return templates.TemplateResponse(
        request=request,
        name="animais/list.html",
        context={
            "paginated": paginated,
            "pastos": pasto_repo.list_all(),
            "filters": {
                "q": q or "",
                "fazenda": fazenda_enum.value if fazenda_enum else "",
                "categoria": categoria_enum.value if categoria_enum else "",
                "status": status_enum.value if status_enum else "",
                "pasto_id": str(pasto_uuid) if pasto_uuid else "",
            },
            "today": date.today().isoformat(),
            "msg": msg,
        },
    )


@router.get("/animais/novo", response_class=HTMLResponse, summary="Formulário de novo animal")
def new_animal_form(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    today_str = date.today().isoformat()
    pasto_repo = PastoRepository(db)
    return templates.TemplateResponse(
        request=request,
        name="animais/form.html",
        context={
            "is_edit": False,
            "pastos": pasto_repo.list_all(),
            "form_data": {
                "numero": "",
                "fazenda": FazendaEnum.TIZIU.value,
                "categoria": CategoriaAnimalEnum.BEZERRO.value,
                "status": StatusAnimalEnum.ATIVO.value,
                "data_entrada": today_str,
                "pasto_id": "",
                "observacoes": "",
                "peso_inicial_kg": "",
                "data_pesagem_inicial": today_str,
                "observacao_pesagem": "Peso de entrada",
            },
            "error": None,
        },
    )


@router.post("/animais/novo", response_class=HTMLResponse, summary="Cadastrar novo animal")
def create_animal_submit(
    request: Request,
    numero: str = Form(""),
    fazenda: str = Form(""),
    categoria: str = Form(""),
    status: str = Form(StatusAnimalEnum.ATIVO.value),
    data_entrada: str = Form(""),
    pasto_id: str = Form(""),
    observacoes: str = Form(""),
    peso_inicial_kg: str = Form(""),
    data_pesagem_inicial: str = Form(""),
    observacao_pesagem: str = Form(""),
    db: Session = Depends(get_db),
):
    form_data = {
        "numero": numero,
        "fazenda": fazenda,
        "categoria": categoria,
        "status": status,
        "data_entrada": data_entrada,
        "pasto_id": pasto_id,
        "observacoes": observacoes,
        "peso_inicial_kg": peso_inicial_kg,
        "data_pesagem_inicial": data_pesagem_inicial,
        "observacao_pesagem": observacao_pesagem,
    }

    try:
        peso_dec = _parse_decimal(peso_inicial_kg)
        dt_entrada = _parse_date(data_entrada)
        if dt_entrada is None:
            raise DomainError("A data de entrada é obrigatória.")
        dt_pesagem = _parse_date(data_pesagem_inicial) or dt_entrada
        pasto_uuid = _parse_uuid(pasto_id)

        schema = AnimalCreate(
            numero=numero,
            fazenda=FazendaEnum(fazenda),
            categoria=CategoriaAnimalEnum(categoria),
            status=StatusAnimalEnum(status),
            data_entrada=dt_entrada,
            pasto_id=pasto_uuid,
            observacoes=observacoes,
            peso_inicial_kg=peso_dec,
            data_pesagem_inicial=dt_pesagem if peso_dec is not None else None,
            observacao_pesagem=observacao_pesagem if peso_dec is not None else None,
        )
        animal = create_animal(db, schema)
        msg = urllib.parse.quote(f"Animal nº {animal.numero} cadastrado com sucesso!")
        return RedirectResponse(url=f"/?msg={msg}", status_code=303)

    except (DomainError, ValidationError, InvalidOperation, ValueError) as exc:
        if isinstance(exc, DomainError):
            error_msg = exc.message
        elif isinstance(exc, InvalidOperation):
            error_msg = "Valor de peso inválido. Informe um número válido (ex: 280.50)."
        elif isinstance(exc, ValidationError):
            error_msg = exc.errors()[0].get("msg", "Dados inválidos no formulário.")
        else:
            error_msg = str(exc)

        pasto_repo = PastoRepository(db)
        return templates.TemplateResponse(
            request=request,
            name="animais/form.html",
            context={
                "is_edit": False,
                "pastos": pasto_repo.list_all(),
                "form_data": form_data,
                "error": error_msg,
            },
            status_code=422,
        )


@router.get("/animais/{animal_id}", response_class=HTMLResponse, summary="Detalhes e pesagens do animal")
def detail_animal(
    animal_id: uuid.UUID,
    request: Request,
    msg: str | None = Query(None),
    error: str | None = Query(None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    repo = AnimalRepository(db)
    animal = repo.get_by_id(animal_id)
    if animal is None:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")

    # Calcula variação de peso entre uma pesagem e a imediatamente anterior (cronológica)
    pesagens_com_variacao = []
    pesagens_list = list(animal.pesagens)
    for idx, p in enumerate(pesagens_list):
        anterior = pesagens_list[idx + 1] if idx + 1 < len(pesagens_list) else None
        variacao = (p.peso_kg - anterior.peso_kg) if anterior is not None else None
        pesagens_com_variacao.append(
            {
                "pesagem": p,
                "variacao_kg": variacao,
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="animais/detail.html",
        context={
            "animal": animal,
            "pesagens_com_variacao": pesagens_com_variacao,
            "ultima_pesagem": pesagens_list[0] if pesagens_list else None,
            "today": date.today().isoformat(),
            "msg": msg,
            "error": error,
        },
    )


@router.get("/animais/{animal_id}/editar", response_class=HTMLResponse, summary="Formulário de edição de animal")
def edit_animal_form(
    animal_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    repo = AnimalRepository(db)
    animal = repo.get_by_id(animal_id)
    if animal is None:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")

    pasto_repo = PastoRepository(db)
    return templates.TemplateResponse(
        request=request,
        name="animais/form.html",
        context={
            "is_edit": True,
            "animal": animal,
            "pastos": pasto_repo.list_all(),
            "form_data": {
                "numero": animal.numero,
                "fazenda": animal.fazenda.value,
                "categoria": animal.categoria.value,
                "status": animal.status.value,
                "data_entrada": animal.data_entrada.isoformat(),
                "pasto_id": str(animal.pasto_id) if animal.pasto_id else "",
                "observacoes": animal.observacoes or "",
            },
            "error": None,
        },
    )


@router.post("/animais/{animal_id}/editar", response_class=HTMLResponse, summary="Atualizar dados do animal")
def update_animal_submit(
    animal_id: uuid.UUID,
    request: Request,
    numero: str = Form(""),
    fazenda: str = Form(""),
    categoria: str = Form(""),
    status: str = Form(""),
    data_entrada: str = Form(""),
    pasto_id: str = Form(""),
    observacoes: str = Form(""),
    db: Session = Depends(get_db),
):
    repo = AnimalRepository(db)
    animal = repo.get_by_id(animal_id)
    if animal is None:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")

    form_data = {
        "numero": numero,
        "fazenda": fazenda,
        "categoria": categoria,
        "status": status,
        "data_entrada": data_entrada,
        "pasto_id": pasto_id,
        "observacoes": observacoes,
    }

    try:
        dt_entrada = _parse_date(data_entrada)
        if dt_entrada is None:
            raise DomainError("A data de entrada é obrigatória.")
        pasto_uuid = _parse_uuid(pasto_id)

        schema = AnimalUpdate(
            numero=numero,
            fazenda=FazendaEnum(fazenda),
            categoria=CategoriaAnimalEnum(categoria),
            status=StatusAnimalEnum(status),
            data_entrada=dt_entrada,
            pasto_id=pasto_uuid,
            observacoes=observacoes,
        )
        updated = update_animal(db, animal_id, schema)
        msg = urllib.parse.quote(f"Dados do animal nº {updated.numero} atualizados!")
        return RedirectResponse(url=f"/animais/{animal_id}?msg={msg}", status_code=303)

    except (DomainError, ValidationError, ValueError) as exc:
        if isinstance(exc, DomainError):
            error_msg = exc.message
        elif isinstance(exc, ValidationError):
            error_msg = exc.errors()[0].get("msg", "Dados inválidos no formulário.")
        else:
            error_msg = str(exc)

        pasto_repo = PastoRepository(db)
        return templates.TemplateResponse(
            request=request,
            name="animais/form.html",
            context={
                "is_edit": True,
                "animal": animal,
                "pastos": pasto_repo.list_all(),
                "form_data": form_data,
                "error": error_msg,
            },
            status_code=422,
        )


@router.post("/animais/{animal_id}/excluir", summary="Excluir animal")
def delete_animal_submit(
    animal_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        delete_animal(db, animal_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    msg = urllib.parse.quote("Animal excluído com sucesso.")
    return RedirectResponse(url=f"/?msg={msg}", status_code=303)

