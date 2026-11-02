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

