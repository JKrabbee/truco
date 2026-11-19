from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConfigFase:
    """Parâmetros de uma fase contra o Diabo (R2.2)."""

    numero: int
    nome: str
    taxa_blefe: float
    tempo_decisao_s: Optional[float]  # None = sem limite
    leitura_mente: bool
    chance_leitura: float  # chance por gatilho de fala
    balas: int
    velocidade_musica: float  # define qual faixa tocar
    luz: str  # "estavel" | "oscila" | "pisca"


FASES: tuple[ConfigFase, ...] = (
    ConfigFase(1, "O Convite", 0.00, None, False, 0.00, 1, 1.00, "estavel"),
    ConfigFase(2, "O Blefe", 0.35, 15.0, True, 0.30, 1, 1.15, "oscila"),
    ConfigFase(3, "A Leitura", 0.50, 6.0, True, 0.60, 2, 1.30, "pisca"),
)
