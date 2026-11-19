from conftest import cartas
from core.diabo import JogadorDiabo
from core.match import EstadoPartida, PartidaTruco
from core.player import JogadorBot
from core.rules import RespostaAposta, TipoEnvido

ENVIDO_33_A = ["7_espadas", "6_espadas", "4_copas"]
ENVIDO_33_B = ["7_ouros", "6_ouros", "4_bastos"]


def test_aumentar_sem_aumento_segue_envido_real_falta(montar_partida):
    p = montar_partida(ENVIDO_33_A, ENVIDO_33_B)
    p.cantar_envido(p.jogador1, TipoEnvido.ENVIDO)

    p.responder_envido(RespostaAposta.AUMENTAR)
    assert p.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO
    assert p.aposta_envido_atual == TipoEnvido.REAL_ENVIDO
    assert p.quem_deve_responder_envido is p.jogador1
    assert p.valor_envido_acumulado == 5

    p.responder_envido(RespostaAposta.AUMENTAR)
    assert p.aposta_envido_atual == TipoEnvido.FALTA_ENVIDO
    assert p.quem_deve_responder_envido is p.jogador2

    # Na Falta não há aumento: vira Quero e o envido é resolvido.
    p.responder_envido(RespostaAposta.AUMENTAR)
    assert p.estado_atual != EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO
    assert p.envido_disputado is True


def test_aumento_explicito_continua_valendo(montar_partida):
    p = montar_partida(ENVIDO_33_A, ENVIDO_33_B)
    p.cantar_envido(p.jogador1, TipoEnvido.ENVIDO)
    p.responder_envido(RespostaAposta.AUMENTAR, aumento=TipoEnvido.FALTA_ENVIDO)
    assert p.aposta_envido_atual == TipoEnvido.FALTA_ENVIDO
    assert p.quem_deve_responder_envido is p.jogador1


def test_bots_com_31_ou_mais_que_sempre_aumentam_nao_travam(monkeypatch):
    # random() = 0.0 faz o JogadorBot escolher AUMENTAR sempre que tem ≥ 31 de envido.
    monkeypatch.setattr("core.player.random.random", lambda: 0.0)
    j1, j2 = JogadorBot("Bot A"), JogadorDiabo(taxa_blefe=0.5)
    p = PartidaTruco(j1, j2)
    p.iniciar_nova_rodada()
    j1.receber_cartas(cartas(*ENVIDO_33_A))
    j2.receber_cartas(cartas(*ENVIDO_33_B))

    assert p.cantar_envido(j1, TipoEnvido.ENVIDO)
    for _ in range(10):
        if p.estado_atual != EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO:
            break
        quem = p.quem_deve_responder_envido
        resposta = quem.responder_aposta(
            p.aposta_envido_atual, p.obter_estado_mesa_para_jogador(quem)
        )
        assert resposta == RespostaAposta.AUMENTAR
        p.responder_envido(resposta)
    assert p.estado_atual != EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO
    assert p.envido_disputado is True


def test_diabo_escolhe_o_aumento_padrao():
    diabo = JogadorDiabo(taxa_blefe=0.0)
    assert diabo.nome == "O Diabo"
    assert diabo.escolher_aumento_envido(TipoEnvido.ENVIDO) == TipoEnvido.REAL_ENVIDO
    assert diabo.escolher_aumento_envido(TipoEnvido.REAL_ENVIDO) == TipoEnvido.FALTA_ENVIDO
    assert diabo.escolher_aumento_envido(TipoEnvido.FALTA_ENVIDO) is None
