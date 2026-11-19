import random
import re

from conftest import cartas
from core.deck import Baralho
from core.fase import FASES
from core.falas import FRASES, FRASES_LEITURA, GATILHOS_LEITURA, FalasDiabo, GatilhoFala

MAO = cartas("7_espadas", "3_copas", "11_ouros")


def cartas_citadas(frase: str) -> set[str]:
    """Ids das cartas cujo nome_completo aparece na frase."""
    return {
        c.para_id()
        for c in Baralho()
        if re.search(rf"(?<!\d){re.escape(c.nome_completo)}(?! \()", frase)
    }


def test_banco_tem_frases_suficientes():
    for gatilho in GatilhoFala:
        assert len(FRASES[gatilho]) >= 3, gatilho
    assert len(FRASES_LEITURA) >= 5
    assert all("{carta}" in f for f in FRASES_LEITURA)


def test_fase_1_nunca_cita_cartas():
    falas = FalasDiabo(random.Random(1))
    for _ in range(300):
        for gatilho in GatilhoFala:
            frase = falas.escolher(gatilho, FASES[0], MAO)
            assert frase is not None
            assert cartas_citadas(frase) == set(), frase


def test_fase_3_cita_carta_real_da_mao():
    falas = FalasDiabo(random.Random(7))
    ids_mao = {c.para_id() for c in MAO}
    citou = 0
    for _ in range(200):
        frase = falas.escolher(GatilhoFala.TURNO_JOGADOR, FASES[2], MAO)
        citadas = cartas_citadas(frase)
        assert citadas <= ids_mao, frase
        citou += bool(citadas)
    assert citou > 0


def test_leitura_so_em_gatilhos_de_provocacao():
    falas = FalasDiabo(random.Random(3))
    for gatilho in set(GatilhoFala) - GATILHOS_LEITURA:
        for _ in range(100):
            assert cartas_citadas(falas.escolher(gatilho, FASES[2], MAO)) == set()


def test_mao_vazia_nao_cita_carta():
    falas = FalasDiabo(random.Random(5))
    for _ in range(100):
        frase = falas.escolher(GatilhoFala.INICIO_MAO, FASES[2], [])
        assert frase in FRASES[GatilhoFala.INICIO_MAO]


def test_rng_fixo_e_deterministico():
    a, b = FalasDiabo(random.Random(9)), FalasDiabo(random.Random(9))
    for gatilho in GatilhoFala:
        assert a.escolher(gatilho, FASES[1], MAO) == b.escolher(gatilho, FASES[1], MAO)


# --- RitmoFalas (fase 3, R6.6) ---------------------------------------------------------
from core.falas import RitmoFalas  # noqa: E402


def test_ritmo_so_na_fase_3():
    assert [RitmoFalas.ativo_na_fase(f) for f in FASES] == [False, False, True]


def test_ritmo_inativo_nao_fala():
    r = RitmoFalas(random.Random(0))
    assert not r.avancar(100.0, False)


def test_ritmo_primeira_fala_apos_atraso_e_depois_intervalo():
    r = RitmoFalas(random.Random(0))
    r.iniciar_decisao()
    assert not r.avancar(RitmoFalas.ATRASO_INICIAL_S - 0.1, False)
    assert r.avancar(0.2, False)
    # a próxima só depois de pelo menos INTERVALO_MIN_S
    t = 0.0
    while not r.avancar(0.1, False):
        t += 0.1
    assert RitmoFalas.INTERVALO_MIN_S - 0.11 <= t <= RitmoFalas.INTERVALO_MAX_S


def test_ritmo_espera_balao_e_intervalo_desde_ultima_fala():
    r = RitmoFalas(random.Random(0))
    r.iniciar_decisao()
    r.registrar_fala()  # ex.: INICIO_MAO acabou de aparecer
    assert not r.avancar(3.0, False)  # passou o atraso, mas não os 4 s desde a fala
    assert not r.avancar(1.5, True)  # 4,5 s, mas com balão na tela
    assert r.avancar(0.1, False)


def test_ritmo_parar_desativa():
    r = RitmoFalas(random.Random(0))
    r.iniciar_decisao()
    r.parar()
    assert not r.ativo
    assert not r.avancar(10.0, False)
