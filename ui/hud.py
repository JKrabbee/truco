from typing import Optional
import pygame
from core.campanha import Campanha
from core.fase import ConfigFase
from core.match import PartidaTruco
from core.revolver import Tambor
from game.layout import layout_mesa


class HUD:
    """
    Componente visual responsável pelo placar de 12 tentos, indicador de mão/pé,
    placa de aposta (coluna direita), faixa de mensagem, rótulo da fase e câmaras do tambor (R4.5).
    Estética rústica de taberna gaúcha (madeira escura, couro e detalhes em latão envelhecido).
    """

    def __init__(self, largura_tela: int, altura_tela: int):
        self.largura = largura_tela
        self.altura = altura_tela

        pygame.font.init()
        self.font_titulo = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 15, bold=True
        )
        self.font_pts = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 24, bold=True
        )
        self.font_sub = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 12)
        self.font_msg = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 13, bold=True
        )
        self.font_badge = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 10, bold=True
        )

    def redimensionar(self, largura: int, altura: int) -> None:
        self.largura = largura
        self.altura = altura

    def desenhar(
        self,
        tela: pygame.Surface,
        partida: PartidaTruco,
        campanha: Optional[Campanha] = None,
        config: Optional[ConfigFase] = None,
        tambor: Optional[Tambor] = None,
    ) -> None:
        """Renderiza o HUD rústico e integrado à mesa.

        `config` e `tambor` substituem os da campanha: no encerramento de uma fase vencida,
        a campanha já avançou, mas o painel continua mostrando a mesa que acabou.
        """
        self._desenhar_placares(tela, partida)
        self._desenhar_placa_truco_central(tela, partida)
        self._desenhar_aviso_flutuante(tela, partida)
        if campanha is not None:
            self._desenhar_fase_tambor(
                tela, config or campanha.config, tambor or campanha.tambor
            )

    def _desenhar_fase_tambor(
        self, tela: pygame.Surface, config: ConfigFase, tambor: Tambor
    ) -> None:
        """Rótulo da fase e câmaras já disparadas, sem revelar a bala (R4.5)."""
        largura = min(240, int(self.largura * 0.23))
        altura = 46
        x, y = 20, 96
        s_fundo = pygame.Surface((largura, altura), pygame.SRCALPHA)
        s_fundo.fill((30, 26, 22, 215))
        tela.blit(s_fundo, (x, y))
        pygame.draw.rect(tela, (95, 75, 55), (x, y, largura, altura), width=1, border_radius=6)

        txt_fase = self.font_badge.render(
            f"FASE {config.numero} — {config.nome.upper()}", True, (215, 175, 80)
        )
        tela.blit(txt_fase, (x + 10, y + 6))

        txt_cam = self.font_sub.render(
            f"câmaras {tambor.disparadas}/{tambor.camaras}", True, (225, 215, 200)
        )
        tela.blit(txt_cam, (x + 10, y + 24))
        cx = x + 22 + txt_cam.get_width()
        for i in range(tambor.camaras):
            centro = (cx + i * 14, y + 31)
            if i < tambor.disparadas:
                pygame.draw.circle(tela, (150, 40, 32), centro, 5)
            else:
                pygame.draw.circle(tela, (165, 135, 75), centro, 5, width=1)

    def _desenhar_placares(self, tela: pygame.Surface, partida: PartidaTruco) -> None:
        largura_placa = min(240, int(self.largura * 0.23))
        altura_placa = 72

        # Placar do Bot (Canto Superior Esquerdo)
        self._desenhar_placa_jogador(
            tela,
            x=20,
            y=16,
            largura=largura_placa,
            altura=altura_placa,
            nome=partida.jogador2.nome,
            pontos=partida.pontos_jogador2,
            eh_mao=partida.jogador_mao == partida.jogador2,
            avatar_simb="⚔",
        )

        # Placar do Jogador (Canto Superior Direito)
        self._desenhar_placa_jogador(
            tela,
            x=self.largura - largura_placa - 20,
            y=16,
            largura=largura_placa,
            altura=altura_placa,
            nome=partida.jogador1.nome,
            pontos=partida.pontos_jogador1,
            eh_mao=partida.jogador_mao == partida.jogador1,
            avatar_simb="★",
        )

    def _desenhar_placa_jogador(
        self,
        tela: pygame.Surface,
        x: int,
        y: int,
        largura: int,
        altura: int,
        nome: str,
        pontos: int,
        eh_mao: bool,
        avatar_simb: str,
    ) -> None:
        # 1. Drop shadow da placa
        sombra = pygame.Surface((largura, altura), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 90))
        tela.blit(sombra, (x + 3, y + 4))

        # 2. Placa de madeira/couro escuro texturizada
        rect = pygame.Rect(x, y, largura, altura)
        s_fundo = pygame.Surface((largura, altura), pygame.SRCALPHA)
        s_fundo.fill((30, 26, 22, 235))  # #1e1a16 - Couro/Madeira escura
        tela.blit(s_fundo, (x, y))

        # Moldura rústica em bronze envelhecido
        pygame.draw.rect(tela, (95, 75, 55), rect, width=2, border_radius=6)
        # Filete interno dourado envelhecido
        rect_interno = pygame.Rect(x + 2, y + 2, largura - 4, altura - 4)
        pygame.draw.rect(tela, (165, 135, 75), rect_interno, width=1, border_radius=5)

        # 3. Nome e Avatar
        txt_nome = self.font_titulo.render(
            f"{avatar_simb} {nome}", True, (235, 225, 210)
        )
        tela.blit(txt_nome, (x + 10, y + 8))

        # Badge "MÃO"
        if eh_mao:
            rect_badge = pygame.Rect(x + largura - 46, y + 8, 36, 16)
            pygame.draw.rect(tela, (180, 140, 50), rect_badge, border_radius=3)
            txt_badge = self.font_badge.render("MÃO", True, (25, 20, 15))
            tela.blit(txt_badge, txt_badge.get_rect(center=rect_badge.center))

        # 4. Pontos
        txt_pts = self.font_pts.render(f"{pontos}", True, (230, 195, 95))
        tela.blit(txt_pts, (x + 12, y + 32))

        txt_tentos = self.font_sub.render("/ 12 tentos", True, (160, 150, 140))
        tela.blit(txt_tentos, (x + 50, y + 42))

    def _desenhar_placa_truco_central(
        self, tela: pygame.Surface, partida: PartidaTruco
    ) -> None:
        """Placa com o valor e o status da aposta, na coluna direita sob a placa do humano.

        Antes ficava no centro do topo e cobria o rótulo "2ª VAZA"; o centro agora é do busto.
        """
        rect_placa = layout_mesa(self.largura, self.altura).placa_aposta()
        largura_placa, altura_placa = rect_placa.size
        x, y = rect_placa.topleft

        # Sombra
        sombra = pygame.Surface((largura_placa, altura_placa), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 85))
        tela.blit(sombra, (x + 2, y + 4))

        # Placa central
        rect = pygame.Rect(x, y, largura_placa, altura_placa)
        s_fundo = pygame.Surface((largura_placa, altura_placa), pygame.SRCALPHA)
        s_fundo.fill((26, 22, 18, 235))
        tela.blit(s_fundo, (x, y))

        pygame.draw.rect(tela, (110, 85, 60), rect, width=2, border_radius=6)
        pygame.draw.rect(
            tela,
            (180, 145, 80),
            (x + 2, y + 2, largura_placa - 4, altura_placa - 4),
            width=1,
            border_radius=5,
        )

        status_truco = (
            partida.nivel_truco.nome_exibicao.upper()
            if partida.nivel_truco
            else "RODADA NORMAL"
        )
        txt_status = self.font_badge.render(status_truco, True, (215, 175, 80))
        tela.blit(
            txt_status, txt_status.get_rect(center=(x + largura_placa // 2, y + 12))
        )

        valor_str = f"VALENDO {partida.valor_truco_atual} TENTO{'S' if partida.valor_truco_atual > 1 else ''}"
        txt_valor = self.font_titulo.render(valor_str, True, (245, 235, 220))
        tela.blit(
            txt_valor, txt_valor.get_rect(center=(x + largura_placa // 2, y + 30))
        )

    def _desenhar_aviso_flutuante(
        self, tela: pygame.Surface, partida: PartidaTruco
    ) -> None:
        """Faixa semitransparente com a última mensagem, logo acima da barra de ações."""
        rect = layout_mesa(self.largura, self.altura).faixa_mensagem()
        x, y = rect.topleft
        largura_banner, altura_banner = rect.size

        s = pygame.Surface((largura_banner, altura_banner), pygame.SRCALPHA)
        s.fill((10, 20, 15, 150))
        tela.blit(s, (x, y))
        pygame.draw.rect(tela, (55, 85, 65), rect, width=1, border_radius=6)

        txt_msg = self.font_msg.render(partida.ultima_mensagem, True, (240, 235, 220))
        tela.blit(txt_msg, txt_msg.get_rect(center=rect.center))
