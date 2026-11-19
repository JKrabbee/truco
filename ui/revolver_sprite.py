import math
from typing import Optional
import pygame
from game.paths import ASSETS


class RevolverSprite:
    """Revólver da roleta: desliza até o atirador, gira para o alvo e dá coice no disparo."""

    LARGURA = 150
    ALTURA = 70
    VELOCIDADE_PX_S = 900.0
    VELOCIDADE_GIRO_GRAUS_S = 360.0
    COICE_PX = 18.0

    def __init__(self, x: float, y: float):
        self.base = self._carregar_imagem()
        self.pos = pygame.Vector2(x, y)
        self.destino: Optional[pygame.Vector2] = None
        self.angulo = 0.0  # graus; 0 = cano para a direita
        self.angulo_alvo = 0.0
        self.coice = 0.0

    @classmethod
    def _carregar_imagem(cls) -> pygame.Surface:
        """PNG de assets/revolver.png, ou polígono cinza com cano (placeholder)."""
        caminho = ASSETS / "revolver.png"
        if caminho.is_file():
            try:
                img = pygame.image.load(str(caminho))
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                return pygame.transform.smoothscale(img, (cls.LARGURA, cls.ALTURA))
            except pygame.error:
                pass
        return cls._desenhar_placeholder()

    @classmethod
    def _desenhar_placeholder(cls) -> pygame.Surface:
        s = pygame.Surface((cls.LARGURA, cls.ALTURA), pygame.SRCALPHA)
        aco, escuro, brilho = (125, 128, 132), (60, 62, 66), (185, 188, 192)
        # Cano (para a direita) e mira
        pygame.draw.rect(s, aco, (62, 14, 86, 12), border_radius=3)
        pygame.draw.rect(s, brilho, (64, 15, 82, 3))
        pygame.draw.rect(s, escuro, (140, 9, 5, 6))
        # Tambor
        pygame.draw.rect(s, escuro, (44, 10, 32, 24), border_radius=6)
        pygame.draw.rect(s, aco, (46, 12, 28, 20), border_radius=5)
        for i in range(3):
            pygame.draw.circle(s, escuro, (52 + i * 8, 22), 3)
        # Armação, cão e guarda-mato
        pygame.draw.polygon(s, aco, [(30, 8), (46, 8), (46, 36), (30, 36)])
        pygame.draw.polygon(s, escuro, [(30, 8), (22, 2), (28, 0), (36, 8)])
        pygame.draw.arc(s, escuro, (40, 30, 22, 18), math.pi, 2 * math.pi, 3)
        pygame.draw.line(s, escuro, (48, 34), (50, 42), 3)
        # Cabo de madeira
        pygame.draw.polygon(
            s, (92, 58, 34), [(24, 30), (44, 34), (36, 66), (14, 66), (10, 58)]
        )
        pygame.draw.polygon(
            s, (60, 36, 20), [(24, 30), (44, 34), (36, 66), (14, 66), (10, 58)], 2
        )
        return s

    @property
    def rect(self) -> pygame.Rect:
        """Retângulo de colisão (sem rotação), centrado na posição atual."""
        r = pygame.Rect(0, 0, self.LARGURA, self.ALTURA)
        r.center = (round(self.pos.x), round(self.pos.y))
        return r

    @property
    def ponta_cano(self) -> tuple[float, float]:
        """Ponta do cano na direção do ângulo atual (para o clarão do disparo)."""
        rad = math.radians(self.angulo)
        meio = self.LARGURA / 2
        return (self.pos.x + math.cos(rad) * meio, self.pos.y - math.sin(rad) * meio)

    @property
    def parado(self) -> bool:
        return self.destino is None

    def posicionar(self, x: float, y: float) -> None:
        self.pos.update(x, y)
        self.destino = None

    def deslizar_para(self, zona: pygame.Rect) -> None:
        """Começa a deslizar até o centro da zona."""
        self.destino = pygame.Vector2(zona.center)

    def apontar_para(self, ponto: tuple[float, float]) -> None:
        """Define o ângulo para o cano apontar para o ponto."""
        dx, dy = ponto[0] - self.pos.x, ponto[1] - self.pos.y
        if dx == 0 and dy == 0:
            return
        self.angulo_alvo = -math.degrees(math.atan2(dy, dx))

    def disparar(self) -> None:
        """Coice visual do disparo."""
        self.coice = self.COICE_PX

    def atualizar(self, dt: float) -> None:
        if self.destino is not None:
            delta = self.destino - self.pos
            passo = self.VELOCIDADE_PX_S * dt
            if delta.length() <= passo:
                self.pos.update(self.destino)
                self.destino = None
            else:
                self.pos += delta.normalize() * passo

        # Gira pelo menor caminho até o ângulo alvo
        diferenca = (self.angulo_alvo - self.angulo + 180) % 360 - 180
        giro = self.VELOCIDADE_GIRO_GRAUS_S * dt
        self.angulo += max(-giro, min(giro, diferenca))

        self.coice = max(0.0, self.coice - 90.0 * dt)

    def desenhar(self, tela: pygame.Surface) -> None:
        img = self.base
        # Cano para a esquerda: espelha para o cabo continuar embaixo
        if abs((self.angulo + 180) % 360 - 180) > 90:
            img = pygame.transform.flip(img, False, True)
        img = pygame.transform.rotate(img, self.angulo)

        rad = math.radians(self.angulo)
        recuo = pygame.Vector2(-math.cos(rad), math.sin(rad)) * self.coice
        centro = self.pos + recuo
        rect = img.get_rect(center=(round(centro.x), round(centro.y)))

        sombra = pygame.mask.from_surface(img).to_surface(
            setcolor=(0, 0, 0, 110), unsetcolor=(0, 0, 0, 0)
        )
        tela.blit(sombra, (rect.x + 5, rect.y + 7))
        tela.blit(img, rect)
