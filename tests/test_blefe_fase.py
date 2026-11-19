import random

from conftest import cartas
from core.campanha import Campanha
from core.fase import FASES

MAO_FRACA = cartas("4_copas", "5_ouros", "6_bastos")  # sem manilha, peso médio baixo


def _quer_truco(indice_fase: int, monkeypatch, sorteio: float) -> bool:
    c = Campanha.nova(random.Random(0))
    c.iniciar_fase(indice_fase)
    c.diabo.mao = list(MAO_FRACA)
    monkeypatch.setattr("core.player.random.random", lambda: sorteio)
    return c.diabo.quer_pedir_truco(None)


def test_taxa_de_blefe_da_fase_muda_a_decisao_da_ia(monkeypatch):
    """R6.1/R6.4: com mão fraca, só a taxa da fase decide o blefe."""
    assert _quer_truco(0, monkeypatch, 0.2) is False  # 0.00
    assert _quer_truco(1, monkeypatch, 0.2) is True  # 0.35
    assert _quer_truco(1, monkeypatch, 0.4) is False
    assert _quer_truco(2, monkeypatch, 0.4) is True  # 0.50


def test_taxa_volta_do_save_com_a_fase(monkeypatch):
    c = Campanha.nova(random.Random(0))
    c.iniciar_fase(2)
    c.partida.iniciar_nova_rodada()
    r = Campanha.de_dict(c.para_dict())
    assert r.diabo.taxa_blefe == FASES[2].taxa_blefe
