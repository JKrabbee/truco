from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from enum import Enum, auto
from typing import Callable, Optional
import pygame
from core.campanha import Campanha, ResultadoCampanha
from core.card import Carta
from core.clima import Expressao, HumorDiabo
from core.falas import FalasDiabo, GatilhoFala, RitmoFalas
from core.match import EstadoPartida
from core.player import Jogador
from core.revolver import Tambor
from core.rules import TipoEnvido, RespostaAposta, obter_peso_carta
from ui.balao_fala import BalaoFala
from ui.button import Button
from ui.card_sprite import CardSprite
from ui.diabo_sprite import DiaboSprite
from ui.hud import HUD
from ui.iluminacao import Iluminacao
from ui.timer_bar import TimerBar
from game.asset_manager import AssetManager
from game.audio import Audio
from game.layout import LayoutMesa, layout_mesa
from game.roleta_controller import RoletaController
from game.save_manager import SaveInvalido, SaveManager


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

    def ao_fechar(self) -> None:
        """Chamado quando a janela fecha; estados de jogo salvam aqui (R12.2)."""


class GameStateManager:
    """Máquina de estados para alternar entre Menu, Partida e Telas Finais com suporte a resize."""

    def __init__(self, largura: int, altura: int):
        self.largura = largura
        self.altura = altura
        self.asset_manager = AssetManager()
        self.audio = Audio()  # silencioso se o mixer ou os arquivos faltarem (R11.3)
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
        self.audio.atualizar(dt)  # completa a troca de faixa depois do fade
        if self.estado_atual:
            self.estado_atual.atualizar(dt)

    def desenhar(self, tela: pygame.Surface) -> None:
        if self.estado_atual:
            self.estado_atual.desenhar(tela)

    def ao_fechar(self) -> None:
        """Delega o fechamento da janela ao estado atual."""
        if self.estado_atual:
            self.estado_atual.ao_fechar()


# ========================================================
# ESTADO: MENU PRINCIPAL
# ========================================================
class MenuState(GameState):
    """Menu principal: Continuar (só com save válido), Novo jogo, Regras e Sair (R9.5, R9.7)."""

    MSG_SAVE_CORROMPIDO = "Save corrompido foi descartado."

    def __init__(self, manager: GameStateManager):
        super().__init__(manager)
        self.botoes: list[Button] = []
        self.botoes_confirmacao: list[Button] = []
        self.indice_selecionado: int = 0
        self.exibindo_regras: bool = False
        self.confirmando_novo_jogo: bool = False
        self.campanha_salva: Optional[Campanha] = None
        self.mensagem: Optional[str] = None

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
        self.font_mensagem = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 16, bold=True
        )

    def entrar(self) -> None:
        self.manager.audio.parar_musica(800)  # o menu fica em silêncio
        self._carregar_save()
        self._posicionar_botoes()

    def sair(self) -> None:
        pass

    def redimensionar(self, largura: int, altura: int) -> None:
        self._posicionar_botoes()

    def _carregar_save(self) -> None:
        """Valida o save; se for inválido, apaga o arquivo e avisa no menu (R9.7)."""
        self.campanha_salva = None
        try:
            dados = SaveManager.carregar()
            if dados is not None:
                self.campanha_salva = Campanha.de_dict(dados)
        except SaveInvalido:
            SaveManager.apagar()
            self.mensagem = self.MSG_SAVE_CORROMPIDO

    def _posicionar_botoes(self) -> None:
        largura = self.manager.largura
        altura = self.manager.altura
        btn_w, btn_h, passo = 240, 48, 58
        x_center = (largura - btn_w) // 2

        opcoes: list[tuple[str, Callable[[], None], tuple[int, int, int], tuple[int, int, int]]] = []
        if self.campanha_salva is not None:
            opcoes.append(("Continuar", self._continuar, (45, 90, 55), (85, 140, 95)))
        opcoes += [
            (
                "Novo jogo",
                self._novo_jogo,
                Button.COR_PADRAO_BG,
                Button.COR_PADRAO_BORDA,
            ),
            (
                "Regras",
                self._alternar_regras,
                Button.COR_ENVIDO_BG,
                Button.COR_ENVIDO_BORDA,
            ),
            ("Sair", self._sair, Button.COR_TRUCO_BG, Button.COR_TRUCO_BORDA),
        ]

        y_inicial = altura // 2 - 50
        self.botoes = [
            Button(
                rect=pygame.Rect(x_center, y_inicial + i * passo, btn_w, btn_h),
                texto=texto,
                callback=callback,
                cor_padrao=cor,
                cor_borda=borda,
            )
            for i, (texto, callback, cor, borda) in enumerate(opcoes)
        ]
        self.indice_selecionado = min(self.indice_selecionado, len(self.botoes) - 1)

        # Modal de confirmação do "Novo jogo".
        conf_w = 150
        y_conf = altura // 2 + 30
        self.botoes_confirmacao = [
            Button(
                rect=pygame.Rect(largura // 2 - conf_w - 10, y_conf, conf_w, 44),
                texto="Sim (Enter)",
                callback=self._iniciar_novo_jogo,
                cor_padrao=Button.COR_TRUCO_BG,
                cor_borda=Button.COR_TRUCO_BORDA,
            ),
            Button(
                rect=pygame.Rect(largura // 2 + 10, y_conf, conf_w, 44),
                texto="Não (Esc)",
                callback=self._cancelar_novo_jogo,
            ),
        ]

    def _continuar(self) -> None:
        """Retoma o save; uma fase ainda não começada abre pela tela de introdução."""
        from game.telas import IntroFaseState

        campanha = self.campanha_salva
        if campanha is None:
            return
        if campanha.partida.numero_rodada == 0:
            self.manager.mudar_estado(IntroFaseState(self.manager, campanha))
        else:
            self.manager.mudar_estado(PartidaState(self.manager, campanha))

    def _novo_jogo(self) -> None:
        """Com save existente, pede confirmação antes de sobrescrever (R9.5)."""
        if SaveManager.existe():
            self.confirmando_novo_jogo = True
        else:
            self._iniciar_novo_jogo()

    def _iniciar_novo_jogo(self) -> None:
        from game.telas import IntroFaseState

        self.confirmando_novo_jogo = False
        SaveManager.apagar()
        self.manager.mudar_estado(IntroFaseState(self.manager, Campanha.nova()))

    def _cancelar_novo_jogo(self) -> None:
        self.confirmando_novo_jogo = False

    def _alternar_regras(self) -> None:
        self.exibindo_regras = not self.exibindo_regras

    def _sair(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def tratar_evento(self, event: pygame.event.Event) -> None:
        if self.exibindo_regras:
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.exibindo_regras = False
            return

        if self.confirmando_novo_jogo:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._iniciar_novo_jogo()
                elif event.key == pygame.K_ESCAPE:
                    self._cancelar_novo_jogo()
                return
            for btn in self.botoes_confirmacao:
                if btn.tratar_evento(event):
                    return
            return

        if event.type == pygame.KEYDOWN:
            self._tratar_tecla(event.key)
            return

        if event.type == pygame.MOUSEMOTION:
            for i, btn in enumerate(self.botoes):
                if btn.rect_base.collidepoint(event.pos):
                    self.indice_selecionado = i

        for btn in self.botoes:
            if btn.tratar_evento(event):
                return

    def _tratar_tecla(self, key: int) -> None:
        """↑/↓ escolhem o botão e Enter aciona (R7.1)."""
        if not self.botoes:
            return
        if key == pygame.K_UP:
            self.indice_selecionado = (self.indice_selecionado - 1) % len(self.botoes)
        elif key == pygame.K_DOWN:
            self.indice_selecionado = (self.indice_selecionado + 1) % len(self.botoes)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            callback = self.botoes[self.indice_selecionado].callback
            if callback:
                callback()

    def atualizar(self, dt: float) -> None:
        if self.confirmando_novo_jogo:
            pos_mouse = pygame.mouse.get_pos()
            for btn in self.botoes_confirmacao:
                btn.verificar_hover(pos_mouse)
            return

        # O destaque segue a seleção, que o mouse e o teclado atualizam.
        for i, btn in enumerate(self.botoes):
            selecionado = i == self.indice_selecionado and not self.exibindo_regras
            btn.hover = selecionado
            btn.rect.y = btn.rect_base.y - (3 if selecionado else 0)

    def desenhar(self, tela: pygame.Surface) -> None:
        largura = self.manager.largura
        altura = self.manager.altura
        mesa = self.manager.asset_manager.obter_mesa_feltro(largura, altura)
        tela.blit(mesa, (0, 0))

        titulo = "TRUCO CONTRA O DIABO"
        sombra = self.font_titulo.render(titulo, True, (15, 8, 8))
        txt_tit = self.font_titulo.render(titulo, True, (200, 55, 40))
        rect_tit = txt_tit.get_rect(center=(largura // 2, altura // 2 - 150))
        tela.blit(sombra, (rect_tit.x + 3, rect_tit.y + 4))
        tela.blit(txt_tit, rect_tit)

        txt_sub = self.font_sub.render(
            "Doze tentos. Seis câmaras. Uma alma em jogo.", True, (210, 200, 185)
        )
        tela.blit(txt_sub, txt_sub.get_rect(center=(largura // 2, altura // 2 - 100)))

        for btn in self.botoes:
            btn.desenhar(tela)

        if self.mensagem:
            y_msg = self.botoes[-1].rect_base.bottom + 30 if self.botoes else altura - 60
            txt_msg = self.font_mensagem.render(self.mensagem, True, (230, 120, 95))
            tela.blit(txt_msg, txt_msg.get_rect(center=(largura // 2, y_msg)))

        txt_dica = self.font_regras_txt.render(
            "↑ / ↓ escolher   ·   Enter confirmar", True, (170, 160, 145)
        )
        tela.blit(txt_dica, txt_dica.get_rect(center=(largura // 2, altura - 24)))

        if self.exibindo_regras:
            self._desenhar_modal_regras(tela)
        elif self.confirmando_novo_jogo:
            self._desenhar_modal_confirmacao(tela)

    def _desenhar_overlay(self, tela: pygame.Surface) -> None:
        overlay = pygame.Surface(
            (self.manager.largura, self.manager.altura), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 190))
        tela.blit(overlay, (0, 0))

    def _desenhar_moldura(self, tela: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(tela, (25, 22, 18), rect, border_radius=10)
        pygame.draw.rect(tela, (165, 135, 75), rect, width=2, border_radius=10)

    def _desenhar_modal_confirmacao(self, tela: pygame.Surface) -> None:
        """Pergunta antes de sobrescrever o save (Enter = sim, Esc = não)."""
        self._desenhar_overlay(tela)
        largura_m, altura_m = min(480, self.manager.largura - 40), 190
        rect = pygame.Rect(
            (self.manager.largura - largura_m) // 2,
            self.manager.altura // 2 - 100,
            largura_m,
            altura_m,
        )
        self._desenhar_moldura(tela, rect)

        tit = self.font_regras_tit.render("Começar um novo jogo?", True, (235, 195, 95))
        tela.blit(tit, tit.get_rect(center=(rect.centerx, rect.y + 38)))
        txt = self.font_regras_txt.render(
            "O jogo salvo será apagado.", True, (225, 215, 200)
        )
        tela.blit(txt, txt.get_rect(center=(rect.centerx, rect.y + 76)))

        for btn in self.botoes_confirmacao:
            btn.desenhar(tela)

    def _desenhar_modal_regras(self, tela: pygame.Surface) -> None:
        self._desenhar_overlay(tela)

        largura_m, altura_m = min(740, self.manager.largura - 40), 500
        x = (self.manager.largura - largura_m) // 2
        y = (self.manager.altura - altura_m) // 2
        self._desenhar_moldura(tela, pygame.Rect(x, y, largura_m, altura_m))

        tit = self.font_regras_tit.render(
            "REGRAS DO TRUCO CONTRA O DIABO", True, (235, 195, 95)
        )
        tela.blit(tit, tit.get_rect(center=(x + largura_m // 2, y + 30)))

        linhas = [
            "• Três fases: 1 — O Convite, 2 — O Blefe e 3 — A Leitura.",
            "• Cada fase é uma partida de 12 tentos contra O Diabo.",
            "• Um só revólver de 6 câmaras: cada puxada avança uma câmara.",
            "• Perdeu a mão: atira em si mesmo (1 puxada, ou o valor do truco aceito).",
            "• Recusou aposta: 1 puxada em si mesmo. Ir ao baralho: o valor do truco.",
            "• Envido aceito: o vencedor atira no outro (Falta Envido: até a bala sair).",
            "• Flor: 3 puxadas no oponente.",
            "• Bala no Diabo ou 12 tentos seus: fase vencida. Bala em você: morte.",
            "• Se O Diabo chegar a 12 tentos, vem um tiro final que não falha.",
            "• Manilhas: Espadilha > Bastilha > 7 de Espadas > 7 de Ouros.",
            "• Comuns: 3 > 2 > 1 (Copas/Ouros) > 12 > 11 > 10 > 7 > 6 > 5 > 4.",
            "• Melhor de 3 vazas. O jogo salva sozinho; na morte, o save é apagado.",
            "",
            "[ Clique ou aperte qualquer tecla para fechar ]",
        ]

        curr_y = y + 66
        for linha in linhas:
            cor = (235, 195, 95) if linha.startswith("[") else (225, 215, 200)
            txt = self.font_regras_txt.render(linha, True, cor)
            tela.blit(txt, (x + 35, curr_y))
            curr_y += 29


# ========================================================
# ESTADO: PARTIDA (MESA ORGÂNICA E FLUIDA)
# ========================================================
class ModoPartida(Enum):
    """Modo interno do PartidaState (design §4.5)."""

    JOGANDO = auto()
    CARTA_EM_VOO = auto()
    ROLETA = auto()
    PAUSA = auto()
    ENCERRANDO = auto()


@dataclass
class VooCarta:
    """Carta lançada à vaza (R8): o sprite, quem jogou e a vaza de destino."""

    sprite: CardSprite
    jogador: Jogador
    carta: Carta
    indice_vaza: int


# Teclas de envido (R7.1) e os aumentos aceitos sobre cada aposta pendente.
# A UI restringe o que o core aceitaria, para não rebaixar a aposta (ex.: E sobre Real).
TECLAS_ENVIDO: dict[int, TipoEnvido] = {
    pygame.K_e: TipoEnvido.ENVIDO,
    pygame.K_r: TipoEnvido.REAL_ENVIDO,
    pygame.K_x: TipoEnvido.FALTA_ENVIDO,
}
AUMENTOS_ENVIDO: dict[TipoEnvido, tuple[TipoEnvido, ...]] = {
    TipoEnvido.ENVIDO: (
        TipoEnvido.ENVIDO,
        TipoEnvido.REAL_ENVIDO,
        TipoEnvido.FALTA_ENVIDO,
    ),
    TipoEnvido.REAL_ENVIDO: (TipoEnvido.FALTA_ENVIDO,),
    TipoEnvido.FALTA_ENVIDO: (),
}
TECLAS_ENTER = (pygame.K_RETURN, pygame.K_KP_ENTER)


class PartidaState(GameState):
    """
    Mesa contra O Diabo sobre a Campanha:
    - toda ação passa por _pos_acao, que coleta lotes, salva e decide o próximo passo;
    - teclado (R7) e mouse agem pelos mesmos métodos _..._humano; Esc abre a pausa (R12);
    - jogar carta lança o sprite (_lancar_carta), e a jogada só vale ao colidir com a vaza (R8);
    - lotes de tiros viram a sequência da roleta (RoletaController);
    - nas fases com limite, um timer força a decisão do humano (R10);
    - o Diabo fala num balão nos gatilhos de FalasDiabo (R6.5, R6.6);
    - fim de fase leva à introdução da próxima, à morte ou à vitória final.
    """

    TEMPO_RESPOSTA_BOT_S = 0.75
    TEMPO_ENCERRANDO_S = 1.5
    TIMER_MINIMO_RETOMADA_S = 2.0  # ao reabrir um save, nunca perde a vez na hora
    # Áudio (R11): volume relativo da música e fades do fim de fase
    VOLUME_PAUSA = 0.35
    VOLUME_ROLETA = 0.5
    FADE_MORTE_MS = 150
    FADE_ENCERRANDO_MS = 1500

    # Ângulos sutis pré-definidos para simular o descarte orgânico de cartas na mesa
    ANGULOS_VAZAS = [
        (-2.5, 3.0),  # Vaza 1: 1ª e 2ª carta
        (2.0, -3.5),  # Vaza 2
        (-3.0, 2.5),  # Vaza 3
    ]

    def __init__(self, manager: GameStateManager, campanha: Campanha):
        super().__init__(manager)
        self.hud = HUD(self.manager.largura, self.manager.altura)

        # Jogadores e partida vêm da campanha, nova ou carregada do save (design §4.5).
        self.campanha = campanha
        self.humano = campanha.humano
        self.diabo = campanha.diabo
        self.partida = campanha.partida

        self.sprites_humano: list[CardSprite] = []
        self.sprites_bot: list[CardSprite] = []

        self.botoes_acao: list[Button] = []
        self.botoes_resposta_aposta: list[Button] = []
        self.botao_proxima_mao: Optional[Button] = None

        self.timer_bot: float = 0.0
        self.bot_pensando: bool = False

        self.modo = ModoPartida.JOGANDO
        self.roleta: Optional[RoletaController] = None
        # Resultado que encerrou a fase, capturado antes de avançar a campanha.
        self.resultado_fase: Optional[ResultadoCampanha] = None
        self.tempo_encerrando: float = 0.0

        # Teclado (R7) e pausa (R12)
        self.indice_selecionado: int = 0
        self.modo_antes_pausa: ModoPartida = ModoPartida.JOGANDO
        self.botoes_pausa: list[Button] = []
        self.indice_pausa: int = 0

        # Colisão (R8): a carta em voo só vale ao colidir; depois, o pouso é só visual.
        self.voo: Optional[VooCarta] = None
        self.pouso: Optional[VooCarta] = None

        # Timer de decisão (R10): None = sem decisão do humano ou fase sem limite.
        self.timer_decisao: Optional[float] = None
        self.timer_total: float = 0.0
        self.timer_a_restaurar: Optional[float] = None  # vindo do save, usado no entrar()
        self.audio = manager.audio
        self.timer_bar = TimerBar(ao_tique=self._tocar_tique)  # acelera nos 3 s finais (R10.2)

        # Falas do Diabo (R6): só FalasDiabo vê a mão do humano, e só para o texto.
        self.falas = FalasDiabo()
        self.ritmo_falas = RitmoFalas()
        self.balao: Optional[BalaoFala] = None

        # Clima (Bloco 7): busto com expressões e luz da fase. A luz fica fixa na
        # construção, porque o _salvar avança a fase durante o encerramento.
        self.humor = HumorDiabo()
        self.diabo_sprite = DiaboSprite()
        self.iluminacao = Iluminacao(campanha.config.luz)
        # Pelo mesmo motivo, o painel da fase mostra a mesa que está na tela: a fase da
        # construção e, depois que a fase avança, o tambor que disparou (design §4.5 item 12).
        self.config_mesa = campanha.config
        self.tambor_mesa: Optional[Tambor] = None

        pygame.font.init()
        self.font_pausa = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 34, bold=True)
        self.font_dica = pygame.font.SysFont("DejaVu Sans, Arial, sans-serif", 11)
        self.font_vaza_label = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 12, bold=True
        )
        self.font_vencedor = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 11, bold=True
        )
        self.font_pensando = pygame.font.SysFont(
            "DejaVu Sans, Arial, sans-serif", 12, italic=True
        )
        self.font_encerrando = pygame.font.SysFont(
            "DejaVu Sans, Georgia, serif", 30, bold=True
        )

    def entrar(self) -> None:
        """Começa a mão se preciso; _pos_acao retoma roleta, fim de fase ou a vez do Diabo.

        O tempo restante do timer salvo é retomado na primeira decisão do humano.
        A música da fase entra com fade; vindo da intro, ela já está tocando (R11.1).
        """
        self.audio.tocar_musica_fase(self.campanha.config)
        self.timer_a_restaurar = self.campanha.timer_restante
        mao_nova = self.partida.mao_atual is None
        if mao_nova:
            self.partida.iniciar_nova_rodada()
        self._pos_acao()
        self.timer_a_restaurar = None
        if mao_nova:
            self._falar_se_jogando(GatilhoFala.INICIO_MAO, bloqueia=True)

    def sair(self) -> None:
        pass

    def redimensionar(self, largura: int, altura: int) -> None:
        self.hud.redimensionar(largura, altura)
        if self.roleta is not None:
            self.roleta.redimensionar(largura, altura)
        self.pouso = None
        if self.voo is not None:
            # A zona mudou de lugar: o voo segue da posição atual até o novo destino.
            self.voo.sprite.mover_para(self._destino_carta_na_vaza(self.voo.indice_vaza))
        self._sincronizar_sprites_cartas()
        self._atualizar_botoes()
        if self.modo == ModoPartida.PAUSA:
            self._posicionar_botoes_pausa()

    def ao_fechar(self) -> None:
        self._salvar()

    # ==========================
    # FLUXO CENTRAL
    # ==========================
    def _salvar(self) -> None:
        """Salva a campanha; resolve no mesmo frame os resultados que encerram a fase.

        Uma bala que saiu deixa o tambor num estado que não volta do save, então:
        MORTE e VITORIA_FINAL apagam o save, e VITORIA_FASE avança a fase e salva a nova.
        Assim fechar o jogo nunca desfaz uma puxada (R9.8).
        """
        c = self.campanha
        c.timer_restante = self.timer_decisao  # R9.3: tempo restante da decisão
        if self.resultado_fase is None and c.resultado != ResultadoCampanha.EM_JOGO:
            self.resultado_fase = c.resultado
            if c.resultado == ResultadoCampanha.VITORIA_FASE:
                self.tambor_mesa = replace(c.tambor, balas=list(c.tambor.balas))
                c.avancar_fase()
        if self.resultado_fase in (ResultadoCampanha.MORTE, ResultadoCampanha.VITORIA_FINAL):
            SaveManager.apagar()
            return
        SaveManager.salvar(c.para_dict())

    def _vez_do_diabo(self) -> bool:
        """True se a próxima decisão (jogar ou responder) é do Diabo."""
        p = self.partida
        if p.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO:
            return p.quem_deve_responder_truco is self.diabo
        if p.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO:
            return p.quem_deve_responder_envido is self.diabo
        return (
            p.estado_atual in (EstadoPartida.AGUARDANDO_ENVIDO, EstadoPartida.JOGANDO_VAZA)
            and p.jogador_vez is self.diabo
        )

    def _vez_do_humano(self) -> bool:
        """True se o humano pode agir na sua vez (cantar, pedir, jogar, ir ao baralho)."""
        p = self.partida
        return (
            self.modo == ModoPartida.JOGANDO
            and not self.bot_pensando
            and p.estado_atual in (EstadoPartida.AGUARDANDO_ENVIDO, EstadoPartida.JOGANDO_VAZA)
            and p.jogador_vez is self.humano
        )

    def _humano_pode_jogar_carta(self) -> bool:
        return self._vez_do_humano() and bool(self.humano.mao)

    def _aposta_pendente_humano(self) -> Optional[EstadoPartida]:
        """O estado de aposta que o humano precisa responder, ou None."""
        p = self.partida
        if self.modo != ModoPartida.JOGANDO or self.bot_pensando:
            return None
        if (
            p.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO
            and p.quem_deve_responder_truco is self.humano
        ):
            return p.estado_atual
        if (
            p.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO
            and p.quem_deve_responder_envido is self.humano
        ):
            return p.estado_atual
        return None

    def _pode_aumentar_truco(self) -> bool:
        nivel = self.partida.nivel_truco
        return nivel is not None and nivel.proximo_nivel is not None

    def _aumentos_envido(self) -> tuple[TipoEnvido, ...]:
        atual = self.partida.aposta_envido_atual
        return AUMENTOS_ENVIDO.get(atual, ()) if atual is not None else ()

    def _pos_acao(self) -> None:
        """Depois de cada ação: coleta lotes, salva e decide entre fim, roleta ou jogo (design §4.5)."""
        c = self.campanha
        # A decisão anterior acabou: o save não leva um timer velho.
        self.timer_decisao = None
        self.ritmo_falas.parar()
        c.coletar_lotes()
        if self.partida.estado_atual == EstadoPartida.FIM_DE_JOGO:
            c.verificar_fim_por_tentos()
        self._sincronizar_sprites_cartas()
        self._salvar()

        if self.resultado_fase is not None:
            self._encerrar_fase()
        elif c.proximo_lote() is not None:
            self._iniciar_roleta()
        else:
            self.modo = ModoPartida.JOGANDO
            self._atualizar_botoes()
            if self._vez_do_diabo():
                self._iniciar_pensamento_bot()
            else:
                self._iniciar_decisao_humano()

    def _decisao_do_humano(self) -> bool:
        """Jogar carta ou responder aposta (R10.1); "Próxima mão" não conta."""
        return self._vez_do_humano() or self._aposta_pendente_humano() is not None

    def _iniciar_decisao_humano(self) -> None:
        """Começa o timer (cheio, ou o restante do save) e o ritmo de falas da fase 3."""
        restaurar, self.timer_a_restaurar = self.timer_a_restaurar, None
        config = self.campanha.config
        if not self._decisao_do_humano():
            return
        if config.tempo_decisao_s is not None:
            self.timer_total = config.tempo_decisao_s
            self.timer_decisao = config.tempo_decisao_s
            if restaurar is not None:
                self.timer_decisao = max(
                    self.TIMER_MINIMO_RETOMADA_S, min(restaurar, self.timer_total)
                )
            self.timer_bar.reiniciar()
        if RitmoFalas.ativo_na_fase(config):
            self.ritmo_falas.iniciar_decisao()

    def _atualizar_timer(self, dt: float) -> None:
        """Só roda em JOGANDO; para durante a digitação de uma fala bloqueante (R10.5)."""
        if self.timer_decisao is None or self.bot_pensando:
            return
        if self.balao is not None and self.balao.bloqueando:
            return
        if self.ritmo_falas.avancar(dt, self.balao is not None):
            self._falar(GatilhoFala.TURNO_JOGADOR)
        self.timer_decisao -= dt
        self.timer_bar.atualizar(dt, self.timer_decisao)
        if self.timer_decisao <= 0:
            self._estourar_timer()

    def _estourar_timer(self) -> None:
        """Tempo esgotado: "Não quero" com aposta pendente, senão a carta mais fraca (R10.3–4)."""
        self.timer_decisao = None
        self.ritmo_falas.parar()
        if self._aposta_pendente_humano() is not None:
            self._responder_aposta_humano(RespostaAposta.NAO_QUERO)
        elif self._humano_pode_jogar_carta():
            carta = min(self.humano.mao, key=obter_peso_carta)
            # A jogada vale na colisão, onde o _pos_acao inicia a próxima decisão.
            self._lancar_carta(self.humano, carta)

    # ==========================
    # FALAS (R6)
    # ==========================
    def _falar(self, gatilho: GatilhoFala, bloqueia: bool = False) -> None:
        """Mostra uma fala do gatilho; uma fala nova substitui a que estiver na tela.

        Também é o ponto da expressão do Diabo (o humano sobreviver a um tiro o irrita)
        e da risada: ele ri quando escapa da bala e quando o humano morre (R11.2).
        """
        if gatilho == GatilhoFala.TIRO_VAZIO_JOGADOR:
            self.humor.irritar()
        elif gatilho in (GatilhoFala.TIRO_VAZIO_DIABO, GatilhoFala.MORTE_JOGADOR):
            self.audio.efeito("risada")
        em_voo = self.voo.carta if self.voo is not None else None
        mao = [c for c in self.humano.mao if c != em_voo]
        texto = self.falas.escolher(gatilho, self.campanha.config, mao)
        if texto:
            self.balao = BalaoFala(texto, bloqueia=bloqueia)
            self.ritmo_falas.registrar_fala()

    def _falar_se_jogando(self, gatilho: GatilhoFala, bloqueia: bool = False) -> None:
        """Fala depois de um _pos_acao, se ele não abriu a roleta (que tem as suas falas)."""
        if self.modo == ModoPartida.JOGANDO:
            self._falar(gatilho, bloqueia=bloqueia)

    def _iniciar_roleta(self) -> None:
        self.modo = ModoPartida.ROLETA
        self.bot_pensando = False
        if self.roleta is None:
            self.roleta = RoletaController(
                self.campanha,
                self._salvar,
                self.manager.largura,
                self.manager.altura,
                ao_falar=self._falar,
                ao_disparar=self._ao_disparar,
                ao_som=self.audio.efeito,
            )
        self.roleta.iniciar()

    def _ao_disparar(self, alvo: Jogador) -> None:
        """A bala saiu: o Diabo fica ferido se era ele o alvo; no humano, a música corta."""
        if alvo is self.diabo:
            self.humor.ferir()
        else:
            self.audio.parar_musica(self.FADE_MORTE_MS)  # silêncio junto com a tela preta

    def _tocar_tique(self, intensidade: float) -> None:
        self.audio.efeito("tique", intensidade)

    def _ajustar_volume_musica(self) -> None:
        """Música mais baixa na pausa e na roleta (antes da bala); normal no resto."""
        if self.modo == ModoPartida.PAUSA:
            fator = self.VOLUME_PAUSA
        elif self.modo == ModoPartida.ROLETA:
            fator = self.VOLUME_ROLETA
        else:
            fator = 1.0
        if self.modo != ModoPartida.ENCERRANDO:
            self.audio.abaixar_musica(fator)

    def _expressao_diabo(self) -> Expressao:
        """Expressão do busto: ferido > irritado > falando > calmo (core/clima.py)."""
        falando = self.balao is not None and self.balao.digitando
        r = self.roleta
        modo = self.modo_antes_pausa if self.modo == ModoPartida.PAUSA else self.modo
        # Contrariado: num lote em que ele é o alvo, ou perdendo a mesa por tentos.
        contrariado = (
            modo == ModoPartida.ROLETA
            and r is not None
            and r.lote is not None
            and r.lote.alvo is self.diabo
        ) or (
            modo == ModoPartida.ENCERRANDO
            and self.resultado_fase not in (None, ResultadoCampanha.MORTE)
            and not (r is not None and r.disparou)
        )
        return self.humor.expressao(falando, contrariado)

    @property
    def layout(self) -> LayoutMesa:
        return layout_mesa(self.manager.largura, self.manager.altura)

    def _encerrar_fase(self) -> None:
        """Pausa curta na mesa e troca para Morte, Intro da próxima fase ou Vitória final."""
        self.modo = ModoPartida.ENCERRANDO
        self.bot_pensando = False
        self.tempo_encerrando = self.TEMPO_ENCERRANDO_S
        # A faixa some durante o encerramento; a intro seguinte traz a da nova fase.
        self.audio.parar_musica(
            self.FADE_MORTE_MS
            if self.resultado_fase == ResultadoCampanha.MORTE
            else self.FADE_ENCERRANDO_MS
        )
        self._falar(
            GatilhoFala.MORTE_JOGADOR
            if self.resultado_fase == ResultadoCampanha.MORTE
            else GatilhoFala.MORTE_DIABO
        )

    def _trocar_para_tela_final(self) -> None:
        from game.telas import IntroFaseState, MorteState, VitoriaFinalState

        if self.resultado_fase == ResultadoCampanha.MORTE:
            self.manager.mudar_estado(MorteState(self.manager))
        elif self.resultado_fase == ResultadoCampanha.VITORIA_FINAL:
            self.manager.mudar_estado(VitoriaFinalState(self.manager))
        else:
            self.manager.mudar_estado(IntroFaseState(self.manager, self.campanha))

    def _sincronizar_sprites_cartas(self) -> None:
        self.sprites_humano.clear()
        self.sprites_bot.clear()
        # A carta em voo ainda está na mão (só sai ao colidir), mas é desenhada à parte.
        em_voo = self.voo.carta if self.voo is not None else None
        mao_bot = [c for c in self.diabo.mao if c != em_voo]
        mao_humano = [c for c in self.humano.mao if c != em_voo]

        # 1. Cartas do Diabo: na mesa, à direita do busto (game/layout.py).
        # O voo dele sai do centro de cada uma (R8.4).
        layout = self.layout
        w_bot, h_bot = layout.carta_diabo_w, layout.carta_diabo_h
        y_bot = layout.cartas_diabo_y

        for i, carta in enumerate(mao_bot):
            x = layout.x_carta_diabo(i)
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
        total_humano = len(mao_humano)
        w_h = 105
        espaco_h = 18
        largura_total_h = total_humano * w_h + max(0, total_humano - 1) * espaco_h
        inicio_x_h = (self.manager.largura - largura_total_h) // 2
        y_humano = self.manager.altura - 175
        # A seleção fica dentro da mão, que encolhe a cada carta jogada (R7.1).
        self.indice_selecionado = max(0, min(self.indice_selecionado, total_humano - 1))

        for i, carta in enumerate(mao_humano):
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
        self._aplicar_selecao()

    def _aplicar_selecao(self) -> None:
        """Marca a carta selecionada; a seleção só aparece quando o humano pode jogar."""
        pode_jogar = self._humano_pode_jogar_carta()
        pos_mouse = pygame.mouse.get_pos()
        for i, sprite in enumerate(self.sprites_humano):
            sprite.selecionada = pode_jogar and i == self.indice_selecionado
            # Com a seleção ativa, o hover só move a seleção (um destaque por vez).
            sprite.atualizar(pos_mouse, usar_hover=not pode_jogar)

    def _mover_selecao(self, passo: int) -> None:
        total = len(self.humano.mao)
        if total:
            self.indice_selecionado = (self.indice_selecionado + passo) % total
            self._aplicar_selecao()

    def _jogar_carta_selecionada(self) -> None:
        if 0 <= self.indice_selecionado < len(self.humano.mao):
            self._jogar_carta_humano(self.humano.mao[self.indice_selecionado])

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
                texto="Próxima Mão [Enter]",
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
                btn_w = 140
                espaco = 14
                eh_truco = self.partida.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO
                botoes = [
                    Button(
                        rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                        texto="Quero [Q]",
                        callback=lambda: self._responder_aposta_humano(
                            RespostaAposta.QUERO
                        ),
                        cor_padrao=(45, 90, 55),
                        cor_borda=(85, 140, 95),
                        tamanho_fonte=15,
                    ),
                    Button(
                        rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                        texto="Não Quero [N]",
                        callback=lambda: self._responder_aposta_humano(
                            RespostaAposta.NAO_QUERO
                        ),
                        cor_padrao=Button.COR_TRUCO_BG,
                        cor_borda=Button.COR_TRUCO_BORDA,
                        tamanho_fonte=15,
                    ),
                ]
                # "Aumentar" só existe se houver um próximo nível (no topo, viraria Quero).
                pode_aumentar = (
                    self._pode_aumentar_truco() if eh_truco else bool(self._aumentos_envido())
                )
                if pode_aumentar:
                    botoes.append(
                        Button(
                            rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                            texto="Aumentar [T]" if eh_truco else "Aumentar [E/R/X]",
                            callback=lambda: self._responder_aposta_humano(
                                RespostaAposta.AUMENTAR
                            ),
                            cor_padrao=(180, 140, 50),
                            cor_borda=(220, 180, 80),
                            tamanho_fonte=15,
                        )
                    )
                self.botoes_resposta_aposta = self._distribuir_botoes(botoes, espaco)
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
                    texto=f"{prox_truco} [T]",
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
                    texto="FLOR [F]",
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
                    texto="ENVIDO [E]",
                    callback=lambda: self._cantar_envido_humano(TipoEnvido.ENVIDO),
                    cor_padrao=Button.COR_ENVIDO_BG,
                    cor_borda=Button.COR_ENVIDO_BORDA,
                    tamanho_fonte=14,
                )
            )
            botoes.append(
                Button(
                    rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                    texto="REAL ENVIDO [R]",
                    callback=lambda: self._cantar_envido_humano(TipoEnvido.REAL_ENVIDO),
                    cor_padrao=Button.COR_ENVIDO_BG,
                    cor_borda=Button.COR_ENVIDO_BORDA,
                    tamanho_fonte=13,
                )
            )
            botoes.append(
                Button(
                    rect=pygame.Rect(0, y_botoes, btn_w, btn_h),
                    texto="FALTA ENVIDO [X]",
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
                texto="Ao Baralho [B]",
                callback=self._ir_ao_baralho_humano,
                cor_padrao=Button.COR_PADRAO_BG,
                cor_borda=Button.COR_PADRAO_BORDA,
                tamanho_fonte=14,
            )
        )

        # Fora da vez do humano a barra fica visível, mas desativada (R7.2).
        p = self.partida
        vez_humano = p.jogador_vez is self.humano and p.estado_atual in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        )
        for btn in botoes:
            btn.ativo = vez_humano
        self.botoes_acao = self._distribuir_botoes(botoes, espaco)

    def _distribuir_botoes(self, botoes: list[Button], espaco: int) -> list[Button]:
        """Centraliza a fileira; encolhe as larguras se não couber na tela (margem de 20 px)."""
        if not botoes:
            return botoes
        disponivel = self.manager.largura - 40 - espaco * (len(botoes) - 1)
        soma = sum(b.rect.width for b in botoes)
        fator = min(1.0, disponivel / soma)
        larguras = [int(b.rect.width * fator) for b in botoes]
        total_w = sum(larguras) + espaco * (len(botoes) - 1)

        curr_x = (self.manager.largura - total_w) // 2
        for btn, w in zip(botoes, larguras):
            btn.definir_rect(pygame.Rect(curr_x, btn.rect.y, w, btn.rect.height))
            curr_x += w + espaco
        return botoes

    def _pedir_truco_humano(self) -> None:
        if self.partida.pedir_truco(self.humano):
            self._pos_acao()

    def _cantar_flor_humano(self) -> None:
        if self.partida.cantar_flor(self.humano):
            self._pos_acao()

    def _cantar_envido_humano(self, tipo: TipoEnvido) -> None:
        if self.partida.cantar_envido(self.humano, tipo):
            self._pos_acao()

    def _ir_ao_baralho_humano(self) -> None:
        if self.partida.estado_atual not in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        ):
            return
        self.partida.ir_ao_baralho(self.humano)
        self._pos_acao()

    def _responder_aposta_humano(self, resposta: RespostaAposta) -> None:
        if self.partida.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO:
            self.partida.responder_truco(resposta, self.humano)
        elif self.partida.estado_atual == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO:
            self.partida.responder_envido(resposta)
        else:
            return
        self._pos_acao()

    def _aumentar_envido_humano(self, tipo: TipoEnvido) -> None:
        """E/R/X com envido pendente: aumenta para o tipo escolhido (design §4.5 item 3)."""
        if tipo not in self._aumentos_envido():
            return
        self.partida.responder_envido(RespostaAposta.AUMENTAR, aumento=tipo)
        self._pos_acao()

    def _jogar_carta_humano(self, carta: Carta) -> None:
        """Clique ou Enter na carta: lança o sprite; a jogada vale na colisão (R8)."""
        self._lancar_carta(self.humano, carta)

    # ==========================
    # VOO E COLISÃO (R8)
    # ==========================
    def _lancar_carta(self, jogador: Jogador, carta: Carta) -> bool:
        """Põe a carta em voo até a vaza atual; partida.jogar_carta só roda na colisão.

        Valida a jogada antes (modo, vez, estado e carta na mão), para que clique, Enter,
        o Diabo e o timeout do Bloco 6 usem o mesmo caminho. Retorna True se lançou.
        """
        p = self.partida
        if (
            self.modo != ModoPartida.JOGANDO
            or self.voo is not None
            or p.mao_atual is None
            or p.jogador_vez is not jogador
            or p.estado_atual
            not in (EstadoPartida.AGUARDANDO_ENVIDO, EstadoPartida.JOGANDO_VAZA)
            or carta not in jogador.mao
        ):
            return False

        self.pouso = None  # um pouso anterior termina na hora
        indice_vaza = p.mao_atual.indice_vaza_atual
        if jogador is self.humano:
            sprite = self._retirar_sprite(self.sprites_humano, carta)
            if sprite is None:
                sprite = CardSprite(carta, 0, 0, self.manager.asset_manager)
            sprite.selecionada = False
            sprite.interativa = False
            sprite.destacada = False
            sprite.atualizar_posicao_rect()
        else:
            # Sai do topo: a carta pequena (68×100) vira um sprite virado de tamanho cheio,
            # centrado na origem; ela só abre quando a jogada vale (colisão).
            origem = self._retirar_sprite(self.sprites_bot, carta)
            centro = origem.rect.center if origem else (self.manager.largura // 2, 0)
            sprite = CardSprite(
                carta, 0, 0, self.manager.asset_manager, aberta=False, interativa=False
            )
            sprite.rect.center = centro
            sprite.pos_x_base, sprite.pos_y_base = sprite.rect.topleft

        sprite.mover_para(self._destino_carta_na_vaza(indice_vaza))
        self.voo = VooCarta(sprite, jogador, carta, indice_vaza)
        self.modo = ModoPartida.CARTA_EM_VOO
        self.bot_pensando = False
        for btn in self.botoes_acao:
            btn.ativo = False
        return True

    @staticmethod
    def _retirar_sprite(sprites: list[CardSprite], carta: Carta) -> Optional[CardSprite]:
        """Tira da lista o sprite da carta, sem redistribuir as outras."""
        for i, sprite in enumerate(sprites):
            if sprite.carta == carta:
                return sprites.pop(i)
        return None

    def _atualizar_voo(self, dt: float) -> None:
        """Move a carta em voo e efetiva a jogada quando ela colide com a zona da vaza."""
        voo = self.voo
        if voo is None:
            self.modo = ModoPartida.JOGANDO
            return
        voo.sprite.atualizar_movimento(dt)
        if voo.sprite.rect.colliderect(self._rect_zona_vaza(voo.indice_vaza)):
            self._efetivar_voo()

    def _efetivar_voo(self) -> None:
        """Colisão: joga a carta no core; o sprite segue até o monte como pouso visual."""
        voo = self.voo
        self.voo = None
        self.modo = ModoPartida.JOGANDO
        if voo is None:
            return
        voo.sprite.set_aberta(True)
        self.audio.efeito("carta")  # a carta bate na mesa (R11.2)
        if self.partida.jogar_carta(voo.jogador, voo.carta) and voo.sprite.em_movimento:
            self.pouso = voo
        self._pos_acao()

    def _geometria_vazas(self) -> tuple[list[int], int, int, int]:
        """Centros x das 3 vazas, o y central e o tamanho da carta na mesa (game/layout.py)."""
        layout = self.layout
        return (
            list(layout.pontos_x_vazas),
            layout.y_centro_vazas,
            layout.carta_vaza_w,
            layout.carta_vaza_h,
        )

    def _rect_zona_vaza(self, i: int) -> pygame.Rect:
        """Slot 105×155 da vaza i: desenho do placeholder e zona de colisão (R8.2)."""
        pontos_x, y_centro, w, h = self._geometria_vazas()
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (pontos_x[i], y_centro)
        return rect

    def _centro_carta_na_vaza(self, i: int, j: int) -> tuple[int, int]:
        """Centro da j-ésima carta (0 ou 1) no monte da vaza i."""
        pontos_x, y_centro, _, _ = self._geometria_vazas()
        cx = pontos_x[i]
        return (cx - 18, y_centro - 10) if j == 0 else (cx + 18, y_centro + 10)

    def _destino_carta_na_vaza(self, i: int) -> tuple[int, int]:
        """Para onde voa a próxima carta da vaza i (1ª ou 2ª posição do monte)."""
        mao = self.partida.mao_atual
        j = len(mao.vazas[i].cartas_jogadas) if mao is not None else 0
        return self._centro_carta_na_vaza(i, min(j, 1))

    def _avancar_proxima_mao(self) -> None:
        if self.partida.estado_atual != EstadoPartida.FIM_DA_MAO:
            return
        self.partida.iniciar_nova_rodada()
        self.indice_selecionado = 0
        self.pouso = None
        self._pos_acao()  # salva o início da mão (R9.2)
        self._falar_se_jogando(GatilhoFala.INICIO_MAO, bloqueia=True)

    # ==========================
    # PAUSA (R12)
    # ==========================
    def _pode_pausar(self) -> bool:
        """Pausa em JOGANDO e na roleta; não depois de uma bala nem no encerramento."""
        if self.modo == ModoPartida.JOGANDO:
            return True
        return (
            self.modo == ModoPartida.ROLETA
            and self.roleta is not None
            and not self.roleta.disparou
        )

    def _abrir_pausa(self) -> None:
        if not self._pode_pausar():
            return
        self.modo_antes_pausa = self.modo
        self.modo = ModoPartida.PAUSA
        self.indice_pausa = 0
        self._posicionar_botoes_pausa()
        self._salvar()  # ao pausar (R9.2)

    def _continuar_pausa(self) -> None:
        self.modo = self.modo_antes_pausa
        if self.modo == ModoPartida.ROLETA and self.roleta is not None:
            self.roleta.soltar_gatilho()
        self._atualizar_botoes()
        self._aplicar_selecao()

    def _salvar_e_voltar_ao_menu(self) -> None:
        self._salvar()
        self.manager.mudar_estado(MenuState(self.manager))

    def _posicionar_botoes_pausa(self) -> None:
        btn_w, btn_h, passo = 280, 46, 58
        x = (self.manager.largura - btn_w) // 2
        y = self.manager.altura // 2 - 10
        self.botoes_pausa = [
            Button(
                rect=pygame.Rect(x, y, btn_w, btn_h),
                texto="Continuar [Esc]",
                callback=self._continuar_pausa,
                cor_padrao=(45, 90, 55),
                cor_borda=(85, 140, 95),
            ),
            Button(
                rect=pygame.Rect(x, y + passo, btn_w, btn_h),
                texto="Salvar e voltar ao menu",
                callback=self._salvar_e_voltar_ao_menu,
            ),
        ]

    def _tratar_evento_pausa(self, event: pygame.event.Event) -> None:
        """↑/↓ e Enter escolhem; Esc continua; o mouse também funciona."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._continuar_pausa()
            elif event.key == pygame.K_UP:
                self.indice_pausa = (self.indice_pausa - 1) % len(self.botoes_pausa)
            elif event.key == pygame.K_DOWN:
                self.indice_pausa = (self.indice_pausa + 1) % len(self.botoes_pausa)
            elif event.key in TECLAS_ENTER:
                callback = self.botoes_pausa[self.indice_pausa].callback
                if callback:
                    callback()
            return
        if event.type == pygame.MOUSEMOTION:
            for i, btn in enumerate(self.botoes_pausa):
                if btn.rect_base.collidepoint(event.pos):
                    self.indice_pausa = i
        for btn in self.botoes_pausa:
            if btn.tratar_evento(event):
                return

    # ==========================
    # TECLADO (R7)
    # ==========================
    def _tratar_tecla(self, key: int) -> None:
        """Mapeia a tabela de R7.1; só age se a ação for válida agora (R7.2)."""
        if self.modo != ModoPartida.JOGANDO:
            return
        if key == pygame.K_ESCAPE:
            self._abrir_pausa()
            return

        p = self.partida
        if p.estado_atual == EstadoPartida.FIM_DA_MAO:
            if key in TECLAS_ENTER or key == pygame.K_SPACE:
                self._avancar_proxima_mao()
            return

        pendente = self._aposta_pendente_humano()
        if pendente is not None:
            if key == pygame.K_q:
                self._responder_aposta_humano(RespostaAposta.QUERO)
            elif key == pygame.K_n:
                self._responder_aposta_humano(RespostaAposta.NAO_QUERO)
            elif key == pygame.K_t and pendente == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO:
                if self._pode_aumentar_truco():
                    self._responder_aposta_humano(RespostaAposta.AUMENTAR)
            elif key in TECLAS_ENVIDO and pendente == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO:
                self._aumentar_envido_humano(TECLAS_ENVIDO[key])
            return

        if not self._vez_do_humano():
            return
        if key == pygame.K_LEFT:
            self._mover_selecao(-1)
        elif key == pygame.K_RIGHT:
            self._mover_selecao(1)
        elif key in TECLAS_ENTER:
            if self._humano_pode_jogar_carta():
                self._jogar_carta_selecionada()
        elif key == pygame.K_t:
            if p.pode_pedir_truco(self.humano):
                self._pedir_truco_humano()
        elif key in TECLAS_ENVIDO:
            if p.pode_cantar_envido(self.humano):
                self._cantar_envido_humano(TECLAS_ENVIDO[key])
        elif key == pygame.K_f:
            if p.pode_cantar_flor(self.humano):
                self._cantar_flor_humano()
        elif key == pygame.K_b:
            self._ir_ao_baralho_humano()

    def _iniciar_pensamento_bot(self) -> None:
        self.bot_pensando = True
        self.timer_bot = self.TEMPO_RESPOSTA_BOT_S

    def _executar_turno_bot(self) -> None:
        self.bot_pensando = False
        estado = self.partida.estado_atual

        if (
            estado == EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO
            and self.partida.quem_deve_responder_truco == self.diabo
        ):
            estado_mesa = self.partida.obter_estado_mesa_para_jogador(self.diabo)
            resposta = self.diabo.responder_aposta(self.partida.nivel_truco, estado_mesa)
            self.partida.responder_truco(resposta, self.diabo)
            self._pos_acao()
            if resposta == RespostaAposta.AUMENTAR:
                self._falar_se_jogando(GatilhoFala.PEDE_TRUCO, bloqueia=True)
            return

        if (
            estado == EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO
            and self.partida.quem_deve_responder_envido == self.diabo
        ):
            estado_mesa = self.partida.obter_estado_mesa_para_jogador(self.diabo)
            resposta = self.diabo.responder_aposta(
                self.partida.aposta_envido_atual, estado_mesa
            )
            self.partida.responder_envido(resposta)
            self._pos_acao()
            if resposta == RespostaAposta.AUMENTAR:
                self._falar_se_jogando(GatilhoFala.CANTA_ENVIDO, bloqueia=True)
            return

        if self.partida.jogador_vez == self.diabo and estado in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        ):
            # 1. Se o Diabo tem Flor e pode cantar Flor, canta Flor!
            if self.partida.pode_cantar_flor(self.diabo):
                self.partida.cantar_flor(self.diabo)
                self._pos_acao()
                return

            # 2. Se pode cantar Envido e tem mão forte (>= 29 pts), canta Envido!
            if (
                self.partida.pode_cantar_envido(self.diabo)
                and self.diabo.pontos_envido >= 29
                and not self.partida.envido_disputado
            ):
                self.partida.cantar_envido(self.diabo, TipoEnvido.ENVIDO)
                self._pos_acao()
                self._falar_se_jogando(GatilhoFala.CANTA_ENVIDO, bloqueia=True)
                return

            if self.partida.pode_pedir_truco(self.diabo) and self.diabo.quer_pedir_truco(
                self.partida.nivel_truco
            ):
                self.partida.pedir_truco(self.diabo)
                self._pos_acao()
                self._falar_se_jogando(GatilhoFala.PEDE_TRUCO, bloqueia=True)
                return

            if self.diabo.mao:
                estado_mesa = self.partida.obter_estado_mesa_para_jogador(self.diabo)
                carta_escolhida = self.diabo.decidir_jogada(estado_mesa)
                # Mesmo fluxo do humano: voa do topo e só vale ao colidir (R8.4).
                self._lancar_carta(self.diabo, carta_escolhida)

    def tratar_evento(self, event: pygame.event.Event) -> None:
        if self.modo == ModoPartida.PAUSA:
            self._tratar_evento_pausa(event)
            return
        # Durante a roleta só contam o Espaço do gatilho e o Esc; no encerramento, nada.
        if self.modo == ModoPartida.ROLETA:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._abrir_pausa()
            elif self.roleta is not None:
                self.roleta.tratar_evento(event)
            return
        if self.modo != ModoPartida.JOGANDO:
            return

        if event.type == pygame.KEYDOWN:
            self._tratar_tecla(event.key)
            return

        # O mouse sobre uma carta move a seleção, como no menu.
        if event.type == pygame.MOUSEMOTION and self._humano_pode_jogar_carta():
            for i, sprite in enumerate(self.sprites_humano):
                if sprite.contem_ponto_base(event.pos):
                    self.indice_selecionado = i

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
            if self._humano_pode_jogar_carta():
                pos_mouse = event.pos
                for sprite in self.sprites_humano:
                    if sprite.verificar_clique(pos_mouse):
                        self._jogar_carta_humano(sprite.carta)
                        break

    def atualizar(self, dt: float) -> None:
        self._ajustar_volume_musica()
        if self.modo == ModoPartida.PAUSA:
            # Tudo congela (IA, roleta, timer e balão); só o destaque acompanha.
            for i, btn in enumerate(self.botoes_pausa):
                btn.hover = i == self.indice_pausa
                btn.rect.y = btn.rect_base.y - (3 if btn.hover else 0)
            return

        # O pouso é só visual (a jogada já valeu) e termina em qualquer modo.
        if self.pouso is not None and not self.pouso.sprite.atualizar_movimento(dt):
            self.pouso = None

        # Clima: luz, busto e humor do Diabo também congelam só na pausa.
        self.iluminacao.atualizar(dt)
        self.diabo_sprite.atualizar(dt)
        self.humor.avancar(dt)

        # O balão corre em qualquer modo menos a pausa; o timer só em JOGANDO (abaixo).
        if self.balao is not None:
            self.balao.atualizar(dt)
            if self.balao.terminou:
                self.balao = None

        if self.modo == ModoPartida.CARTA_EM_VOO:
            self._atualizar_voo(dt)  # entradas ficam ignoradas em tratar_evento (R8.3)
            return

        if self.modo == ModoPartida.ENCERRANDO:
            if self.roleta is not None:
                self.roleta.atualizar(dt)  # deixa a animação do tiro terminar
            self.tempo_encerrando -= dt
            if self.tempo_encerrando <= 0:
                self._trocar_para_tela_final()
            return

        if self.modo == ModoPartida.ROLETA and self.roleta is not None:
            self.roleta.atualizar(dt)
            if self.roleta.terminou_fase:
                self._encerrar_fase()
            elif self.roleta.concluido:
                self._pos_acao()  # volta ao jogo de onde parou
            return

        pos_mouse = pygame.mouse.get_pos()
        self._aplicar_selecao()

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
            return

        self._atualizar_timer(dt)  # depois dos ramos de PAUSA, voo, encerramento e roleta

    def desenhar(self, tela: pygame.Surface) -> None:
        """Ordem do design §5 (Bloco 7): cena → luz → HUD/botões → timer → roleta → balão → pausa."""
        layout = self.layout
        mesa = self.manager.asset_manager.obter_mesa_feltro(
            self.manager.largura, self.manager.altura
        )
        tela.blit(mesa, (0, 0))

        # Busto do Diabo no topo, atrás das cartas dele (R1.1)
        expressao = self._expressao_diabo()
        self.diabo_sprite.desenhar(tela, layout.busto(), expressao)

        # Cartas do Diabo, à direita do busto
        for s in self.sprites_bot:
            s.desenhar(tela)

        # Centro da mesa (Arenas fluidas sem caixas pesadas)
        self._desenhar_centro_organico(tela)

        # Cartas do Jogador (ancoradas na base)
        for s in self.sprites_humano:
            s.desenhar(tela)

        # Carta em voo ou pousando
        for v in (self.pouso, self.voo):
            if v is not None:
                v.sprite.desenhar(tela)

        # Luz baixa (R1.2) antes do HUD, para os textos continuarem legíveis;
        # os olhos do Diabo brilham por cima da vinheta.
        self.iluminacao.desenhar(tela, (layout.largura // 2, layout.y_centro_vazas))
        self.diabo_sprite.desenhar_brilho(tela, layout.busto(), expressao)

        # HUD com placares, fase, tambor, aposta e mensagem
        self.hud.desenhar(
            tela, self.partida, self.campanha, config=self.config_mesa, tambor=self.tambor_mesa
        )

        # Botões de ação (com o jogo correndo; no voo ficam visíveis e desativados)
        if self.modo in (ModoPartida.JOGANDO, ModoPartida.CARTA_EM_VOO):
            if self.botao_proxima_mao:
                self.botao_proxima_mao.desenhar(tela)
            for btn in self.botoes_resposta_aposta:
                btn.desenhar(tela)
            for btn in self.botoes_acao:
                btn.desenhar(tela)
            if self._humano_pode_jogar_carta():
                self._desenhar_dica_teclado(tela)

        if self.bot_pensando:
            self._desenhar_aviso_bot_pensando(tela)

        # Timer de decisão à direita da mão (R10.2)
        if self.timer_decisao is not None and self.modo != ModoPartida.ENCERRANDO:
            self._desenhar_timer(tela)

        # Overlay da roleta (inclui o flash e a tela preta do disparo)
        em_roleta = self.modo == ModoPartida.ROLETA or (
            self.modo == ModoPartida.PAUSA and self.modo_antes_pausa == ModoPartida.ROLETA
        )
        if self.roleta is not None and (
            em_roleta or (self.modo == ModoPartida.ENCERRANDO and self.roleta.disparou)
        ):
            self.roleta.desenhar(tela, sobre_escuro=self._desenhar_busto_ferido)
        elif self.modo == ModoPartida.ENCERRANDO:
            self._desenhar_encerramento(tela)

        # O balão fica acima da roleta e do encerramento, e abaixo da pausa (design §5).
        if self.balao is not None:
            self._desenhar_balao(tela)

        if self.modo == ModoPartida.PAUSA:
            self._desenhar_pausa(tela)
        else:
            self._aplicar_tremida(tela)

    def _desenhar_busto_ferido(self, tela: pygame.Surface) -> None:
        """Bala no Diabo (7.5): o busto ferido sobre a mesa escurecida, sumindo junto."""
        if self.roleta is None:
            return
        # O busto some um pouco mais devagar que a mesa escurece.
        alfa = 255 - int((self.roleta.alfa_escuro_disparo() - 190) / 65 * 200)
        busto = self.layout.busto()
        self.diabo_sprite.desenhar(tela, busto, Expressao.FERIDO, alfa)
        self.diabo_sprite.desenhar_brilho(tela, busto, Expressao.FERIDO, alfa)

    def _aplicar_tremida(self, tela: pygame.Surface) -> None:
        """Tremida do tiro (7.5): desloca o quadro pronto; nenhum rect lógico muda."""
        if self.roleta is None or self.modo not in (ModoPartida.ROLETA, ModoPartida.ENCERRANDO):
            return
        dx, dy = self.roleta.deslocamento_tremida
        if dx or dy:
            quadro = tela.copy()
            tela.fill((0, 0, 0))
            tela.blit(quadro, (dx, dy))

    def _rect_timer(self) -> pygame.Rect:
        """À direita da mão; em 800×600 a mão de 3 cartas termina em x ≈ 575."""
        return pygame.Rect(self.manager.largura - 210, self.manager.altura - 110, 180, 12)

    def _desenhar_timer(self, tela: pygame.Surface) -> None:
        self.timer_bar.desenhar(tela, self._rect_timer(), self.timer_decisao, self.timer_total)

    def _desenhar_balao(self, tela: pygame.Surface) -> None:
        """Coluna esquerda, sob o painel da fase, com o rabicho na boca do busto.

        No encerramento, centralizado (sobre a tela preta do disparo ou o overlay).
        """
        largura, altura = self.manager.largura, self.manager.altura
        if self.modo == ModoPartida.ENCERRANDO:
            self.balao.desenhar(
                tela, (largura // 2, int(altura * 0.6)), min(420, largura - 40), centralizar=True
            )
            return
        pos, largura_max = self.layout.balao()
        self.balao.desenhar(tela, pos, largura_max, ponta=self.layout.boca_diabo())

    def _desenhar_dica_teclado(self, tela: pygame.Surface) -> None:
        """Linha discreta no rodapé com as teclas da mão (útil para o vídeo)."""
        txt = self.font_dica.render(
            "← / → escolher carta   ·   Enter jogar   ·   Esc pausa", True, (200, 190, 170)
        )
        tela.blit(
            txt, txt.get_rect(center=(self.manager.largura // 2, self.manager.altura - 9))
        )

    def _desenhar_pausa(self, tela: pygame.Surface) -> None:
        overlay = pygame.Surface((self.manager.largura, self.manager.altura), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        tela.blit(overlay, (0, 0))
        txt = self.font_pausa.render("PAUSA", True, (230, 195, 95))
        tela.blit(
            txt,
            txt.get_rect(center=(self.manager.largura // 2, self.manager.altura // 2 - 70)),
        )
        for btn in self.botoes_pausa:
            btn.desenhar(tela)

    def _desenhar_encerramento(self, tela: pygame.Surface) -> None:
        """Fim por tentos: escurece a mesa com o resultado da fase."""
        overlay = pygame.Surface((self.manager.largura, self.manager.altura), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        tela.blit(overlay, (0, 0))
        texto = (
            "Você morreu."
            if self.resultado_fase == ResultadoCampanha.MORTE
            else "O Diabo perdeu a mesa."
        )
        txt = self.font_encerrando.render(texto, True, (230, 195, 95))
        tela.blit(
            txt,
            txt.get_rect(center=(self.manager.largura // 2, self.manager.altura // 2)),
        )

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

        # Mesma geometria da zona de colisão (_rect_zona_vaza): 3 vazas com cartas 105×155.
        pontos_x, y_centro, w_carta, h_carta = self._geometria_vazas()

        for i, vaza in enumerate(self.partida.mao_atual.vazas):
            cx = pontos_x[i]
            eh_vaza_atual = i == self.partida.mao_atual.indice_vaza_atual
            vaza_concluida = len(vaza.cartas_jogadas) == 2

            # 1. Rótulo acima do slot; numa vaza concluída vira "1ª" + a etiqueta do
            # vencedor na mesma linha (embaixo, ela cobria a barra de ações em 800×600).
            y_rotulo = self.layout.y_rotulo_vaza
            cor_label = (241, 196, 15) if eh_vaza_atual else (222, 211, 189)
            texto_label = f"{i + 1}ª" if vaza_concluida else f"{i + 1}ª VAZA"
            sombra_label = self.font_vaza_label.render(texto_label, True, (15, 25, 20))
            txt_vaza = self.font_vaza_label.render(texto_label, True, cor_label)
            rect_label = txt_vaza.get_rect(center=(cx, y_rotulo))
            if vaza_concluida:
                w_tag = self._largura_tag_resultado_vaza(vaza)
                total = rect_label.width + 6 + w_tag
                # O bloco fica entre as colunas das placas (em 800 px encostaria nelas).
                x0, x1 = self.layout.faixa_central_x()
                rect_label.left = max(x0, min(cx - total // 2, x1 - total))
                self._desenhar_tag_resultado_vaza(
                    tela, rect_label.right + 6 + w_tag // 2, y_rotulo, vaza
                )
            tela.blit(sombra_label, (rect_label.x + 1, rect_label.y + 2))
            tela.blit(txt_vaza, rect_label)

            # 2. Se a vaza não tiver cartas, desenha o placeholder tátil nítido
            if not vaza.cartas_jogadas:
                rect_slot = self._rect_zona_vaza(i)

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
                eh_primeira = j == 0
                # A carta ainda pousando é desenhada pelo próprio sprite.
                if (
                    self.pouso is not None
                    and self.pouso.indice_vaza == i
                    and self.pouso.carta == carta
                ):
                    continue

                # 1ª carta jogada fica na base (-18, -10); 2ª carta jogada cai por cima (+18, +16)
                pos_x, pos_y = self._centro_carta_na_vaza(i, j)
                angulo = angulos[0] if eh_primeira else angulos[1]

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

    def _texto_tag_resultado_vaza(self, vaza) -> tuple[tuple[int, int, int], str]:
        if vaza.empate:
            return (130, 100, 30), "= Canguçu"
        if vaza.vencedor == self.humano:
            return (40, 95, 55), "★ Você"
        return (120, 35, 30), "⚔ O Diabo"

    def _largura_tag_resultado_vaza(self, vaza) -> int:
        _, txt_msg = self._texto_tag_resultado_vaza(vaza)
        return self.font_vencedor.size(txt_msg)[0] + 18

    def _desenhar_tag_resultado_vaza(
        self, tela: pygame.Surface, cx: int, cy: int, vaza
    ) -> None:
        """Pill compacto com o vencedor da vaza, na linha do rótulo."""
        cor_bg, txt_msg = self._texto_tag_resultado_vaza(vaza)

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
        rect = self.layout.aviso_pensando()  # coluna direita, sob a placa de aposta
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, 130))
        tela.blit(s, rect.topleft)
        pygame.draw.rect(tela, (160, 130, 70), rect, width=1, border_radius=4)
        txt = self.font_pensando.render("O Diabo pensa…", True, (230, 220, 200))
        tela.blit(txt, txt.get_rect(center=rect.center))
