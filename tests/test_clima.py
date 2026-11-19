"""Curva da luz por fase (R2.2), humor do Diabo (R1.1) e tique do timer (R10.2), sem pygame."""

import random

import pytest

from core.clima import CurvaLuz, Expressao, HumorDiabo, RitmoTique
from core.fase import FASES

DT = 1 / 60


def _amostrar(curva: CurvaLuz, segundos: float) -> list[tuple[int, float, bool]]:
    amostras = []
    for _ in range(int(segundos / DT)):
        curva.avancar(DT)
        amostras.append((curva.escurecimento, curva.foco, curva.em_queda))
    return amostras


def test_luz_de_cada_fase_e_diferente():
    assert [f.luz for f in FASES] == ["estavel", "oscila", "pisca"]


def test_luz_desconhecida_rejeitada():
    with pytest.raises(ValueError):
        CurvaLuz("disco")


def test_estavel_e_constante():
    amostras = _amostrar(CurvaLuz("estavel", random.Random(1)), 10)
    assert {(e, f) for e, f, _ in amostras} == {(0, 1.0)}


def test_oscila_e_senoide_lenta_sem_quedas():
    curva = CurvaLuz("oscila", random.Random(1))
    amostras = _amostrar(curva, 2 * CurvaLuz.PERIODO_OSCILA_S)
    alfas = [e for e, _, _ in amostras]
    assert max(alfas) == CurvaLuz.ALFA_OSCILA
    assert min(alfas) == 0
    assert not any(q for _, _, q in amostras)
    # Lenta: entre quadros o alfa muda no máximo 1 ponto.
    assert max(abs(a - b) for a, b in zip(alfas, alfas[1:])) <= 1
    focos = [f for _, f, _ in amostras]
    assert min(focos) == pytest.approx(1 - CurvaLuz.VARIACAO_FOCO_OSCILA, abs=1e-3)
    assert max(focos) <= 1.0


@pytest.mark.parametrize("semente", [1, 2, 3, 4, 5])
def test_pisca_tem_quedas_curtas(semente):
    curva = CurvaLuz("pisca", random.Random(semente))
    duracoes: list[float] = []
    atual = 0.0
    for _ in range(int(60 / 0.005)):  # passo fino para medir a duração
        curva.avancar(0.005)
        if curva.em_queda:
            atual += 0.005
            assert curva.escurecimento == CurvaLuz.ALFA_QUEDA
            assert curva.foco == 0.0
        elif atual:
            duracoes.append(atual)
            atual = 0.0
    assert len(duracoes) >= 60 / CurvaLuz.INTERVALO_QUEDA_MAX_S
    for d in duracoes:
        assert CurvaLuz.QUEDA_MIN_S - 0.006 <= d <= CurvaLuz.QUEDA_MAX_S + 0.006


def test_pisca_tem_quedas_duplas_e_nunca_triplas():
    curva = CurvaLuz("pisca", random.Random(7))
    inicios: list[float] = []
    t, antes = 0.0, False
    for _ in range(int(300 / 0.005)):
        curva.avancar(0.005)
        t += 0.005
        if curva.em_queda and not antes:
            inicios.append(t)
        antes = curva.em_queda
    # Pausa curta entre as quedas de uma dupla (< 0,3 s entre inícios).
    curtos = [b - a < 0.3 for a, b in zip(inicios, inicios[1:])]
    assert any(curtos)
    assert not any(x and y for x, y in zip(curtos, curtos[1:]))


def test_pisca_com_quadro_longo_nao_trava():
    curva = CurvaLuz("pisca", random.Random(3))
    curva.avancar(30.0)
    assert 0 <= curva.escurecimento <= CurvaLuz.ALFA_QUEDA


def test_humor_prioridades():
    humor = HumorDiabo()
    assert humor.expressao(falando=False) is Expressao.CALMO
    assert humor.expressao(falando=True) is Expressao.FALANDO
    assert humor.expressao(falando=True, contrariado=True) is Expressao.IRRITADO
    humor.irritar()
    assert humor.expressao(falando=True) is Expressao.IRRITADO
    humor.ferir()
    assert humor.expressao(falando=True, contrariado=True) is Expressao.FERIDO


def test_irritacao_expira():
    humor = HumorDiabo()
    humor.irritar()
    humor.avancar(HumorDiabo.DURACAO_IRRITADO_S - 0.1)
    assert humor.expressao(falando=False) is Expressao.IRRITADO
    humor.avancar(0.2)
    assert humor.expressao(falando=False) is Expressao.CALMO


def test_irritar_de_novo_nao_encurta():
    humor = HumorDiabo()
    humor.irritar(5.0)
    humor.irritar(1.0)
    humor.avancar(3.0)
    assert humor.expressao(falando=False) is Expressao.IRRITADO


def test_valores_das_expressoes_sao_nomes_dos_pngs():
    assert {e.value for e in Expressao} == {"calmo", "falando", "irritado", "ferido"}


# ==========================
# RitmoTique (R10.2)
# ==========================
def _tiques(inicio: float, dt: float = DT) -> list[tuple[float, float]]:
    """(restante, intensidade) de cada tique, do timer em `inicio` até zerar."""
    ritmo = RitmoTique()
    restante, tiques = inicio, []
    while restante > 0:
        restante -= dt
        intensidade = ritmo.avancar(dt, restante)
        if intensidade is not None:
            tiques.append((restante, intensidade))
    return tiques


def test_tique_silencioso_antes_dos_3_s_finais():
    tiques = _tiques(15.0)
    assert tiques
    assert all(r <= RitmoTique.ULTIMOS_S for r, _ in tiques)
    assert tiques[0][0] > RitmoTique.ULTIMOS_S - 2 * DT  # o primeiro sai ao entrar na janela


def test_tique_acelera_e_fica_mais_forte():
    tiques = _tiques(6.0)
    assert 8 <= len(tiques) <= 12
    intervalos = [a[0] - b[0] for a, b in zip(tiques, tiques[1:])]
    assert intervalos[0] == pytest.approx(RitmoTique.INTERVALO_INICIAL_S, abs=0.05)
    assert intervalos[-1] < 0.25
    assert all(b <= a + DT for a, b in zip(intervalos, intervalos[1:]))  # nunca desacelera
    intensidades = [i for _, i in tiques]
    assert intensidades == sorted(intensidades)
    assert intensidades[0] == pytest.approx(RitmoTique.INTENSIDADE_MIN, abs=0.05)
    assert intensidades[-1] > 0.9


def test_tique_nao_toca_com_tempo_esgotado_nem_acumula_em_quadro_longo():
    ritmo = RitmoTique()
    assert ritmo.avancar(DT, 0.0) is None
    assert ritmo.avancar(DT, 2.5) is not None
    assert ritmo.avancar(2.0, 0.5) is not None  # um tique só, mesmo atrasado
    assert ritmo.avancar(DT, 0.5 - DT) is None


def test_tique_reinicia_por_decisao_e_retomada_dentro_da_janela():
    ritmo = RitmoTique()
    assert ritmo.avancar(DT, 2.9) is not None
    assert ritmo.avancar(DT, 2.9 - DT) is None
    ritmo.reiniciar()
    assert ritmo.avancar(DT, 2.0) is not None  # timer retomado com 2 s: tique na hora
    assert ritmo.avancar(DT, 6.0) is None  # nova decisão com o timer cheio: silêncio
    assert ritmo.ate_proximo is None
