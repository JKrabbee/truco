import random
from typing import Optional
import pygame
from core.clima import CurvaLuz


class Iluminacao:
    """Luz baixa da cena (R1.2): vinheta radial, foco quente sobre a mesa e flicker por fase (R2.2).

    A vinheta e o foco são pré-renderizados em baixa resolução e ampliados, com cache por
    tamanho de tela; o flicker (`CurvaLuz`) só escolhe o alfa da camada preta e o nível do foco.
    Desenhada depois das cartas e antes do HUD, para os textos continuarem legíveis.
    """

    ALFA_MAX_VINHETA = 200
    RAIO_LIVRE = 0.35  # fração do raio da vinheta sem escurecimento
    ESCALA_RASCUNHO = 4  # a vinheta é desenhada em 1/4 e ampliada (suaviza os degraus)
    COR_FOCO = (44, 34, 16)  # somada ao centro da mesa (BLEND_ADD)
    NIVEIS_FOCO = 8  # o foco varia em degraus, para caber em cache

    def __init__(self, luz: str, rng: Optional[random.Random] = None):
        self.curva = CurvaLuz(luz, rng)
        self._cache_vinheta: dict[tuple, pygame.Surface] = {}
        self._cache_foco: dict[tuple, pygame.Surface] = {}
        self._preto: Optional[pygame.Surface] = None

    def atualizar(self, dt: float) -> None:
        self.curva.avancar(dt)

    def desenhar(self, tela: pygame.Surface, centro: tuple[int, int]) -> None:
        """Escurece a tela em volta de `centro` (o meio das vazas)."""
        tamanho = tela.get_size()
        tela.blit(self._vinheta(tamanho, centro), (0, 0))

        nivel = round(self.curva.foco * self.NIVEIS_FOCO)
        if nivel > 0:
            foco = self._foco(tamanho, nivel)
            tela.blit(foco, foco.get_rect(center=centro), special_flags=pygame.BLEND_ADD)

        alfa = self.curva.escurecimento
        if alfa > 0:
            if self._preto is None or self._preto.get_size() != tamanho:
                self._preto = pygame.Surface(tamanho)
                self._preto.fill((0, 0, 0))
            self._preto.set_alpha(alfa)
            tela.blit(self._preto, (0, 0))

    def _vinheta(self, tamanho: tuple[int, int], centro: tuple[int, int]) -> pygame.Surface:
        chave = (tamanho, centro)
        if chave not in self._cache_vinheta:
            self._cache_vinheta.clear()
            k = self.ESCALA_RASCUNHO
            w, h = max(1, tamanho[0] // k), max(1, tamanho[1] // k)
            cx, cy = centro[0] / k, centro[1] / k
            rx, ry = 0.72 * w, 0.72 * h
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            s.fill((0, 0, 0, self.ALFA_MAX_VINHETA))
            # Elipses concêntricas, de fora para dentro: draw substitui o alfa do pixel.
            passos = 48
            externo = 1.0
            for i in range(passos + 1):
                t = externo - (externo - self.RAIO_LIVRE) * i / passos
                frac = max(0.0, (t - self.RAIO_LIVRE) / (1.0 - self.RAIO_LIVRE))
                alfa = int(self.ALFA_MAX_VINHETA * min(1.0, frac) ** 2)
                r = pygame.Rect(0, 0, int(2 * rx * t), int(2 * ry * t))
                r.center = (round(cx), round(cy))
                pygame.draw.ellipse(s, (0, 0, 0, alfa), r)
            self._cache_vinheta[chave] = pygame.transform.smoothscale(s, tamanho)
        return self._cache_vinheta[chave]

    def _foco(self, tamanho: tuple[int, int], nivel: int) -> pygame.Surface:
        chave = (tamanho, nivel)
        if chave not in self._cache_foco:
            if len(self._cache_foco) > 2 * self.NIVEIS_FOCO:
                self._cache_foco.clear()
            k = self.ESCALA_RASCUNHO
            fw, fh = int(tamanho[0] * 0.68), int(tamanho[1] * 0.64)
            w, h = max(1, fw // k), max(1, fh // k)
            s = pygame.Surface((w, h))
            s.fill((0, 0, 0))
            intensidade = nivel / self.NIVEIS_FOCO
            passos = 24
            for i in range(passos):
                t = 1.0 - i / passos  # raio relativo, de fora para dentro
                forca = intensidade * (1.0 - t) ** 1.5
                cor = tuple(int(c * forca) for c in self.COR_FOCO)
                r = pygame.Rect(0, 0, int(w * t), int(h * t))
                r.center = (w // 2, h // 2)
                pygame.draw.ellipse(s, cor, r)
            self._cache_foco[chave] = pygame.transform.smoothscale(s, (fw, fh))
        return self._cache_foco[chave]
