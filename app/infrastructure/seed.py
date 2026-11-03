from datetime import date, timedelta
from decimal import Decimal
import logging

from sqlalchemy.orm import Session

from app.domain.models.animal import Animal
from app.domain.models.enums import CategoriaAnimalEnum, FazendaEnum, StatusAnimalEnum
from app.domain.models.pasto import Pasto
from app.domain.models.pesagem import Pesagem
from app.domain.repositories.animal_repository import AnimalRepository
from app.domain.repositories.pasto_repository import PastoRepository
from app.domain.repositories.pesagem_repository import PesagemRepository
from app.infrastructure.database import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_seed_pastos() -> list[str]:
    """Retorna os nomes dos pastos iniciais para seed."""
    return [
        "Pasto da Represa",
        "Pasto da Baixada",
        "Pasto Curral",
        "Piquete Rotacionado 1",
        "Piquete Maternidade",
    ]


def get_seed_data() -> list[dict]:
    """Retorna a lista de animais e suas respectivas pesagens para seed."""
    today = date.today()

    def days_ago(days: int) -> date:
        return today - timedelta(days=days)

    return [
        # ==================== FAZENDA TIZIU ====================
        {
            "numero": "101",
            "fazenda": FazendaEnum.TIZIU,
            "categoria": CategoriaAnimalEnum.BEZERRO,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(120),
            "pasto": "Pasto Curral",
            "observacoes": "Nascido na propriedade. Pelagem nelore padrão.",
            "pesagens": [
                {"data_pesagem": days_ago(120), "peso_kg": Decimal("185.00"), "observacao": "Peso na desmama"},
                {"data_pesagem": days_ago(60), "peso_kg": Decimal("220.50"), "observacao": " Suplementação mineral"},
                {"data_pesagem": days_ago(10), "peso_kg": Decimal("252.00"), "observacao": "Pesagem de rotina"},
            ],
        },
        {
            "numero": "102",
            "fazenda": FazendaEnum.TIZIU,
            "categoria": CategoriaAnimalEnum.BEZERRO,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(95),
            "pasto": "Piquete Rotacionado 1",
            "observacoes": "Lote de reposição.",
            "pesagens": [
                {"data_pesagem": days_ago(95), "peso_kg": Decimal("192.00"), "observacao": "Peso de entrada"},
                {"data_pesagem": days_ago(30), "peso_kg": Decimal("231.00"), "observacao": "Bom ganho no pasto rotacionado"},
            ],
        },
        {
            "numero": "204",
            "fazenda": FazendaEnum.TIZIU,
            "categoria": CategoriaAnimalEnum.NOVILHA,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(240),
            "observacoes": "Aptidão para futura matriz.",
            "pesagens": [
                {"data_pesagem": days_ago(240), "peso_kg": Decimal("275.00"), "observacao": "Peso de entrada"},
                {"data_pesagem": days_ago(150), "peso_kg": Decimal("310.00"), "observacao": "Vacinação aftosa + vermífugo"},
                {"data_pesagem": days_ago(60), "peso_kg": Decimal("342.50"), "observacao": "Início estação de águas"},
                {"data_pesagem": days_ago(5), "peso_kg": Decimal("368.00"), "observacao": "Pronta para estação de monta"},
            ],
        },
        {
            "numero": "208",
            "fazenda": FazendaEnum.TIZIU,
            "categoria": CategoriaAnimalEnum.NOVILHA,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(180),
            "observacoes": "Cruzamento industrial Angus x Nelore.",
            "pesagens": [
                {"data_pesagem": days_ago(180), "peso_kg": Decimal("290.00"), "observacao": "Entrada no piquete 3"},
                {"data_pesagem": days_ago(90), "peso_kg": Decimal("335.00"), "observacao": "Suplementação proteica"},
                {"data_pesagem": days_ago(15), "peso_kg": Decimal("379.50"), "observacao": "Excelente escore corporal"},
            ],
        },
        {
            "numero": "315",
            "fazenda": FazendaEnum.TIZIU,
            "categoria": CategoriaAnimalEnum.VACA,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(400),
            "observacoes": "Matriz multipara, mansa de curral.",
            "pesagens": [
                {"data_pesagem": days_ago(400), "peso_kg": Decimal("440.00"), "observacao": "Peso inicial de cadastro"},
                {"data_pesagem": days_ago(200), "peso_kg": Decimal("468.00"), "observacao": "Diagnóstico de gestação positivo"},
                {"data_pesagem": days_ago(45), "peso_kg": Decimal("452.00"), "observacao": "Pós-parto"},
            ],
        },
        {
            "numero": "401",
            "fazenda": FazendaEnum.TIZIU,
            "categoria": CategoriaAnimalEnum.TOURO,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(500),
            "observacoes": "Reprodutor Nelore PO - Exame andrológico aprovado.",
            "pesagens": [
                {"data_pesagem": days_ago(365), "peso_kg": Decimal("720.00"), "observacao": "Pré-estação de monta"},
                {"data_pesagem": days_ago(180), "peso_kg": Decimal("695.00"), "observacao": "Pós-estação de monta"},
                {"data_pesagem": days_ago(20), "peso_kg": Decimal("748.00"), "observacao": "Recuperação completa de peso"},
            ],
        },
        {
            "numero": "199",
            "fazenda": FazendaEnum.TIZIU,
            "categoria": CategoriaAnimalEnum.NOVILHA,
            "status": StatusAnimalEnum.ABATIDO,
            "data_entrada": days_ago(300),
            "observacoes": "Terminação em semiconfinamento. Abate frigorífico regional.",
            "pesagens": [
                {"data_pesagem": days_ago(300), "peso_kg": Decimal("310.00"), "observacao": "Peso de entrada"},
                {"data_pesagem": days_ago(120), "peso_kg": Decimal("380.00"), "observacao": "Entrada no semiconfinamento"},
                {"data_pesagem": days_ago(30), "peso_kg": Decimal("435.00"), "observacao": "Pesagem de embarque"},
            ],
        },
        # ==================== FAZENDA N. S. DA PENHA ====================
        {
            "numero": "101",
            "fazenda": FazendaEnum.NS_PENHA,
            "categoria": CategoriaAnimalEnum.BEZERRO,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(110),
            "observacoes": "Bezerro de desmama precoce.",
            "pesagens": [
                {"data_pesagem": days_ago(110), "peso_kg": Decimal("178.00"), "observacao": "Peso de entrada"},
                {"data_pesagem": days_ago(40), "peso_kg": Decimal("214.00"), "observacao": "Manejo sanitário em dia"},
            ],
        },
        {
            "numero": "115",
            "fazenda": FazendaEnum.NS_PENHA,
            "categoria": CategoriaAnimalEnum.BEZERRO,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(75),
            "observacoes": "Adquirido em leilão regional.",
            "pesagens": [
                {"data_pesagem": days_ago(75), "peso_kg": Decimal("205.00"), "observacao": "Recepção na fazenda"},
                {"data_pesagem": days_ago(12), "peso_kg": Decimal("241.50"), "observacao": "Adaptação concluída"},
            ],
        },
        {
            "numero": "220",
            "fazenda": FazendaEnum.NS_PENHA,
            "categoria": CategoriaAnimalEnum.NOVILHA,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(210),
            "observacoes": "Lote cabeceira de recria.",
            "pesagens": [
                {"data_pesagem": days_ago(210), "peso_kg": Decimal("265.00"), "observacao": "Peso inicial"},
                {"data_pesagem": days_ago(100), "peso_kg": Decimal("312.00"), "observacao": "Controle parasitário"},
                {"data_pesagem": days_ago(18), "peso_kg": Decimal("350.00"), "observacao": "Pesagem mensal"},
            ],
        },
        {
            "numero": "302",
            "fazenda": FazendaEnum.NS_PENHA,
            "categoria": CategoriaAnimalEnum.VACA,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(450),
            "observacoes": "Matriz leiteira/corte mista.",
            "pesagens": [
                {"data_pesagem": days_ago(300), "peso_kg": Decimal("460.00"), "observacao": "Pesagem de inverno"},
                {"data_pesagem": days_ago(120), "peso_kg": Decimal("485.00"), "observacao": "Terço final de gestação"},
                {"data_pesagem": days_ago(25), "peso_kg": Decimal("470.00"), "observacao": "Lactação com cria ao pé"},
            ],
        },
        {
            "numero": "310",
            "fazenda": FazendaEnum.NS_PENHA,
            "categoria": CategoriaAnimalEnum.VACA,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(380),
            "observacoes": "Matriz Nelore mocho.",
            "pesagens": [
                {"data_pesagem": days_ago(250), "peso_kg": Decimal("430.00"), "observacao": "Entrada no lote de cria"},
                {"data_pesagem": days_ago(35), "peso_kg": Decimal("462.50"), "observacao": "Escore corporal 3.5"},
            ],
        },
        {
            "numero": "500",
            "fazenda": FazendaEnum.NS_PENHA,
            "categoria": CategoriaAnimalEnum.TOURO,
            "status": StatusAnimalEnum.ATIVO,
            "data_entrada": days_ago(600),
            "observacoes": "Touro repasse Tabapuã.",
            "pesagens": [
                {"data_pesagem": days_ago(240), "peso_kg": Decimal("680.00"), "observacao": "Avaliação semestral"},
                {"data_pesagem": days_ago(14), "peso_kg": Decimal("715.00"), "observacao": "Pré-temporada de monta"},
            ],
        },
        {
            "numero": "144",
            "fazenda": FazendaEnum.NS_PENHA,
            "categoria": CategoriaAnimalEnum.BEZERRO,
            "status": StatusAnimalEnum.MORTO,
            "data_entrada": days_ago(160),
            "observacoes": "Óbito por acidente ofídico no pasto da baixada.",
            "pesagens": [
                {"data_pesagem": days_ago(160), "peso_kg": Decimal("170.00"), "observacao": "Peso de entrada"},
            ],
        },
    ]


def seed_database(db: Session) -> tuple[int, int]:
    """
    Popula o banco de dados com registros iniciais de pastos, animais e pesagens de forma idempotente.
    Retorna a tupla (animais_criados, pesagens_criadas).
    """
    pasto_repo = PastoRepository(db)
    animal_repo = AnimalRepository(db)
    pesagem_repo = PesagemRepository(db)

    pastos_map: dict[str, Pasto] = {}
    for nome_pasto in get_seed_pastos():
        pasto_obj = pasto_repo.get_by_nome(nome_pasto)
        if pasto_obj is None:
            pasto_obj = pasto_repo.create(Pasto(nome=nome_pasto))
        pastos_map[nome_pasto] = pasto_obj

    animais_criados = 0
    pesagens_criadas = 0

    for item in get_seed_data():
        existing = animal_repo.get_by_fazenda_and_numero(item["fazenda"], item["numero"])
        if existing is not None:
            continue

        pasto_nome = item.get("pasto")
        pasto_ref = pastos_map.get(pasto_nome) if pasto_nome else None

        animal = Animal(
            numero=item["numero"],
            fazenda=item["fazenda"],
            categoria=item["categoria"],
            status=item["status"],
            data_entrada=item["data_entrada"],
            pasto_id=pasto_ref.id if pasto_ref else None,
            observacoes=item["observacoes"],
        )
        animal_repo.create(animal)
        animais_criados += 1

        pesagens = [
            Pesagem(
                animal_id=animal.id,
                pasto_id=animal.pasto_id,
                data_pesagem=p["data_pesagem"],
                peso_kg=p["peso_kg"],
                observacao=p["observacao"],
            )
            for p in item.get("pesagens", [])
        ]
        if pesagens:
            pesagem_repo.create_many(pesagens)
            pesagens_criadas += len(pesagens)

    db.commit()
    return animais_criados, pesagens_criadas


def main() -> None:
    logger.info("Iniciando seed do banco de dados local...")
    with SessionLocal() as db:
        animais_count, pesagens_count = seed_database(db)
    if animais_count == 0 and pesagens_count == 0:
        logger.info("Seed concluído: os registros iniciais já existem no banco.")
    else:
        logger.info(
            "Seed concluído com sucesso: %d animais e %d pesagens inseridos.",
            animais_count,
            pesagens_count,
        )


if __name__ == "__main__":
    main()

