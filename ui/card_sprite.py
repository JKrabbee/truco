from typing import Optional
import pygame
from core.card import Carta
from game.asset_manager import AssetManager


class CardSprite(pygame.sprite.Sprite):
    """
    Sprite visual para cartas de Truco com transparência perfeita,
    drop shadow projetada sobre o feltro e elevação tátil no hover.
    """

    ELEVACAO_HOVER_PX = 14
    VELOCIDADE_PADRAO = 900.0  # px/s (design §5; 1400 ficava rápido demais para ver)
    DURACAO_MINIMA_S = 0.25

    def __init__(
        self,
        carta: Carta,
        pos_x: int,
        pos_y: int,
        asset_manager: AssetManager,
        aberta: bool = True,
        interativa: bool = True,
    ):
        super().__init__()
        self.carta = carta
        self.asset_manager = asset_manager
        self.aberta = aberta
        self.interativa = interativa

        self.pos_x_base = pos_x
        self.pos_y_base = pos_y

        self.destacada: bool = False
        self.hover: bool = False
        # Seleção por teclado (R7.1); o destaque é o mesmo do hover.
        self.selecionada: bool = False

        self.image = self.asset_manager.obter_sprite_carta(
            self.carta, aberta=self.aberta
        )
        self.rect = self.image.get_rect(topleft=(pos_x, pos_y))

        # Movimento (R8.1): interpolação do centro com ease-out, de origem a alvo.
        self._origem_mov: tuple[float, float] = (float(self.rect.centerx), float(self.rect.centery))
        self._alvo_mov: Optional[tuple[float, float]] = None
        self._duracao_mov: float = 0.0
        self._tempo_mov: float = 0.0

    @property
    def em_movimento(self) -> bool:
        return self._alvo_mov is not None

    def mover_para(
        self, alvo_xy: tuple[float, float], velocidade: float = VELOCIDADE_PADRAO
    ) -> None:
        """Começa a mover o centro da carta até alvo_xy (duração = distância / velocidade)."""
        self._origem_mov = (float(self.rect.centerx), float(self.rect.centery))
        self._alvo_mov = (float(alvo_xy[0]), float(alvo_xy[1]))
        dx = self._alvo_mov[0] - self._origem_mov[0]
        dy = self._alvo_mov[1] - self._origem_mov[1]
        distancia = (dx * dx + dy * dy) ** 0.5
        self._duracao_mov = max(self.DURACAO_MINIMA_S, distancia / max(velocidade, 1.0))
        self._tempo_mov = 0.0

    def atualizar_movimento(self, dt: float) -> bool:
        """Avança o movimento; o rect acompanha. Retorna True enquanto ainda se move."""
        if self._alvo_mov is None:
            return False
        self._tempo_mov = min(self._duracao_mov, self._tempo_mov + dt)
        t = self._tempo_mov / self._duracao_mov
        k = 1.0 - (1.0 - t) ** 2  # ease-out quadrático
        ox, oy = self._origem_mov
        ax, ay = self._alvo_mov
        self.rect.center = (round(ox + (ax - ox) * k), round(oy + (ay - oy) * k))
        self.pos_x_base, self.pos_y_base = self.rect.topleft
        if t >= 1.0:
            self._alvo_mov = None
            return False
        return True

    def definir_posicao_base(self, x: int, y: int) -> None:
        self.pos_x_base = x
        self.pos_y_base = y
        self.atualizar_posicao_rect()

    def set_aberta(self, aberta: bool) -> None:
        if self.aberta != aberta:
            self.aberta = aberta
            self.image = self.asset_manager.obter_sprite_carta(
                self.carta, aberta=self.aberta
            )

    def atualizar_posicao_rect(self) -> None:
        deslocamento_y = -self.ELEVACAO_HOVER_PX if self.destacada else 0
        self.rect.topleft = (self.pos_x_base, self.pos_y_base + deslocamento_y)

    def contem_ponto_base(self, pos: tuple[int, int]) -> bool:
        """True se o ponto está sobre a posição de repouso da carta (sem a elevação)."""
        rect_base = pygame.Rect(
            self.pos_x_base, self.pos_y_base, self.rect.width, self.rect.height
        )
        return rect_base.collidepoint(pos)

    def atualizar(self, pos_mouse: tuple[int, int], usar_hover: bool = True) -> None:
        """Eleva a carta se estiver selecionada ou, com usar_hover, sob o mouse."""
        if not self.interativa:
            self.hover = False
            novo = False
        else:
            self.hover = self.contem_ponto_base(pos_mouse)
            novo = self.selecionada or (usar_hover and self.hover)

        if novo != self.destacada:
            self.destacada = novo
            self.atualizar_posicao_rect()

    def verificar_clique(self, pos_mouse: tuple[int, int]) -> bool:
        if not self.interativa:
            return False
        return self.rect.collidepoint(pos_mouse)

    def desenhar(self, tela: pygame.Surface) -> None:
        # 1. Drop shadow projetada sobre o feltro verde
        sombra_offset_y = 8 if self.destacada else 4
        sombra_offset_x = 4 if self.destacada else 3
        sombra_rect = pygame.Rect(
            self.rect.x + sombra_offset_x,
            self.rect.y + sombra_offset_y,
            self.rect.width,
            self.rect.height,
        )
        sombra_surf = pygame.Surface(
            (self.rect.width, self.rect.height), pygame.SRCALPHA
        )
        # Sombra suave com cantos arredondados
        alpha_sombra = 110 if self.destacada else 80
        pygame.draw.rect(
            sombra_surf,
            (0, 0, 0, alpha_sombra),
            (0, 0, self.rect.width, self.rect.height),
            border_radius=8,
        )
        tela.blit(sombra_surf, sombra_rect.topleft)

        # 2. Renderização da imagem da carta (com canal alfa limpo)
        tela.blit(self.image, self.rect)

        # 3. Moldura sutil de destaque no hover
        if self.destacada and self.interativa:
            pygame.draw.rect(tela, (241, 196, 15), self.rect, width=2, border_radius=8)
