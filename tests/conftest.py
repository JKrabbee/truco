import sys
from pathlib import Path
from typing import Callable

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from core.card import Carta  # noqa: E402
from core.match import PartidaTruco  # noqa: E402
from core.player import JogadorHumano, JogadorBot  # noqa: E402


def cartas(*ids: str) -> list[Carta]:
    """Converte ids como "7_espadas" em cartas."""
    return [Carta.de_id(i) for i in ids]


@pytest.fixture
def montar_partida() -> Callable[..., PartidaTruco]:
    """Fábrica de partidas com mãos fixas e baralho coerente (sem cartas repetidas)."""

    def _montar(
        mao_j1: list[str],
        mao_j2: list[str],
        pontos_j1: int = 0,
        pontos_j2: int = 0,
    ) -> PartidaTruco:
        humano = JogadorHumano()
        bot = JogadorBot(taxa_blefe=0.0)
        partida = PartidaTruco(humano, bot)
        partida.iniciar_nova_rodada()  # rodada 1: jogador1 é mão
        humano.receber_cartas(cartas(*mao_j1))
        bot.receber_cartas(cartas(*mao_j2))
        usadas = set(humano.mao) | set(bot.mao)
        partida.baralho.reiniciar()
        partida.baralho.cartas = [c for c in partida.baralho.cartas if c not in usadas]
        partida.pontos_jogador1 = humano.tentos = pontos_j1
        partida.pontos_jogador2 = bot.tentos = pontos_j2
        return partida

    return _montar
