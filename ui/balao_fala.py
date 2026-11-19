from typing import Optional
import pygame


class BalaoFala:
    """Balão com a fala do Diabo (R6.5): máquina de escrever, quebra de linha e fade-out.

    `bloqueia` marca as falas que pausam o timer do jogador enquanto são digitadas (R10.5).
    A posição vem de fora em `desenhar`, para o Bloco 7 ancorar o balão no busto.
    """

    VELOCIDADE_CPS = 40.0  # caracteres por segundo
    TEMPO_LEITURA_S = 2.0  # visível depois de digitado
    FADE_S = 0.3
    PADDING = 10
    RABICHO_MAX = 26  # px
    COR_FUNDO = (18, 12, 10, 225)
    COR_BORDA = (150, 40, 32)
    COR_TEXTO = (235, 220, 200)

    _font: Optional[pygame.font.Font] = None

    def __init__(self, texto: str, duracao: Optional[float] = None, bloqueia: bool = False):
        self.texto = texto
        self.bloqueia = bloqueia
        self.tempo_digitacao = len(texto) / self.VELOCIDADE_CPS
        self.duracao = (
            duracao if duracao is not None else self.TEMPO_LEITURA_S + self.tempo_digitacao
        )
        self.tempo = 0.0

    @classmethod
    def fonte(cls) -> pygame.font.Font:
        if cls._font is None:
            pygame.font.init()
            cls._font = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 14, italic=True)
        return cls._font

    # ==========================
    # ESTADO
    # ==========================
    def atualizar(self, dt: float) -> None:
        self.tempo += dt

    @property
    def digitando(self) -> bool:
        return self.tempo < self.tempo_digitacao

    @property
    def bloqueando(self) -> bool:
        """True enquanto uma fala bloqueante ainda está sendo digitada."""
        return self.bloqueia and self.digitando

    @property
    def terminou(self) -> bool:
        return self.tempo >= self.duracao

    @property
    def texto_visivel(self) -> str:
        n = int(self.tempo * self.VELOCIDADE_CPS)
        return self.texto[: max(0, min(len(self.texto), n))]

    # ==========================
    # DESENHO
    # ==========================
    def _quebrar(self, largura_texto: int) -> list[str]:
        """Quebra o texto completo em linhas (o tamanho do balão não muda ao digitar)."""
        font = self.fonte()
        linhas: list[str] = []
        atual = ""
        for palavra in self.texto.split():
            tentativa = f"{atual} {palavra}".strip()
            if atual and font.size(tentativa)[0] > largura_texto:
                linhas.append(atual)
                atual = palavra
            else:
                atual = tentativa
        if atual:
            linhas.append(atual)
        return linhas

    def desenhar(
        self,
        tela: pygame.Surface,
        pos: tuple[int, int],
        largura_max: int,
        ponta: Optional[tuple[int, int]] = None,
        centralizar: bool = False,
    ) -> None:
        """Desenha em `pos` (topo-esquerda, ou topo-centro com `centralizar`).

        `ponta` é o ponto para onde aponta o rabicho, saindo da borda direita.
        """
        if self.terminou:
            return
        font = self.fonte()
        p = self.PADDING
        linhas = self._quebrar(largura_max - 2 * p)
        alt_linha = font.get_linesize()
        largura = min(largura_max, max(font.size(l)[0] for l in linhas) + 2 * p)
        altura = len(linhas) * alt_linha + 2 * p
        x, y = pos
        if centralizar:
            x -= largura // 2

        restante = self.duracao - self.tempo
        alfa = 255 if restante >= self.FADE_S else int(255 * restante / self.FADE_S)

        # Superfície com margem à direita para o rabicho.
        margem = self.RABICHO_MAX + 4 if ponta is not None else 0
        surf = pygame.Surface((largura + margem, max(altura, 1) + 200), pygame.SRCALPHA)
        oy = 100  # folga vertical para o rabicho subir ou descer
        corpo = pygame.Rect(0, oy, largura, altura)

        if ponta is not None:
            base_y = oy + min(12, altura // 3)
            # Rabicho curto, só na direção da ponta (não atravessa a mesa).
            dx, dy = ponta[0] - (x + largura), ponta[1] - y + oy - (base_y + 8)
            dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
            k = min(1.0, self.RABICHO_MAX / dist)
            px, py = largura + dx * k, base_y + 8 + dy * k
            rabicho = [(largura - 1, base_y), (largura - 1, base_y + 16), (px, py)]
            pygame.draw.polygon(surf, self.COR_FUNDO, rabicho)
            pygame.draw.lines(surf, self.COR_BORDA, False, [rabicho[0], rabicho[2], rabicho[1]], 1)

        pygame.draw.rect(surf, self.COR_FUNDO, corpo, border_radius=8)
        pygame.draw.rect(surf, self.COR_BORDA, corpo, width=1, border_radius=8)

        # Máquina de escrever: revela os caracteres linha a linha.
        faltam = len(self.texto_visivel)
        ty = oy + p
        for linha in linhas:
            if faltam <= 0:
                break
            parte = linha[:faltam]
            faltam -= len(linha) + 1  # +1 pelo espaço consumido na quebra
            txt = font.render(parte, True, self.COR_TEXTO)
            surf.blit(txt, (p, ty))
            ty += alt_linha

        if alfa < 255:
            surf.set_alpha(alfa)
        tela.blit(surf, (x, y - oy))
