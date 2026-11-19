import json
import os
from pathlib import Path
from typing import Any, Optional

from core.campanha import SaveInvalido  # reexportada: game.save_manager.SaveInvalido
from game.paths import SAVE_DIR, SAVE_FILE

__all__ = ["SaveManager", "SaveInvalido", "VERSAO_SAVE"]

VERSAO_SAVE = 1


class SaveManager:
    """Grava, lê e apaga o save único em save/save.json (R9)."""

    @staticmethod
    def _arquivo_tmp() -> Path:
        """Arquivo temporário da escrita atômica, ao lado do save."""
        return SAVE_FILE.with_name(SAVE_FILE.name + ".tmp")

    @staticmethod
    def existe() -> bool:
        """True se há um arquivo de save (válido ou não)."""
        return SAVE_FILE.is_file()

    @staticmethod
    def salvar(dados: dict[str, Any]) -> None:
        """Grava os dados com "versao" em um .tmp e troca pelo save com os.replace (R9.4)."""
        # Cópia com "versao" na frente; o dict do chamador não é alterado.
        conteudo = {"versao": VERSAO_SAVE}
        conteudo.update((k, v) for k, v in dados.items() if k != "versao")
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SaveManager._arquivo_tmp()
        try:
            with open(tmp, "w", encoding="utf-8") as arquivo:
                json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(tmp, SAVE_FILE)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    @staticmethod
    def carregar() -> Optional[dict[str, Any]]:
        """Lê o save; None se não existe, SaveInvalido se o JSON ou a versão forem inválidos."""
        if not SAVE_FILE.is_file():
            return None
        try:
            with open(SAVE_FILE, encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
        except (OSError, ValueError) as erro:  # JSONDecodeError e UnicodeDecodeError são ValueError
            raise SaveInvalido(f"Save ilegível: {erro!r}") from erro
        if not isinstance(dados, dict):
            raise SaveInvalido("Save não é um objeto JSON.")
        versao = dados.get("versao")
        if type(versao) is not int or versao != VERSAO_SAVE:
            raise SaveInvalido(f"Versão de save incompatível: {versao!r}")
        return dados

    @staticmethod
    def apagar() -> None:
        """Remove o save e o .tmp, se existirem (R9.6)."""
        SAVE_FILE.unlink(missing_ok=True)
        SaveManager._arquivo_tmp().unlink(missing_ok=True)
