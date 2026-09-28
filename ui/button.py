from typing import Callable, Optional
import pygame


class Button:
    """
    Botão tátil com temática rústica (estilo madeira/ferro/pergaminho), auto-ajuste de fonte,
    elevação suave no hover e drop shadow orgânica.
    """

    COR_PADRAO_BG = (59, 54, 49)  # #3b3631 - Madeira / Ferro escuro
    COR_PADRAO_BORDA = (94, 84, 73)  # #5e5449 - Bronze / Madeira clara
    COR_PADRAO_TEXTO = (229, 218, 202)  # #e5daca - Pergaminho marfim

    COR_TRUCO_BG = (144, 33, 27)  # #90211B - Vermelho cardeal rústico dramático
    COR_TRUCO_BORDA = (192, 57, 43)
    COR_TRUCO_HOVER = (175, 40, 34)

    COR_ENVIDO_BG = (47, 72, 88)  # #2F4858 - Azul noturno lavado / colonial
    COR_ENVIDO_BORDA = (70, 105, 128)
    COR_ENVIDO_HOVER = (60, 92, 112)

    def __init__(
        self,
        rect: pygame.Rect,
        texto: str,
        callback: Optional[Callable[[], None]] = None,
        cor_padrao: tuple[int, int, int] = COR_PADRAO_BG,
        cor_hover: Optional[tuple[int, int, int]] = None,
        cor_borda: tuple[int, int, int] = COR_PADRAO_BORDA,
        cor_desativado: tuple[int, int, int] = (80, 75, 70),
        cor_texto: tuple[int, int, int] = COR_PADRAO_TEXTO,
        fonte: Optional[pygame.font.Font] = None,
        tamanho_fonte: int = 16,
    ):
        self.rect_base = pygame.Rect(rect)
        self.rect = pygame.Rect(rect)
        self.texto = texto
        self.callback = callback
        self.cor_padrao = cor_padrao
        self.cor_hover = cor_hover or (
            min(255, cor_padrao[0] + 28),
            min(255, cor_padrao[1] + 28),
            min(255, cor_padrao[2] + 28),
        )
        self.cor_borda = cor_borda
        self.cor_desativado = cor_desativado
        self.cor_texto = cor_texto
        self.ativo: bool = True
        self.hover: bool = False
        self.tamanho_fonte_base = tamanho_fonte

        pygame.font.init()
        if fonte is None:
            self._ajustar_fonte()
        else:
            self.fonte = fonte

    def _ajustar_fonte(self) -> None:
        """Garante que o texto nunca fure as bordas do botão diminuindo a fonte se necessário."""
        tamanho = self.tamanho_fonte_base
        largura_maxima = max(10, self.rect.width - 14)
        while tamanho > 9:
            fonte = pygame.font.SysFont(
                "DejaVu Sans, Georgia, serif", tamanho, bold=True
            )
            w, _ = fonte.size(self.texto)
            if w <= largura_maxima:
                self.fonte = fonte
                return
            tamanho -= 1
        self.fonte = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 9, bold=True)

    def definir_texto(self, texto: str) -> None:
        self.texto = texto
        self._ajustar_fonte()

    def definir_rect(self, rect: pygame.Rect) -> None:
        self.rect_base = pygame.Rect(rect)
        self.rect = pygame.Rect(rect)
        self._ajustar_fonte()

    def verificar_hover(self, pos_mouse: tuple[int, int]) -> bool:
        if not self.ativo:
            self.hover = False
            self.rect.y = self.rect_base.y
            return False
        novo_hover = self.rect_base.collidepoint(pos_mouse)
        if novo_hover != self.hover:
            self.hover = novo_hover
            # Micro-interação: elevação de 3px no hover
            self.rect.y = self.rect_base.y - (3 if self.hover else 0)
        return self.hover

    def tratar_evento(self, event: pygame.event.Event) -> bool:
        if not self.ativo:
            return False

        if event.type == pygame.MOUSEMOTION:
            self.verificar_hover(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect_base.collidepoint(event.pos):
                if self.callback:
                    self.callback()
                return True
        return False

    def desenhar(self, tela: pygame.Surface) -> None:
        """Renderiza o botão com drop shadow tátil e moldura rústica."""
        # 1. Drop shadow projetada (offset 3px, 3px com alpha=100)
        sombra_offset_y = 5 if self.hover else 3
        sombra_rect = pygame.Rect(
            self.rect.x + 3,
            self.rect.y + sombra_offset_y,
            self.rect.width,
            self.rect.height,
        )
        sombra_surf = pygame.Surface(
            (self.rect.width, self.rect.height), pygame.SRCALPHA
        )
        sombra_surf.fill((0, 0, 0, 110 if self.hover else 75))
        tela.blit(sombra_surf, sombra_rect.topleft)

        # 2. Cores de estado
        if not self.ativo:
            cor_fundo = self.cor_desativado
            cor_borda = (70, 65, 60)
            cor_txt = (140, 135, 130)
        elif self.hover:
            cor_fundo = self.cor_hover
            cor_borda = (230, 215, 180)  # Borda dourada/marfim ao passar o mouse
            cor_txt = (255, 255, 255)
        else:
            cor_fundo = self.cor_padrao
            cor_borda = self.cor_borda
            cor_txt = self.cor_texto

        # 3. Corpo e borda rústica chanfrada
        pygame.draw.rect(tela, cor_fundo, self.rect, border_radius=6)
        pygame.draw.rect(tela, cor_borda, self.rect, width=2, border_radius=6)

        # 4. Texto centralizado
        superficie_texto = self.fonte.render(self.texto, True, cor_txt)
        pos_texto = superficie_texto.get_rect(center=self.rect.center)
        tela.blit(superficie_texto, pos_texto)
