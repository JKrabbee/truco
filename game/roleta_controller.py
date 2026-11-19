import random
from enum import Enum, auto
from typing import Callable, Optional
import pygame
from core.campanha import Campanha
from core.falas import GatilhoFala
from core.player import Jogador
from core.roleta import LoteTiros
from game.layout import layout_mesa
from game.paths import ASSETS
from ui.revolver_sprite import RevolverSprite


class EtapaRoleta(Enum):
    DESLIZANDO = auto()
    ENGATILHANDO = auto()
    RESULTADO = auto()
    CONCLUIDO = auto()  # lotes acabaram e ninguém morreu
    FIM = auto()  # uma bala saiu: a fase terminou


class RoletaController:
    """Sequência visual dos lotes de tiros (design §4.4, R4, R7.4, R8.5, R9.8)."""

    TEMPO_GATILHO_HUMANO_S = 1.0
    TEMPO_GATILHO_DIABO_S = 1.5
    TEMPO_RESULTADO_S = 0.9
    TEMPO_FLASH_S = 0.25
    TEMPO_CLARAO_S = 0.15
    # Tremida de tela (só visual: nenhum rect de colisão muda)
    TREMIDA_DISPARO = (12.0, 0.45)  # amplitude em px, duração em s
    TREMIDA_VAZIO = (3.0, 0.12)
    # Bala no Diabo: a mesa escurece aos poucos, com o busto ferido por cima
    ALFA_ESCURO_INICIAL = 190
    TEMPO_ESCURECER_S = 2.2

    _clarao_base: Optional[pygame.Surface] = None

    def __init__(
        self,
        campanha: Campanha,
        ao_puxar: Callable[[], None],
        largura: int,
        altura: int,
        ao_falar: Optional[Callable[[GatilhoFala], None]] = None,
        ao_disparar: Optional[Callable[[Jogador], None]] = None,
        ao_som: Optional[Callable[[str], None]] = None,
    ):
        self.campanha = campanha
        self.ao_puxar = ao_puxar  # salva; chamado no mesmo frame do puxar() (R9.8)
        self.ao_falar = ao_falar  # falas do Diabo (R6.5), escolhidas pelo PartidaState
        self.ao_disparar = ao_disparar  # recebe o alvo atingido (expressão "ferido")
        self.ao_som = ao_som  # efeitos (R11.2): engatilhar, clique_vazio, disparo
        self.largura = largura
        self.altura = altura
        self.revolver = RevolverSprite(largura / 2, layout_mesa(largura, altura).y_centro_vazas)
        self.rng = random.Random()

        self.alvo_atingido: Optional[Jogador] = None
        self.tempo_desde_disparo = 0.0
        self.tremida_amplitude = 0.0
        self.tremida_duracao = 0.0
        self.tremida_restante = 0.0
        self.deslocamento_tremida: tuple[int, int] = (0, 0)

        self.etapa = EtapaRoleta.CONCLUIDO
        self.lote: Optional[LoteTiros] = None
        self.tempo_gatilho = 0.0
        self.tempo_resultado = 0.0
        self.segurando = False
        self.disparou = False

        pygame.font.init()
        self.font_titulo = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 20, bold=True)
        self.font_info = pygame.font.SysFont("DejaVu Sans, Arial, sans-serif", 14)
        self.font_clic = pygame.font.SysFont("DejaVu Sans, Georgia, serif", 46, bold=True, italic=True)

    # ==========================
    # ESTADO
    # ==========================
    @property
    def concluido(self) -> bool:
        return self.etapa == EtapaRoleta.CONCLUIDO

    @property
    def terminou_fase(self) -> bool:
        return self.etapa == EtapaRoleta.FIM

    @property
    def progresso_gatilho(self) -> float:
        """0..1, para a barra de tensão."""
        if self.etapa != EtapaRoleta.ENGATILHANDO or self.lote is None:
            return 0.0
        return min(1.0, self.tempo_gatilho / self._tempo_necessario())

    def _atirador_humano(self) -> bool:
        return self.lote is not None and self.lote.atirador is self.campanha.humano

    def _tempo_necessario(self) -> float:
        if self._atirador_humano():
            return self.TEMPO_GATILHO_HUMANO_S
        return self.TEMPO_GATILHO_DIABO_S

    # ==========================
    # GEOMETRIA
    # ==========================
    def redimensionar(self, largura: int, altura: int) -> None:
        self.largura = largura
        self.altura = altura
        if self.lote is not None:
            zona = self.zona_atirador(self.lote.atirador)
            if self.etapa == EtapaRoleta.DESLIZANDO:
                self.revolver.deslizar_para(zona)
            else:
                self.revolver.posicionar(*zona.center)
            self.revolver.apontar_para(self._ponto_alvo(self.lote.alvo))

    def zona_atirador(self, jogador: Jogador) -> pygame.Rect:
        """Faixa acima da mão do humano, ou logo abaixo do busto do Diabo (game/layout.py)."""
        layout = layout_mesa(self.largura, self.altura)
        if jogador is self.campanha.humano:
            return layout.zona_atirador_humano()
        return layout.zona_atirador_diabo()

    def _ponto_alvo(self, jogador: Jogador) -> tuple[float, float]:
        """Para onde o cano aponta: a borda de baixo (humano) ou o rosto do busto (Diabo)."""
        if jogador is self.campanha.humano:
            return (self.largura / 2, self.altura + 200)
        return layout_mesa(self.largura, self.altura).rosto_diabo()

    # ==========================
    # FLUXO
    # ==========================
    def iniciar(self) -> None:
        """Começa o lote ativo da campanha: o revólver desliza até o atirador."""
        self.lote = self.campanha.lote_atual
        if self.lote is None:
            self.etapa = EtapaRoleta.CONCLUIDO
            return
        self.etapa = EtapaRoleta.DESLIZANDO
        self.tempo_gatilho = 0.0
        self.segurando = False
        self.disparou = False
        self.alvo_atingido = None
        self.revolver.deslizar_para(self.zona_atirador(self.lote.atirador))
        self.revolver.apontar_para(self._ponto_alvo(self.lote.alvo))
        self._falar(GatilhoFala.ANTES_PUXAR)  # uma vez por lote

    def _falar(self, gatilho: GatilhoFala) -> None:
        if self.ao_falar is not None:
            self.ao_falar(gatilho)

    def _som(self, nome: str) -> None:
        if self.ao_som is not None:
            self.ao_som(nome)

    def _engatilhar(self) -> None:
        """Cada puxada começa com o cão armado (som de giro/engatilhar)."""
        self.etapa = EtapaRoleta.ENGATILHANDO
        self.tempo_gatilho = 0.0
        self._som("engatilhar")

    def tratar_evento(self, event: pygame.event.Event) -> None:
        """Espaço segurado puxa o gatilho do humano; soltar reinicia a barra (R7.4)."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self.segurando = True
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self.segurando = False
            if self.etapa == EtapaRoleta.ENGATILHANDO and self._atirador_humano():
                self.tempo_gatilho = 0.0

    def soltar_gatilho(self) -> None:
        """Esquece o Espaço segurado (ex.: ao sair da pausa, o KEYUP pode ter se perdido)."""
        self.segurando = False
        if self.etapa == EtapaRoleta.ENGATILHANDO and self._atirador_humano():
            self.tempo_gatilho = 0.0

    def atualizar(self, dt: float) -> None:
        self.revolver.atualizar(dt)
        self._atualizar_tremida(dt)
        if self.disparou:
            self.tempo_desde_disparo += dt

        if self.etapa == EtapaRoleta.DESLIZANDO and self.lote is not None:
            zona = self.zona_atirador(self.lote.atirador)
            if self.revolver.rect.colliderect(zona):  # R8.5
                self._engatilhar()

        elif self.etapa == EtapaRoleta.ENGATILHANDO:
            if self._atirador_humano():
                self.tempo_gatilho = self.tempo_gatilho + dt if self.segurando else 0.0
            else:
                self.tempo_gatilho += dt
            if self.tempo_gatilho >= self._tempo_necessario():
                self._puxar()

        elif self.etapa == EtapaRoleta.RESULTADO:
            self.tempo_resultado -= dt
            if self.tempo_resultado <= 0:
                self._apos_resultado()

    def _puxar(self) -> None:
        """Puxa e salva no mesmo frame, antes da animação do resultado (R9.8)."""
        self.disparou = self.campanha.puxar()
        self.ao_puxar()
        self.etapa = EtapaRoleta.RESULTADO
        self.tempo_resultado = self.TEMPO_RESULTADO_S
        self.tempo_gatilho = 0.0
        self.segurando = False  # cada puxada exige apertar Espaço de novo
        if self.disparou:
            self._som("disparo")
            self.revolver.disparar()
            self.tempo_desde_disparo = 0.0
            self._tremer(*self.TREMIDA_DISPARO)
            if self.lote is not None:
                self.alvo_atingido = self.lote.alvo
                if self.ao_disparar is not None:
                    self.ao_disparar(self.lote.alvo)
        elif self.lote is not None:
            self._som("clique_vazio")
            self._tremer(*self.TREMIDA_VAZIO)
            # A fala depende de quem era o alvo do tiro vazio.
            self._falar(
                GatilhoFala.TIRO_VAZIO_JOGADOR
                if self.lote.alvo is self.campanha.humano
                else GatilhoFala.TIRO_VAZIO_DIABO
            )

    def _apos_resultado(self) -> None:
        if self.disparou:
            # A bala saiu: a fase acabou (R4.4). Não consulta campanha.resultado,
            # que já pode ter avançado de fase ao salvar.
            self.etapa = EtapaRoleta.FIM
        elif self.campanha.lote_atual is not None:
            self._engatilhar()
        elif self.campanha.proximo_lote() is not None:
            self.iniciar()
        else:
            self.lote = None
            self.etapa = EtapaRoleta.CONCLUIDO

    # ==========================
    # DESENHO
    # ==========================
    def _tremer(self, amplitude: float, duracao: float) -> None:
        self.tremida_amplitude = amplitude
        self.tremida_duracao = duracao
        self.tremida_restante = duracao

    def _atualizar_tremida(self, dt: float) -> None:
        """Deslocamento visual da tela, decaindo até zero; sorteado uma vez por quadro."""
        self.tremida_restante = max(0.0, self.tremida_restante - dt)
        if self.tremida_restante <= 0:
            self.deslocamento_tremida = (0, 0)
            return
        amp = self.tremida_amplitude * self.tremida_restante / self.tremida_duracao
        self.deslocamento_tremida = (
            round(self.rng.uniform(-amp, amp)),
            round(self.rng.uniform(-amp, amp)),
        )

    @property
    def diabo_atingido(self) -> bool:
        """A bala acertou o Diabo: a cena fica visível, escurecendo, com o busto ferido."""
        return self.disparou and self.alvo_atingido is self.campanha.diabo

    def alfa_escuro_disparo(self) -> int:
        """Alfa da camada preta depois de uma bala no Diabo (190 → 255)."""
        k = min(1.0, self.tempo_desde_disparo / self.TEMPO_ESCURECER_S)
        return int(self.ALFA_ESCURO_INICIAL + (255 - self.ALFA_ESCURO_INICIAL) * k)

    def desenhar(
        self,
        tela: pygame.Surface,
        sobre_escuro: Optional[Callable[[pygame.Surface], None]] = None,
    ) -> None:
        """`sobre_escuro` desenha o busto ferido entre a camada escura e o clarão."""
        if self.disparou and self.etapa in (EtapaRoleta.RESULTADO, EtapaRoleta.FIM):
            self._desenhar_disparo(tela, sobre_escuro)
            return

        sombra = pygame.Surface((self.largura, self.altura), pygame.SRCALPHA)
        sombra.fill((0, 0, 0, 120))
        tela.blit(sombra, (0, 0))

        if self.lote is not None:
            self._desenhar_zona(tela)
        self.revolver.desenhar(tela)
        if self.lote is not None:
            self._desenhar_textos(tela)

        if self.etapa == EtapaRoleta.RESULTADO:
            txt = self.font_clic.render("*clic*", True, (235, 225, 205))
            y = layout_mesa(self.largura, self.altura).y_textos_roleta() + 50
            tela.blit(txt, txt.get_rect(center=(self.largura // 2, y)))

    def _desenhar_zona(self, tela: pygame.Surface) -> None:
        zona = self.zona_atirador(self.lote.atirador)
        cor = (200, 60, 45) if self.etapa != EtapaRoleta.DESLIZANDO else (120, 90, 70)
        pygame.draw.rect(tela, cor, zona, width=2, border_radius=10)

    def _desenhar_textos(self, tela: pygame.Surface) -> None:
        humano = self.campanha.humano
        atirador, alvo = self.lote.atirador, self.lote.alvo
        if atirador is alvo:
            titulo = "Você aponta para si mesmo" if atirador is humano else "O Diabo aponta para si mesmo"
        else:
            titulo = "Você aponta para O Diabo" if atirador is humano else "O Diabo aponta para você"

        restantes = self.campanha.puxadas_restantes
        if self.lote.fatal:
            info = "Tiro final. Este não falha."
        elif restantes is None:
            info = "Até a bala sair."
        else:
            info = f"Puxadas restantes: {restantes}"

        cx = self.largura // 2
        y = layout_mesa(self.largura, self.altura).y_textos_roleta()
        txt = self.font_titulo.render(titulo, True, (235, 200, 120))
        tela.blit(txt, txt.get_rect(center=(cx, y)))
        txt = self.font_info.render(info, True, (225, 215, 200))
        tela.blit(txt, txt.get_rect(center=(cx, y + 26)))

        if self.etapa == EtapaRoleta.ENGATILHANDO:
            if self._atirador_humano():
                dica = "Segure ESPAÇO para puxar o gatilho"
            else:
                dica = "O Diabo puxa o gatilho..."
            txt = self.font_info.render(dica, True, (225, 215, 200))
            tela.blit(txt, txt.get_rect(center=(cx, y + 50)))
            self._desenhar_barra(tela, cx, y + 70)

    def _desenhar_barra(self, tela: pygame.Surface, cx: int, y: int) -> None:
        w, h = 220, 10
        rect = pygame.Rect(cx - w // 2, y, w, h)
        pygame.draw.rect(tela, (30, 26, 22), rect, border_radius=4)
        cheio = rect.copy()
        cheio.width = int(w * self.progresso_gatilho)
        if cheio.width > 0:
            pygame.draw.rect(tela, (190, 45, 35), cheio, border_radius=4)
        pygame.draw.rect(tela, (165, 135, 75), rect, width=1, border_radius=4)

    def _desenhar_disparo(
        self,
        tela: pygame.Surface,
        sobre_escuro: Optional[Callable[[pygame.Surface], None]] = None,
    ) -> None:
        """Bala no humano: tela preta. Bala no Diabo: a mesa escurece com o busto ferido.

        Nos dois casos, o clarão na ponta do cano e o flash branco vêm por cima.
        """
        if self.diabo_atingido:
            escuro = pygame.Surface((self.largura, self.altura))
            escuro.fill((0, 0, 0))
            escuro.set_alpha(self.alfa_escuro_disparo())
            tela.blit(escuro, (0, 0))
            if sobre_escuro is not None:
                sobre_escuro(tela)
            if self.tempo_desde_disparo < self.TEMPO_RESULTADO_S:
                self.revolver.desenhar(tela)
        else:
            tela.fill((0, 0, 0))

        t = self.tempo_desde_disparo
        if t < self.TEMPO_CLARAO_S:
            self._desenhar_clarao(tela, t / self.TEMPO_CLARAO_S)
        if t < self.TEMPO_FLASH_S:
            alfa = int(255 * (1 - t / self.TEMPO_FLASH_S))
            flash = pygame.Surface((self.largura, self.altura))
            flash.fill((255, 255, 255))
            flash.set_alpha(alfa)
            tela.blit(flash, (0, 0))

    @classmethod
    def _clarao(cls) -> pygame.Surface:
        """assets/fx/clarao.png, ou um círculo radial amarelo-alaranjado."""
        if cls._clarao_base is None:
            caminho = ASSETS / "fx" / "clarao.png"
            img: Optional[pygame.Surface] = None
            if caminho.is_file():
                try:
                    img = pygame.image.load(str(caminho))
                    if pygame.display.get_surface() is not None:
                        img = img.convert_alpha()
                    img = pygame.transform.smoothscale(img, (256, 256))
                except pygame.error:
                    img = None
            if img is None:
                img = pygame.Surface((256, 256), pygame.SRCALPHA)
                for i in range(32, 0, -1):
                    f = i / 32
                    cor = (255, int(150 + 100 * (1 - f)), int(60 + 180 * (1 - f) ** 2), int(255 * (1 - f) ** 0.8))
                    pygame.draw.circle(img, cor, (128, 128), int(128 * f))
            cls._clarao_base = img
        return cls._clarao_base

    def _desenhar_clarao(self, tela: pygame.Surface, progresso: float) -> None:
        """Clarão na ponta do cano: cresce e some em TEMPO_CLARAO_S."""
        lado = int(256 * (0.6 + 0.8 * progresso))
        img = pygame.transform.smoothscale(self._clarao(), (lado, lado))
        img.set_alpha(int(255 * (1 - progresso)))
        x, y = self.revolver.ponta_cano
        tela.blit(img, img.get_rect(center=(round(x), round(y))))
