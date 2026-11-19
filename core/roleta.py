from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional
from core.player import Jogador


class OrigemTiro(Enum):
    """Evento de jogo que gerou um lote de tiros (R5.1)."""

    MAO_PERDIDA = auto()
    BARALHO = auto()
    RECUSA_TRUCO = auto()
    ENVIDO = auto()
    FALTA_ENVIDO = auto()
    RECUSA_ENVIDO = auto()
    FLOR = auto()
    TIRO_FINAL = auto()


@dataclass
class LoteTiros:
    """Sequência de puxadas com um atirador e um alvo."""

    atirador: Jogador
    alvo: Jogador
    puxadas: Optional[int]  # None = até disparar (Falta Envido)
    origem: OrigemTiro
    fatal: bool = False  # TIRO_FINAL: dispara sem consultar o tambor
