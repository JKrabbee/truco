import math
from typing import Optional
import pygame
from core.clima import Expressao
from game.paths import ASSETS


class DiaboSprite:
    """Busto do Diabo no topo da mesa (R1.1), com as expressões de `Expressao`.

    Usa `assets/diabo/{calmo,falando,irritado,ferido}.png` se existirem (uma expressão que
    faltar usa o `calmo.png`; sem o `calmo.png`, tudo é procedural, para não misturar estilos).
    O fallback é uma silhueta com chifres e olhos vermelhos, cujo brilho é desenhado à parte
    (`desenhar_brilho`), depois da vinheta, para brilhar no escuro.
    """

    INICIO_FADE = 0.72  # fração da altura em que a base do busto começa a sumir no feltro

    def __init__(self) -> None:
        self.tempo = 0.0
        self.imagens = self._carregar_imagens()
        self._cache_png: dict[tuple, pygame.Surface] = {}
        self._mascara: Optional[pygame.Surface] = None

    @property
    def procedural(self) -> bool:
        return not self.imagens

    @staticmethod
    def _carregar_imagens() -> dict[Expressao, pygame.Surface]:
        """PNGs de assets/diabo/; vazio se não houver o calmo.png."""
        imagens: dict[Expressao, pygame.Surface] = {}
        for expressao in Expressao:
            caminho = ASSETS / "diabo" / f"{expressao.value}.png"
            if not caminho.is_file():
                continue
            try:
                img = pygame.image.load(str(caminho))
                if pygame.display.get_surface() is not None:
                    img = img.convert_alpha()
                imagens[expressao] = img
            except pygame.error:
                pass
        if Expressao.CALMO not in imagens:
            return {}
        for expressao in Expressao:
            imagens.setdefault(expressao, imagens[Expressao.CALMO])
        return imagens

    def atualizar(self, dt: float) -> None:
        self.tempo += dt

    # ==========================
    # DESENHO
    # ==========================
    def _balanco(self, h: int) -> float:
        """Respiração: sobe e desce ~2 px."""
        return math.sin(self.tempo * 1.6) * 2.0 * h / 114

    def _tremor(self, expressao: Expressao) -> int:
        return round(math.sin(self.tempo * 47.0) * 2) if expressao is Expressao.FERIDO else 0

    def desenhar(
        self, tela: pygame.Surface, rect: pygame.Rect, expressao: Expressao, alfa: int = 255
    ) -> None:
        """Desenha o busto em `rect`, com a base sumindo no feltro."""
        if alfa <= 0:
            return
        w, h = rect.size
        if self.procedural:
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            self._desenhar_procedural(surf, expressao)
        else:
            chave = (expressao, (w, h))
            if chave not in self._cache_png:
                self._cache_png[chave] = pygame.transform.smoothscale(
                    self.imagens[expressao], (w, h)
                )
            surf = self._cache_png[chave].copy()
        surf.blit(self._mascara_fade((w, h)), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

        if expressao is Expressao.FERIDO:
            surf = pygame.transform.rotate(surf, -5)
        if alfa < 255:
            surf.set_alpha(alfa)
        destino = surf.get_rect(center=rect.center)
        destino.move_ip(self._tremor(expressao), 0)
        if self.procedural:
            destino.move_ip(0, round(self._balanco(h)))
        tela.blit(surf, destino)

    def desenhar_brilho(
        self, tela: pygame.Surface, rect: pygame.Rect, expressao: Expressao, alfa: int = 255
    ) -> None:
        """Brilho dos olhos (só no procedural), somado depois da vinheta."""
        if not self.procedural or alfa < 40:
            return
        w, h = rect.size
        pulso = 1.0 + 0.15 * math.sin(self.tempo * 3.0)
        forte = expressao is Expressao.IRRITADO
        raio = max(3, int(w * 0.05 * pulso * (1.25 if forte else 1.0)))
        cor = (120, 22, 10) if forte else (80, 14, 6)
        k = alfa / 255
        cor = tuple(int(c * k) for c in cor)
        dx = self._tremor(expressao)
        dy = round(self._balanco(h))
        for i, (ex, ey) in enumerate(self._olhos(w, h)):
            if expressao is Expressao.FERIDO and i == 0:
                continue  # o olho ferido está fechado
            brilho = pygame.Surface((raio * 2, raio * 2))
            brilho.fill((0, 0, 0))
            for passo in range(6, 0, -1):
                f = passo / 6
                c = tuple(int(v * (1.2 - f)) for v in cor)
                pygame.draw.circle(brilho, c, (raio, raio), int(raio * f))
            cx, cy = rect.x + int(ex) + dx, rect.y + int(ey) + dy
            tela.blit(brilho, (cx - raio, cy - raio), special_flags=pygame.BLEND_ADD)

    def _mascara_fade(self, tamanho: tuple[int, int]) -> pygame.Surface:
        """Multiplicador de alfa: opaco em cima, sumindo na base."""
        if self._mascara is None or self._mascara.get_size() != tamanho:
            w, h = tamanho
            m = pygame.Surface((w, h), pygame.SRCALPHA)
            m.fill((255, 255, 255, 255))
            inicio = int(h * self.INICIO_FADE)
            for y in range(inicio, h):
                a = int(255 * (1 - (y - inicio) / max(1, h - inicio)))
                pygame.draw.line(m, (255, 255, 255, a), (0, y), (w, y))
            self._mascara = m
        return self._mascara

    @staticmethod
    def _olhos(w: int, h: int) -> tuple[tuple[float, float], tuple[float, float]]:
        return (0.445 * w, 0.385 * h), (0.555 * w, 0.385 * h)

    def _desenhar_procedural(self, s: pygame.Surface, expressao: Expressao) -> None:
        """Silhueta original: ombros, cabeça com queixo pontudo, chifres e olhos vermelhos."""
        w, h = s.get_size()

        def p(x: float, y: float) -> tuple[int, int]:
            return (round(x * w), round(y * h))

        pele, sombra = (108, 24, 22), (70, 15, 15)
        chifre, contorno = (58, 42, 30), (24, 14, 10)
        if expressao is Expressao.FERIDO:
            pele = (88, 18, 18)

        # Ombros, gola e pescoço
        pygame.draw.ellipse(s, (32, 8, 10), (0.06 * w, 0.66 * h, 0.88 * w, 0.8 * h))
        pygame.draw.polygon(s, (16, 4, 6), [p(0.39, 0.66), p(0.5, 0.9), p(0.61, 0.66)])
        pygame.draw.lines(s, (78, 20, 20), False, [p(0.30, 0.74), p(0.42, 0.68)], 2)
        pygame.draw.lines(s, (78, 20, 20), False, [p(0.70, 0.74), p(0.58, 0.68)], 2)
        pygame.draw.rect(s, sombra, (0.45 * w, 0.54 * h, 0.10 * w, 0.14 * h))

        # Chifres (atrás da cabeça)
        for lado in (0, 1):
            pts = [(0.41, 0.24), (0.46, 0.19), (0.39, 0.10), (0.31, 0.01), (0.35, 0.13)]
            if lado:
                pts = [(1 - x, y) for x, y in pts]
            pontos = [p(x, y) for x, y in pts]
            pygame.draw.polygon(s, chifre, pontos)
            pygame.draw.polygon(s, contorno, pontos, 1)

        # Orelhas pontudas
        for lado in (0, 1):
            pts = [(0.37, 0.36), (0.31, 0.30), (0.37, 0.46)]
            if lado:
                pts = [(1 - x, y) for x, y in pts]
            pygame.draw.polygon(s, sombra, [p(x, y) for x, y in pts])

        # Cabeça e queixo pontudo
        pygame.draw.ellipse(s, pele, (0.35 * w, 0.15 * h, 0.30 * w, 0.48 * h))
        pygame.draw.polygon(s, pele, [p(0.37, 0.46), p(0.5, 0.69), p(0.63, 0.46)])
        pygame.draw.polygon(s, (24, 6, 6), [p(0.465, 0.60), p(0.5, 0.75), p(0.535, 0.60)])

        # Sobrancelhas
        if expressao is Expressao.IRRITADO:
            pygame.draw.line(s, contorno, p(0.40, 0.31), p(0.48, 0.36), 3)
            pygame.draw.line(s, contorno, p(0.60, 0.31), p(0.52, 0.36), 3)
        else:
            pygame.draw.line(s, contorno, p(0.40, 0.33), p(0.48, 0.34), 2)
            pygame.draw.line(s, contorno, p(0.60, 0.32), p(0.52, 0.34), 2)

        # Olhos
        ew, eh = 0.06 * w, 0.04 * h
        if expressao is Expressao.IRRITADO:
            eh *= 0.6
        for i, (ex, ey) in enumerate(self._olhos(w, h)):
            if expressao is Expressao.FERIDO and i == 0:
                d = 0.025 * w
                pygame.draw.line(s, contorno, (ex - d, ey - d), (ex + d, ey + d), 2)
                pygame.draw.line(s, contorno, (ex - d, ey + d), (ex + d, ey - d), 2)
                continue
            r = pygame.Rect(0, 0, max(2, int(ew)), max(2, int(eh)))
            r.center = (round(ex), round(ey))
            pygame.draw.ellipse(s, (230, 40, 20), r)
            pygame.draw.circle(s, (255, 190, 80), r.center, max(1, int(eh / 3)))

        # Boca
        cx, cy = 0.5 * w, 0.53 * h
        if expressao is Expressao.FALANDO:
            abertura = (0.015 + 0.035 * abs(math.sin(self.tempo * 14.0))) * h
            r = pygame.Rect(0, 0, int(0.09 * w), max(2, int(abertura)))
            r.center = (round(cx), round(cy))
            pygame.draw.ellipse(s, (14, 0, 0), r)
            pygame.draw.line(s, (220, 205, 175), (r.left + 2, r.top + 1), (r.right - 2, r.top + 1), 1)
        elif expressao is Expressao.IRRITADO:
            r = pygame.Rect(0, 0, int(0.10 * w), max(2, int(0.025 * h)))
            r.center = (round(cx), round(cy))
            pygame.draw.rect(s, (220, 205, 175), r)
            pygame.draw.rect(s, (14, 0, 0), r, 1)
        elif expressao is Expressao.FERIDO:
            r = pygame.Rect(0, 0, int(0.08 * w), max(3, int(0.05 * h)))
            r.center = (round(cx), round(cy + 0.01 * h))
            pygame.draw.ellipse(s, (14, 0, 0), r)
            # Ferida e sangue escorrendo
            pygame.draw.circle(s, (55, 0, 0), p(0.56, 0.27), max(2, int(0.03 * h)))
            pygame.draw.line(s, (130, 0, 0), p(0.56, 0.28), p(0.57, 0.42), 2)
            pygame.draw.line(s, (130, 0, 0), (r.right - 2, r.centery), p(0.55, 0.66), 2)
        else:
            # Sorriso torto
            pygame.draw.lines(
                s, (14, 0, 0), False, [p(0.45, 0.525), p(0.5, 0.54), p(0.565, 0.515)], 2
            )
