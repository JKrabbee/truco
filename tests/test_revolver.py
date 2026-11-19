import json
import random

import pytest

from core.revolver import Tambor


def test_carregar_com_rng_fixo_e_deterministico():
    a = Tambor.carregar(2, rng=random.Random(42))
    b = Tambor.carregar(2, rng=random.Random(42))
    assert a == b
    assert a.camaras == 6
    assert len(a.balas) == 2 and len(set(a.balas)) == 2
    assert all(0 <= x < 6 for x in a.balas)
    assert a.indice == 0


@pytest.mark.parametrize("n_balas", [0, 7])
def test_carregar_rejeita_numero_de_balas_invalido(n_balas):
    with pytest.raises(ValueError):
        Tambor.carregar(n_balas)


def test_puxada_avanca_uma_camara():
    tambor = Tambor(6, [5])
    assert tambor.disparadas == 0
    tambor.puxar()
    assert tambor.indice == 1
    assert tambor.disparadas == 1


@pytest.mark.parametrize("posicao", range(6))
def test_dispara_exatamente_na_posicao_da_bala(posicao):
    tambor = Tambor(6, [posicao])
    resultados = [tambor.puxar() for _ in range(posicao + 1)]
    assert resultados == [False] * posicao + [True]


def test_com_bala_a_sexta_puxada_sempre_dispara():
    for semente in range(50):
        tambor = Tambor.carregar(1, rng=random.Random(semente))
        assert any(tambor.puxar() for _ in range(6))


def test_puxar_alem_das_camaras_levanta_erro():
    tambor = Tambor(6, [0], indice=6)
    with pytest.raises(RuntimeError):
        tambor.puxar()


def test_para_dict_de_dict_ida_e_volta():
    tambor = Tambor(6, [2, 4], indice=2)
    copia = Tambor.de_dict(json.loads(json.dumps(tambor.para_dict())))
    assert copia == tambor
    assert copia.puxar() is True


@pytest.mark.parametrize(
    "dados",
    [
        {"camaras": 6, "balas": [], "indice": 0},
        {"camaras": 6, "balas": [6], "indice": 0},
        {"camaras": 6, "balas": [2, 2], "indice": 0},
        {"camaras": 6, "balas": [1], "indice": 3},  # a bala já teria disparado
        {"camaras": 6, "balas": [3]},
    ],
)
def test_de_dict_rejeita_tambor_incoerente(dados):
    with pytest.raises((ValueError, KeyError)):
        Tambor.de_dict(dados)
