import pygame
from core.card import Carta, Naipe, NOMES_ESPECIAIS


class AssetManager:
    """
    Gerenciador e gerador procedural de assets gráficos (cartas, feltro, verso).
    Garante que o jogo rode perfeitamente sem necessidade de assets externos.
    """

    CARD_WIDTH = 105
    CARD_HEIGHT = 155

    def __init__(self):
        pygame.font.init()
        self.font_valor = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 18, bold=True
        )
        self.font_simbolo = pygame.font.SysFont(
            "Segoe UI Emoji, DejaVu Sans, Symbola, Arial", 32
        )
        self.font_simbolo_pequeno = pygame.font.SysFont(
            "Segoe UI Emoji, DejaVu Sans, Symbola, Arial", 16
        )
        self.font_especial = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 11, bold=True
        )
        self.font_hud = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 20, bold=True
        )
        self.font_hud_sm = pygame.font.SysFont("DejaVu Sans, Arial, sans-serif", 14)

        self._cache_cartas: dict[tuple[int, Naipe, bool], pygame.Surface] = {}
        self._superficie_verso: pygame.Surface | None = None
        self._superficie_mesa: pygame.Surface | None = None

    def obter_verso_carta(self) -> pygame.Surface:
        """Carrega imagem externa de assets/cards/verso.png ou gera verso em cache."""
        if self._superficie_verso is None:
            from pathlib import Path

            caminhos_verso = [
                Path("assets/cards/verso.png"),
                Path("assets/cards/card_back.png"),
                Path("assets/cards/back.png"),
            ]
            for p in caminhos_verso:
                if p.is_file():
                    try:
                        img = pygame.image.load(str(p)).convert_alpha()
                        self._superficie_verso = pygame.transform.scale(
                            img, (self.CARD_WIDTH, self.CARD_HEIGHT)
                        )
                        return self._superficie_verso
                    except Exception:
                        pass

            surf = pygame.Surface((self.CARD_WIDTH, self.CARD_HEIGHT), pygame.SRCALPHA)
            # Fundo base do verso
            pygame.draw.rect(
                surf,
                (245, 245, 240),
                (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT),
                border_radius=8,
            )
            # Moldura interna azul marinho
            margem = 6
            rect_interno = pygame.Rect(
                margem,
                margem,
                self.CARD_WIDTH - (margem * 2),
                self.CARD_HEIGHT - (margem * 2),
            )
            pygame.draw.rect(surf, (26, 42, 70), rect_interno, border_radius=6)
            pygame.draw.rect(
                surf, (200, 160, 60), rect_interno, width=2, border_radius=6
            )

            # Padrão geométrico xadrez elegante
            for y in range(margem + 4, self.CARD_HEIGHT - margem - 4, 12):
                pygame.draw.line(
                    surf,
                    (38, 60, 95),
                    (margem + 4, y),
                    (self.CARD_WIDTH - margem - 4, y),
                    1,
                )
            for x in range(margem + 4, self.CARD_WIDTH - margem - 4, 12):
                pygame.draw.line(
                    surf,
                    (38, 60, 95),
                    (x, margem + 4),
                    (x, self.CARD_HEIGHT - margem - 4),
                    1,
                )

            # Brasão / círculo central
            centro = (self.CARD_WIDTH // 2, self.CARD_HEIGHT // 2)
            pygame.draw.circle(surf, (200, 160, 60), centro, 18, width=2)
            pygame.draw.circle(surf, (26, 42, 70), centro, 15)

            # Borda externa fina
            pygame.draw.rect(
                surf,
                (80, 80, 80),
                (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT),
                width=1,
                border_radius=8,
            )
            self._superficie_verso = surf

        return self._superficie_verso

    def obter_sprite_carta(self, carta: Carta, aberta: bool = True) -> pygame.Surface:
        """Carrega imagem de assets/cards/ ou gera proceduralmente caso não exista."""
        if not aberta:
            return self.obter_verso_carta()

        chave = (carta.valor_facial, carta.naipe, aberta)
        if chave in self._cache_cartas:
            return self._cache_cartas[chave]

        # Tentar carregar arquivo de imagem externa em pixel art
        from pathlib import Path

        nome_naipe = carta.naipe.name.lower()
        especial = NOMES_ESPECIAIS.get((carta.valor_facial, carta.naipe))
        nomes_tentativa = [
            f"{carta.valor_facial}_{nome_naipe}.png",
            f"{carta.valor_facial}_{nome_naipe}.jpg",
        ]
        if especial:
            nomes_tentativa.insert(0, f"{especial.lower().replace(' ', '_')}.png")

        for nome_arq in nomes_tentativa:
            caminho_img = Path("assets/cards") / nome_arq
            if caminho_img.is_file():
                try:
                    img = pygame.image.load(str(caminho_img))
                    if pygame.display.get_surface() is not None:
                        img = img.convert_alpha()
                    # Usa scale nearest-neighbor para manter a nitidez perfeita do Pixel Art
                    surf_escalada = pygame.transform.scale(
                        img, (self.CARD_WIDTH, self.CARD_HEIGHT)
                    )
                    self._cache_cartas[chave] = surf_escalada
                    return surf_escalada
                except Exception:
                    pass

        surf = pygame.Surface((self.CARD_WIDTH, self.CARD_HEIGHT), pygame.SRCALPHA)
        # Fundo de papel pergaminho
        pygame.draw.rect(
            surf,
            (253, 252, 248),
            (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT),
            border_radius=8,
        )
        # Borda sutil da carta
        pygame.draw.rect(
            surf,
            (180, 175, 160),
            (0, 0, self.CARD_WIDTH, self.CARD_HEIGHT),
            width=1,
            border_radius=8,
        )

        # Cor do texto baseada no naipe
        cor_rgb = pygame.Color(carta.naipe.cor)

        # Canto Superior Esquerdo (Valor e Símbolo)
        txt_val = self.font_valor.render(str(carta.valor_facial), True, cor_rgb)
        surf.blit(txt_val, (7, 6))

        txt_simb_pq = self.font_simbolo_pequeno.render(
            carta.naipe.simbolo, True, cor_rgb
        )
        surf.blit(txt_simb_pq, (7, 26))

        # Canto Inferior Direito (Invertido/Valor e Símbolo)
        txt_val_inf = self.font_valor.render(str(carta.valor_facial), True, cor_rgb)
        rect_val_inf = txt_val_inf.get_rect(
            bottomright=(self.CARD_WIDTH - 7, self.CARD_HEIGHT - 6)
        )
        surf.blit(txt_val_inf, rect_val_inf)

        rect_simb_inf = txt_simb_pq.get_rect(
            bottomright=(self.CARD_WIDTH - 7, self.CARD_HEIGHT - 26)
        )
        surf.blit(txt_simb_pq, rect_simb_inf)

        # Se for manilha/especial, adicionar faixa no topo
        especial = NOMES_ESPECIAIS.get((carta.valor_facial, carta.naipe))
        if especial:
            rect_faixa = pygame.Rect(18, 5, self.CARD_WIDTH - 36, 16)
            pygame.draw.rect(surf, (241, 196, 15), rect_faixa, border_radius=4)
            pygame.draw.rect(surf, (180, 140, 10), rect_faixa, width=1, border_radius=4)
            txt_esp = self.font_especial.render(especial[:8], True, (40, 30, 10))
            surf.blit(txt_esp, txt_esp.get_rect(center=rect_faixa.center))

        # Centro da Carta (Símbolo grande e nome do naipe)
        txt_simb_centro = self.font_simbolo.render(carta.naipe.simbolo, True, cor_rgb)
        rect_centro = txt_simb_centro.get_rect(
            center=(self.CARD_WIDTH // 2, self.CARD_HEIGHT // 2 - 4)
        )
        surf.blit(txt_simb_centro, rect_centro)

        txt_naipe_nome = self.font_especial.render(
            carta.naipe.nome_exibicao.upper(), True, (120, 120, 120)
        )
        rect_naipe = txt_naipe_nome.get_rect(
            center=(self.CARD_WIDTH // 2, self.CARD_HEIGHT // 2 + 26)
        )
        surf.blit(txt_naipe_nome, rect_naipe)

        self._cache_cartas[chave] = surf
        return surf

    def obter_mesa_feltro(self, largura: int, altura: int) -> pygame.Surface:
        """Gera o fundo da mesa de feltro verde com borda de madeira elegante."""
        if self._superficie_mesa is None or self._superficie_mesa.get_size() != (
            largura,
            altura,
        ):
            surf = pygame.Surface((largura, altura))
            # Feltro Verde central
            surf.fill((22, 102, 60))

            # Borda de madeira
            espessura_borda = 22
            # Moldura externa escura
            pygame.draw.rect(
                surf, (55, 35, 20), (0, 0, largura, altura), width=espessura_borda
            )
            # Filete dourado da madeira
            pygame.draw.rect(
                surf,
                (185, 145, 60),
                (
                    espessura_borda - 3,
                    espessura_borda - 3,
                    largura - 2 * (espessura_borda - 3),
                    altura - 2 * (espessura_borda - 3),
                ),
                width=2,
            )

            # Gradiente sutil / vinheta nas bordas do feltro
            sombra = pygame.Surface((largura, altura), pygame.SRCALPHA)
            pygame.draw.rect(
                sombra,
                (0, 0, 0, 45),
                (
                    espessura_borda,
                    espessura_borda,
                    largura - 2 * espessura_borda,
                    altura - 2 * espessura_borda,
                ),
                width=18,
            )
            surf.blit(sombra, (0, 0))

            # Linha sutil elíptica delimitadora da mesa de feltro
            ret_mesa_interna = pygame.Rect(40, 40, largura - 80, altura - 80)
            pygame.draw.ellipse(surf, (18, 88, 52), ret_mesa_interna, width=2)

            self._superficie_mesa = surf

        return self._superficie_mesa
