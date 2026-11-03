import urllib.parse
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.application.schemas.pasto import (
    PastoCreate,
    PastoRodizioCreate,
    PastoTransferenciaItem,
    PastoUpdate,
)
from app.application.templating import templates
from app.domain.repositories.pasto_repository import PastoRepository
from app.domain.use_cases.exceptions import DomainError, NotFoundError
from app.domain.use_cases.pasto_use_cases import (
    create_pasto,
    delete_pasto,
    rodar_pastos,
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


@router.post(
    "/pastos/rodizio",
    response_class=HTMLResponse,
    summary="Rodar/transferir animais entre pastos em lote (em cadeia)",
)
def rodizio_pastos_submit(
    request: Request,
    origens: list[str] = Form(default=[]),
    destinos: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    try:
        max_len = max(len(origens), len(destinos))
        etapas: list[PastoTransferenciaItem] = []

        for idx in range(max_len):
            orig_str = origens[idx].strip() if idx < len(origens) else ""
            dest_str = destinos[idx].strip() if idx < len(destinos) else ""

            if not orig_str and not dest_str:
                continue
            if not orig_str or not dest_str:
                raise DomainError(
                    f"Etapa {idx + 1}: selecione o pasto de origem e o pasto de destino."
                )

            etapas.append(
                PastoTransferenciaItem(
                    pasto_origem_id=uuid.UUID(orig_str),
                    pasto_destino_id=uuid.UUID(dest_str),
                )
            )

        if not etapas:
            raise DomainError("Informe ao menos uma transferência de pasto para realizar o rodízio.")

        schema = PastoRodizioCreate(etapas=etapas)
        resultado = rodar_pastos(db, schema)
        resumo = "; ".join(resultado.resumo_etapas)
        label_mov = "animal movimentado" if resultado.total_animais_movidos == 1 else "animais movimentados"
        msg = urllib.parse.quote(
            f"Rodízio concluído ({resultado.total_animais_movidos} {label_mov}): {resumo}."
        )
        return RedirectResponse(url=f"/pastos?msg={msg}", status_code=303)

    except (DomainError, NotFoundError, ValueError) as exc:
        if isinstance(exc, (DomainError, NotFoundError)):
            error_msg = exc.message
        else:
            error_msg = "Identificador de pasto inválido no rodízio."

        repo = PastoRepository(db)
        items = repo.list_with_counts()
        return templates.TemplateResponse(
            request=request,
            name="pastos/list.html",
            context={
                "items": items,
                "form_data": {"nome": ""},
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

