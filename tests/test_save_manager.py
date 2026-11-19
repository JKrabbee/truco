import json
import random
from pathlib import Path

import pytest

from core.campanha import Campanha
from game import save_manager
from game.save_manager import VERSAO_SAVE, SaveInvalido, SaveManager


@pytest.fixture
def arquivo_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Aponta SAVE_DIR/SAVE_FILE para uma pasta temporária (a pasta ainda não existe)."""
    pasta = tmp_path / "save"
    arquivo = pasta / "save.json"
    monkeypatch.setattr(save_manager, "SAVE_DIR", pasta)
    monkeypatch.setattr(save_manager, "SAVE_FILE", arquivo)
    return arquivo


def _campanha_em_jogo() -> Campanha:
    campanha = Campanha.nova(rng=random.Random(7))
    campanha.partida.iniciar_nova_rodada()
    return campanha


def test_reexporta_save_invalido_de_core() -> None:
    from core import campanha

    assert SaveInvalido is campanha.SaveInvalido
    assert issubclass(SaveInvalido, ValueError)


def test_sem_save_carregar_devolve_none(arquivo_save: Path) -> None:
    assert not SaveManager.existe()
    assert SaveManager.carregar() is None


def test_ida_e_volta_com_campanha(arquivo_save: Path) -> None:
    campanha = _campanha_em_jogo()
    dados = campanha.para_dict()

    SaveManager.salvar(dados)

    assert SaveManager.existe()
    assert "versao" not in dados  # o dict do chamador não é alterado
    carregado = SaveManager.carregar()
    assert carregado is not None
    assert carregado["versao"] == VERSAO_SAVE
    assert carregado["campanha"] == json.loads(json.dumps(dados["campanha"]))
    assert carregado["partida"] == json.loads(json.dumps(dados["partida"]))

    retomada = Campanha.de_dict(carregado)
    assert retomada.indice_fase == campanha.indice_fase
    assert [c.para_id() for c in retomada.humano.mao] == [
        c.para_id() for c in campanha.humano.mao
    ]


def test_escrita_atomica_sem_tmp_sobrando(arquivo_save: Path) -> None:
    SaveManager.salvar({"campanha": {"a": 1}, "partida": {}})
    SaveManager.salvar({"campanha": {"a": 2}, "partida": {}})

    assert sorted(p.name for p in arquivo_save.parent.iterdir()) == ["save.json"]
    assert SaveManager.carregar()["campanha"] == {"a": 2}


def test_falha_na_escrita_preserva_save_e_remove_tmp(
    arquivo_save: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    SaveManager.salvar({"campanha": {"a": 1}, "partida": {}})

    def replace_quebrado(*_args: object) -> None:
        raise OSError("disco cheio")

    monkeypatch.setattr(save_manager.os, "replace", replace_quebrado)
    with pytest.raises(OSError):
        SaveManager.salvar({"campanha": {"a": 2}, "partida": {}})

    assert sorted(p.name for p in arquivo_save.parent.iterdir()) == ["save.json"]
    assert SaveManager.carregar()["campanha"] == {"a": 1}


@pytest.mark.parametrize(
    "conteudo",
    [b"{isso nao e json", b"", b"\xff\xfe\x00lixo", b"[1, 2, 3]", b'"texto"'],
)
def test_json_lixo_levanta_save_invalido(arquivo_save: Path, conteudo: bytes) -> None:
    arquivo_save.parent.mkdir(parents=True)
    arquivo_save.write_bytes(conteudo)

    with pytest.raises(SaveInvalido):
        SaveManager.carregar()


@pytest.mark.parametrize("versao", [None, 0, VERSAO_SAVE + 1, "1", 1.0, True])
def test_versao_errada_levanta_save_invalido(arquivo_save: Path, versao: object) -> None:
    dados = _campanha_em_jogo().para_dict()
    if versao is not None:
        dados["versao"] = versao
    arquivo_save.parent.mkdir(parents=True)
    arquivo_save.write_text(json.dumps(dados), encoding="utf-8")

    with pytest.raises(SaveInvalido):
        SaveManager.carregar()


def test_chaves_faltando_viram_save_invalido_na_campanha(arquivo_save: Path) -> None:
    SaveManager.salvar({"campanha": {}, "partida": {}})

    dados = SaveManager.carregar()
    with pytest.raises(SaveInvalido):
        Campanha.de_dict(dados)


def test_apagar_remove_save_e_tmp(arquivo_save: Path) -> None:
    SaveManager.salvar({"campanha": {}, "partida": {}})
    tmp = arquivo_save.with_name(arquivo_save.name + ".tmp")
    tmp.write_text("resto de escrita interrompida", encoding="utf-8")

    SaveManager.apagar()

    assert not SaveManager.existe()
    assert not arquivo_save.exists()
    assert not tmp.exists()
    SaveManager.apagar()  # sem arquivos, não levanta erro
