import math
from typing import Callable, Optional
import pygame
from core.clima import RitmoTique


class TimerBar:
    """Barra do tempo de decisão (R10.2): encolhe e fica vermelha, pulsando, nos últimos 3 s.

    `ao_tique(intensidade)` é chamado a cada tique do `RitmoTique`: nos 3 s finais, cada
    vez mais rápido e mais forte (intensidade 0.5..1.0, usada como volume).
    """

    ULTIMOS_S = 3.0
    COR_FUNDO = (30, 26, 22)
    COR_BORDA = (165, 135, 75)
    COR_NORMAL = (215, 175, 80)
    COR_ALERTA = (200, 45, 35)

    def __init__(self, ao_tique: Optional[Callable[[float], None]] = None):
        self.ao_tique = ao_tique
        self.ritmo = RitmoTique()
        self._pulso = 0.0
        pygame.font.init()
        self.font = pygame.font.SysFont("DejaVu Sans, Arial, sans-serif", 12, bold=True)

    def reiniciar(self) -> None:
        """Nova decisão: o tique volta ao silêncio."""
        self.ritmo.reiniciar()
        self._pulso = 0.0

    def atualizar(self, dt: float, restante: float) -> None:
        """Avança o pulso e chama ao_tique nos tiques do RitmoTique (R10.2)."""
        self._pulso += dt
        intensidade = self.ritmo.avancar(dt, restante)
        if intensidade is not None and self.ao_tique is not None:
            self.ao_tique(intensidade)

    def desenhar(
        self, tela: pygame.Surface, rect: pygame.Rect, restante: float, total: float
    ) -> None:
        """Rótulo "TEMPO n s" acima e a barra proporcional ao tempo restante."""
        alerta = restante <= self.ULTIMOS_S
        cor = self.COR_ALERTA if alerta else self.COR_NORMAL

        rotulo = self.font.render(
            f"TEMPO  {math.ceil(max(0.0, restante))} s", True, cor if alerta else (225, 215, 200)
        )
        tela.blit(rotulo, (rect.x, rect.y - rotulo.get_height() - 4))

        pygame.draw.rect(tela, self.COR_FUNDO, rect, border_radius=4)
        fracao = max(0.0, min(1.0, restante / total)) if total > 0 else 0.0
        cheio = rect.copy()
        cheio.width = int(rect.width * fracao)
        if cheio.width > 0:
            if alerta:
                # Pulso de ~3 Hz clareando a cor de alerta.
                k = 0.5 + 0.5 * math.sin(self._pulso * 2 * math.pi * 3)
                cor = tuple(min(255, int(c + (255 - c) * 0.35 * k)) for c in cor)
            pygame.draw.rect(tela, cor, cheio, border_radius=4)
        pygame.draw.rect(tela, self.COR_BORDA, rect, width=1, border_radius=4)
