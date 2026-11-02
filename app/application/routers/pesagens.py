from datetime import date
from decimal import Decimal, InvalidOperation
import html
import urllib.parse
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.application.schemas.pesagem import (
    PesagemCreate,
    PesagemLoteCreate,
    PesagemLoteItem,
)
from app.application.templating import templates
from app.domain.models.enums import FazendaEnum
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.use_cases.exceptions import DomainError, NotFoundError
from app.domain.use_cases.pesagem_use_cases import (
    create_pesagem_individual,
    create_pesagens_em_lote,
    delete_pesagem,
)
from app.infrastructure.database import get_db

router = APIRouter(tags=["Pesagens"])


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


@router.post(
    "/animais/{animal_id}/pesagens",
    summary="Registrar pesagem individual para um animal",
)
def create_pesagem_individual_submit(
    animal_id: uuid.UUID,
    data_pesagem: str = Form(""),
    peso_kg: str = Form(""),
    observacao: str = Form(""),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    target_url = redirect_to if redirect_to.startswith("/") else f"/animais/{animal_id}"
    sep = "&" if "?" in target_url else "?"

    try:
        dt_pesagem = _parse_date(data_pesagem)
        if dt_pesagem is None:
            raise DomainError("Informe a data da pesagem.")
        peso_dec = _parse_decimal(peso_kg)
        if peso_dec is None or peso_dec <= 0:
            raise DomainError("Informe um peso válido maior que zero.")

        schema = PesagemCreate(
            animal_id=animal_id,
            data_pesagem=dt_pesagem,
            peso_kg=peso_dec,
            observacao=observacao,
        )
        create_pesagem_individual(db, schema)
        msg = urllib.parse.quote("Pesagem registrada com sucesso!")
        return RedirectResponse(url=f"{target_url}{sep}msg={msg}", status_code=303)

    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    except (DomainError, ValidationError, InvalidOperation, ValueError) as exc:
        if isinstance(exc, DomainError):
            err_str = exc.message
        elif isinstance(exc, InvalidOperation):
            err_str = "Valor de peso inválido."
        else:
            err_str = "Dados inválidos para registro de pesagem."
        err_param = urllib.parse.quote(err_str)
        return RedirectResponse(
            url=f"/animais/{animal_id}?error={err_param}", status_code=303
        )


@router.post(
    "/pesagens/{pesagem_id}/excluir",
    summary="Excluir uma pesagem",
)
def delete_pesagem_submit(
    pesagem_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        animal_id = delete_pesagem(db, pesagem_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    msg = urllib.parse.quote("Pesagem excluída com sucesso.")
    return RedirectResponse(url=f"/animais/{animal_id}?msg={msg}", status_code=303)


@router.get(
    "/pesagens/lote",
    response_class=HTMLResponse,
    summary="Tela de lançamento de pesagem em lote",
)
def pesagem_lote_form(
    request: Request,
    fazenda: str | None = Query(None),
) -> HTMLResponse:
    fazenda_val = (
        fazenda
        if fazenda in FazendaEnum._value2member_map_
        else FazendaEnum.TIZIU.value
    )
    default_rows = [{"numero": "", "peso_kg": "", "observacao": ""} for _ in range(5)]
    return templates.TemplateResponse(
        request=request,
        name="pesagens/lote.html",
        context={
            "fazenda": fazenda_val,
            "data_pesagem": date.today().isoformat(),
            "observacao_padrao": "",
            "rows": default_rows,
            "error": None,
            "missing_numeros": set(),
        },
    )


@router.post(
    "/pesagens/lote",
    response_class=HTMLResponse,
    summary="Processar lançamento de pesagens em lote",
)
def pesagem_lote_submit(
    request: Request,
    fazenda: str = Form(FazendaEnum.TIZIU.value),
    data_pesagem: str = Form(""),
    observacao_padrao: str = Form(""),
    numeros: list[str] = Form(default=[]),
    pesos: list[str] = Form(default=[]),
    observacoes: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    rows: list[dict[str, str]] = []
    max_len = max(len(numeros), len(pesos), len(observacoes), 1)
    for i in range(max_len):
        num = numeros[i].strip() if i < len(numeros) else ""
        peso = pesos[i].strip() if i < len(pesos) else ""
        obs = observacoes[i].strip() if i < len(observacoes) else ""
        rows.append({"numero": num, "peso_kg": peso, "observacao": obs})

    # Filtra apenas linhas que tiveram algum campo preenchido
    filled_rows = [r for r in rows if r["numero"] or r["peso_kg"]]
    missing_numeros: set[str] = set()

    try:
        if not filled_rows:
            raise DomainError("Preencha ao menos um animal e seu respectivo peso.")

        dt_pesagem = _parse_date(data_pesagem)
        if dt_pesagem is None:
            raise DomainError("A data da pesagem do lote é obrigatória.")

        fazenda_enum = FazendaEnum(fazenda)
        itens_schema: list[PesagemLoteItem] = []

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
                PesagemLoteItem(
                    numero=r["numero"],
                    peso_kg=peso_dec,
                    observacao=r["observacao"] or None,
                )
            )

        # Verifica quais números não existem para destacar visualmente no form em caso de erro
        repo = AnimalRepository(db)
        found_map = repo.get_by_fazenda_and_numeros(
            fazenda_enum, [item.numero for item in itens_schema]
        )
        for item in itens_schema:
            if item.numero not in found_map:
                missing_numeros.add(item.numero)

        lote_schema = PesagemLoteCreate(
            fazenda=fazenda_enum,
            data_pesagem=dt_pesagem,
            observacao_padrao=observacao_padrao,
            itens=itens_schema,
        )
        created = create_pesagens_em_lote(db, lote_schema)
        qtd = len(created)
        msg = urllib.parse.quote(
            f"{qtd} {'pesagem registrada' if qtd == 1 else 'pesagens registradas'} em lote com sucesso!"
        )
        return RedirectResponse(
            url=f"/?fazenda={fazenda_enum.value}&msg={msg}", status_code=303
        )

    except (DomainError, ValidationError, ValueError) as exc:
        if isinstance(exc, DomainError):
            error_msg = exc.message
        elif isinstance(exc, ValidationError):
            error_msg = exc.errors()[0].get("msg", "Dados inválidos no lote.")
        else:
            error_msg = str(exc)

        display_rows = filled_rows if filled_rows else rows
        while len(display_rows) < 3:
            display_rows.append({"numero": "", "peso_kg": "", "observacao": ""})

        return templates.TemplateResponse(
            request=request,
            name="pesagens/lote.html",
            context={
                "fazenda": fazenda,
                "data_pesagem": data_pesagem,
                "observacao_padrao": observacao_padrao,
                "rows": display_rows,
                "error": error_msg,
                "missing_numeros": missing_numeros,
            },
            status_code=422,
        )


@router.get(
    "/htmx/animal-lookup",
    response_class=HTMLResponse,
    summary="Consulta rápida HTMX de animal por fazenda e número",
)
def htmx_animal_lookup(
    fazenda: str = Query(""),
    numero: str = Query(""),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    num_clean = numero.strip()
    if not num_clean or fazenda not in FazendaEnum._value2member_map_:
        return HTMLResponse(content="")

    repo = AnimalRepository(db)
    animal = repo.get_by_fazenda_and_numero(FazendaEnum(fazenda), num_clean)
    if animal is None:
        safe_num = html.escape(num_clean)
        return HTMLResponse(
            content=(
                f'<span class="inline-flex items-center gap-1 text-xs font-medium text-rose-600">'
                f"✕ Nº {safe_num} não encontrado nesta fazenda</span>"
            )
        )

    cat_label = html.escape(animal.categoria.label)
    status_label = html.escape(animal.status.label)
    color_cls = (
        "text-emerald-700"
        if animal.status.value == "ativo"
        else "text-amber-700"
    )
    return HTMLResponse(
        content=(
            f'<span class="inline-flex items-center gap-1 text-xs font-medium {color_cls}">'
            f"✓ {cat_label} ({status_label})</span>"
        )
    )

