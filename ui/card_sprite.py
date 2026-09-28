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

        self.image = self.asset_manager.obter_sprite_carta(
            self.carta, aberta=self.aberta
        )
        self.rect = self.image.get_rect(topleft=(pos_x, pos_y))

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

    def atualizar(self, pos_mouse: tuple[int, int]) -> None:
        """Verifica se o mouse está sobre a carta para aplicar efeito de elevação."""
        if not self.interativa:
            if self.destacada:
                self.destacada = False
                self.atualizar_posicao_rect()
            return

        rect_base = pygame.Rect(
            self.pos_x_base,
            self.pos_y_base,
            self.rect.width,
            self.rect.height,
        )
        esta_sobre = rect_base.collidepoint(pos_mouse)

        if esta_sobre != self.destacada:
            self.destacada = esta_sobre
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
