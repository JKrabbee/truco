import json

import pytest

from conftest import cartas
from core.card import Carta
from core.match import EstadoPartida, PartidaTruco
from core.player import JogadorBot, JogadorHumano
from core.rules import RespostaAposta, TipoEnvido, TipoTruco


def ida_e_volta(p: PartidaTruco) -> PartidaTruco:
    dados = json.loads(json.dumps(p.para_dict()))
    return PartidaTruco.de_dict(dados, JogadorHumano(), JogadorBot(taxa_blefe=0.0))


@pytest.fixture
def partida_meio_2a_vaza(montar_partida) -> PartidaTruco:
    """Envido recusado, 1ª vaza do humano, 2ª vaza com uma carta e truco pendente."""
    p = montar_partida(
        ["1_espadas", "3_copas", "4_ouros"],
        ["2_bastos", "5_copas", "12_ouros"],
        pontos_j1=3,
        pontos_j2=4,
    )
    h, d = p.jogador1, p.jogador2
    p.cantar_envido(d, TipoEnvido.ENVIDO)
    p.responder_envido(RespostaAposta.NAO_QUERO)
    p.jogar_carta(h, Carta.de_id("1_espadas"))
    p.jogar_carta(d, Carta.de_id("5_copas"))
    p.jogar_carta(h, Carta.de_id("4_ouros"))
    assert p.pedir_truco(d)
    p.consumir_lotes()
    return p


def test_estado_equivalente_apos_json(partida_meio_2a_vaza):
    p = partida_meio_2a_vaza
    q = ida_e_volta(p)

    assert q.para_dict() == p.para_dict()
    # placar
    assert (q.pontos_jogador1, q.pontos_jogador2) == (3, 5)
    assert (q.jogador1.tentos, q.jogador2.tentos) == (3, 5)
    # mãos
    assert q.jogador1.mao == cartas("3_copas")
    assert q.jogador2.mao == cartas("2_bastos", "12_ouros")
    assert len(q.baralho) == 34
    # vazas
    assert q.mao_atual.indice_vaza_atual == 1
    v1, v2, v3 = q.mao_atual.vazas
    assert [(j, c) for j, c in v1.cartas_jogadas] == [
        (q.jogador1, Carta.de_id("1_espadas")),
        (q.jogador2, Carta.de_id("5_copas")),
    ]
    assert v1.vencedor is q.jogador1 and v1.empate is False
    assert v2.cartas_jogadas == [(q.jogador1, Carta.de_id("4_ouros"))]
    assert v3.cartas_jogadas == []
    assert q.mao_atual.jogador_mao is q.jogador1
    # apostas
    assert q.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO
    assert q.nivel_truco == TipoTruco.TRUCO
    assert q.quem_pediu_truco is q.jogador2
    assert q.quem_deve_responder_truco is q.jogador1
    assert q.envido_disputado is True
    # vez
    assert q.jogador_vez is q.jogador2


def test_jogo_continua_igual_depois_de_carregar(partida_meio_2a_vaza):
    p = partida_meio_2a_vaza
    q = ida_e_volta(p)

    for partida in (p, q):
        partida.responder_truco(RespostaAposta.QUERO, partida.jogador1)
        # 2ª vaza: 12 de Ouros mata o 4 de Ouros → 1 a 1, vai para a 3ª
        assert partida.jogar_carta(partida.jogador2, Carta.de_id("12_ouros"))
        assert partida.mao_atual.indice_vaza_atual == 2
        assert partida.jogador_vez is partida.jogador2
        # 3ª vaza: 3 de Copas mata o 2 de Bastos → mão do humano, valendo 2
        assert partida.jogar_carta(partida.jogador2, Carta.de_id("2_bastos"))
        assert partida.jogar_carta(partida.jogador1, Carta.de_id("3_copas"))
        assert partida.estado_atual == EstadoPartida.FIM_DA_MAO

    assert q.para_dict() == p.para_dict()
    assert q.pontos_jogador1 == 5
    [lote] = q.consumir_lotes()
    assert lote.alvo is q.jogador2 and lote.puxadas == 2


def test_partida_sem_mao_atual(montar_partida):
    p = PartidaTruco(JogadorHumano(), JogadorBot())
    q = ida_e_volta(p)
    assert q.mao_atual is None
    assert q.para_dict() == p.para_dict()
    q.iniciar_nova_rodada()
    assert len(q.jogador1.mao) == 3


def test_ids_de_jogador_no_formato_do_save(partida_meio_2a_vaza):
    dados = partida_meio_2a_vaza.para_dict()
    assert dados["jogador_vez"] == "j2"
    assert dados["mao_atual"]["vazas"][0]["cartas"] == [["j1", "1_espadas"], ["j2", "5_copas"]]
    assert dados["mao_atual"]["vazas"][0]["vencedor"] == "j1"


@pytest.mark.parametrize(
    "campo, valor, erro",
    [
        ("estado_atual", "NAO_EXISTE", KeyError),
        ("jogador_vez", "j3", ValueError),
        ("mao_j1", ["1_espadas", "99_copas"], ValueError),
        ("mao_j2", ["1_espadas"], ValueError),  # repetida (já está na mesa)
        ("indice_mao", 2, ValueError),
    ],
)
def test_dados_invalidos_levantam_erro(partida_meio_2a_vaza, campo, valor, erro):
    dados = partida_meio_2a_vaza.para_dict()
    dados[campo] = valor
    with pytest.raises(erro):
        PartidaTruco.de_dict(dados, JogadorHumano(), JogadorBot())


def test_chave_faltando_levanta_key_error(partida_meio_2a_vaza):
    dados = partida_meio_2a_vaza.para_dict()
    del dados["baralho"]
    with pytest.raises(KeyError):
        PartidaTruco.de_dict(dados, JogadorHumano(), JogadorBot())
