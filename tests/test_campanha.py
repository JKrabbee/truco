import json
import random

import pytest

from core.campanha import Campanha, ResultadoCampanha, SaveInvalido
from core.fase import FASES
from core.match import EstadoPartida
from core.revolver import Tambor
from core.roleta import LoteTiros, OrigemTiro


@pytest.fixture
def campanha() -> Campanha:
    return Campanha.nova(random.Random(0))


def enfileirar(c: Campanha, alvo, puxadas, origem=OrigemTiro.MAO_PERDIDA) -> LoteTiros:
    lote = LoteTiros(alvo, alvo, puxadas, origem)
    c.fila_lotes.append(lote)
    return lote


def ida_e_volta(c: Campanha) -> Campanha:
    return Campanha.de_dict(json.loads(json.dumps(c.para_dict())))


# --- nova / iniciar_fase ------------------------------------------------------------


def test_campanha_nova_comeca_na_fase_1(campanha):
    c = campanha
    assert c.indice_fase == 0
    assert c.config is FASES[0]
    assert c.resultado == ResultadoCampanha.EM_JOGO
    assert len(c.tambor.balas) == 1 and c.tambor.indice == 0
    assert c.diabo.nome == "O Diabo"
    assert c.diabo.taxa_blefe == 0.0
    assert c.partida.jogador1 is c.humano and c.partida.jogador2 is c.diabo
    assert c.partida.mao_atual is None
    assert c.lote_atual is None and c.fila_lotes == []


def test_iniciar_fase_zera_placar_e_recarrega_tambor(campanha):
    c = campanha
    c.partida.iniciar_nova_rodada()
    c.partida.adicionar_pontos(c.humano, 5)
    c.tambor.indice = 0
    c.iniciar_fase(2)
    assert c.partida.pontos_jogador1 == 0 and c.humano.tentos == 0
    assert c.humano.mao == []
    assert len(c.tambor.balas) == 2
    assert c.diabo.taxa_blefe == FASES[2].taxa_blefe


# --- puxar -------------------------------------------------------------------------


def test_morte_quando_alvo_e_o_humano(campanha):
    c = campanha
    c.tambor = Tambor(6, [0])
    enfileirar(c, c.humano, 1)
    assert c.proximo_lote() is not None
    assert c.puxar() is True
    assert c.resultado == ResultadoCampanha.MORTE


def test_vitoria_quando_alvo_e_o_diabo(campanha):
    c = campanha
    c.tambor = Tambor(6, [0])
    enfileirar(c, c.diabo, 1)
    c.proximo_lote()
    assert c.puxar() is True
    assert c.resultado == ResultadoCampanha.VITORIA_FASE


def test_lote_termina_apos_as_puxadas(campanha):
    c = campanha
    c.tambor = Tambor(6, [5])
    enfileirar(c, c.humano, 2)
    segundo = enfileirar(c, c.diabo, 1)
    c.proximo_lote()
    assert c.puxar() is False
    assert c.puxadas_restantes == 1
    assert c.puxar() is False
    assert c.lote_atual is None
    assert c.proximo_lote() is segundo
    assert c.tambor.disparadas == 2
    assert c.resultado == ResultadoCampanha.EM_JOGO


def test_disparo_descarta_resto_do_lote_e_a_fila(campanha):
    c = campanha
    c.tambor = Tambor(6, [1])
    enfileirar(c, c.diabo, 3)
    enfileirar(c, c.humano, 2)
    c.proximo_lote()
    assert c.puxar() is False
    assert c.puxar() is True
    assert c.lote_atual is None
    assert c.puxadas_restantes is None
    assert c.fila_lotes == []
    assert c.proximo_lote() is None
    assert c.tambor.indice == 2


def test_puxadas_none_puxa_ate_a_bala(campanha):
    c = campanha
    c.tambor = Tambor(6, [4])
    enfileirar(c, c.diabo, None, OrigemTiro.FALTA_ENVIDO)
    c.proximo_lote()
    resultados = [c.puxar() for _ in range(5)]
    assert resultados == [False, False, False, False, True]
    assert c.resultado == ResultadoCampanha.VITORIA_FASE


def test_lote_fatal_dispara_sem_tocar_no_tambor(campanha):
    c = campanha
    c.tambor = Tambor(6, [5])
    c.fila_lotes.append(
        LoteTiros(c.humano, c.humano, 1, OrigemTiro.TIRO_FINAL, fatal=True)
    )
    c.proximo_lote()
    assert c.puxar() is True
    assert c.tambor.indice == 0
    assert c.resultado == ResultadoCampanha.MORTE


def test_puxar_sem_lote_levanta_erro(campanha):
    with pytest.raises(RuntimeError):
        campanha.puxar()


def test_coletar_lotes_da_partida(campanha):
    c = campanha
    c.partida.iniciar_nova_rodada()
    c.partida.ir_ao_baralho(c.diabo)
    c.coletar_lotes()
    assert c.partida.lotes_pendentes == []
    lote = c.proximo_lote()
    assert lote.alvo is c.diabo and lote.origem == OrigemTiro.BARALHO
    assert c.puxadas_restantes == 1


# --- fim por tentos e fases -----------------------------------------------------------


def test_humano_chega_a_12_vence_a_fase(campanha):
    c = campanha
    c.partida.iniciar_nova_rodada()
    c.partida.adicionar_pontos(c.humano, 12)
    c.verificar_fim_por_tentos()
    assert c.resultado == ResultadoCampanha.VITORIA_FASE
    assert c.fila_lotes == []


def test_diabo_chega_a_12_gera_tiro_final_fatal(campanha):
    c = campanha
    c.partida.iniciar_nova_rodada()
    c.partida.adicionar_pontos(c.diabo, 12)
    assert c.partida.estado_atual == EstadoPartida.FIM_DE_JOGO
    c.verificar_fim_por_tentos()
    c.verificar_fim_por_tentos()  # idempotente
    assert c.resultado == ResultadoCampanha.EM_JOGO
    [lote] = c.fila_lotes
    assert (lote.atirador, lote.alvo) == (c.humano, c.humano)
    assert lote.origem == OrigemTiro.TIRO_FINAL and lote.fatal is True
    c.proximo_lote()
    assert c.puxar() is True
    assert c.resultado == ResultadoCampanha.MORTE


def test_avancar_fase_ate_a_vitoria_final(campanha):
    c = campanha
    for indice in range(len(FASES)):
        assert c.indice_fase == indice
        assert len(c.tambor.balas) == FASES[indice].balas
        assert c.diabo.taxa_blefe == FASES[indice].taxa_blefe
        c.tambor = Tambor(6, [0])
        enfileirar(c, c.diabo, 1)
        c.proximo_lote()
        assert c.puxar() is True
        if indice < len(FASES) - 1:
            assert c.resultado == ResultadoCampanha.VITORIA_FASE
            c.avancar_fase()
            assert c.resultado == ResultadoCampanha.EM_JOGO
            assert c.partida.pontos_jogador1 == 0
            assert c.tambor.indice == 0
    assert c.resultado == ResultadoCampanha.VITORIA_FINAL


def test_vitoria_por_tentos_na_fase_3_e_final(campanha):
    c = campanha
    c.iniciar_fase(2)
    c.partida.iniciar_nova_rodada()
    c.partida.adicionar_pontos(c.humano, 12)
    c.verificar_fim_por_tentos()
    assert c.resultado == ResultadoCampanha.VITORIA_FINAL


def test_avancar_fase_ignora_quando_em_jogo(campanha):
    campanha.avancar_fase()
    assert campanha.indice_fase == 0


# --- serialização ---------------------------------------------------------------------


def test_salvar_no_meio_da_roleta_e_retomar(campanha):
    c = campanha
    c.iniciar_fase(1)
    c.partida.iniciar_nova_rodada()
    c.tambor = Tambor(6, [4])
    enfileirar(c, c.humano, 3)
    enfileirar(c, c.diabo, 2, OrigemTiro.RECUSA_ENVIDO)
    c.proximo_lote()
    c.puxar()  # câmara 0 vazia
    c.timer_restante = 9.4

    dados = c.para_dict()
    assert dados["campanha"]["lote_atual"]["puxadas"] == 2  # restantes
    assert dados["campanha"]["lote_atual"]["atirador"] == "j1"
    assert dados["campanha"]["tambor"] == {"camaras": 6, "balas": [4], "indice": 1}

    r = ida_e_volta(c)
    assert r.para_dict() == c.para_dict()
    assert r.indice_fase == 1 and r.config is FASES[1]
    assert r.diabo.taxa_blefe == FASES[1].taxa_blefe
    assert r.lote_atual.alvo is r.humano
    assert r.puxadas_restantes == 2
    assert r.fila_lotes[0].alvo is r.diabo
    assert r.timer_restante == 9.4
    assert r.partida.jogador1 is r.humano and r.partida.jogador2 is r.diabo

    # R9.8: as próximas puxadas dão o mesmo resultado na original e na carregada
    for camp in (c, r):
        assert [camp.puxar(), camp.puxar()] == [False, False]
        camp.proximo_lote()
        assert [camp.puxar(), camp.puxar()] == [False, True]
        assert camp.resultado == ResultadoCampanha.VITORIA_FASE


def test_para_dict_inclui_lotes_ainda_na_partida(campanha):
    c = campanha
    c.partida.iniciar_nova_rodada()
    c.partida.ir_ao_baralho(c.humano)
    r = ida_e_volta(c)
    assert len(r.fila_lotes) == 1
    assert r.fila_lotes[0].origem == OrigemTiro.BARALHO


@pytest.mark.parametrize(
    "estragar",
    [
        lambda d: d.pop("campanha"),
        lambda d: d["campanha"].update(indice_fase=7),
        lambda d: d["campanha"].update(resultado="GANHOU"),
        lambda d: d["campanha"].update(tambor={"camaras": 6, "balas": [], "indice": 0}),
        lambda d: d["campanha"].update(fila_lotes=[{"atirador": "j9"}]),
        lambda d: d["partida"].update(estado_atual=None),
        lambda d: d["partida"].pop("mao_j1"),
    ],
)
def test_save_invalido(campanha, estragar):
    campanha.partida.iniciar_nova_rodada()
    dados = json.loads(json.dumps(campanha.para_dict()))
    estragar(dados)
    with pytest.raises(SaveInvalido):
        Campanha.de_dict(dados)


@pytest.mark.parametrize("lixo", [None, [], "texto", 42])
def test_save_lixo(lixo):
    with pytest.raises(SaveInvalido):
        Campanha.de_dict(lixo)
