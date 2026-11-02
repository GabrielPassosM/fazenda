import urllib.parse
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.application.schemas.pasto import PastoCreate, PastoUpdate
from app.application.templating import templates
from app.domain.repositories.pasto_repository import PastoRepository
from app.domain.use_cases.exceptions import DomainError, NotFoundError
from app.domain.use_cases.pasto_use_cases import (
    create_pasto,
    delete_pasto,
    update_pasto,
)
from app.infrastructure.database import get_db

router = APIRouter(tags=["Pastos"])


@router.get("/pastos", response_class=HTMLResponse, summary="Listagem e cadastro de pastos")
def list_pastos(
    request: Request,
    msg: str | None = Query(None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    repo = PastoRepository(db)
    items = repo.list_with_counts()
    return templates.TemplateResponse(
        request=request,
        name="pastos/list.html",
        context={
            "items": items,
            "form_data": {"nome": ""},
            "msg": msg,
            "error": None,
        },
    )


@router.post("/pastos/novo", response_class=HTMLResponse, summary="Cadastrar novo pasto")
def create_pasto_submit(
    request: Request,
    nome: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        schema = PastoCreate(nome=nome)
        pasto = create_pasto(db, schema)
        msg = urllib.parse.quote(f"Pasto '{pasto.nome}' cadastrado com sucesso!")
        return RedirectResponse(url=f"/pastos?msg={msg}", status_code=303)
    except (DomainError, ValidationError) as exc:
        if isinstance(exc, DomainError):
            error_msg = exc.message
        else:
            error_msg = exc.errors()[0].get("msg", "Dados inválidos no formulário.")

        repo = PastoRepository(db)
        items = repo.list_with_counts()
        return templates.TemplateResponse(
            request=request,
            name="pastos/list.html",
            context={
                "items": items,
                "form_data": {"nome": nome},
                "msg": None,
                "error": error_msg,
            },
            status_code=422,
        )


@router.get(
    "/pastos/{pasto_id}/editar",
    response_class=HTMLResponse,
    summary="Formulário de edição de pasto",
)
def edit_pasto_form(
    pasto_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    repo = PastoRepository(db)
    pasto = repo.get_by_id(pasto_id)
    if pasto is None:
        raise HTTPException(status_code=404, detail="Pasto não encontrado.")

    return templates.TemplateResponse(
        request=request,
        name="pastos/form.html",
        context={
            "pasto": pasto,
            "form_data": {"nome": pasto.nome},
            "error": None,
        },
    )


@router.post(
    "/pastos/{pasto_id}/editar",
    response_class=HTMLResponse,
    summary="Atualizar dados do pasto",
)
def update_pasto_submit(
    pasto_id: uuid.UUID,
    request: Request,
    nome: str = Form(""),
    db: Session = Depends(get_db),
):
    repo = PastoRepository(db)
    pasto = repo.get_by_id(pasto_id)
    if pasto is None:
        raise HTTPException(status_code=404, detail="Pasto não encontrado.")

    try:
        schema = PastoUpdate(nome=nome)
        updated = update_pasto(db, pasto_id, schema)
        msg = urllib.parse.quote(f"Pasto '{updated.nome}' atualizado com sucesso!")
        return RedirectResponse(url=f"/pastos?msg={msg}", status_code=303)
    except (DomainError, ValidationError) as exc:
        if isinstance(exc, DomainError):
            error_msg = exc.message
        else:
            error_msg = exc.errors()[0].get("msg", "Dados inválidos no formulário.")

        return templates.TemplateResponse(
            request=request,
            name="pastos/form.html",
            context={
                "pasto": pasto,
                "form_data": {"nome": nome},
                "error": error_msg,
            },
            status_code=422,
        )


@router.post("/pastos/{pasto_id}/excluir", summary="Excluir pasto")
def delete_pasto_submit(
    pasto_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        delete_pasto(db, pasto_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    msg = urllib.parse.quote("Pasto excluído com sucesso.")
    return RedirectResponse(url=f"/pastos?msg={msg}", status_code=303)

