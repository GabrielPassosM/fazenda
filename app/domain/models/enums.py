from enum import Enum


class FazendaEnum(str, Enum):
    TIZIU = "tiziu"
    NS_PENHA = "ns_penha"

    @property
    def label(self) -> str:
        labels = {
            FazendaEnum.TIZIU: "Tiziu",
            FazendaEnum.NS_PENHA: "N. S. da Penha",
        }
        return labels[self]


class CategoriaAnimalEnum(str, Enum):
    BEZERRO = "bezerro"
    NOVILHA = "novilha"
    VACA = "vaca"
    TOURO = "touro"

    @property
    def label(self) -> str:
        labels = {
            CategoriaAnimalEnum.BEZERRO: "Bezerro",
            CategoriaAnimalEnum.NOVILHA: "Novilha",
            CategoriaAnimalEnum.VACA: "Vaca",
            CategoriaAnimalEnum.TOURO: "Touro",
        }
        return labels[self]


class StatusAnimalEnum(str, Enum):
    ATIVO = "ativo"
    ABATIDO = "abatido"
    MORTO = "morto"

    @property
    def label(self) -> str:
        labels = {
            StatusAnimalEnum.ATIVO: "Ativo",
            StatusAnimalEnum.ABATIDO: "Abatido",
            StatusAnimalEnum.MORTO: "Morto",
        }
        return labels[self]


class OrdenacaoAnimalEnum(str, Enum):
    DATA_ENTRADA_DESC = "data_entrada_desc"
    DATA_ENTRADA_ASC = "data_entrada_asc"
    PESO_DESC = "peso_desc"
    PESO_ASC = "peso_asc"

    @property
    def label(self) -> str:
        labels = {
            OrdenacaoAnimalEnum.DATA_ENTRADA_DESC: "Data de entrada (mais recente)",
            OrdenacaoAnimalEnum.DATA_ENTRADA_ASC: "Data de entrada (mais antiga)",
            OrdenacaoAnimalEnum.PESO_DESC: "Peso (maior para menor)",
            OrdenacaoAnimalEnum.PESO_ASC: "Peso (menor para maior)",
        }
        return labels[self]


