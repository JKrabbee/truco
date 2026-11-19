from typing import Optional
import pygame
from core.campanha import Campanha
from game.game_state import GameState, GameStateManager, MenuState, PartidaState
from game.save_manager import SaveManager
from ui.button import Button

# Abertura fixa por fase; as falas do FalasDiabo entram no Bloco 6.
SUBTITULOS_FASE = {
    1: "O Diabo te convida para uma mão. Ninguém levanta antes do fim.",
    2: "Agora ele mente. E sorri do mesmo jeito.",
    3: "Ele sabe o que tu tem na mão. Duas balas no tambor.",
}


class TelaTexto(GameState):
    """Tela preta com título, linhas e um botão; Enter/Espaço avança (R7.1)."""

    TEXTO_BOTAO = "Continuar"

    def __init__(self, manager: GameStateManager):
        super().__init__(manager)
        self.botao: Optional[Button] = None
        pygame.font.init()
        self.font_tit = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 40, bold=True)
        self.font_sub = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 18, italic=True)
        self.font_info = pygame.font.SysFont("DejaVu Sans, Arial, sans-serif", 14)

    # Conteúdo definido pelas subclasses
    def titulo(self) -> str:
        raise NotImplementedError

    def cor_titulo(self) -> tuple[int, int, int]:
        return (200, 55, 40)

    def linhas(self) -> list[str]:
        return []

    def avancar(self) -> None:
        raise NotImplementedError

    def entrar(self) -> None:
        self._posicionar_botao()

    def sair(self) -> None:
        pass

    def redimensionar(self, largura: int, altura: int) -> None:
        self._posicionar_botao()

    def _posicionar_botao(self) -> None:
        btn_w, btn_h = 240, 48
        self.botao = Button(
            rect=pygame.Rect(
                (self.manager.largura - btn_w) // 2,
                self.manager.altura // 2 + 90,
                btn_w,
                btn_h,
            ),
            texto=f"{self.TEXTO_BOTAO} (Enter)",
            callback=self.avancar,
        )

    def tratar_evento(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (
            pygame.K_RETURN,
            pygame.K_KP_ENTER,
            pygame.K_SPACE,
        ):
            self.avancar()
            return
        if self.botao is not None:
            self.botao.tratar_evento(event)

    def atualizar(self, dt: float) -> None:
        if self.botao is not None:
            self.botao.verificar_hover(pygame.mouse.get_pos())

    def desenhar(self, tela: pygame.Surface) -> None:
        tela.fill((0, 0, 0))
        cx, cy = self.manager.largura // 2, self.manager.altura // 2

        txt = self.font_tit.render(self.titulo(), True, self.cor_titulo())
        tela.blit(txt, txt.get_rect(center=(cx, cy - 110)))

        y = cy - 50
        for i, linha in enumerate(self.linhas()):
            font = self.font_sub if i == 0 else self.font_info
            txt = font.render(linha, True, (220, 210, 195))
            tela.blit(txt, txt.get_rect(center=(cx, y)))
            y += 34 if i == 0 else 24

        if self.botao is not None:
            self.botao.desenhar(tela)


class IntroFaseState(TelaTexto):
    """Introdução da fase com número e nome (R2.3). Salva e troca a música ao entrar."""

    TEXTO_BOTAO = "Sentar à mesa"

    def __init__(self, manager: GameStateManager, campanha: Campanha):
        super().__init__(manager)
        self.campanha = campanha

    def entrar(self) -> None:
        super().entrar()
        self.manager.audio.tocar_musica_fase(self.campanha.config)  # R11.1
        SaveManager.salvar(self.campanha.para_dict())  # troca de fase (R9.2)

    def ao_fechar(self) -> None:
        SaveManager.salvar(self.campanha.para_dict())

    def titulo(self) -> str:
        config = self.campanha.config
        return f"FASE {config.numero} — {config.nome.upper()}"

    def linhas(self) -> list[str]:
        config = self.campanha.config
        tempo = (
            "sem limite"
            if config.tempo_decisao_s is None
            else f"{config.tempo_decisao_s:.0f} s"
        )
        balas = "1 bala" if config.balas == 1 else f"{config.balas} balas"
        return [
            SUBTITULOS_FASE.get(config.numero, ""),
            f"Tambor: {balas} em 6 câmaras   ·   Tempo por decisão: {tempo}",
        ]

    def avancar(self) -> None:
        self.manager.mudar_estado(PartidaState(self.manager, self.campanha))


class MorteState(TelaTexto):
    """Tela de morte; o save já foi apagado (R3.5, R9.6)."""

    TEXTO_BOTAO = "Menu"

    def entrar(self) -> None:
        super().entrar()
        self.manager.audio.parar_musica(150)  # já cortada no disparo; garante o silêncio
        SaveManager.apagar()

    def titulo(self) -> str:
        return "VOCÊ MORREU"

    def linhas(self) -> list[str]:
        return ["A bala era tua. O Diabo recolhe as cartas.", "Teu save foi apagado."]

    def avancar(self) -> None:
        self.manager.mudar_estado(MenuState(self.manager))


class VitoriaFinalState(TelaTexto):
    """Vitória sobre as 3 fases; o save é apagado (R2.5, R9.6)."""

    TEXTO_BOTAO = "Menu"

    def entrar(self) -> None:
        super().entrar()
        self.manager.audio.parar_musica(2000)
        SaveManager.apagar()

    def titulo(self) -> str:
        return "VOCÊ VENCEU O DIABO"

    def cor_titulo(self) -> tuple[int, int, int]:
        return (230, 195, 95)

    def linhas(self) -> list[str]:
        return [
            "Três mesas, três fases. Tu levanta vivo.",
            "O jogo terminou e o save foi apagado.",
        ]

    def avancar(self) -> None:
        self.manager.mudar_estado(MenuState(self.manager))
