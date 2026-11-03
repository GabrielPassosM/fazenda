from datetime import date
from decimal import Decimal, InvalidOperation
import urllib.parse
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.application.schemas.animal import (
    AnimalCreate,
    AnimalLoteCreate,
    AnimalLoteItem,
    AnimalUpdate,
)
from app.application.templating import templates
from app.domain.models.enums import (
    CategoriaAnimalEnum,
    FazendaEnum,
    OrdenacaoAnimalEnum,
    StatusAnimalEnum,
)
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.repositories.pasto_repository import PastoRepository
from app.domain.use_cases.animal_use_cases import (
    create_animais_em_lote,
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
    peso_min: str | None = Query(None),
    peso_max: str | None = Query(None),
    ordenar_por: str | None = Query(None),
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
    ordenar_por_enum = (
        OrdenacaoAnimalEnum(ordenar_por)
        if ordenar_por in OrdenacaoAnimalEnum._value2member_map_
        else OrdenacaoAnimalEnum.DATA_ENTRADA_DESC
    )
    try:
        pasto_uuid = _parse_uuid(pasto_id)
    except ValueError:
        pasto_uuid = None

    try:
        peso_min_dec = _parse_decimal(peso_min)
    except InvalidOperation:
        peso_min_dec = None

    try:
        peso_max_dec = _parse_decimal(peso_max)
    except InvalidOperation:
        peso_max_dec = None

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
        peso_min=peso_min_dec,
        peso_max=peso_max_dec,
        ordenar_por=ordenar_por_enum,
    )

    return templates.TemplateResponse(
        request=request,
        name="animais/list.html",
        context={
            "paginated": paginated,
            "total_ativos": repo.count_ativos(),
            "pastos": pasto_repo.list_all(),
            "filters": {
                "q": q or "",
                "fazenda": fazenda_enum.value if fazenda_enum else "",
                "categoria": categoria_enum.value if categoria_enum else "",
                "status": status_enum.value if status_enum else "",
                "pasto_id": str(pasto_uuid) if pasto_uuid else "",
                "peso_min": str(peso_min_dec) if peso_min_dec is not None else "",
                "peso_max": str(peso_max_dec) if peso_max_dec is not None else "",
                "ordenar_por": ordenar_por_enum.value,
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


@router.get(
    "/animais/lote",
    response_class=HTMLResponse,
    summary="Formulário de cadastro de animais em lote",
)
@router.get(
    "/animais/lote/novo",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def new_animais_lote_form(
    request: Request,
    fazenda: str | None = Query(None),
) -> HTMLResponse:
    fazenda_val = (
        fazenda
        if fazenda in FazendaEnum._value2member_map_
        else FazendaEnum.TIZIU.value
    )
    default_rows = [{"numero": "", "peso_kg": ""} for _ in range(5)]
    return templates.TemplateResponse(
        request=request,
        name="animais/lote.html",
        context={
            "fazenda": fazenda_val,
            "data": date.today().isoformat(),
            "rows": default_rows,
            "error": None,
            "duplicate_numeros": set(),
        },
    )


@router.post(
    "/animais/lote",
    response_class=HTMLResponse,
    summary="Cadastrar animais em lote com peso inicial",
)
@router.post(
    "/animais/lote/novo",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def create_animais_lote_submit(
    request: Request,
    fazenda: str = Form(FazendaEnum.TIZIU.value),
    data: str = Form(""),
    numeros: list[str] = Form(default=[]),
    pesos: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    rows: list[dict[str, str]] = []
    max_len = max(len(numeros), len(pesos), 1)
    for i in range(max_len):
        num = numeros[i].strip() if i < len(numeros) else ""
        peso = pesos[i].strip() if i < len(pesos) else ""
        rows.append(
            {
                "numero": num,
                "peso_kg": peso,
            }
        )

    filled_rows = [r for r in rows if r["numero"] or r["peso_kg"]]
    duplicate_numeros: set[str] = set()

    try:
        if not filled_rows:
            raise DomainError("Preencha ao menos um animal e seu respectivo peso.")

        dt = _parse_date(data)
        if dt is None:
            raise DomainError("A data é obrigatória.")

        fazenda_enum = FazendaEnum(fazenda)
        itens_schema: list[AnimalLoteItem] = []

        for idx, r in enumerate(filled_rows, start=1):
            if not r["numero"]:
                raise DomainError(f"Linha {idx}: informe o número do animal.")
            if not r["peso_kg"]:
                raise DomainError(
                    f"Linha {idx} (Animal nº {r['numero']}): informe o peso em kg."
                )
            try:
                peso_dec = _parse_decimal(r["peso_kg"])
            except InvalidOperation as exc:
                raise DomainError(
                    f"Linha {idx} (Animal nº {r['numero']}): peso '{r['peso_kg']}' inválido."
                ) from exc

            if peso_dec is None or peso_dec <= 0:
                raise DomainError(
                    f"Linha {idx} (Animal nº {r['numero']}): o peso deve ser maior que zero."
                )

            itens_schema.append(
                AnimalLoteItem(
                    numero=r["numero"],
                    peso_kg=peso_dec,
                )
            )

        repo = AnimalRepository(db)
        found_map = repo.get_by_fazenda_and_numeros(
            fazenda_enum, [item.numero for item in itens_schema]
        )
        seen_nums: set[str] = set()
        for item in itens_schema:
            if item.numero in found_map or item.numero in seen_nums:
                duplicate_numeros.add(item.numero)
            seen_nums.add(item.numero)

        lote_schema = AnimalLoteCreate(
            fazenda=fazenda_enum,
            data=dt,
            itens=itens_schema,
        )
        created = create_animais_em_lote(db, lote_schema)
        qtd = len(created)
        msg = urllib.parse.quote(
            f"{qtd} {'animal cadastrado' if qtd == 1 else 'animais cadastrados'} em lote com sucesso!"
        )
        return RedirectResponse(url=f"/?msg={msg}", status_code=303)

    except (DomainError, ValidationError, ValueError) as exc:
        if isinstance(exc, DomainError):
            error_msg = exc.message
        elif isinstance(exc, ValidationError):
            error_msg = exc.errors()[0].get("msg", "Dados inválidos no lote.")
        else:
            error_msg = str(exc)

        display_rows = filled_rows if filled_rows else rows
        while len(display_rows) < 3:
            display_rows.append({"numero": "", "peso_kg": ""})

        return templates.TemplateResponse(
            request=request,
            name="animais/lote.html",
            context={
                "fazenda": fazenda,
                "data": data,
                "rows": display_rows,
                "error": error_msg,
                "duplicate_numeros": duplicate_numeros,
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

    # Dados em ordem cronológica (da mais antiga para a mais recente) para o gráfico
    pesagens_grafico = [
        {
            "data": item["pesagem"].data_pesagem.strftime("%d/%m/%Y"),
            "peso_kg": float(item["pesagem"].peso_kg),
            "variacao_kg": float(item["variacao_kg"]) if item["variacao_kg"] is not None else None,
            "pasto": item["pesagem"].pasto.nome if item["pesagem"].pasto else None,
            "observacao": item["pesagem"].observacao or None,
        }
        for item in reversed(pesagens_com_variacao)
    ]
    ganho_total_kg = (
        (pesagens_list[0].peso_kg - pesagens_list[-1].peso_kg)
        if len(pesagens_list) >= 2
        else None
    )

    return templates.TemplateResponse(
        request=request,
        name="animais/detail.html",
        context={
            "animal": animal,
            "pesagens_com_variacao": pesagens_com_variacao,
            "pesagens_grafico": pesagens_grafico,
            "primeira_pesagem": pesagens_list[-1] if pesagens_list else None,
            "ultima_pesagem": pesagens_list[0] if pesagens_list else None,
            "ganho_total_kg": ganho_total_kg,
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

