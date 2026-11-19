import pytest

from conftest import RAIZ
from core.card import Carta
from core.deck import Baralho


def test_todas_as_cartas_fazem_ida_e_volta():
    baralho = Baralho()
    assert len(baralho) == 40
    for carta in baralho:
        assert Carta.de_id(carta.para_id()) == carta


def test_ids_sao_unicos():
    ids = [c.para_id() for c in Baralho()]
    assert len(set(ids)) == 40


def test_para_id_bate_com_os_pngs():
    pngs = {p.stem for p in (RAIZ / "assets" / "cards").glob("*_*.png")}
    ids = {c.para_id() for c in Baralho()}
    assert ids <= pngs


def test_formato_do_id():
    assert Carta.de_id("7_espadas").nome_completo == "7 de Espadas (Manilha)"
    assert Carta.de_id("12_ouros").para_id() == "12_ouros"


@pytest.mark.parametrize("id_ruim", ["", "8_copas", "7_paus", "sete_espadas", "7", "1_2_3"])
def test_id_invalido_levanta_value_error(id_ruim):
    with pytest.raises(ValueError):
        Carta.de_id(id_ruim)


def test_baralho_serializa_lista_restante():
    baralho = Baralho()
    baralho.embaralhar()
    baralho.distribuir_mao(3)
    copia = Baralho.de_lista(baralho.para_lista())
    assert copia.cartas == baralho.cartas
