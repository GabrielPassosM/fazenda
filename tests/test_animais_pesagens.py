from datetime import date
from decimal import Decimal
import uuid

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest
from sqlalchemy.orm import Session

from app.application.routers.animais import _parse_decimal as animais_parse_decimal
from app.application.routers.pesagens import _parse_decimal as pesagens_parse_decimal
from app.application.schemas.animal import (
    AnimalCreate,
    AnimalLoteCreate,
    AnimalLoteItem,
    AnimalUpdate,
)
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

    # Nos detalhes devem aparecer ambas as pesagens e a evolução (+25,75 kg), além da alternância Lista/Gráfico
    detail_resp = client.get(f"/animais/{animal.id}")
    assert detail_resp.status_code == 200
    assert "180,00 kg" in detail_resp.text
    assert "205,75 kg" in detail_resp.text
    assert "+25,75 kg" in detail_resp.text
    assert 'id="btn-view-lista"' in detail_resp.text
    assert 'id="btn-view-grafico"' in detail_resp.text
    assert 'id="pesagens-view-lista"' in detail_resp.text
    assert 'id="pesagens-view-grafico"' in detail_resp.text
    assert 'id="pesagens-chart-svg"' in detail_resp.text
    assert "PESAGENS_CHART_DATA" in detail_resp.text


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

    # Por padrão, /pesagens/lote exibe o histórico (inicialmente vazio) e o botão para adicionar
    empty_hist = client.get("/pesagens/lote")
    assert empty_hist.status_code == 200
    assert "Histórico de Pesagens em Lote" in empty_hist.text
    assert "Nenhuma pesagem em lote registrada" in empty_hist.text
    assert "Adicionar Pesagem em Lote" in empty_hist.text
    assert "/pesagens/lote/novo" in empty_hist.text

    # Acessa a tela de lançamento de pesagem em lote
    form_lote = client.get("/pesagens/lote/novo")
    assert form_lote.status_code == 200
    assert "Lançamento de Pesagem em Lote" in form_lote.text

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
    assert "Histórico de Pesagens em Lote" in ok_resp.text
    assert "Tiziu" in ok_resp.text
    assert "01/11/2026" in ok_resp.text
    assert "2 animais" in ok_resp.text
    assert "517,75 kg" in ok_resp.text
    assert "Lote Nov" in ok_resp.text

    # Verifica que na listagem geral do rebanho os pesos individuais foram atualizados
    rebanho_resp = client.get("/")
    assert rebanho_resp.status_code == 200
    assert "420,00 kg" in rebanho_resp.text
    assert "615,50 kg" in rebanho_resp.text

    # Verifica que o flag em_lote foi salvo como True nos registros criados
    db_session.expire_all()
    pesagens_salvas = db_session.query(Pesagem).all()
    assert len(pesagens_salvas) == 2
    assert all(p.em_lote is True for p in pesagens_salvas)


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


def test_list_animais_default_active_and_filter_other_status(
    client: TestClient, db_session: Session
) -> None:
    ativo = Animal(
        numero="A-01",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    abatido = Animal(
        numero="AB-02",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ABATIDO,
    )
    morto = Animal(
        numero="M-03",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.MORTO,
    )
    db_session.add_all([ativo, abatido, morto])
    db_session.commit()

    # Por padrão (sem parâmetro status), traz apenas os ativos
    default_resp = client.get("/")
    assert default_resp.status_code == 200
    assert "A-01" in default_resp.text
    assert "AB-02" not in default_resp.text
    assert "M-03" not in default_resp.text

    # Filtrando por status=abatido
    abatido_resp = client.get("/?status=abatido")
    assert abatido_resp.status_code == 200
    assert "AB-02" in abatido_resp.text
    assert "A-01" not in abatido_resp.text
    assert "M-03" not in abatido_resp.text

    # Filtrando por "Todos os status" (status="")
    all_resp = client.get("/?status=")
    assert all_resp.status_code == 200
    assert "A-01" in all_resp.text
    assert "AB-02" in all_resp.text
    assert "M-03" in all_resp.text



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

    # GET /pesagens/lote e /pesagens/lote/novo
    lote_get = client.get("/pesagens/lote?fazenda=tiziu")
    assert lote_get.status_code == 200
    lote_novo_get = client.get("/pesagens/lote/novo?fazenda=tiziu")
    assert lote_novo_get.status_code == 200

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

    # Simula animal existente sem pasto_id para cobrir backfill de pasto no seed
    animal_repo = AnimalRepository(db_session)
    existing_animal = animal_repo.get_by_fazenda_and_numero(FazendaEnum.TIZIU, "101")
    assert existing_animal is not None
    existing_animal.pasto_id = None
    db_session.commit()

    animais_2, pesagens_2 = seed.seed_database(db_session)
    assert animais_2 == 0
    assert pesagens_2 == 0
    db_session.refresh(existing_animal)
    assert existing_animal.pasto_id is not None


def test_pasto_crud_and_animal_relationship(
    client: TestClient, db_session: Session
) -> None:
    from app.application.schemas.pasto import PastoCreate, PastoUpdate
    from app.domain.repositories.pasto_repository import PastoRepository
    from app.domain.use_cases.animal_use_cases import create_animal
    from app.domain.use_cases.pasto_use_cases import (
        create_pasto,
        delete_pasto,
        update_pasto,
    )

    # Lista vazia inicialmente
    empty_resp = client.get("/pastos")
    assert empty_resp.status_code == 200
    assert "Nenhum pasto cadastrado" in empty_resp.text

    # Cadastra pasto via POST
    create_resp = client.post(
        "/pastos/novo",
        data={"nome": "Pasto da Represa"},
        follow_redirects=True,
    )
    assert create_resp.status_code == 200
    assert "Pasto da Represa" in create_resp.text

    pasto_repo = PastoRepository(db_session)
    pasto1 = pasto_repo.get_by_nome("Pasto da Represa")
    assert pasto1 is not None

    # Duplicado no cadastro -> 422 DomainError
    dup_resp = client.post("/pastos/novo", data={"nome": "Pasto da Represa"})
    assert dup_resp.status_code == 422
    assert "Já existe um pasto cadastrado" in dup_resp.text

    # Nome inválido (em branco) -> 422 ValidationError
    blank_resp = client.post("/pastos/novo", data={"nome": "   "})
    assert blank_resp.status_code == 422

    # Cadastra segundo pasto
    pasto2 = create_pasto(db_session, PastoCreate(nome="Pasto da Baixada"))

    # Formulário de edição de pasto
    edit_form = client.get(f"/pastos/{pasto1.id}/editar")
    assert edit_form.status_code == 200
    assert "Pasto da Represa" in edit_form.text

    # Edição com sucesso
    edit_ok = client.post(
        f"/pastos/{pasto1.id}/editar",
        data={"nome": "Pasto da Represa Novo"},
        follow_redirects=True,
    )
    assert edit_ok.status_code == 200
    assert "Pasto da Represa Novo" in edit_ok.text

    # Edição duplicando nome de outro pasto -> 422 DomainError
    edit_dup = client.post(
        f"/pastos/{pasto1.id}/editar",
        data={"nome": "Pasto da Baixada"},
    )
    assert edit_dup.status_code == 422
    assert "Já existe outro pasto" in edit_dup.text

    # Edição com nome em branco -> 422 ValidationError
    edit_blank = client.post(
        f"/pastos/{pasto1.id}/editar",
        data={"nome": "   "},
    )
    assert edit_blank.status_code == 422

    # Rotas com pasto inexistente -> 404
    fake_pasto_id = uuid.uuid4()
    assert client.get(f"/pastos/{fake_pasto_id}/editar").status_code == 404
    assert client.post(f"/pastos/{fake_pasto_id}/editar", data={"nome": "X"}).status_code == 404
    assert client.post(f"/pastos/{fake_pasto_id}/excluir").status_code == 404

    with pytest.raises(NotFoundError):
        update_pasto(db_session, fake_pasto_id, PastoUpdate(nome="Inexistente"))
    with pytest.raises(NotFoundError):
        delete_pasto(db_session, fake_pasto_id)

    # Cadastra animal vinculado ao pasto1 via rota
    animal_resp = client.post(
        "/animais/novo",
        data={
            "numero": "901",
            "fazenda": "tiziu",
            "categoria": "novilha",
            "status": "ativo",
            "data_entrada": "2026-10-01",
            "pasto_id": str(pasto1.id),
        },
        follow_redirects=True,
    )
    assert animal_resp.status_code == 200
    assert "Pasto da Represa Novo" in animal_resp.text

    # Filtra listagem de animais por pasto_id válido e inválido
    filter_ok = client.get(f"/?pasto_id={pasto1.id}")
    assert filter_ok.status_code == 200
    assert "901" in filter_ok.text

    filter_other = client.get(f"/?pasto_id={pasto2.id}")
    assert filter_other.status_code == 200
    assert "901" not in filter_other.text

    filter_invalid_uuid = client.get("/?pasto_id=uuid-invalido")
    assert filter_invalid_uuid.status_code == 200
    assert "901" in filter_invalid_uuid.text

    # Edita animal trocando para pasto2
    animal_repo = AnimalRepository(db_session)
    animal_901 = animal_repo.get_by_fazenda_and_numero(FazendaEnum.TIZIU, "901")
    assert animal_901 is not None
    assert animal_901.pasto_id == pasto1.id

    upd_animal_resp = client.post(
        f"/animais/{animal_901.id}/editar",
        data={
            "numero": "901",
            "fazenda": "tiziu",
            "categoria": "novilha",
            "status": "ativo",
            "data_entrada": "2026-10-01",
            "pasto_id": str(pasto2.id),
        },
        follow_redirects=True,
    )
    assert upd_animal_resp.status_code == 200
    assert "Pasto da Baixada" in upd_animal_resp.text

    # Exclui pasto2 e verifica que o animal continua existindo mas com pasto_id=None
    del_pasto_resp = client.post(f"/pastos/{pasto2.id}/excluir", follow_redirects=True)
    assert del_pasto_resp.status_code == 200
    db_session.expire_all()
    animal_after = animal_repo.get_by_id(animal_901.id)
    assert animal_after is not None
    assert animal_after.pasto_id is None

    # Use cases de animal com pasto_id inexistente -> NotFoundError
    with pytest.raises(NotFoundError):
        create_animal(
            db_session,
            AnimalCreate(
                numero="999",
                fazenda=FazendaEnum.TIZIU,
                data_entrada=date(2026, 10, 1),
                categoria=CategoriaAnimalEnum.BEZERRO,
                pasto_id=uuid.uuid4(),
            ),
        )

    with pytest.raises(NotFoundError):
        update_animal(
            db_session,
            animal_901.id,
            AnimalUpdate(
                numero="901",
                fazenda=FazendaEnum.TIZIU,
                data_entrada=date(2026, 10, 1),
                categoria=CategoriaAnimalEnum.NOVILHA,
                status=StatusAnimalEnum.ATIVO,
                pasto_id=uuid.uuid4(),
            ),
        )

    # Pesagem individual selecionando um pasto específico (diferente do pasto atual do animal, sem alterar o do animal)
    pasto3 = create_pasto(db_session, PastoCreate(nome="Pasto Maternidade"))
    pesagem_pasto_resp = client.post(
        f"/animais/{animal_901.id}/pesagens",
        data={
            "data_pesagem": "2026-10-15",
            "peso_kg": "310.00",
            "pasto_id": str(pasto3.id),
            "observacao": "Pesado na maternidade",
        },
        follow_redirects=True,
    )
    assert pesagem_pasto_resp.status_code == 200
    assert "Pasto Maternidade" in pesagem_pasto_resp.text

    db_session.expire_all()
    animal_check = animal_repo.get_by_id(animal_901.id)
    assert animal_check is not None
    assert animal_check.pasto_id is None
    assert animal_check.pesagens[0].pasto_id == pasto3.id

    # Pesagem individual sem pasto selecionado (pasto_id="")
    pesagem_sem_pasto_resp = client.post(
        f"/animais/{animal_901.id}/pesagens",
        data={
            "data_pesagem": "2026-10-20",
            "peso_kg": "315.00",
            "pasto_id": "",
        },
        follow_redirects=True,
    )
    assert pesagem_sem_pasto_resp.status_code == 200

    # Pesagem em lote informando pastos por linha
    lote_pasto_resp = client.post(
        "/pesagens/lote",
        data={
            "fazenda": "tiziu",
            "data_pesagem": "2026-10-25",
            "numeros": ["901"],
            "pesos": ["322.00"],
            "pastos": [str(pasto1.id)],
            "observacoes": ["Lote com pasto"],
        },
        follow_redirects=True,
    )
    assert lote_pasto_resp.status_code == 200

    # Pesagem em lote com pasto inexistente -> 422 DomainError
    lote_bad_pasto = client.post(
        "/pesagens/lote",
        data={
            "fazenda": "tiziu",
            "data_pesagem": "2026-10-26",
            "numeros": ["901"],
            "pesos": ["325.00"],
            "pastos": [str(uuid.uuid4())],
            "observacoes": [""],
        },
    )
    assert lote_bad_pasto.status_code == 422
    assert "Pasto selecionado não encontrado" in lote_bad_pasto.text

    # create_pesagem_individual com pasto_id inexistente -> NotFoundError
    with pytest.raises(NotFoundError):
        create_pesagem_individual(
            db_session,
            PesagemCreate(
                animal_id=animal_901.id,
                data_pesagem=date(2026, 10, 27),
                peso_kg=Decimal("330.00"),
                pasto_id=uuid.uuid4(),
            ),
        )


def test_rodizio_pastos_em_lote_e_em_cadeia(
    client: TestClient, db_session: Session
) -> None:
    from app.application.schemas.pasto import (
        PastoCreate,
        PastoRodizioCreate,
        PastoTransferenciaItem,
    )
    from app.domain.use_cases.pasto_use_cases import create_pasto, rodar_pastos

    pasto_a = create_pasto(db_session, PastoCreate(nome="Pasto A"))
    pasto_b = create_pasto(db_session, PastoCreate(nome="Pasto B"))
    pasto_c = create_pasto(db_session, PastoCreate(nome="Pasto C"))
    pasto_vazio = create_pasto(db_session, PastoCreate(nome="Pasto Vazio"))

    a1 = Animal(
        numero="A1",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
        pasto_id=pasto_a.id,
    )
    a2 = Animal(
        numero="A2",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.NOVILHA,
        status=StatusAnimalEnum.ATIVO,
        pasto_id=pasto_a.id,
    )
    b1 = Animal(
        numero="B1",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.TOURO,
        status=StatusAnimalEnum.ATIVO,
        pasto_id=pasto_b.id,
    )
    db_session.add_all([a1, a2, b1])
    db_session.commit()

    # 1. Rodízio em cadeia: Pasto A (2 animais) -> Pasto B, e Pasto B (1 animal) -> Pasto C (vazio)
    # Inclui uma linha em branco extra que deve ser ignorada
    resp_cadeia = client.post(
        "/pastos/rodizio",
        data={
            "origens": [str(pasto_a.id), str(pasto_b.id), ""],
            "destinos": [str(pasto_b.id), str(pasto_c.id), ""],
        },
        follow_redirects=True,
    )
    assert resp_cadeia.status_code == 200
    assert "Rodízio concluído (3 animais movimentados)" in resp_cadeia.text

    db_session.expire_all()
    animal_repo = AnimalRepository(db_session)
    assert animal_repo.get_by_id(a1.id).pasto_id == pasto_b.id
    assert animal_repo.get_by_id(a2.id).pasto_id == pasto_b.id
    # O animal original do Pasto B foi para o Pasto C sem se misturar com os que vieram do Pasto A
    assert animal_repo.get_by_id(b1.id).pasto_id == pasto_c.id

    # 2. Troca circular direta: Pasto B (2 animais) <-> Pasto C (1 animal)
    resp_ciclo = client.post(
        "/pastos/rodizio",
        data={
            "origens": [str(pasto_b.id), str(pasto_c.id)],
            "destinos": [str(pasto_c.id), str(pasto_b.id)],
        },
        follow_redirects=True,
    )
    assert resp_ciclo.status_code == 200
    db_session.expire_all()
    assert animal_repo.get_by_id(a1.id).pasto_id == pasto_c.id
    assert animal_repo.get_by_id(a2.id).pasto_id == pasto_c.id
    assert animal_repo.get_by_id(b1.id).pasto_id == pasto_b.id

    # 3. Movimentação simples de 1 animal (verifica singular "1 animal movimentado")
    resp_um = client.post(
        "/pastos/rodizio",
        data={
            "origens": [str(pasto_b.id)],
            "destinos": [str(pasto_a.id)],
        },
        follow_redirects=True,
    )
    assert resp_um.status_code == 200
    assert "1 animal movimentado" in resp_um.text
    db_session.expire_all()
    assert animal_repo.get_by_id(b1.id).pasto_id == pasto_a.id

    # 4. Validações de erro na rota POST /pastos/rodizio
    # Sem etapas preenchidas
    r_empty = client.post("/pastos/rodizio", data={"origens": [""], "destinos": [""]})
    assert r_empty.status_code == 422
    assert "Informe ao menos uma transferência" in r_empty.text

    # Etapa incompleta (origem preenchida, destino vazio)
    r_incomplete = client.post(
        "/pastos/rodizio",
        data={"origens": [str(pasto_a.id)], "destinos": [""]},
    )
    assert r_incomplete.status_code == 422
    assert "selecione o pasto de origem e o pasto de destino" in r_incomplete.text

    # UUID inválido
    r_bad_uuid = client.post(
        "/pastos/rodizio",
        data={"origens": ["uuid-invalido"], "destinos": [str(pasto_b.id)]},
    )
    assert r_bad_uuid.status_code == 422
    assert "Identificador de pasto inválido" in r_bad_uuid.text

    # Origem igual ao destino
    r_same = client.post(
        "/pastos/rodizio",
        data={"origens": [str(pasto_a.id)], "destinos": [str(pasto_a.id)]},
    )
    assert r_same.status_code == 422
    assert "deve ser diferente do pasto de origem" in r_same.text

    # Mesma origem repetida duas vezes no mesmo rodízio
    r_dup_orig = client.post(
        "/pastos/rodizio",
        data={
            "origens": [str(pasto_a.id), str(pasto_a.id)],
            "destinos": [str(pasto_b.id), str(pasto_c.id)],
        },
    )
    assert r_dup_orig.status_code == 422
    assert "não pode ser transferido mais de uma vez" in r_dup_orig.text

    # Pasto de origem vazio (sem animais alocados)
    r_empty_pasto = client.post(
        "/pastos/rodizio",
        data={"origens": [str(pasto_vazio.id)], "destinos": [str(pasto_a.id)]},
    )
    assert r_empty_pasto.status_code == 422
    assert "não possui animais alocados" in r_empty_pasto.text

    # Pasto de origem inexistente -> NotFoundError tratado como 422
    r_missing_orig = client.post(
        "/pastos/rodizio",
        data={"origens": [str(uuid.uuid4())], "destinos": [str(pasto_a.id)]},
    )
    assert r_missing_orig.status_code == 422
    assert "Pasto de origem não encontrado" in r_missing_orig.text

    # Pasto de destino inexistente -> NotFoundError
    with pytest.raises(NotFoundError):
        rodar_pastos(
            db_session,
            PastoRodizioCreate(
                etapas=[
                    PastoTransferenciaItem(
                        pasto_origem_id=pasto_a.id,
                        pasto_destino_id=uuid.uuid4(),
                    )
                ]
            ),
        )


def test_list_animais_filter_by_peso_min_and_peso_max(
    client: TestClient, db_session: Session
) -> None:
    a_leve = Animal(
        numero="W-100",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.BEZERRO,
        status=StatusAnimalEnum.ATIVO,
    )
    a_medio = Animal(
        numero="W-200",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.NOVILHA,
        status=StatusAnimalEnum.ATIVO,
    )
    a_pesado = Animal(
        numero="W-300",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.TOURO,
        status=StatusAnimalEnum.ATIVO,
    )
    a_sem_peso = Animal(
        numero="W-000",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add_all([a_leve, a_medio, a_pesado, a_sem_peso])
    db_session.commit()

    # a_leve tinha 150 kg antes e agora tem 180 kg (deve considerar o último peso: 180 kg)
    db_session.add_all(
        [
            Pesagem(
                animal_id=a_leve.id,
                data_pesagem=date(2026, 9, 1),
                peso_kg=Decimal("150.00"),
            ),
            Pesagem(
                animal_id=a_leve.id,
                data_pesagem=date(2026, 10, 15),
                peso_kg=Decimal("180.00"),
            ),
            Pesagem(
                animal_id=a_medio.id,
                data_pesagem=date(2026, 10, 15),
                peso_kg=Decimal("320.50"),
            ),
            Pesagem(
                animal_id=a_pesado.id,
                data_pesagem=date(2026, 10, 15),
                peso_kg=Decimal("510.00"),
            ),
        ]
    )
    db_session.commit()

    # 1. Apenas peso_min (ex: >= 300)
    resp_min = client.get("/?peso_min=300")
    assert resp_min.status_code == 200
    assert "W-200" in resp_min.text
    assert "W-300" in resp_min.text
    assert "W-100" not in resp_min.text
    assert "W-000" not in resp_min.text

    # 2. Apenas peso_max (ex: <= 320,50 com vírgula)
    resp_max = client.get("/?peso_max=320,50")
    assert resp_max.status_code == 200
    assert "W-100" in resp_max.text
    assert "W-200" in resp_max.text
    assert "W-300" not in resp_max.text
    assert "W-000" not in resp_max.text

    # 3. Ambos peso_min e peso_max (intervalo 200 a 400)
    resp_range = client.get("/?peso_min=200&peso_max=400")
    assert resp_range.status_code == 200
    assert "W-200" in resp_range.text
    assert "W-100" not in resp_range.text
    assert "W-300" not in resp_range.text
    assert "W-000" not in resp_range.text

    # 4. Valores inválidos para peso_min / peso_max são ignorados sem erro
    resp_invalid = client.get("/?peso_min=invalido&peso_max=xyz")
    assert resp_invalid.status_code == 200
    assert "W-100" in resp_invalid.text
    assert "W-200" in resp_invalid.text
    assert "W-300" in resp_invalid.text
    assert "W-000" in resp_invalid.text


def test_list_animais_ordering_by_data_entrada_and_peso(
    client: TestClient, db_session: Session
) -> None:
    a_antigo_pesado = Animal(
        numero="ORD-1",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 8, 1),
        categoria=CategoriaAnimalEnum.TOURO,
        status=StatusAnimalEnum.ATIVO,
    )
    a_medio_leve = Animal(
        numero="ORD-2",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 9, 1),
        categoria=CategoriaAnimalEnum.BEZERRO,
        status=StatusAnimalEnum.ATIVO,
    )
    a_recente_medio = Animal(
        numero="ORD-3",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 1),
        categoria=CategoriaAnimalEnum.NOVILHA,
        status=StatusAnimalEnum.ATIVO,
    )
    a_sem_peso = Animal(
        numero="ORD-4",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 10, 15),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add_all([a_antigo_pesado, a_medio_leve, a_recente_medio, a_sem_peso])
    db_session.commit()

    db_session.add_all(
        [
            Pesagem(
                animal_id=a_antigo_pesado.id,
                data_pesagem=date(2026, 10, 10),
                peso_kg=Decimal("550.00"),
            ),
            Pesagem(
                animal_id=a_medio_leve.id,
                data_pesagem=date(2026, 10, 10),
                peso_kg=Decimal("180.00"),
            ),
            Pesagem(
                animal_id=a_recente_medio.id,
                data_pesagem=date(2026, 10, 10),
                peso_kg=Decimal("320.00"),
            ),
        ]
    )
    db_session.commit()

    # 1. Padrão / data_entrada_desc: mais recente para mais antiga -> ORD-4, ORD-3, ORD-2, ORD-1
    r_desc = client.get("/?ordenar_por=data_entrada_desc")
    assert r_desc.status_code == 200
    assert (
        r_desc.text.index("ORD-4")
        < r_desc.text.index("ORD-3")
        < r_desc.text.index("ORD-2")
        < r_desc.text.index("ORD-1")
    )

    # 2. data_entrada_asc: mais antiga para mais recente -> ORD-1, ORD-2, ORD-3, ORD-4
    r_asc = client.get("/?ordenar_por=data_entrada_asc")
    assert r_asc.status_code == 200
    assert (
        r_asc.text.index("ORD-1")
        < r_asc.text.index("ORD-2")
        < r_asc.text.index("ORD-3")
        < r_asc.text.index("ORD-4")
    )

    # 3. peso_desc: maior peso para menor (sem pesagem no final) -> ORD-1 (550), ORD-3 (320), ORD-2 (180), ORD-4 (NULL)
    r_peso_desc = client.get("/?ordenar_por=peso_desc")
    assert r_peso_desc.status_code == 200
    assert (
        r_peso_desc.text.index("ORD-1")
        < r_peso_desc.text.index("ORD-3")
        < r_peso_desc.text.index("ORD-2")
        < r_peso_desc.text.index("ORD-4")
    )

    # 4. peso_asc: menor peso para maior (sem pesagem no final) -> ORD-2 (180), ORD-3 (320), ORD-1 (550), ORD-4 (NULL)
    r_peso_asc = client.get("/?ordenar_por=peso_asc")
    assert r_peso_asc.status_code == 200
    assert (
        r_peso_asc.text.index("ORD-2")
        < r_peso_asc.text.index("ORD-3")
        < r_peso_asc.text.index("ORD-1")
        < r_peso_asc.text.index("ORD-4")
    )

    # 5. Valor inválido faz fallback para data_entrada_desc
    r_invalid = client.get("/?ordenar_por=invalido")
    assert r_invalid.status_code == 200
    assert (
        r_invalid.text.index("ORD-4")
        < r_invalid.text.index("ORD-3")
        < r_invalid.text.index("ORD-2")
        < r_invalid.text.index("ORD-1")
    )
    # No modo encolhido (apenas fazenda/ordenação), #advanced-filters inicia oculto e o botão exibe "Mais filtros"
    assert 'id="btn-toggle-filters"' in r_invalid.text
    assert "Mais filtros" in r_invalid.text
    assert 'aria-expanded="false"' in r_invalid.text

    # Quando há um filtro avançado ativo (ex: peso_min), #advanced-filters inicia expandido ("Menos filtros")
    r_expanded = client.get("/?peso_min=200")
    assert r_expanded.status_code == 200
    assert "Menos filtros" in r_expanded.text
    assert 'aria-expanded="true"' in r_expanded.text


def test_historico_pesagens_em_lote_columns_and_ignore_individual(
    client: TestClient, db_session: Session
) -> None:
    a_tiziu_1 = Animal(
        numero="L-01",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 9, 1),
        categoria=CategoriaAnimalEnum.BEZERRO,
        status=StatusAnimalEnum.ATIVO,
    )
    a_tiziu_2 = Animal(
        numero="L-02",
        fazenda=FazendaEnum.TIZIU,
        data_entrada=date(2026, 9, 1),
        categoria=CategoriaAnimalEnum.NOVILHA,
        status=StatusAnimalEnum.ATIVO,
    )
    a_penha = Animal(
        numero="P-01",
        fazenda=FazendaEnum.NS_PENHA,
        data_entrada=date(2026, 9, 1),
        categoria=CategoriaAnimalEnum.VACA,
        status=StatusAnimalEnum.ATIVO,
    )
    db_session.add_all([a_tiziu_1, a_tiziu_2, a_penha])
    db_session.commit()

    # Pesagem individual não deve aparecer no histórico de lotes
    client.post(
        f"/animais/{a_tiziu_1.id}/pesagens",
        data={
            "data_pesagem": "2026-09-10",
            "peso_kg": "190.00",
            "observacao": "Individual Setembro",
        },
    )

    resp_vazio = client.get("/pesagens/lote")
    assert resp_vazio.status_code == 200
    assert "Nenhuma pesagem em lote registrada" in resp_vazio.text
    assert "Individual Setembro" not in resp_vazio.text

    # Lança 1º lote na Fazenda Tiziu (2 animais: 200 kg e 300 kg -> média 250,00 kg)
    client.post(
        "/pesagens/lote",
        data={
            "fazenda": "tiziu",
            "data_pesagem": "2026-10-05",
            "observacao_padrao": "Pesagem Outubro Tiziu",
            "numeros": ["L-01", "L-02"],
            "pesos": ["200.00", "300.00"],
            "observacoes": ["", "Obs individual L-02"],
        },
    )

    # Lança 2º lote na Fazenda N. S. da Penha sem observação padrão (1 animal: 440,50 kg)
    client.post(
        "/pesagens/lote/novo",
        data={
            "fazenda": "ns_penha",
            "data_pesagem": "2026-10-20",
            "observacao_padrao": "",
            "numeros": ["P-01"],
            "pesos": ["440.50"],
            "observacoes": [""],
        },
    )

    hist_resp = client.get("/pesagens/lote")
    assert hist_resp.status_code == 200
    # Verifica cabeçalhos das colunas exigidas
    assert "Fazenda" in hist_resp.text
    assert "Data Pesagem" in hist_resp.text
    assert "Quantidade de Animais" in hist_resp.text
    assert "Peso Médio Obtido" in hist_resp.text
    assert "Observação Padrão do Lote" in hist_resp.text
    # Verifica dados dos lotes lançados (mais recente primeiro)
    assert hist_resp.text.index("20/10/2026") < hist_resp.text.index("05/10/2026")
    assert "N. S. da Penha" in hist_resp.text
    assert "1 animal" in hist_resp.text
    assert "440,50 kg" in hist_resp.text
    assert "Tiziu" in hist_resp.text
    assert "2 animais" in hist_resp.text
    assert "250,00 kg" in hist_resp.text
    assert "Pesagem Outubro Tiziu" in hist_resp.text


def test_create_animais_em_lote_success_and_validations(
    client: TestClient, db_session: Session
) -> None:
    # 1. GET /animais/lote exibe apenas os inputs essenciais (fazenda, data, numeros, pesos)
    get_resp = client.get("/animais/lote?fazenda=ns_penha")
    assert get_resp.status_code == 200
    assert "Cadastro de Animais em Lote" in get_resp.text
    assert 'name="fazenda"' in get_resp.text
    assert 'name="data"' in get_resp.text
    assert 'name="numeros"' in get_resp.text
    assert 'name="pesos"' in get_resp.text
    assert 'name="categoria"' not in get_resp.text
    assert 'name="status"' not in get_resp.text
    assert 'name="pastos"' not in get_resp.text

    # 2. Cria lote de animais com peso inicial (e ignora linha vazia)
    post_ok = client.post(
        "/animais/lote",
        data={
            "fazenda": "tiziu",
            "data": "2026-11-02",
            "numeros": ["VL-01", "VL-02", ""],
            "pesos": ["410.00", "450.50", ""],
        },
        follow_redirects=True,
    )
    assert post_ok.status_code == 200
    assert "2 animais cadastrados em lote com sucesso!" in post_ok.text
    assert "VL-01" in post_ok.text
    assert "VL-02" in post_ok.text
    assert "410,00 kg" in post_ok.text
    assert "450,50 kg" in post_ok.text

    # 3. Verifica dados no banco: categoria=vaca, status=ativo, data_entrada=data_pesagem=data, em_lote=True
    animal_repo = AnimalRepository(db_session)
    a1 = animal_repo.get_by_fazenda_and_numero(FazendaEnum.TIZIU, "VL-01")
    a2 = animal_repo.get_by_fazenda_and_numero(FazendaEnum.TIZIU, "VL-02")
    assert a1 is not None and a2 is not None
    for animal_obj, expected_peso in [(a1, Decimal("410.00")), (a2, Decimal("450.50"))]:
        assert animal_obj.categoria == CategoriaAnimalEnum.VACA
        assert animal_obj.status == StatusAnimalEnum.ATIVO
        assert animal_obj.data_entrada == date(2026, 11, 2)
        full_animal = animal_repo.get_by_id(animal_obj.id)
        assert full_animal is not None
        assert len(full_animal.pesagens) == 1
        p = full_animal.pesagens[0]
        assert p.data_pesagem == date(2026, 11, 2)
        assert p.peso_kg == expected_peso
        assert p.em_lote is True
        assert p.lote_id is not None

    # Ambos pertencem ao mesmo lote_id e aparecem no histórico de pesagens em lote
    p1 = animal_repo.get_by_id(a1.id).pesagens[0]
    p2 = animal_repo.get_by_id(a2.id).pesagens[0]
    assert p1.lote_id == p2.lote_id

    hist_resp = client.get("/pesagens/lote")
    assert hist_resp.status_code == 200
    assert "02/11/2026" in hist_resp.text
    assert "2 animais" in hist_resp.text
    assert "430,25 kg" in hist_resp.text

    # 4. Mesmo número em outra fazenda é permitido (1 animal -> mensagem no singular)
    post_other_farm = client.post(
        "/animais/lote/novo",
        data={
            "fazenda": "ns_penha",
            "data": "2026-11-03",
            "numeros": ["VL-01"],
            "pesos": ["395,25"],
        },
        follow_redirects=True,
    )
    assert post_other_farm.status_code == 200
    assert "1 animal cadastrado em lote com sucesso!" in post_other_farm.text

    # 5. Validações de erro no POST /animais/lote
    # Nenhuma linha preenchida
    r_empty = client.post(
        "/animais/lote",
        data={"fazenda": "tiziu", "data": "2026-11-02", "numeros": [""], "pesos": [""]},
    )
    assert r_empty.status_code == 422
    assert "Preencha ao menos um animal" in r_empty.text

    # Sem data
    r_no_date = client.post(
        "/animais/lote",
        data={"fazenda": "tiziu", "data": "", "numeros": ["VL-03"], "pesos": ["400"]},
    )
    assert r_no_date.status_code == 422
    assert "A data é obrigatória" in r_no_date.text

    # Linha sem número
    r_no_num = client.post(
        "/animais/lote",
        data={"fazenda": "tiziu", "data": "2026-11-02", "numeros": [""], "pesos": ["400"]},
    )
    assert r_no_num.status_code == 422
    assert "informe o número do animal" in r_no_num.text

    # Linha sem peso
    r_no_peso = client.post(
        "/animais/lote",
        data={"fazenda": "tiziu", "data": "2026-11-02", "numeros": ["VL-03"], "pesos": [""]},
    )
    assert r_no_peso.status_code == 422
    assert "informe o peso em kg" in r_no_peso.text

    # Peso inválido (não numérico)
    r_bad_peso = client.post(
        "/animais/lote",
        data={"fazenda": "tiziu", "data": "2026-11-02", "numeros": ["VL-03"], "pesos": ["abc"]},
    )
    assert r_bad_peso.status_code == 422
    assert "inválido" in r_bad_peso.text

    # Peso <= 0
    r_zero_peso = client.post(
        "/animais/lote",
        data={"fazenda": "tiziu", "data": "2026-11-02", "numeros": ["VL-03"], "pesos": ["0"]},
    )
    assert r_zero_peso.status_code == 422
    assert "maior que zero" in r_zero_peso.text

    # Número repetido dentro do mesmo lote
    r_dup_batch = client.post(
        "/animais/lote",
        data={
            "fazenda": "tiziu",
            "data": "2026-11-02",
            "numeros": ["VL-99", "VL-99"],
            "pesos": ["400", "410"],
        },
    )
    assert r_dup_batch.status_code == 422
    assert "repetido(s) no mesmo lote" in r_dup_batch.text

    # Número já existente na mesma fazenda
    r_existing = client.post(
        "/animais/lote",
        data={
            "fazenda": "tiziu",
            "data": "2026-11-02",
            "numeros": ["VL-01"],
            "pesos": ["400"],
        },
    )
    assert r_existing.status_code == 422
    assert "Já existe(m) animal(is) cadastrado(s)" in r_existing.text

    # ValidationError do Pydantic (número com mais de 50 caracteres)
    r_val_err = client.post(
        "/animais/lote",
        data={
            "fazenda": "tiziu",
            "data": "2026-11-02",
            "numeros": ["X" * 60],
            "pesos": ["400"],
        },
    )
    assert r_val_err.status_code == 422

    # ValueError (fazenda inválida)
    r_fazenda_err = client.post(
        "/animais/lote",
        data={
            "fazenda": "invalida",
            "data": "2026-11-02",
            "numeros": ["VL-10"],
            "pesos": ["400"],
        },
    )
    assert r_fazenda_err.status_code == 422

    # Schema validation direta para AnimalLoteItem com string em branco
    with pytest.raises(ValidationError):
        AnimalLoteItem(numero="   ", peso_kg=Decimal("400"))

    alc = AnimalLoteCreate(
        fazenda=FazendaEnum.TIZIU,
        data=date(2026, 11, 2),
        itens=[AnimalLoteItem(numero="  555  ", peso_kg=Decimal("400"))],
    )
    assert alc.itens[0].numero == "555"











