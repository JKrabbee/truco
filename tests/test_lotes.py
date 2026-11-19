"""Um caso por linha da tabela R5.1, mais R3.4 (mão que fecha 12 não gera lote)."""

import pytest

from core.match import EstadoPartida, PartidaTruco
from core.roleta import LoteTiros, OrigemTiro
from core.rules import RespostaAposta, TipoEnvido, obter_peso_carta

FORTE = ["1_espadas", "1_bastos", "7_ouros"]
FRACA = ["4_copas", "5_ouros", "6_bastos"]


def jogar_ate_fim_da_mao(p: PartidaTruco) -> None:
    """Cada jogador da vez joga sua carta mais forte até a mão acabar."""
    while p.estado_atual in (EstadoPartida.AGUARDANDO_ENVIDO, EstadoPartida.JOGANDO_VAZA):
        jogador = p.jogador_vez
        assert p.jogar_carta(jogador, max(jogador.mao, key=obter_peso_carta))


def lote_unico(p: PartidaTruco) -> LoteTiros:
    lotes = p.consumir_lotes()
    assert len(lotes) == 1, lotes
    return lotes[0]


def aceitar_truco_ate(p: PartidaTruco, nivel: int) -> None:
    """Truco (1), Retruco (2) ou Vale Quatro (3) aceito, alternando quem pede."""
    pede, responde = p.jogador1, p.jogador2
    for _ in range(nivel):
        assert p.pedir_truco(pede)
        p.responder_truco(RespostaAposta.QUERO, responde)
        pede, responde = responde, pede


# --- Perdeu a mão ---------------------------------------------------------------


def test_perdeu_mao_sem_truco_puxa_1(montar_partida):
    p = montar_partida(FORTE, FRACA)
    jogar_ate_fim_da_mao(p)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador2, p.jogador2)
    assert lote.puxadas == 1
    assert lote.origem == OrigemTiro.MAO_PERDIDA
    assert lote.fatal is False


def test_humano_perdendo_a_mao_atira_em_si(montar_partida):
    p = montar_partida(FRACA, FORTE)
    jogar_ate_fim_da_mao(p)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador1, p.jogador1)


@pytest.mark.parametrize("nivel, puxadas", [(1, 2), (2, 3), (3, 4)])
def test_perdeu_mao_com_truco_aceito_puxa_valor_do_truco(montar_partida, nivel, puxadas):
    p = montar_partida(FORTE, FRACA)
    aceitar_truco_ate(p, nivel)
    assert p.valor_truco_atual == puxadas
    jogar_ate_fim_da_mao(p)
    lote = lote_unico(p)
    assert lote.alvo is p.jogador2
    assert lote.puxadas == puxadas
    assert lote.origem == OrigemTiro.MAO_PERDIDA


# --- Foi ao baralho ---------------------------------------------------------------


@pytest.mark.parametrize("nivel, puxadas", [(0, 1), (1, 2), (2, 3)])
def test_ir_ao_baralho_puxa_valor_do_truco(montar_partida, nivel, puxadas):
    p = montar_partida(FRACA, FORTE)
    aceitar_truco_ate(p, nivel)
    p.ir_ao_baralho(p.jogador1)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador1, p.jogador1)
    assert lote.puxadas == puxadas
    assert lote.origem == OrigemTiro.BARALHO


# --- Recusou truco ----------------------------------------------------------------


def test_recusou_truco_puxa_1(montar_partida):
    p = montar_partida(FORTE, FRACA)
    p.pedir_truco(p.jogador1)
    p.responder_truco(RespostaAposta.NAO_QUERO, p.jogador2)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador2, p.jogador2)
    assert lote.puxadas == 1
    assert lote.origem == OrigemTiro.RECUSA_TRUCO
    assert p.estado_atual == EstadoPartida.FIM_DA_MAO


def test_recusou_retruco_tambem_puxa_1(montar_partida):
    p = montar_partida(FORTE, FRACA)
    aceitar_truco_ate(p, 1)
    p.pedir_truco(p.jogador2)  # Retruco
    p.responder_truco(RespostaAposta.NAO_QUERO, p.jogador1)
    lote = lote_unico(p)
    assert lote.alvo is p.jogador1
    assert lote.puxadas == 1
    assert lote.origem == OrigemTiro.RECUSA_TRUCO


# --- Envido ---------------------------------------------------------------------------

ENVIDO_33 = ["7_espadas", "6_espadas", "4_copas"]
ENVIDO_23 = ["1_ouros", "2_ouros", "4_bastos"]


@pytest.mark.parametrize(
    "tipo, puxadas", [(TipoEnvido.ENVIDO, 2), (TipoEnvido.REAL_ENVIDO, 3)]
)
def test_ganhou_envido_atira_no_outro(montar_partida, tipo, puxadas):
    p = montar_partida(ENVIDO_23, ENVIDO_33)
    p.cantar_envido(p.jogador1, tipo)
    p.responder_envido(RespostaAposta.QUERO)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador2, p.jogador1)
    assert lote.puxadas == puxadas
    assert lote.origem == OrigemTiro.ENVIDO
    assert p.estado_atual == EstadoPartida.JOGANDO_VAZA


def test_envido_e_real_envido_encadeados_somam(montar_partida):
    p = montar_partida(ENVIDO_33, ENVIDO_23)
    p.cantar_envido(p.jogador1, TipoEnvido.ENVIDO)
    p.responder_envido(RespostaAposta.AUMENTAR, aumento=TipoEnvido.REAL_ENVIDO)
    p.responder_envido(RespostaAposta.QUERO)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador1, p.jogador2)
    assert lote.puxadas == 5


def test_ganhou_falta_envido_puxa_ate_disparar(montar_partida):
    # Diabo com 10: a Falta vale 2 e o humano não fecha 12 com ela.
    p = montar_partida(ENVIDO_33, ENVIDO_23, pontos_j2=10)
    p.cantar_envido(p.jogador1, TipoEnvido.FALTA_ENVIDO)
    p.responder_envido(RespostaAposta.QUERO)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador1, p.jogador2)
    assert lote.puxadas is None
    assert lote.origem == OrigemTiro.FALTA_ENVIDO


def test_recusou_envido_puxa_1(montar_partida):
    p = montar_partida(ENVIDO_33, ENVIDO_23)
    p.cantar_envido(p.jogador1, TipoEnvido.ENVIDO)
    p.responder_envido(RespostaAposta.NAO_QUERO)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador2, p.jogador2)
    assert lote.puxadas == 1
    assert lote.origem == OrigemTiro.RECUSA_ENVIDO


# --- Flor -----------------------------------------------------------------------------

FLOR_38 = ["7_copas", "6_copas", "5_copas"]
FLOR_35 = ["4_ouros", "5_ouros", "6_ouros"]
SEM_FLOR = ["1_espadas", "2_bastos", "3_ouros"]


def test_flor_sem_contraflor_atira_3_no_outro(montar_partida):
    p = montar_partida(FLOR_38, SEM_FLOR)
    assert p.cantar_flor(p.jogador1)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador1, p.jogador2)
    assert lote.puxadas == 3
    assert lote.origem == OrigemTiro.FLOR


def test_contraflor_vencedor_atira_3_no_outro(montar_partida):
    # Quem canta (Diabo, 35) perde a contraflor para o humano (38).
    p = montar_partida(FLOR_38, FLOR_35)
    assert p.cantar_flor(p.jogador2)
    lote = lote_unico(p)
    assert (lote.atirador, lote.alvo) == (p.jogador1, p.jogador2)
    assert lote.puxadas == 3
    assert lote.origem == OrigemTiro.FLOR


# --- R3.4 e fila ----------------------------------------------------------------------


def test_mao_que_fecha_12_nao_gera_lote(montar_partida):
    p = montar_partida(FORTE, FRACA, pontos_j1=11)
    jogar_ate_fim_da_mao(p)
    assert p.estado_atual == EstadoPartida.FIM_DE_JOGO
    assert p.vencedor_partida is p.jogador1
    assert p.consumir_lotes() == []


def test_envido_que_fecha_12_nao_gera_lote(montar_partida):
    p = montar_partida(ENVIDO_23, ENVIDO_33, pontos_j2=10)
    p.cantar_envido(p.jogador1, TipoEnvido.ENVIDO)
    p.responder_envido(RespostaAposta.QUERO)
    assert p.vencedor_partida is p.jogador2
    assert p.consumir_lotes() == []


def test_consumir_esvazia_a_fila(montar_partida):
    p = montar_partida(FORTE, FRACA)
    p.ir_ao_baralho(p.jogador2)
    assert len(p.consumir_lotes()) == 1
    assert p.consumir_lotes() == []


def test_nova_rodada_zera_lotes_pendentes(montar_partida):
    p = montar_partida(FORTE, FRACA)
    p.ir_ao_baralho(p.jogador2)
    assert p.lotes_pendentes
    p.iniciar_nova_rodada()
    assert p.lotes_pendentes == []


def test_partida_vai_ate_12_tentos():
    assert PartidaTruco.TENTOS_VITORIA == 12
    assert not hasattr(PartidaTruco, "esta_nas_boas")


def test_placar_tradicional_formato_x_de_12(montar_partida):
    p = montar_partida(FORTE, FRACA, pontos_j1=5)
    assert p.formatar_placar_tradicional(p.jogador1) == "5/12"
