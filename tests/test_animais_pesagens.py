from datetime import date
from decimal import Decimal
import uuid

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy.orm import Session

from app.application.routers.animais import _parse_decimal as animais_parse_decimal
from app.application.routers.pesagens import _parse_decimal as pesagens_parse_decimal
from app.application.schemas.animal import AnimalCreate, AnimalUpdate
from app.application.schemas.pesagem import (
    PesagemCreate,
    PesagemLoteCreate,
    PesagemLoteItem,
)
from app.domain.models.animal import Animal
from app.domain.models.enums import CategoriaAnimalEnum, FazendaEnum, StatusAnimalEnum
from app.domain.models.pesagem import Pesagem
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.use_cases.animal_use_cases import delete_animal, update_animal
from app.domain.use_cases.exceptions import DomainError, NotFoundError
from app.domain.use_cases.pesagem_use_cases import (
    create_pesagem_individual,
    delete_pesagem,
)


def test_create_animal_with_initial_weight_and_list(client: TestClient) -> None:
    # Cadastra animal com peso inicial junto
    resp = client.post(
        "/animais/novo",
        data={
            "numero": "101",
            "fazenda": "tiziu",
            "categoria": "novilha",
            "status": "ativo",
            "data_entrada": "2026-10-01",
            "observacoes": "Lote A",
            "peso_inicial_kg": "285.50",
            "data_pesagem_inicial": "2026-10-01",
            "observacao_pesagem": "Peso de entrada",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "101" in resp.text
    assert "Lote A" not in resp.text
    assert "285,50 kg" in resp.text
    assert "Novilha" in resp.text
    assert "Tiziu" in resp.text


def test_duplicate_animal_numero_same_fazenda_rejected(client: TestClient) -> None:
    payload = {
        "numero": "202",
        "fazenda": "ns_penha",
        "categoria": "vaca",
        "status": "ativo",
        "data_entrada": "2026-10-10",
    }
    r1 = client.post("/animais/novo", data=payload, follow_redirects=False)
    assert r1.status_code == 303

    # Mesmo número na mesma fazenda deve retornar 422 com mensagem de erro
    r2 = client.post("/animais/novo", data=payload, follow_redirects=False)
    assert r2.status_code == 422
    assert "Já existe um animal cadastrado com o número &#39;202&#39;" in r2.text or "202" in r2.text

    # Mesmo número em outra fazenda é permitido
    payload_other_farm = {**payload, "fazenda": "tiziu"}
    r3 = client.post("/animais/novo", data=payload_other_farm, follow_redirects=False)
    assert r3.status_code == 303


def test_individual_pesagem_updates_latest_weight_in_list(
    client: TestClient, db_session: Session
) -> None:
    animal = Animal(
        numero="305",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 9, 1),
        categoria=CategoriaAnimalEnum.BEZERRO,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add(animal)
    db_session.commit()
    db_session.refresh(animal)

    # Primeira pesagem (mais antiga)
    client.post(
        f"/animais/{animal.id}/pesagens",
        data={
            "data_pesagem": "2026-09-15",
            "peso_kg": "180.00",
            "observacao": "Setembro",
        },
    )

    # Segunda pesagem (mais recente)
    client.post(
        f"/animais/{animal.id}/pesagens",
        data={
            "data_pesagem": "2026-10-15",
            "peso_kg": "205.75",
            "observacao": "Outubro",
        },
    )

    # Na listagem deve aparecer a pesagem mais recente (205,75 kg)
    list_resp = client.get("/")
    assert list_resp.status_code == 200
    assert "205,75 kg" in list_resp.text
    assert "15/10/2026" in list_resp.text

    # Nos detalhes devem aparecer ambas as pesagens e a evolução (+25,75 kg)
    detail_resp = client.get(f"/animais/{animal.id}")
    assert detail_resp.status_code == 200
    assert "180,00 kg" in detail_resp.text
    assert "205,75 kg" in detail_resp.text
    assert "+25,75 kg" in detail_resp.text


def test_pesagem_em_lote_success_and_missing_validation(
    client: TestClient, db_session: Session
) -> None:
    a1 = Animal(
        numero="10",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 8, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    a2 = Animal(
        numero="20",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 8, 1),
        categoria=CategoriaAnimalEnum.TOURO,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add_all([a1, a2])
    db_session.commit()

    # Tenta lançar lote com um número inexistente ('999')
    bad_resp = client.post(
        "/pesagens/lote",
        data={
            "fazenda": "tiziu",
            "data_pesagem": "2026-11-01",
            "observacao_padrao": "Lote Nov",
            "numeros": ["10", "999"],
            "pesos": ["420", "510"],
            "observacoes": ["", ""],
        },
    )
    assert bad_resp.status_code == 422
    assert "999" in bad_resp.text

    # Agora lança lote válido com animais 10 e 20 (e uma linha vazia que deve ser ignorada)
    ok_resp = client.post(
        "/pesagens/lote",
        data={
            "fazenda": "tiziu",
            "data_pesagem": "2026-11-01",
            "observacao_padrao": "Lote Nov",
            "numeros": ["10", "20", ""],
            "pesos": ["420.00", "615.50", ""],
            "observacoes": ["", "Touro reprodutor", ""],
        },
        follow_redirects=True,
    )
    assert ok_resp.status_code == 200
    assert "420,00 kg" in ok_resp.text
    assert "615,50 kg" in ok_resp.text


def test_edit_and_delete_animal(client: TestClient, db_session: Session) -> None:
    animal = Animal(
        numero="500",
        fazenda=FazendaEnum.NS_PENHA,
        data_entrada=date(2026, 5, 1),
        categoria=CategoriaAnimalEnum.BEZERRO,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add(animal)
    db_session.commit()
    db_session.refresh(animal)

    # Edita status para abatido e categoria para novilha
    edit_resp = client.post(
        f"/animais/{animal.id}/editar",
        data={
            "numero": "500",
            "fazenda": "ns_penha",
            "categoria": "novilha",
            "status": "abatido",
            "data_entrada": "2026-05-01",
            "observacoes": "Abatido em nov/2026",
        },
        follow_redirects=True,
    )
    assert edit_resp.status_code == 200
    assert "Abatido" in edit_resp.text
    assert "Novilha" in edit_resp.text

    # Exclui o animal
    del_resp = client.post(f"/animais/{animal.id}/excluir", follow_redirects=True)
    assert del_resp.status_code == 200
    assert f"/animais/{animal.id}" not in del_resp.text
    assert "Nenhum animal encontrado" in del_resp.text


def test_pagination_animais(client: TestClient, db_session: Session) -> None:
    for i in range(1, 21):
        db_session.add(
            Animal(
                numero=f"B-{i:02d}",
                fazenda=FazendaEnum.TIZIU,
                data_entrada=date(2026, 10, 1),
                categoria=CategoriaAnimalEnum.VACA,
                status=StatusAnimalEnum.ATIVO,
            )
        )
    db_session.commit()

    page1 = client.get("/?page=1&page_size=15")
    assert page1.status_code == 200
    assert "Página" in page1.text
    assert "B-01" in page1.text

    page2 = client.get("/?page=2&page_size=15")
    assert page2.status_code == 200
    assert "B-16" in page2.text


def test_parse_helpers_and_schemas_validation() -> None:
    assert animais_parse_decimal(None) is None
    assert pesagens_parse_decimal(None) is None
    assert pesagens_parse_decimal("   ") is None

    with pytest.raises(ValidationError):
        AnimalCreate(
            numero="   ",
            fazenda=FazendaEnum.TIZIU,
            data_entrada=date(2026, 10, 1),
            categoria=CategoriaAnimalEnum.BEZERRO,
        )

    with pytest.raises(ValidationError):
        AnimalCreate(
            numero="10",
            fazenda=FazendaEnum.TIZIU,
            data_entrada=date(2026, 10, 1),
            categoria=CategoriaAnimalEnum.BEZERRO,
            peso_inicial_kg=Decimal("0"),
        )

    with pytest.raises(ValidationError):
        AnimalUpdate(
            numero="   ",
            fazenda=FazendaEnum.TIZIU,
            data_entrada=date(2026, 10, 1),
            categoria=CategoriaAnimalEnum.BEZERRO,
            status=StatusAnimalEnum.ATIVO,
        )

    upd = AnimalUpdate(
        numero="10",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.BEZERRO,
        status=StatusAnimalEnum.ATIVO,
        observacoes=None,
    )
    assert upd.observacoes is None

    pc = PesagemCreate(
        animal_id=uuid.uuid4(),
        data_pesagem=date(2026, 10, 1),
        peso_kg=Decimal("200"),
        observacao=None,
    )
    assert pc.observacao is None

    with pytest.raises(ValidationError):
        PesagemLoteItem(numero="   ", peso_kg=Decimal("200"))

    plc = PesagemLoteCreate(
        fazenda=FazendaEnum.TIZIU,
        data_pesagem=date(2026, 10, 1),
        observacao_padrao=None,
        itens=[PesagemLoteItem(numero="10", peso_kg=Decimal("200"))],
    )
    assert plc.observacao_padrao is None


def test_repository_and_use_cases_edge_cases(db_session: Session) -> None:
    repo = AnimalRepository(db_session)
    assert repo.get_by_fazenda_and_numeros(FazendaEnum.TIZIU, ["", "   "]) == {}

    a1 = Animal(
        numero="111",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    a2 = Animal(
        numero="222",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.NOVILHA,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add_all([a1, a2])
    db_session.commit()
    db_session.refresh(a1)
    db_session.refresh(a2)

    paginated = repo.list_paginated(
        page=99,
        page_size=15,
        q="11",
        fazenda=FazendaEnum.TIZIU,
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    assert paginated.page == 1
    assert paginated.total == 1

    # update_animal not found
    with pytest.raises(NotFoundError):
        update_animal(
            db_session,
            uuid.uuid4(),
            AnimalUpdate(
                numero="999",
                fazenda=FazendaEnum.TIZIU,
                data_entrada=date(2026, 10, 1),
                categoria=CategoriaAnimalEnum.VACA,
                status=StatusAnimalEnum.ATIVO,
            ),
        )

    # update_animal duplicate numero on same fazenda
    with pytest.raises(DomainError):
        update_animal(
            db_session,
            a1.id,
            AnimalUpdate(
                numero="222",
                fazenda=FazendaEnum.TIZIU,
                data_entrada=date(2026, 10, 1),
                categoria=CategoriaAnimalEnum.VACA,
                status=StatusAnimalEnum.ATIVO,
            ),
        )

    # delete_animal not found
    with pytest.raises(NotFoundError):
        delete_animal(db_session, uuid.uuid4())

    # create_pesagem_individual not found
    with pytest.raises(NotFoundError):
        create_pesagem_individual(
            db_session,
            PesagemCreate(
                animal_id=uuid.uuid4(),
                data_pesagem=date(2026, 10, 1),
                peso_kg=Decimal("250"),
            ),
        )

    # delete_pesagem not found
    with pytest.raises(NotFoundError):
        delete_pesagem(db_session, uuid.uuid4())


def test_animais_router_forms_and_error_branches(
    client: TestClient, db_session: Session
) -> None:
    # GET /animais/novo
    form_resp = client.get("/animais/novo")
    assert form_resp.status_code == 200
    assert "form" in form_resp.text

    # POST /animais/novo sem data_entrada -> DomainError
    r_no_date = client.post(
        "/animais/novo",
        data={
            "numero": "10",
            "fazenda": "tiziu",
            "categoria": "bezerro",
            "status": "ativo",
            "data_entrada": "",
        },
    )
    assert r_no_date.status_code == 422
    assert "A data de entrada é obrigatória" in r_no_date.text

    # POST /animais/novo com peso inválido -> InvalidOperation
    r_bad_weight = client.post(
        "/animais/novo",
        data={
            "numero": "10",
            "fazenda": "tiziu",
            "categoria": "bezerro",
            "status": "ativo",
            "data_entrada": "2026-10-01",
            "peso_inicial_kg": "peso_invalido",
        },
    )
    assert r_bad_weight.status_code == 422
    assert "Valor de peso inválido" in r_bad_weight.text

    # POST /animais/novo com erro de validação Pydantic (numero vazio) -> ValidationError
    r_val_err = client.post(
        "/animais/novo",
        data={
            "numero": "   ",
            "fazenda": "tiziu",
            "categoria": "bezerro",
            "status": "ativo",
            "data_entrada": "2026-10-01",
        },
    )
    assert r_val_err.status_code == 422

    # POST /animais/novo com ValueError (fazenda inválida)
    r_val_exc = client.post(
        "/animais/novo",
        data={
            "numero": "10",
            "fazenda": "fazenda_inexistente",
            "categoria": "bezerro",
            "status": "ativo",
            "data_entrada": "2026-10-01",
        },
    )
    assert r_val_exc.status_code == 422

    # Rotas com animal_id inexistente -> 404
    fake_id = uuid.uuid4()
    assert client.get(f"/animais/{fake_id}").status_code == 404
    assert client.get(f"/animais/{fake_id}/editar").status_code == 404
    assert client.post(f"/animais/{fake_id}/editar", data={}).status_code == 404
    assert client.post(f"/animais/{fake_id}/excluir").status_code == 404

    # Cria animal para testar GET e erros do POST /animais/{id}/editar
    animal = Animal(
        numero="700",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.BEZERRO,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add(animal)
    db_session.commit()
    db_session.refresh(animal)

    edit_get = client.get(f"/animais/{animal.id}/editar")
    assert edit_get.status_code == 200
    assert "700" in edit_get.text

    # POST editar sem data_entrada -> DomainError
    edit_no_date = client.post(
        f"/animais/{animal.id}/editar",
        data={
            "numero": "700",
            "fazenda": "tiziu",
            "categoria": "bezerro",
            "status": "ativo",
            "data_entrada": "",
        },
    )
    assert edit_no_date.status_code == 422
    assert "A data de entrada é obrigatória" in edit_no_date.text

    # POST editar com ValidationError (numero em branco)
    edit_val_err = client.post(
        f"/animais/{animal.id}/editar",
        data={
            "numero": "   ",
            "fazenda": "tiziu",
            "categoria": "bezerro",
            "status": "ativo",
            "data_entrada": "2026-10-01",
        },
    )
    assert edit_val_err.status_code == 422

    # POST editar com ValueError (fazenda inválida)
    edit_value_err = client.post(
        f"/animais/{animal.id}/editar",
        data={
            "numero": "700",
            "fazenda": "invalida",
            "categoria": "bezerro",
            "status": "ativo",
            "data_entrada": "2026-10-01",
        },
    )
    assert edit_value_err.status_code == 422


def test_pesagens_router_and_htmx_branches(
    client: TestClient, db_session: Session
) -> None:
    animal_ativo = Animal(
        numero="801",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    animal_abatido = Animal(
        numero="802",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.TOURO,
        status=StatusAnimalEnum.ABATIDO,
    )
    db_session.add_all([animal_ativo, animal_abatido])
    db_session.commit()
    db_session.refresh(animal_ativo)
    db_session.refresh(animal_abatido)

    # Pesagem individual em animal inexistente -> 404
    fake_id = uuid.uuid4()
    resp_404 = client.post(
        f"/animais/{fake_id}/pesagens",
        data={"data_pesagem": "2026-10-10", "peso_kg": "300"},
    )
    assert resp_404.status_code == 404

    # Pesagem individual sem data_pesagem -> redirect com error (DomainError)
    r_no_dt = client.post(
        f"/animais/{animal_ativo.id}/pesagens",
        data={"data_pesagem": "", "peso_kg": "300"},
        follow_redirects=False,
    )
    assert r_no_dt.status_code == 303
    assert "error=" in r_no_dt.headers["location"]

    # Pesagem individual com peso <= 0 -> redirect com error (DomainError)
    r_zero_w = client.post(
        f"/animais/{animal_ativo.id}/pesagens",
        data={"data_pesagem": "2026-10-10", "peso_kg": "0"},
        follow_redirects=False,
    )
    assert r_zero_w.status_code == 303
    assert "error=" in r_zero_w.headers["location"]

    # Pesagem individual com peso inválido -> InvalidOperation
    r_inv_w = client.post(
        f"/animais/{animal_ativo.id}/pesagens",
        data={"data_pesagem": "2026-10-10", "peso_kg": "abc"},
        follow_redirects=False,
    )
    assert r_inv_w.status_code == 303
    assert "error=" in r_inv_w.headers["location"]

    # Pesagem individual com data inválida -> ValueError
    r_inv_dt = client.post(
        f"/animais/{animal_ativo.id}/pesagens",
        data={"data_pesagem": "data-invalida", "peso_kg": "300"},
        follow_redirects=False,
    )
    assert r_inv_dt.status_code == 303
    assert "error=" in r_inv_dt.headers["location"]

    # Cria pesagem e depois exclui via rota
    pesagem = Pesagem(
        animal_id=animal_ativo.id,
        data_pesagem=date(2026, 10, 10),
        peso_kg=Decimal("350.00"),
    )
    db_session.add(pesagem)
    db_session.commit()
    db_session.refresh(pesagem)

    del_ok = client.post(
        f"/pesagens/{pesagem.id}/excluir",
        follow_redirects=False,
    )
    assert del_ok.status_code == 303

    # Excluir pesagem já excluída / inexistente -> 404
    del_404 = client.post(f"/pesagens/{pesagem.id}/excluir")
    assert del_404.status_code == 404

    # GET /pesagens/lote
    lote_get = client.get("/pesagens/lote?fazenda=tiziu")
    assert lote_get.status_code == 200

    # POST /pesagens/lote sem nenhuma linha preenchida
    lote_empty = client.post(
        "/pesagens/lote",
        data={"fazenda": "tiziu", "data_pesagem": "2026-10-10", "numeros": [""], "pesos": [""]},
    )
    assert lote_empty.status_code == 422
    assert "Preencha ao menos um animal" in lote_empty.text

    # POST /pesagens/lote sem data_pesagem
    lote_no_dt = client.post(
        "/pesagens/lote",
        data={"fazenda": "tiziu", "data_pesagem": "", "numeros": ["801"], "pesos": ["300"]},
    )
    assert lote_no_dt.status_code == 422
    assert "A data da pesagem do lote é obrigatória" in lote_no_dt.text

    # POST /pesagens/lote linha sem número
    lote_no_num = client.post(
        "/pesagens/lote",
        data={"fazenda": "tiziu", "data_pesagem": "2026-10-10", "numeros": [""], "pesos": ["300"]},
    )
    assert lote_no_num.status_code == 422
    assert "informe o número do animal" in lote_no_num.text

    # POST /pesagens/lote linha sem peso
    lote_no_peso = client.post(
        "/pesagens/lote",
        data={"fazenda": "tiziu", "data_pesagem": "2026-10-10", "numeros": ["801"], "pesos": [""]},
    )
    assert lote_no_peso.status_code == 422
    assert "informe o peso em kg" in lote_no_peso.text

    # POST /pesagens/lote linha com peso não numérico (InvalidOperation)
    lote_bad_peso = client.post(
        "/pesagens/lote",
        data={"fazenda": "tiziu", "data_pesagem": "2026-10-10", "numeros": ["801"], "pesos": ["xyz"]},
    )
    assert lote_bad_peso.status_code == 422
    assert "inválido" in lote_bad_peso.text

    # POST /pesagens/lote linha com peso <= 0
    lote_zero_peso = client.post(
        "/pesagens/lote",
        data={"fazenda": "tiziu", "data_pesagem": "2026-10-10", "numeros": ["801"], "pesos": ["-10"]},
    )
    assert lote_zero_peso.status_code == 422
    assert "maior que zero" in lote_zero_peso.text

    # POST /pesagens/lote com ValidationError (numero > 50 chars)
    lote_val_err = client.post(
        "/pesagens/lote",
        data={
            "fazenda": "tiziu",
            "data_pesagem": "2026-10-10",
            "numeros": ["X" * 60],
            "pesos": ["300"],
        },
    )
    assert lote_val_err.status_code == 422

    # POST /pesagens/lote com ValueError (fazenda inválida)
    lote_value_err = client.post(
        "/pesagens/lote",
        data={
            "fazenda": "invalida",
            "data_pesagem": "2026-10-10",
            "numeros": ["801"],
            "pesos": ["300"],
        },
    )
    assert lote_value_err.status_code == 422

    # HTMX lookup: vazio / fazenda inválida
    htmx_empty = client.get("/htmx/animal-lookup?fazenda=tiziu&numero=")
    assert htmx_empty.status_code == 200
    assert htmx_empty.text == ""

    # HTMX lookup: animal não encontrado
    htmx_missing = client.get("/htmx/animal-lookup?fazenda=tiziu&numero=9999")
    assert htmx_missing.status_code == 200
    assert "não encontrado" in htmx_missing.text

    # HTMX lookup: animal ativo
    htmx_active = client.get("/htmx/animal-lookup?fazenda=tiziu&numero=801")
    assert htmx_active.status_code == 200
    assert "text-emerald-700" in htmx_active.text

    # HTMX lookup: animal não ativo (vendido)
    htmx_inactive = client.get("/htmx/animal-lookup?fazenda=tiziu&numero=802")
    assert htmx_inactive.status_code == 200
    assert "text-amber-700" in htmx_inactive.text


def test_seed_database_idempotent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import runpy

    from app.infrastructure import seed
    from tests.conftest import TestingSessionLocal

    monkeypatch.setattr("app.infrastructure.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(seed, "SessionLocal", TestingSessionLocal)

    # Primeira execução via main() insere os registros iniciais
    seed.main()

    # Segunda execução via __main__ deve ser idempotente e não duplicar registros
    runpy.run_path(seed.__file__, run_name="__main__")

    animais_2, pesagens_2 = seed.seed_database(db_session)
    assert animais_2 == 0
    assert pesagens_2 == 0




