from abc import ABC, abstractmethod
from typing import Optional
import pygame
from core.card import Carta
from core.player import JogadorHumano, JogadorBot
from core.match import PartidaTruco, EstadoPartida
from core.rules import TipoTruco, TipoEnvido, RespostaAposta
from ui.button import Button
from ui.card_sprite import CardSprite
from ui.hud import HUD
from game.asset_manager import AssetManager


class GameState(ABC):
    """Classe base abstrata para estados de tela do jogo."""

    def __init__(self, manager: "GameStateManager"):
        self.manager = manager

    @abstractmethod
    def entrar(self) -> None:
        pass

    @abstractmethod
    def sair(self) -> None:
        pass

    @abstractmethod
    def redimensionar(self, largura: int, altura: int) -> None:
        pass

    @abstractmethod
    def tratar_evento(self, event: pygame.event.Event) -> None:
        pass

    @abstractmethod
    def atualizar(self, dt: float) -> None:
        pass

    @abstractmethod
    def desenhar(self, tela: pygame.Surface) -> None:
        pass


class GameStateManager:
    """Máquina de estados para alternar entre Menu, Partida e Telas Finais com suporte a resize."""

    def __init__(self, largura: int, altura: int):
        self.largura = largura
        self.altura = altura
        self.asset_manager = AssetManager()
        self.estado_atual: Optional[GameState] = None

    def mudar_estado(self, novo_estado: GameState) -> None:
        if self.estado_atual:
            self.estado_atual.sair()
        self.estado_atual = novo_estado
        self.estado_atual.entrar()

    def redimensionar(self, largura: int, altura: int) -> None:
        self.largura = max(800, largura)
        self.altura = max(600, altura)
        if self.estado_atual:
            self.estado_atual.redimensionar(self.largura, self.altura)

    def tratar_evento(self, event: pygame.event.Event) -> None:
        if self.estado_atual:
            self.estado_atual.tratar_evento(event)

    def atualizar(self, dt: float) -> None:
        if self.estado_atual:
            self.estado_atual.atualizar(dt)

    def desenhar(self, tela: pygame.Surface) -> None:
        if self.estado_atual:
            self.estado_atual.desenhar(tela)


# ========================================================
# ESTADO: MENU PRINCIPAL
# ========================================================
class MenuState(GameState):
    def __init__(self, manager: GameStateManager):
        super().__init__(manager)
        self.botoes: list[Button] = []
        self.exibindo_regras: bool = False

        pygame.font.init()
        self.font_titulo = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 46, bold=True
        )
        self.font_sub = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 18, italic=True
        )
        self.font_regras_tit = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 18, bold=True
        )
        self.font_regras_txt = pygame.font.SysFont("DejaVu Sans, Arial, sans-serif", 14)

    def entrar(self) -> None:
        self._posicionar_botoes()

    def sair(self) -> None:
        pass

    def redimensionar(self, largura: int, altura: int) -> None:
        self._posicionar_botoes()

    def _posicionar_botoes(self) -> None:
        largura = self.manager.largura
        altura = self.manager.altura
        btn_w, btn_h = 240, 48
        x_center = (largura - btn_w) // 2

        self.botoes = [
            Button(
                rect=pygame.Rect(x_center, altura // 2 - 25, btn_w, btn_h),
                texto="Iniciar Duelo",
                callback=self._iniciar_partida,
                cor_padrao=(45, 90, 55),
                cor_borda=(85, 140, 95),
            ),
            Button(
                rect=pygame.Rect(x_center, altura // 2 + 35, btn_w, btn_h),
                texto="Regras & Hierarquia",
                callback=self._alternar_regras,
                cor_padrao=Button.COR_ENVIDO_BG,
                cor_borda=Button.COR_ENVIDO_BORDA,
            ),
            Button(
                rect=pygame.Rect(x_center, altura // 2 + 95, btn_w, btn_h),
                texto="Sair do Jogo",
                callback=self._sair,
                cor_padrao=Button.COR_TRUCO_BG,
                cor_borda=Button.COR_TRUCO_BORDA,
            ),
        ]

    def _iniciar_partida(self) -> None:
        self.manager.mudar_estado(PartidaState(self.manager))

    def _alternar_regras(self) -> None:
        self.exibindo_regras = not self.exibindo_regras

    def _sair(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def tratar_evento(self, event: pygame.event.Event) -> None:
        if self.exibindo_regras:
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.exibindo_regras = False
            return

        for btn in self.botoes:
            btn.tratar_evento(event)

    def atualizar(self, dt: float) -> None:
        if not self.exibindo_regras:
            pos_mouse = pygame.mouse.get_pos()
            for btn in self.botoes:
                btn.verificar_hover(pos_mouse)

    def desenhar(self, tela: pygame.Surface) -> None:
        mesa = self.manager.asset_manager.obter_mesa_feltro(
            self.manager.largura, self.manager.altura
        )
        tela.blit(mesa, (0, 0))

        # Título estilo xilogravura / ouro velho
        sombra = self.font_titulo.render("TRUCO GAUDÉRIO", True, (15, 20, 15))
        txt_tit = self.font_titulo.render("TRUCO GAUDÉRIO", True, (230, 195, 95))
        rect_tit = txt_tit.get_rect(
            center=(self.manager.largura // 2, self.manager.altura // 2 - 130)
        )
        tela.blit(sombra, (rect_tit.x + 3, rect_tit.y + 4))
        tela.blit(txt_tit, rect_tit)

        txt_sub = self.font_sub.render(
            "O Clássico Duelo de Cartas das Coxilhas (24 Tentos)", True, (210, 200, 185)
        )
        rect_sub = txt_sub.get_rect(
            center=(self.manager.largura // 2, self.manager.altura // 2 - 85)
        )
        tela.blit(txt_sub, rect_sub)

        for btn in self.botoes:
            btn.desenhar(tela)

        if self.exibindo_regras:
            self._desenhar_modal_regras(tela)

    def _desenhar_modal_regras(self, tela: pygame.Surface) -> None:
        overlay = pygame.Surface(
            (self.manager.largura, self.manager.altura), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 190))
        tela.blit(overlay, (0, 0))

        largura_m, altura_m = min(740, self.manager.largura - 40), 480
        x = (self.manager.largura - largura_m) // 2
        y = (self.manager.altura - altura_m) // 2

        pygame.draw.rect(
            tela, (25, 22, 18), (x, y, largura_m, altura_m), border_radius=10
        )
        pygame.draw.rect(
            tela, (165, 135, 75), (x, y, largura_m, altura_m), width=2, border_radius=10
        )

        tit = self.font_regras_tit.render(
            "HIERARQUIA E REGRAS DO TRUCO GAUDÉRIO", True, (235, 195, 95)
        )
        tela.blit(tit, tit.get_rect(center=(x + largura_m // 2, y + 30)))

        linhas = [
            "• Manilhas Fixas (Maior para menor):",
            "   1. Espadilha (1 de Espadas)  |  2. Bastilha (1 de Bastos)",
            "   3. Manilha (7 de Espadas)   |  4. Sete Belo (7 de Ouros)",
            "• Cartas Comuns: 3s > 2s > 1s (Copas/Ouros) > 12s > 11s > 10s > 7s > 6s > 5s > 4s",
            "• Melhor de 3 vazas: quem vencer 2 vazas leva a mão.",
            "• Canguçu (Empate): se a 1ª vaza empatar, quem ganhar a 2ª leva tudo.",
            "• Envido: disputado na 1ª vaza entre cartas do mesmo naipe (+20 pontos).",
            "• Flor: 3 cartas do mesmo naipe valem 3 tentos e bloqueiam o Envido.",
            "• Placar de 24 Tentos: Primeiros 12 são as 'Más'; últimos 12 são as 'Boas'.",
            "",
            "[ Clique em qualquer lugar para fechar ]",
        ]

        curr_y = y + 70
        for linha in linhas:
            cor = (235, 195, 95) if "Clique" in linha else (225, 215, 200)
            txt = self.font_regras_txt.render(linha, True, cor)
            tela.blit(txt, (x + 35, curr_y))
            curr_y += 30


# ========================================================
# ESTADO: PARTIDA (MESA ORGÂNICA E FLUIDA)
# ========================================================
class PartidaState(GameState):
    """
    Mesa orgânica inspirada em Balatro e Inscryption:
    - Oponente ancorado na borda superior (-15px).
    - Centro da mesa limpo sem caixas rígidas.
    - Cartas jogadas com leve rotação angular (-4° a +4°) e drop shadow.
    - Barra de ações rústica com hierarquia de cores sóbria.
    """

    TEMPO_RESPOSTA_BOT_S = 0.75

    # Ângulos sutis pré-definidos para simular o descarte orgânico de cartas na mesa
    ANGULOS_VAZAS = [
        (-2.5, 3.0),  # Vaza 1: Bot, Você
        (2.0, -3.5),  # Vaza 2: Bot, Você
        (-3.0, 2.5),  # Vaza 3: Bot, Você
    ]

    def __init__(self, manager: GameStateManager):
        super().__init__(manager)
        self.hud = HUD(self.manager.largura, self.manager.altura)

        self.humano = JogadorHumano("Você")
        self.bot = JogadorBot("Gaudério Bot")
        self.partida = PartidaTruco(self.humano, self.bot)

        self.sprites_humano: list[CardSprite] = []
        self.sprites_bot: list[CardSprite] = []

        self.botoes_acao: list[Button] = []
        self.botoes_resposta_aposta: list[Button] = []
        self.botao_proxima_mao: Optional[Button] = None

        self.timer_bot: float = 0.0
        self.bot_pensando: bool = False

        pygame.font.init()
        self.font_vaza_label = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 12, bold=True
        )
        self.font_vencedor = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 11, bold=True
        )
        self.font_pensando = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 12, italic=True
        )

    def entrar(self) -> None:
        self.partida.iniciar_nova_rodada()
        self._sincronizar_sprites_cartas()
        self._atualizar_botoes()

    def sair(self) -> None:
        pass

    def redimensionar(self, largura: int, altura: int) -> None:
        self.hud.redimensionar(largura, altura)
        self._sincronizar_sprites_cartas()
        self._atualizar_botoes()

    def _sincronizar_sprites_cartas(self) -> None:
        self.sprites_humano.clear()
        self.sprites_bot.clear()

        # 1. Cartas do Oponente: Ancoradas saindo da borda superior central (Y: -15)
        total_bot = len(self.bot.mao)
        w_bot, h_bot = 68, 100
        espaco_bot = 8
        largura_total_b = total_bot * w_bot + max(0, total_bot - 1) * espaco_bot
        inicio_x_b = (self.manager.largura - largura_total_b) // 2
        y_bot = -12  # Parcialmente fora da tela para dar sensação de presença oposta

        for i, carta in enumerate(self.bot.mao):
            x = inicio_x_b + i * (w_bot + espaco_bot)
            sprite = CardSprite(
                carta=carta,
                pos_x=x,
                pos_y=y_bot,
                asset_manager=self.manager.asset_manager,
                aberta=False,
                interativa=False,
            )
            sprite.image = pygame.transform.scale(sprite.image, (w_bot, h_bot))
            sprite.rect = sprite.image.get_rect(topleft=(x, y_bot))
            self.sprites_bot.append(sprite)

        # 2. Cartas do Jogador: Ancoradas na borda inferior (Y: altura - 165)
        total_humano = len(self.humano.mao)
        w_h = 105
        espaco_h = 18
        largura_total_h = total_humano * w_h + max(0, total_humano - 1) * espaco_h
        inicio_x_h = (self.manager.largura - largura_total_h) // 2
        y_humano = self.manager.altura - 175

        for i, carta in enumerate(self.humano.mao):
            x = inicio_x_h + i * (w_h + espaco_h)
            sprite = CardSprite(
                carta=carta,
                pos_x=x,
                pos_y=y_humano,
                asset_manager=self.manager.asset_manager,
                aberta=True,
                interativa=True,
            )
            self.sprites_humano.append(sprite)

    def _atualizar_botoes(self) -> None:
        """Barra de ações elevada para dar 40-50px de respiro sobre a mão do jogador."""
        self.botoes_acao.clear()
        self.botoes_resposta_aposta.clear()
        self.botao_proxima_mao = None

        # Elevado para altura - 245, evitando cliques acidentais e equilibrando a tela
        y_botoes = self.manager.altura - 245
        btn_h = 36

        if self.partida.estado_atual == EstadoPartida.FIM_DA_MAO:
            btn_w = 190
            x = (self.manager.largura - btn_w) // 2
            self.botao_proxima_mao = Button(
                rect=pygame.Rect(x, y_botoes, btn_w, btn_h),
                texto="Próxima Mão",
                callback=self._avancar_proxima_mao,
                cor_padrao=(45, 90, 55),
                cor_borda=(85, 140, 95),
                tamanho_fonte=15,
            )
            return

        # Resposta a Truco ou Envido
        if self.partida.estado_atual in (
            EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO,
            EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO,
        ):
            quem_responde = (
                self.partida.quem_deve_responder_truco
                if self.partida.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO
                else self.partida.quem_deve_responder_envido
            )

            if quem_responde == self.humano:
                btn_w = 125
                espaco = 14
                x_inicio = (self.manager.largura - (btn_w * 3 + espaco * 2)) // 2

                self.botoes_resposta_aposta = [
                    Button(
                        rect=pygame.Rect(x_inicio, y_botoes, btn_w, btn_h),
                        texto="Quero",
                        callback=lambda: self._responder_aposta_humano(
                            RespostaAposta.QUERO
                        ),
                        cor_padrao=(45, 90, 55),
                        cor_borda=(85, 140, 95),
                        tamanho_fonte=15,
                    ),
                    Button(
                        rect=pygame.Rect(
                            x_inicio + btn_w + espaco, y_botoes, btn_w, btn_h
                        ),
                        texto="Não Quero",
                        callback=lambda: self._responder_aposta_humano(
                            RespostaAposta.NAO_QUERO
                        ),
                        cor_padrao=Button.COR_TRUCO_BG,
                        cor_borda=Button.COR_TRUCO_BORDA,
                        tamanho_fonte=15,
                    ),
                    Button(
                        rect=pygame.Rect(
                            x_inicio + (btn_w + espaco) * 2, y_botoes, btn_w, btn_h
                        ),
                        texto="Aumentar",
                        callback=lambda: self._responder_aposta_humano(
                            RespostaAposta.AUMENTAR
                        ),
                        cor_padrao=(180, 140, 50),
                        cor_borda=(220, 180, 80),
                        tamanho_fonte=15,
                    ),
                ]
            return

        # Barra de Ações Padrão
        btn_w = 130
        espaco = 10
        prox_truco = (
            "TRUCO"
            if self.partida.nivel_truco is None
            else (
                self.partida.nivel_truco.proximo_nivel.nome_exibicao.upper()
                if self.partida.nivel_truco.proximo_nivel
                else None
            )
        )

        botoes = []
        # Botão dramático de Truco / Retruco / Vale Quatro (vermelho cardeal)
        if prox_truco and self.partida.pode_pedir_truco(self.humano):
            botoes.append(
                Button(
                    rect=pygame.Rect(0, y_botoes, btn_w + 10, btn_h),
                    texto=prox_truco,
                    callback=self._pedir_truco_humano,
                    cor_padrao=Button.COR_TRUCO_BG,
                    cor_borda=Button.COR_TRUCO_BORDA,
                    tamanho_fonte=15,
                )
            )

        # Botão de Flor (verde esmeralda vivo)
        if self.partida.pode_cantar_flor(self.humano):
            botoes.append(
                Button(
                    rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                    texto="FLOR",
                    callback=self._cantar_flor_humano,
                    cor_padrao=(35, 115, 65),
                    cor_borda=(75, 175, 110),
                    tamanho_fonte=14,
                )
            )

        # Grupo de Envido (azul noturno uniforme)
        if self.partida.pode_cantar_envido(self.humano):
            botoes.append(
                Button(
                    rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                    texto="ENVIDO",
                    callback=lambda: self._cantar_envido_humano(TipoEnvido.ENVIDO),
                    cor_padrao=Button.COR_ENVIDO_BG,
                    cor_borda=Button.COR_ENVIDO_BORDA,
                    tamanho_fonte=14,
                )
            )
            botoes.append(
                Button(
                    rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                    texto="REAL ENVIDO",
                    callback=lambda: self._cantar_envido_humano(TipoEnvido.REAL_ENVIDO),
                    cor_padrao=Button.COR_ENVIDO_BG,
                    cor_borda=Button.COR_ENVIDO_BORDA,
                    tamanho_fonte=13,
                )
            )
            botoes.append(
                Button(
                    rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                    texto="FALTA ENVIDO",
                    callback=lambda: self._cantar_envido_humano(
                        TipoEnvido.FALTA_ENVIDO
                    ),
                    cor_padrao=Button.COR_ENVIDO_BG,
                    cor_borda=Button.COR_ENVIDO_BORDA,
                    tamanho_fonte=13,
                )
            )

        # Botão discreto de ir ao baralho
        botoes.append(
            Button(
                rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                texto="Ao Baralho",
                callback=self._ir_ao_baralho_humano,
                cor_padrao=Button.COR_PADRAO_BG,
                cor_borda=Button.COR_PADRAO_BORDA,
                tamanho_fonte=14,
            )
        )

        total_w = sum(b.rect.width for b in botoes) + (len(botoes) - 1) * espaco
        x_inicio = (self.manager.largura - total_w) // 2

        curr_x = x_inicio
        for btn in botoes:
            btn.rect.x = curr_x
            btn.definir_rect(btn.rect)
            curr_x += btn.rect.width + espaco
            self.botoes_acao.append(btn)

    def _pedir_truco_humano(self) -> None:
        if self.partida.pedir_truco(self.humano):
            self._atualizar_botoes()
            self._iniciar_pensamento_bot()

    def _cantar_flor_humano(self) -> None:
        if self.partida.cantar_flor(self.humano):
            self._sincronizar_sprites_cartas()
            self._atualizar_botoes()
            if (
                self.partida.jogador_vez == self.bot
                and self.partida.estado_atual == EstadoPartida.JOGANDO_VAZA
            ):
                self._iniciar_pensamento_bot()

    def _cantar_envido_humano(self, tipo: TipoEnvido) -> None:
        if self.partida.cantar_envido(self.humano, tipo):
            self._atualizar_botoes()
            self._iniciar_pensamento_bot()

    def _ir_ao_baralho_humano(self) -> None:
        self.partida.ir_ao_baralho(self.humano)
        self._sincronizar_sprites_cartas()
        self._atualizar_botoes()

    def _responder_aposta_humano(self, resposta: RespostaAposta) -> None:
        if self.partida.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO:
            self.partida.responder_truco(resposta, self.humano)
        elif self.partida.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO:
            self.partida.responder_envido(resposta)

        self._sincronizar_sprites_cartas()
        self._atualizar_botoes()
        if self.partida.jogador_vez == self.bot or self.partida.estado_atual in (
            EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO,
            EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO,
        ):
            self._iniciar_pensamento_bot()

    def _avancar_proxima_mao(self) -> None:
        if self.partida.estado_atual == EstadoPartida.FIM_DE_JOGO:
            self.manager.mudar_estado(GameOverState(self.manager, self.partida))
        else:
            self.partida.iniciar_nova_rodada()
            self._sincronizar_sprites_cartas()
            self._atualizar_botoes()
            if self.partida.jogador_vez == self.bot:
                self._iniciar_pensamento_bot()

    def _iniciar_pensamento_bot(self) -> None:
        self.bot_pensando = True
        self.timer_bot = self.TEMPO_RESPOSTA_BOT_S

    def _executar_turno_bot(self) -> None:
        self.bot_pensando = False
        estado = self.partida.estado_atual

        if (
            estado == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO
            and self.partida.quem_deve_responder_truco == self.bot
        ):
            estado_mesa = self.partida.obter_estado_mesa_para_jogador(self.bot)
            resposta = self.bot.responder_aposta(self.partida.nivel_truco, estado_mesa)
            self.partida.responder_truco(resposta, self.bot)
            self._sincronizar_sprites_cartas()
            self._atualizar_botoes()
            if self.partida.jogador_vez == self.bot:
                self._iniciar_pensamento_bot()
            return

        if (
            estado == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO
            and self.partida.quem_deve_responder_envido == self.bot
        ):
            estado_mesa = self.partida.obter_estado_mesa_para_jogador(self.bot)
            resposta = self.bot.responder_aposta(
                self.partida.aposta_envido_atual, estado_mesa
            )
            self.partida.responder_envido(resposta)
            self._sincronizar_sprites_cartas()
            self._atualizar_botoes()
            if self.partida.jogador_vez == self.bot:
                self._iniciar_pensamento_bot()
            return

        if self.partida.jogador_vez == self.bot and estado in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        ):
            # 1. Se bot tem Flor e pode cantar Flor, canta Flor!
            if self.partida.pode_cantar_flor(self.bot):
                self.partida.cantar_flor(self.bot)
                self._sincronizar_sprites_cartas()
                self._atualizar_botoes()
                if (
                    self.partida.jogador_vez == self.bot
                    and self.partida.estado_atual == EstadoPartida.JOGANDO_VAZA
                ):
                    self._iniciar_pensamento_bot()
                return

            # 2. Se bot pode cantar Envido e tem mão forte (>= 29 pts), canta Envido!
            if (
                self.partida.pode_cantar_envido(self.bot)
                and self.bot.pontos_envido >= 29
                and not self.partida.envido_disputado
            ):
                self.partida.cantar_envido(self.bot, TipoEnvido.ENVIDO)
                self._atualizar_botoes()
                return

            if self.partida.pode_pedir_truco(self.bot) and self.bot.quer_pedir_truco(
                self.partida.nivel_truco
            ):
                self.partida.pedir_truco(self.bot)
                self._atualizar_botoes()
                return

            if self.bot.mao:
                estado_mesa = self.partida.obter_estado_mesa_para_jogador(self.bot)
                carta_escolhida = self.bot.decidir_jogada(estado_mesa)
                self.partida.jogar_carta(self.bot, carta_escolhida)
                self._sincronizar_sprites_cartas()
                self._atualizar_botoes()

                if (
                    self.partida.jogador_vez == self.bot
                    and self.partida.estado_atual == EstadoPartida.JOGANDO_VAZA
                ):
                    self._iniciar_pensamento_bot()

    def tratar_evento(self, event: pygame.event.Event) -> None:
        if self.partida.estado_atual == EstadoPartida.FIM_DE_JOGO:
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.manager.mudar_estado(GameOverState(self.manager, self.partida))
            return

        if self.botao_proxima_mao:
            self.botao_proxima_mao.tratar_evento(event)
            return

        for btn in self.botoes_resposta_aposta:
            if btn.tratar_evento(event):
                return

        for btn in self.botoes_acao:
            if btn.tratar_evento(event):
                return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if (
                self.partida.jogador_vez == self.humano
                and self.partida.estado_atual
                in (EstadoPartida.AGUARDANDO_ENVIDO, EstadoPartida.JOGANDO_VAZA)
                and not self.bot_pensando
            ):
                pos_mouse = event.pos
                for sprite in self.sprites_humano:
                    if sprite.verificar_clique(pos_mouse):
                        self.partida.jogar_carta(self.humano, sprite.carta)
                        self._sincronizar_sprites_cartas()
                        self._atualizar_botoes()
                        if self.partida.jogador_vez == self.bot:
                            self._iniciar_pensamento_bot()
                        break

    def atualizar(self, dt: float) -> None:
        pos_mouse = pygame.mouse.get_pos()

        for sprite in self.sprites_humano:
            sprite.atualizar(pos_mouse)

        if self.botao_proxima_mao:
            self.botao_proxima_mao.verificar_hover(pos_mouse)
        for btn in self.botoes_resposta_aposta:
            btn.verificar_hover(pos_mouse)
        for btn in self.botoes_acao:
            btn.verificar_hover(pos_mouse)

        if self.bot_pensando:
            self.timer_bot -= dt
            if self.timer_bot <= 0:
                self._executar_turno_bot()

    def desenhar(self, tela: pygame.Surface) -> None:
        mesa = self.manager.asset_manager.obter_mesa_feltro(
            self.manager.largura, self.manager.altura
        )
        tela.blit(mesa, (0, 0))

        # HUD superior com placares
        self.hud.desenhar(tela, self.partida)

        # Cartas do Bot (ancoradas na borda superior)
        for s in self.sprites_bot:
            s.desenhar(tela)

        # Centro da mesa (Arenas fluidas sem caixas pesadas)
        self._desenhar_centro_organico(tela)

        # Cartas do Jogador (ancoradas na base)
        for s in self.sprites_humano:
            s.desenhar(tela)

        # Botões de ação
        if self.botao_proxima_mao:
            self.botao_proxima_mao.desenhar(tela)
        for btn in self.botoes_resposta_aposta:
            btn.desenhar(tela)
        for btn in self.botoes_acao:
            btn.desenhar(tela)

        if self.bot_pensando:
            self._desenhar_aviso_bot_pensando(tela)

    def _desenhar_centro_organico(self, tela: pygame.Surface) -> None:
        """
        Renderiza as 3 vazas no centro da mesa:
        - Cartas de tamanho idêntico à mão (105x155), eliminando a síndrome de mesa vazia.
        - Empilhamento tátil em monte: 1ª carta jogada (-18px, -10px) e 2ª carta jogada (+18px, +16px).
        - Ambas as cartas perfeitamente legíveis com identificação de ordem e vencedor.
        - Placeholders vazios com alto contraste e elegância rústica.
        """
        if not self.partida.mao_atual:
            return

        largura_tela = self.manager.largura
        # Posições centrais horizontais das 3 vazas
        pontos_x = [
            int(largura_tela * 0.33),  # Vaza 1
            int(largura_tela * 0.50),  # Vaza 2
            int(largura_tela * 0.67),  # Vaza 3
        ]
        # Âncora vertical central
        y_centro = int(self.manager.altura * 0.41)
        # Cartas da vaza grandes e protagonistas (mesmo tamanho da mão do jogador!)
        w_carta, h_carta = 105, 155

        for i, vaza in enumerate(self.partida.mao_atual.vazas):
            cx = pontos_x[i]
            eh_vaza_atual = i == self.partida.mao_atual.indice_vaza_atual
            vaza_concluida = len(vaza.cartas_jogadas) == 2

            # 1. Rótulo de alto contraste no feltro com folga generosa
            cor_label = (241, 196, 15) if eh_vaza_atual else (222, 211, 189)
            sombra_label = self.font_vaza_label.render(
                f"{i + 1}ª VAZA", True, (15, 25, 20)
            )
            txt_vaza = self.font_vaza_label.render(f"{i + 1}ª VAZA", True, cor_label)
            rect_label = txt_vaza.get_rect(center=(cx, y_centro - h_carta // 2 - 46))
            tela.blit(sombra_label, (rect_label.x + 1, rect_label.y + 2))
            tela.blit(txt_vaza, rect_label)

            # 2. Se a vaza não tiver cartas, desenha o placeholder tátil nítido
            if not vaza.cartas_jogadas:
                rect_slot = pygame.Rect(0, 0, w_carta, h_carta)
                rect_slot.center = (cx, y_centro)

                # Marca d'água nítida e acessível
                s_slot = pygame.Surface((w_carta, h_carta), pygame.SRCALPHA)
                cor_fill = (25, 60, 40, 85) if eh_vaza_atual else (18, 45, 30, 50)
                s_slot.fill(cor_fill)
                tela.blit(s_slot, rect_slot.topleft)

                cor_borda = (80, 135, 95) if eh_vaza_atual else (45, 80, 55)
                pygame.draw.rect(tela, cor_borda, rect_slot, width=1, border_radius=8)

                if eh_vaza_atual:
                    txt_aguarda = self.font_pensando.render(
                        "Aguardando...", True, (135, 185, 150)
                    )
                    tela.blit(
                        txt_aguarda, txt_aguarda.get_rect(center=rect_slot.center)
                    )
                continue

            # 3. Renderização orgânica das cartas jogadas em monte
            angulos = self.ANGULOS_VAZAS[i]

            for j, (jg, carta) in enumerate(vaza.cartas_jogadas):
                eh_bot = jg == self.bot
                eh_primeira = j == 0

                # 1ª carta jogada fica na base (-18, -10); 2ª carta jogada cai por cima (+18, +16)
                if eh_primeira:
                    pos_x = cx - 18
                    pos_y = y_centro - 10
                    angulo = angulos[0]
                else:
                    pos_x = cx + 18
                    pos_y = y_centro + 16
                    angulo = angulos[1]

                # Imagem da carta com tamanho protagonista
                surf_base = self.manager.asset_manager.obter_sprite_carta(
                    carta, aberta=True
                )
                surf_carta = pygame.transform.scale(surf_base, (w_carta, h_carta))

                # Rotação orgânica
                surf_rot = pygame.transform.rotate(surf_carta, angulo)
                rect_rot = surf_rot.get_rect(center=(pos_x, pos_y))

                # Sombra projetada sob a carta rotacionada
                sombra_rot = pygame.Surface(surf_rot.get_size(), pygame.SRCALPHA)
                pygame.draw.rect(
                    sombra_rot,
                    (0, 0, 0, 95 if eh_primeira else 115),
                    (0, 0, surf_rot.get_width(), surf_rot.get_height()),
                    border_radius=8,
                )
                tela.blit(sombra_rot, (rect_rot.x + 3, rect_rot.y + 4))

                # Desenha a carta com pixel art totalmente limpo e desobstruído
                tela.blit(surf_rot, rect_rot)

            # 4. Indicador de resultado na base da vaza com margem limpa
            if vaza_concluida:
                self._desenhar_tag_resultado_vaza(
                    tela, cx, y_centro + h_carta // 2 + 40, vaza
                )

    def _desenhar_tag_resultado_vaza(
        self, tela: pygame.Surface, cx: int, cy: int, vaza
    ) -> None:
        """Pill compacto e elegante com o vencedor da vaza."""
        if vaza.empate:
            cor_bg = (130, 100, 30)
            txt_msg = "= Canguçu"
        elif vaza.vencedor == self.humano:
            cor_bg = (40, 95, 55)
            txt_msg = "★ Você"
        else:
            cor_bg = (120, 35, 30)
            txt_msg = "⚔ Bot"

        superficie_txt = self.font_vencedor.render(txt_msg, True, (250, 245, 235))
        w_pill = superficie_txt.get_width() + 18
        h_pill = 22
        rect_pill = pygame.Rect(0, 0, w_pill, h_pill)
        rect_pill.center = (cx, cy)

        s_pill = pygame.Surface((w_pill, h_pill), pygame.SRCALPHA)
        s_pill.fill(cor_bg)
        tela.blit(s_pill, rect_pill.topleft)
        pygame.draw.rect(tela, (215, 190, 140), rect_pill, width=1, border_radius=4)
        tela.blit(superficie_txt, superficie_txt.get_rect(center=rect_pill.center))

    def _desenhar_aviso_bot_pensando(self, tela: pygame.Surface) -> None:
        rect = pygame.Rect((self.manager.largura - 190) // 2, 70, 190, 22)
        s = pygame.Surface((190, 22), pygame.SRCALPHA)
        s.fill((0, 0, 0, 130))
        tela.blit(s, rect.topleft)
        pygame.draw.rect(tela, (160, 130, 70), rect, width=1, border_radius=4)
        txt = self.font_pensando.render("Gaudério pensando...", True, (230, 220, 200))
        tela.blit(txt, txt.get_rect(center=rect.center))


# ========================================================
# ESTADO: FIM DE JOGO (VITÓRIA / DERROTA)
# ========================================================
class GameOverState(GameState):
    def __init__(self, manager: GameStateManager, partida: PartidaTruco):
        super().__init__(manager)
        self.partida = partida
        self.botoes: list[Button] = []

        pygame.font.init()
        self.font_tit = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 40, bold=True
        )
        self.font_sub = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 18)
        self.font_placar = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 30, bold=True
        )

    def entrar(self) -> None:
        self._posicionar_botoes()

    def sair(self) -> None:
        pass

    def redimensionar(self, largura: int, altura: int) -> None:
        self._posicionar_botoes()

    def _posicionar_botoes(self) -> None:
        largura = self.manager.largura
        altura = self.manager.altura
        btn_w, btn_h = 220, 48
        x_center = (largura - btn_w) // 2

        self.botoes = [
            Button(
                rect=pygame.Rect(x_center, altura // 2 + 55, btn_w, btn_h),
                texto="Jogar Novamente",
                callback=self._jogar_novamente,
                cor_padrao=(45, 90, 55),
                cor_borda=(85, 140, 95),
            ),
            Button(
                rect=pygame.Rect(x_center, altura // 2 + 115, btn_w, btn_h),
                texto="Menu Principal",
                callback=self._menu_principal,
                cor_padrao=Button.COR_PADRAO_BG,
                cor_borda=Button.COR_PADRAO_BORDA,
            ),
        ]

    def _jogar_novamente(self) -> None:
        self.manager.mudar_estado(PartidaState(self.manager))

    def _menu_principal(self) -> None:
        self.manager.mudar_estado(MenuState(self.manager))

    def tratar_evento(self, event: pygame.event.Event) -> None:
        for btn in self.botoes:
            btn.tratar_evento(event)

    def atualizar(self, dt: float) -> None:
        pos_mouse = pygame.mouse.get_pos()
        for btn in self.botoes:
            btn.verificar_hover(pos_mouse)

    def desenhar(self, tela: pygame.Surface) -> None:
        mesa = self.manager.asset_manager.obter_mesa_feltro(
            self.manager.largura, self.manager.altura
        )
        tela.blit(mesa, (0, 0))

        overlay = pygame.Surface(
            (self.manager.largura, self.manager.altura), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 175))
        tela.blit(overlay, (0, 0))

        vencedor = self.partida.vencedor_partida
        eh_humano = vencedor == self.partida.jogador1

        cor_tit = (230, 195, 95) if eh_humano else (192, 57, 43)
        msg_tit = "VITÓRIA GAUDÉRIA!" if eh_humano else "DERROTA NA COXILHA!"
        msg_sub = (
            "Você venceu a peleja de 24 tentos!"
            if eh_humano
            else "O Gaudério Bot levou a melhor desta vez."
        )

        txt_tit = self.font_tit.render(msg_tit, True, cor_tit)
        rect_tit = txt_tit.get_rect(
            center=(self.manager.largura // 2, self.manager.altura // 2 - 110)
        )
        tela.blit(txt_tit, rect_tit)

        txt_sub = self.font_sub.render(msg_sub, True, (225, 215, 200))
        rect_sub = txt_sub.get_rect(
            center=(self.manager.largura // 2, self.manager.altura // 2 - 65)
        )
        tela.blit(txt_sub, rect_sub)

        placar_str = f"Você: {self.partida.pontos_jogador1}  x  {self.partida.pontos_jogador2} :Bot"
        txt_placar = self.font_placar.render(placar_str, True, (245, 240, 230))
        rect_placar = txt_placar.get_rect(
            center=(self.manager.largura // 2, self.manager.altura // 2 - 15)
        )
        tela.blit(txt_placar, rect_placar)

        for btn in self.botoes:
            btn.desenhar(tela)
