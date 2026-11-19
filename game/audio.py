from pathlib import Path
from typing import Optional
import pygame
from core.fase import ConfigFase
from game.paths import ASSETS


class Audio:
    """Música por fase e efeitos, com fallback silencioso (design §4.3, R11).

    - Sem mixer (falha no init, driver ausente) ou sem arquivo, tudo vira no-op: o jogo
      segue sem som e sem erro (R11.3).
    - Procura `{nome}.ogg` e depois `{nome}.wav`; um arquivo que não carrega cai no próximo.
    - A troca de faixa espera o fade de saída terminar antes do `load`, porque
      `mixer.music.load` corta na hora a faixa que ainda está sumindo.
    """

    DIR_MUSICA: Path = ASSETS / "music"
    DIR_SFX: Path = ASSETS / "sfx"
    EXTENSOES = (".ogg", ".wav")

    VOLUME_MUSICA = 0.5
    FADE_SAIDA_TROCA_MS = 600  # fade de saída antes de carregar a faixa nova
    CANAIS = 16
    # Ganho por efeito (0..1), multiplicado pelo volume pedido na chamada.
    GANHO_EFEITO = {
        "disparo": 1.0,
        "clique_vazio": 0.9,
        "engatilhar": 0.8,
        "risada": 0.9,
        "carta": 0.6,
        "tique": 0.5,
    }
    # A risada tem canal próprio: uma nova interrompe a anterior, sem empilhar.
    CANAL_RISADA = 0

    def __init__(self) -> None:
        self.ativo = False
        self._sons: dict[str, Optional[pygame.mixer.Sound]] = {}
        self.faixa_atual: Optional[Path] = None  # faixa tocando ou a caminho
        self._pendente: Optional[tuple[Path, int]] = None  # (faixa, fade_ms) após o fade
        self._espera_ms = 0.0
        self.fator_volume = 1.0  # abaixa a música na pausa e na roleta
        self._canal_risada: Optional[pygame.mixer.Channel] = None
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init()
            self.ativo = pygame.mixer.get_init() is not None
            if self.ativo:
                pygame.mixer.set_num_channels(self.CANAIS)
                pygame.mixer.set_reserved(1)
                self._canal_risada = pygame.mixer.Channel(self.CANAL_RISADA)
        except Exception:  # pygame.error, mixer ausente (NotImplementedError) etc. (R11.3)
            self.ativo = False
            self._canal_risada = None

    # ==========================
    # ARQUIVOS
    # ==========================
    @classmethod
    def _candidatos(cls, pasta: Path, nome: str) -> list[Path]:
        """Arquivos existentes de `nome`, na ordem de preferência (.ogg, .wav)."""
        caminhos = [pasta / f"{nome}{ext}" for ext in cls.EXTENSOES]
        return [c for c in caminhos if c.is_file()]

    def _carregar_som(self, nome: str) -> Optional[pygame.mixer.Sound]:
        """Sound em cache; None se faltar ou nenhum arquivo carregar."""
        if nome not in self._sons:
            som = None
            for caminho in self._candidatos(self.DIR_SFX, nome):
                try:
                    som = pygame.mixer.Sound(str(caminho))
                    break
                except Exception:
                    continue
            self._sons[nome] = som
        return self._sons[nome]

    # ==========================
    # MÚSICA (R11.1)
    # ==========================
    def tocar_musica_fase(self, config: ConfigFase, fade_ms: int = 1200) -> None:
        """Toca `fase{n}` em loop com fade; a mesma faixa já tocando não reinicia."""
        self.fator_volume = 1.0
        if not self.ativo:
            return
        candidatos = self._candidatos(self.DIR_MUSICA, f"fase{config.numero}")
        if not candidatos:
            self.parar_musica()  # a faixa de outra fase não continua no lugar
            return
        if candidatos[0] == self.faixa_atual:
            self._aplicar_volume()
            return
        self.faixa_atual = candidatos[0]
        if self._musica_tocando():
            try:
                pygame.mixer.music.fadeout(self.FADE_SAIDA_TROCA_MS)
            except Exception:
                pass
            self._pendente = (candidatos[0], fade_ms)
            self._espera_ms = self.FADE_SAIDA_TROCA_MS
        else:
            self._pendente = None
            self._iniciar_faixa(fade_ms)

    def _iniciar_faixa(self, fade_ms: int) -> None:
        """Carrega e toca a faixa atual; tenta o próximo formato se um falhar."""
        if self.faixa_atual is None:
            return
        pasta, nome = self.faixa_atual.parent, self.faixa_atual.stem
        for caminho in self._candidatos(pasta, nome):
            try:
                pygame.mixer.music.load(str(caminho))
                pygame.mixer.music.set_volume(self.VOLUME_MUSICA * self.fator_volume)
                pygame.mixer.music.play(-1, fade_ms=fade_ms)
                return
            except Exception:
                continue
        self.faixa_atual = None

    def parar_musica(self, fade_ms: int = 800) -> None:
        """Some com a música (fade_ms = 0 para na hora)."""
        self._pendente = None
        self.faixa_atual = None
        self.fator_volume = 1.0
        if not self.ativo:
            return
        try:
            if fade_ms > 0:
                pygame.mixer.music.fadeout(fade_ms)
            else:
                pygame.mixer.music.stop()
        except Exception:
            pass

    def abaixar_musica(self, fator: float) -> None:
        """Volume relativo da música (1.0 = normal); só muda o mixer se mudou."""
        if abs(fator - self.fator_volume) < 1e-6:
            return
        self.fator_volume = fator
        self._aplicar_volume()

    def _aplicar_volume(self) -> None:
        if not self.ativo:
            return
        try:
            pygame.mixer.music.set_volume(self.VOLUME_MUSICA * self.fator_volume)
        except Exception:
            pass

    def _musica_tocando(self) -> bool:
        try:
            return bool(pygame.mixer.music.get_busy())
        except Exception:
            return False

    def atualizar(self, dt: float) -> None:
        """Completa a troca de faixa quando o fade de saída termina."""
        if self._pendente is None:
            return
        self._espera_ms -= dt * 1000
        if self._espera_ms <= 0 or not self._musica_tocando():
            _, fade_ms = self._pendente
            self._pendente = None
            self._iniciar_faixa(fade_ms)

    # ==========================
    # EFEITOS (R11.2)
    # ==========================
    def efeito(self, nome: str, volume: float = 1.0) -> None:
        """Toca `assets/sfx/{nome}`; silencioso se faltar ou sem mixer."""
        if not self.ativo:
            return
        som = self._carregar_som(nome)
        if som is None:
            return
        try:
            som.set_volume(max(0.0, min(1.0, self.GANHO_EFEITO.get(nome, 1.0) * volume)))
            if nome == "risada" and self._canal_risada is not None:
                self._canal_risada.play(som)
            else:
                som.play()
        except Exception:
            pass
