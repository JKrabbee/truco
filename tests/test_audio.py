"""Fallback silencioso e troca de faixa do `Audio` (R11.1, R11.3), com o driver dummy.

Exceção à regra do §9 (pytest só para `core/`): o R11.3 é fácil de quebrar sem perceber,
e o driver dummy do SDL deixa testar sem placa de som.
"""

import math
import os
import struct
import wave
from pathlib import Path

import pytest

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

from core.fase import FASES  # noqa: E402
from game.audio import Audio  # noqa: E402


def _wav(caminho: Path, segundos: float = 0.3) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        n = int(22050 * segundos)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(n)))


@pytest.fixture
def pastas(tmp_path, monkeypatch):
    """Redireciona assets/music e assets/sfx para um diretório temporário."""
    musica, sfx = tmp_path / "music", tmp_path / "sfx"
    musica.mkdir()
    sfx.mkdir()
    monkeypatch.setattr(Audio, "DIR_MUSICA", musica)
    monkeypatch.setattr(Audio, "DIR_SFX", sfx)
    yield musica, sfx
    if pygame.mixer.get_init():
        pygame.mixer.quit()


def test_mixer_falhando_vira_silencio(pastas, monkeypatch):
    musica, sfx = pastas
    _wav(sfx / "disparo.wav")
    _wav(musica / "fase1.wav")

    def falhar(*_args, **_kwargs):
        raise pygame.error("sem placa de som")

    if pygame.mixer.get_init():
        pygame.mixer.quit()
    monkeypatch.setattr(pygame.mixer, "init", falhar)
    audio = Audio()
    assert not audio.ativo
    audio.efeito("disparo")
    audio.tocar_musica_fase(FASES[0])
    audio.abaixar_musica(0.3)
    audio.atualizar(1.0)
    audio.parar_musica()
    assert audio.faixa_atual is None


def test_arquivos_ausentes_ficam_em_silencio(pastas):
    audio = Audio()
    assert audio.ativo
    for nome in Audio.GANHO_EFEITO:
        audio.efeito(nome)
        assert audio._sons[nome] is None
    audio.tocar_musica_fase(FASES[1])
    assert audio.faixa_atual is None
    assert not pygame.mixer.music.get_busy()


def test_arquivo_corrompido_cai_no_proximo_formato(pastas):
    musica, sfx = pastas
    (sfx / "clique_vazio.ogg").write_bytes(b"lixo")
    _wav(sfx / "clique_vazio.wav")
    (sfx / "risada.wav").write_bytes(b"RIFF quebrado")
    (musica / "fase1.ogg").write_bytes(b"lixo")
    _wav(musica / "fase1.wav")

    audio = Audio()
    audio.efeito("clique_vazio")
    audio.efeito("risada")
    assert audio._sons["clique_vazio"] is not None
    assert audio._sons["risada"] is None
    audio.tocar_musica_fase(FASES[0])
    assert pygame.mixer.music.get_busy()


def test_troca_de_faixa_espera_o_fade_e_mesma_faixa_nao_reinicia(pastas):
    musica, _ = pastas
    for n in (1, 2):
        _wav(musica / f"fase{n}.wav", segundos=3.0)
    audio = Audio()

    audio.tocar_musica_fase(FASES[0])
    assert audio.faixa_atual == musica / "fase1.wav"
    assert audio._pendente is None and pygame.mixer.music.get_busy()

    audio.tocar_musica_fase(FASES[0])  # intro → partida: nada muda
    assert audio._pendente is None

    audio.tocar_musica_fase(FASES[1])
    assert audio.faixa_atual == musica / "fase2.wav"
    assert audio._pendente is not None  # ainda saindo a fase 1
    audio.atualizar(Audio.FADE_SAIDA_TROCA_MS / 1000 + 0.05)
    assert audio._pendente is None and pygame.mixer.music.get_busy()

    audio.parar_musica(0)
    assert audio.faixa_atual is None


def test_volume_relativo_da_musica(pastas):
    musica, _ = pastas
    _wav(musica / "fase1.wav", segundos=2.0)
    audio = Audio()
    audio.tocar_musica_fase(FASES[0])
    audio.abaixar_musica(0.5)
    assert pygame.mixer.music.get_volume() == pytest.approx(Audio.VOLUME_MUSICA * 0.5, abs=0.02)
    audio.tocar_musica_fase(FASES[0])  # voltar à partida restaura o volume
    assert pygame.mixer.music.get_volume() == pytest.approx(Audio.VOLUME_MUSICA, abs=0.02)
