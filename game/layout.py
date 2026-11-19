"""Geometria da mesa com o busto do Diabo (design §5, Layout), compartilhada pela UI.

`PartidaState`, `HUD` e `RoletaController` leem daqui, para o desenho, as zonas de colisão
e a roleta acompanharem o mesmo layout em qualquer tamanho de janela.
"""

from functools import lru_cache
import pygame

MARGEM = 20
ESPACO_BUSTO_CARTAS = 12
PROPORCAO_BUSTO = 360 / 260  # assets/diabo/*.png


class LayoutMesa:
    """Retângulos e pontos da mesa para uma janela largura × altura.

    Faixa do topo: placas nas colunas laterais; no centro, o busto e, à direita dele,
    as cartas do Diabo. As vazas ficam no meio da mesa, e a mão do humano embaixo.
    Os métodos devolvem cópias, então quem chama pode mexer nos Rects.
    """

    def __init__(self, largura: int, altura: int):
        self.largura = largura
        self.altura = altura
        # Coluna das placas (mesma largura das placas do HUD).
        self.largura_coluna = min(240, int(largura * 0.23))

        # Busto e cartas do Diabo, centrados juntos na faixa entre as colunas.
        h_busto = int(altura * 0.19)
        w_busto = int(h_busto * PROPORCAO_BUSTO)
        self.carta_diabo_h = int(altura * 0.14)
        self.carta_diabo_w = int(self.carta_diabo_h * 0.68)
        self.espaco_cartas_diabo = max(6, self.carta_diabo_w // 9)
        largura_cartas = 3 * self.carta_diabo_w + 2 * self.espaco_cartas_diabo
        total = w_busto + ESPACO_BUSTO_CARTAS + largura_cartas
        faixa_x0 = MARGEM + self.largura_coluna + 10
        x0 = max(faixa_x0, (largura - total) // 2)
        self._busto = pygame.Rect(x0, 2, w_busto, h_busto)
        self.cartas_diabo_x0 = self._busto.right + ESPACO_BUSTO_CARTAS
        self.cartas_diabo_y = int(altura * 0.035)

        # Vazas
        # 0,32/0,68 (eram 0,33/0,67): em 800 px os montes vizinhos se tocavam por ~5 px.
        self.pontos_x_vazas = [int(largura * 0.32), int(largura * 0.50), int(largura * 0.68)]
        self.y_centro_vazas = int(altura * 0.39)
        self.carta_vaza_w, self.carta_vaza_h = 105, 155
        self.y_rotulo_vaza = self.y_centro_vazas - self.carta_vaza_h // 2 - 30

    # ---------- Diabo ----------
    def busto(self) -> pygame.Rect:
        return self._busto.copy()

    def boca_diabo(self) -> tuple[int, int]:
        """Ponta do rabicho do balão."""
        b = self._busto
        return (b.centerx - b.width // 6, b.top + int(b.height * 0.62))

    def rosto_diabo(self) -> tuple[int, int]:
        """Para onde o cano aponta quando o alvo é o Diabo."""
        b = self._busto
        return (b.centerx, b.top + int(b.height * 0.42))

    def x_carta_diabo(self, i: int) -> int:
        """x da i-ésima carta do Diabo; a fileira fica encostada no busto."""
        return self.cartas_diabo_x0 + i * (self.carta_diabo_w + self.espaco_cartas_diabo)

    def faixa_central_x(self) -> tuple[int, int]:
        """Limites x entre as colunas das placas (para os rótulos das vazas)."""
        return (
            MARGEM + self.largura_coluna + 6,
            self.largura - MARGEM - self.largura_coluna - 6,
        )

    # ---------- Colunas laterais ----------
    def placa_aposta(self) -> pygame.Rect:
        """Placa "VALENDO n TENTOS": coluna direita, sob a placa do humano."""
        return pygame.Rect(
            self.largura - MARGEM - self.largura_coluna, 96, self.largura_coluna, 46
        )

    def aviso_pensando(self) -> pygame.Rect:
        """"O Diabo pensa…": coluna direita, sob a placa de aposta, alinhado à direita."""
        w = min(150, self.largura_coluna)
        return pygame.Rect(self.largura - MARGEM - w, 150, w, 22)

    def balao(self) -> tuple[tuple[int, int], int]:
        """Posição (topo-esquerda) e largura máxima do balão, na coluna esquerda.

        A largura para antes da 1ª carta da 1ª vaza, para não cobri-la.
        """
        borda_vaza = self.pontos_x_vazas[0] - 18 - self.carta_vaza_w // 2
        largura_max = min(self.largura_coluna, borda_vaza - MARGEM - 8)
        return (MARGEM, 150), largura_max

    # ---------- Faixa de mensagem ----------
    def faixa_mensagem(self) -> pygame.Rect:
        """Logo acima da barra de ações (altura − 245)."""
        w = min(self.largura - 120, 780)
        return pygame.Rect((self.largura - w) // 2, self.altura - 245 - 28, w, 24)

    # ---------- Roleta ----------
    def zona_atirador_diabo(self) -> pygame.Rect:
        r = pygame.Rect(0, 0, 240, 90)
        r.center = (self._busto.centerx, self._busto.bottom + 50)
        return r

    def zona_atirador_humano(self) -> pygame.Rect:
        r = pygame.Rect(0, 0, 240, 90)
        r.center = (self.largura // 2, self.altura - 225)
        return r

    def y_textos_roleta(self) -> int:
        """Título da roleta, entre a zona do Diabo e a do humano."""
        return self.y_centro_vazas


@lru_cache(maxsize=8)
def layout_mesa(largura: int, altura: int) -> LayoutMesa:
    """Layout em cache por tamanho de janela."""
    return LayoutMesa(largura, altura)
