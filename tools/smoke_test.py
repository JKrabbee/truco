"""Smoke test sem janela: confere o checklist de teste do jogo jogando como um jogador.

Uso (da raiz do projeto):
    python tools/smoke_test.py                       # todos os itens automatizáveis
    python tools/smoke_test.py --campanhas 8 --semente 7
    python tools/smoke_test.py --capturas capturas/  # também salva capturas de tela
    python tools/smoke_test.py --assets              # valida os sprites de assets/ (9.1)

Roda com SDL_VIDEODRIVER=dummy e SDL_AUDIODRIVER=dummy, dirigindo o jogo por eventos de
teclado como um jogador. O save e as pastas de áudio vão para um diretório temporário
(o `save/` do projeto não é tocado). Espiões em `PartidaTruco.jogar_carta`, `Campanha.puxar`,
`RoletaController`, `PartidaState` e `Audio` cruzam cada evento do jogo com o que deveria
acontecer. Sai com código 1 se algum item falhar.
"""

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

RAIZ = Path(__file__).resolve().parents[1]
for caminho in (RAIZ, RAIZ / "tools"):
    if str(caminho) not in sys.path:
        sys.path.insert(0, str(caminho))

import pygame  # noqa: E402

import preparar_save  # noqa: E402
import preparar_sprites  # noqa: E402
from core.campanha import Campanha  # noqa: E402
from core.card import Carta  # noqa: E402
from core.clima import Expressao, RitmoTique  # noqa: E402
from core.falas import GatilhoFala  # noqa: E402
from core.match import EstadoPartida, PartidaTruco  # noqa: E402
from core.revolver import Tambor  # noqa: E402
from core.roleta import LoteTiros, OrigemTiro  # noqa: E402
from core.rules import RespostaAposta, TipoEnvido, obter_peso_carta  # noqa: E402
from game import save_manager  # noqa: E402
from game.asset_manager import AssetManager  # noqa: E402
from game.audio import Audio  # noqa: E402
from game.game_state import GameStateManager, MenuState, ModoPartida, PartidaState  # noqa: E402
from game.layout import layout_mesa  # noqa: E402
from game.roleta_controller import EtapaRoleta, RoletaController  # noqa: E402
from game.telas import IntroFaseState, MorteState, VitoriaFinalState  # noqa: E402
from ui.balao_fala import BalaoFala  # noqa: E402
from ui.diabo_sprite import DiaboSprite  # noqa: E402
from ui.hud import HUD  # noqa: E402

DT = 1 / 60
TAMANHOS = ((800, 600), (1024, 720))

FORTE = ["1_espadas", "1_bastos", "7_ouros"]
FRACA = ["4_copas", "5_ouros", "6_bastos"]
ENVIDO_33 = ["7_espadas", "6_espadas", "4_copas"]
ENVIDO_23 = ["1_ouros", "2_ouros", "4_bastos"]
FLOR_38 = ["7_copas", "6_copas", "5_copas"]
FLOR_35 = ["4_ouros", "5_ouros", "6_ouros"]
SEM_FLOR = ["1_espadas", "2_bastos", "3_ouros"]

TECLAS_ALEATORIAS = [
    pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_RETURN, pygame.K_t, pygame.K_e,
    pygame.K_r, pygame.K_x, pygame.K_f, pygame.K_q, pygame.K_n, pygame.K_b, pygame.K_SPACE,
    pygame.K_a, pygame.K_z, pygame.K_ESCAPE, pygame.K_UP, pygame.K_DOWN,
]


class Falha(AssertionError):
    """Um item do checklist não se comportou como esperado."""


def verificar(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise Falha(mensagem)


# ==========================
# ESPIÕES
# ==========================
@dataclass
class Puxada:
    frame: int
    origem: OrigemTiro
    atirador_humano: bool
    alvo_humano: bool
    disparou: bool


class Observador:
    """Registro de tudo o que os espiões viram, cruzado no fim de cada item."""

    def __init__(self) -> None:
        self.frame = 0
        self.jogo: Optional["Jogo"] = None
        self.montando = False  # jogadas feitas direto no core pelo próprio teste
        self.dentro_efetivar = False
        self.efetivados = 0
        self.jogadas = 0
        self.jogadas_fora_do_voo = 0
        self.jogadas_sem_colisao = 0
        self.engatilhados = 0
        self.engatilhar_sem_colisao = 0
        self.puxadas: list[Puxada] = []
        self.sons: list[tuple[int, str, float]] = []
        self.musica: list[tuple[int, str, object]] = []
        self.falas: list[tuple[int, GatilhoFala]] = []
        self.tiques_cedo = 0
        self.timeouts = 0
        self.expressoes: set[Expressao] = set()
        self.luz: dict[str, list[tuple[int, bool]]] = {}
        self.volume_errado: list[str] = []
        self.fases_vistas: set[int] = set()
        self._anterior: Optional[tuple[object, ModoPartida]] = None
        self.painel_fase: Optional[tuple[int, int]] = None  # (fase, câmaras) do último HUD

    def observar(self, estado: object) -> None:
        """Chamado a cada quadro."""
        if not isinstance(estado, PartidaState):
            self._anterior = None
            return
        if estado.modo != ModoPartida.ENCERRANDO:
            self.fases_vistas.add(estado.campanha.config.numero)
        self.expressoes.add(estado._expressao_diabo())
        curva = estado.iluminacao.curva
        self.luz.setdefault(curva.luz, []).append((curva.escurecimento, curva.em_queda))
        # O volume é ajustado no início do `atualizar`: o quadro em que o modo muda ainda
        # tem o volume anterior (atraso de 1 quadro, por design). Só confere modos estáveis.
        anterior, self._anterior = self._anterior, (estado, estado.modo)
        if anterior != (estado, estado.modo):
            return
        fator = estado.audio.fator_volume
        if estado.modo == ModoPartida.PAUSA and abs(fator - PartidaState.VOLUME_PAUSA) > 1e-6:
            self.volume_errado.append(f"pausa com volume {fator}")
        if (
            estado.modo == ModoPartida.ROLETA
            and estado.roleta is not None
            and not estado.roleta.disparou
            and abs(fator - PartidaState.VOLUME_ROLETA) > 1e-6
        ):
            self.volume_errado.append(f"roleta com volume {fator}")


OBS = Observador()


def instalar_espioes() -> None:
    """Envolve os pontos do jogo que o checklist precisa observar."""
    jogar_original = PartidaTruco.jogar_carta

    def jogar_carta(self: PartidaTruco, jogador, carta) -> bool:
        ok = jogar_original(self, jogador, carta)
        if ok and not OBS.montando:
            OBS.jogadas += 1
            if not OBS.dentro_efetivar:
                OBS.jogadas_fora_do_voo += 1
        return ok

    PartidaTruco.jogar_carta = jogar_carta

    efetivar_original = PartidaState._efetivar_voo

    def efetivar(self: PartidaState) -> None:
        voo = self.voo
        if voo is not None:
            OBS.efetivados += 1
            if not voo.sprite.rect.colliderect(self._rect_zona_vaza(voo.indice_vaza)):
                OBS.jogadas_sem_colisao += 1
        OBS.dentro_efetivar = True
        try:
            efetivar_original(self)
        finally:
            OBS.dentro_efetivar = False

    PartidaState._efetivar_voo = efetivar

    engatilhar_original = RoletaController._engatilhar

    def engatilhar(self: RoletaController) -> None:
        OBS.engatilhados += 1
        if self.etapa == EtapaRoleta.DESLIZANDO and (
            self.lote is None
            or not self.revolver.rect.colliderect(self.zona_atirador(self.lote.atirador))
        ):
            OBS.engatilhar_sem_colisao += 1
        engatilhar_original(self)

    RoletaController._engatilhar = engatilhar

    puxar_original = Campanha.puxar

    def puxar(self: Campanha) -> bool:
        lote = self.lote_atual
        disparou = puxar_original(self)
        OBS.puxadas.append(
            Puxada(OBS.frame, lote.origem, lote.atirador is self.humano, lote.alvo is self.humano, disparou)
        )
        return disparou

    Campanha.puxar = puxar

    falar_original = PartidaState._falar

    def falar(self: PartidaState, gatilho: GatilhoFala, bloqueia: bool = False) -> None:
        OBS.falas.append((OBS.frame, gatilho))
        falar_original(self, gatilho, bloqueia)

    PartidaState._falar = falar

    estourar_original = PartidaState._estourar_timer

    def estourar(self: PartidaState) -> None:
        OBS.timeouts += 1
        estourar_original(self)

    PartidaState._estourar_timer = estourar

    painel_original = HUD._desenhar_fase_tambor

    def painel(self: HUD, tela, config, tambor) -> None:
        OBS.painel_fase = (config.numero, tambor.disparadas)
        painel_original(self, tela, config, tambor)

    HUD._desenhar_fase_tambor = painel

    efeito_original = Audio.efeito

    def efeito(self: Audio, nome: str, volume: float = 1.0) -> None:
        OBS.sons.append((OBS.frame, nome, volume))
        if nome == "tique" and OBS.jogo is not None:
            e = OBS.jogo.estado
            if not isinstance(e, PartidaState) or e.timer_decisao is None or (
                e.timer_decisao > RitmoTique.ULTIMOS_S + 1e-6
            ):
                OBS.tiques_cedo += 1
        efeito_original(self, nome, volume)

    Audio.efeito = efeito

    for metodo in ("tocar_musica_fase", "parar_musica"):
        original = getattr(Audio, metodo)

        def espiao(self: Audio, *args, _original=original, _nome=metodo, **kwargs) -> None:
            OBS.musica.append((OBS.frame, _nome, args[0] if args else None))
            _original(self, *args, **kwargs)

        setattr(Audio, metodo, espiao)


# ==========================
# JOGO DIRIGIDO POR EVENTOS
# ==========================
class Jogo:
    """Uma "abertura" do jogo: manager novo, começando no menu, como o main.py."""

    def __init__(self, tamanho: tuple[int, int] = (800, 600), desenhar: bool = True):
        self.tela = pygame.display.set_mode(tamanho)
        self.manager = GameStateManager(*tamanho)
        self.desenhar = desenhar
        OBS.jogo = self
        self.manager.mudar_estado(MenuState(self.manager))

    @property
    def estado(self):
        return self.manager.estado_atual

    @property
    def mesa(self) -> PartidaState:
        e = self.estado
        verificar(isinstance(e, PartidaState), f"esperava a mesa, está em {type(e).__name__}")
        return e

    def passo(self, n: int = 1) -> None:
        for _ in range(n):
            self.manager.atualizar(DT)
            if self.desenhar:
                self.manager.desenhar(self.tela)
            OBS.frame += 1
            OBS.observar(self.estado)

    def evento(self, tipo: int, **dados) -> None:
        self.manager.tratar_evento(pygame.event.Event(tipo, **dados))

    def segurar(self, tecla: int) -> None:
        self.evento(pygame.KEYDOWN, key=tecla, mod=0, unicode="", scancode=0)

    def soltar(self, tecla: int) -> None:
        self.evento(pygame.KEYUP, key=tecla, mod=0, unicode="", scancode=0)

    def apertar(self, tecla: int) -> None:
        self.segurar(tecla)
        self.soltar(tecla)

    def fechar(self) -> None:
        """Como o QUIT do main.py: salva pelo estado atual."""
        self.manager.ao_fechar()

    def ate(self, condicao: Callable[[], bool], max_frames: int, mensagem: str,
            agir: Optional[Callable[[], None]] = None) -> int:
        """Roda quadros até a condição; devolve quantos quadros levou."""
        for n in range(max_frames):
            if condicao():
                return n
            if agir is not None:
                agir()
            self.passo()
        raise Falha(f"{mensagem} (após {max_frames} quadros)")

    def capturar(self, pasta: Optional[Path], nome: str) -> None:
        if pasta is None:
            return
        self.manager.desenhar(self.tela)
        w, h = self.tela.get_size()
        pygame.image.save(self.tela, str(pasta / f"{w}x{h}_{nome}.png"))


def textos_menu(jogo: Jogo) -> list[str]:
    verificar(isinstance(jogo.estado, MenuState), f"esperava o menu, está em {type(jogo.estado).__name__}")
    return [b.texto for b in jogo.estado.botoes]


def menu_novo_jogo(jogo: Jogo) -> None:
    """Novo jogo só pelo teclado (↓ até o botão, Enter, e Enter na confirmação)."""
    textos = textos_menu(jogo)
    alvo = textos.index("Novo jogo")
    while jogo.estado.indice_selecionado != alvo:
        jogo.apertar(pygame.K_DOWN)
    jogo.apertar(pygame.K_RETURN)
    if isinstance(jogo.estado, MenuState) and jogo.estado.confirmando_novo_jogo:
        jogo.apertar(pygame.K_RETURN)
    verificar(isinstance(jogo.estado, IntroFaseState), "Novo jogo não abriu a introdução")


def reabrir_e_continuar(tamanho: tuple[int, int] = (800, 600)) -> Jogo:
    """Reabre o jogo e escolhe Continuar (o 1º botão) com Enter."""
    jogo = Jogo(tamanho)
    verificar(textos_menu(jogo)[0] == "Continuar", f"menu sem Continuar: {textos_menu(jogo)}")
    jogo.apertar(pygame.K_RETURN)
    return jogo


def segurar_gatilho(jogo: Jogo) -> None:
    """Na vez do humano na roleta, segura o Espaço (cada puxada pede um novo aperto)."""
    e = jogo.estado
    if isinstance(e, PartidaState) and e.modo == ModoPartida.ROLETA and e.roleta is not None:
        r = e.roleta
        if r.etapa == EtapaRoleta.ENGATILHANDO and r._atirador_humano() and not r.segurando:
            jogo.segurar(pygame.K_SPACE)


def ler_save() -> Optional[dict]:
    if not save_manager.SAVE_FILE.is_file():
        return None
    return json.loads(save_manager.SAVE_FILE.read_text(encoding="utf-8"))


def foto(campanha: Campanha) -> str:
    """Estado lógico comparável (sem o timer, que anda)."""
    dados = campanha.para_dict()
    dados["campanha"]["timer_restante"] = None
    return json.dumps(dados, sort_keys=True)


class Agente:
    """Jogador só de teclado: "cartas" joga e aceita; "aleatoria" aperta qualquer tecla;
    "lenta" não decide nas fases com timer (o tempo esgota)."""

    def __init__(self, rng: random.Random, politica: str, intervalo: int = 8):
        self.rng = rng
        self.politica = politica
        self.intervalo = intervalo
        self.espera = 0

    def agir(self, jogo: Jogo) -> None:
        e = jogo.estado
        if isinstance(e, IntroFaseState):
            jogo.apertar(self.rng.choice([pygame.K_RETURN, pygame.K_SPACE]))
            return
        if not isinstance(e, PartidaState):
            return
        if e.modo == ModoPartida.ROLETA:
            segurar_gatilho(jogo)
            if self.politica == "aleatoria" and self.rng.random() < 0.002:
                jogo.apertar(pygame.K_ESCAPE)  # pausa no meio da roleta
            return
        if e.modo == ModoPartida.PAUSA:
            if self.rng.random() < 0.05:
                jogo.apertar(pygame.K_ESCAPE)
            return
        if e.modo != ModoPartida.JOGANDO or e.bot_pensando:
            return
        self.espera -= 1
        if self.espera > 0:
            return
        self.espera = self.intervalo
        if e.partida.estado_atual == EstadoPartida.FIM_DA_MAO:
            jogo.apertar(self.rng.choice([pygame.K_RETURN, pygame.K_SPACE]))
            return
        if self.politica == "lenta" and e.campanha.config.tempo_decisao_s is not None:
            return
        if self.politica == "aleatoria":
            jogo.apertar(self.rng.choice(TECLAS_ALEATORIAS))
            return
        if e._aposta_pendente_humano() is not None:
            jogo.apertar(self.rng.choice([pygame.K_q, pygame.K_q, pygame.K_n]))
        elif e._humano_pode_jogar_carta():
            if self.rng.random() < 0.3:
                jogo.apertar(self.rng.choice([pygame.K_LEFT, pygame.K_RIGHT]))
            else:
                jogo.apertar(pygame.K_RETURN)


def jogar_campanha(jogo: Jogo, agente: Agente, max_frames: int = 200_000) -> str:
    """Joga até a morte ou a vitória final; devolve "morte" ou "vitoria"."""
    for _ in range(max_frames):
        e = jogo.estado
        if isinstance(e, MorteState):
            return "morte"
        if isinstance(e, VitoriaFinalState):
            return "vitoria"
        agente.agir(jogo)
        jogo.passo()
    raise Falha(f"campanha ({agente.politica}) não terminou em {max_frames} quadros")


# ==========================
# CENÁRIOS MONTADOS
# ==========================
def campanha_fixa(
    mao_j1: Optional[list[str]] = None,
    mao_j2: Optional[list[str]] = None,
    pontos: tuple[int, int] = (0, 0),
    fase: int = 0,
    tambor: Optional[Tambor] = None,
    semente: int = 0,
) -> Campanha:
    """Campanha na fase pedida, 1ª mão distribuída (humano é a mão) e tambor sob controle."""
    c = Campanha.nova(random.Random(semente))
    c.iniciar_fase(fase)
    c.partida.iniciar_nova_rodada()
    if mao_j1 is not None and mao_j2 is not None:
        preparar_save._dar_mao(c, mao_j1, mao_j2)
    preparar_save._placar(c, *pontos)
    c.tambor = tambor or Tambor(6, [5], 0)  # 5 puxadas seguras
    return c


def abrir_mesa(jogo: Jogo, campanha: Campanha) -> PartidaState:
    e = PartidaState(jogo.manager, campanha)
    jogo.manager.mudar_estado(e)
    return e


def no_core(acao: Callable[[], None]) -> None:
    """Executa ações direto no core (montagem do cenário), fora da contagem de jogadas."""
    OBS.montando = True
    try:
        acao()
    finally:
        OBS.montando = False


def jogar_ate_fim_da_mao(p: PartidaTruco) -> None:
    while p.estado_atual in (EstadoPartida.AGUARDANDO_ENVIDO, EstadoPartida.JOGANDO_VAZA):
        jogador = p.jogador_vez
        p.jogar_carta(jogador, max(jogador.mao, key=obter_peso_carta))


def aceitar_truco_ate(p: PartidaTruco, nivel: int) -> None:
    pede, responde = p.jogador1, p.jogador2
    for _ in range(nivel):
        verificar(p.pedir_truco(pede), "pedir_truco falhou na montagem")
        p.responder_truco(RespostaAposta.QUERO, responde)
        pede, responde = responde, pede


def rodar_roleta(jogo: Jogo, max_frames: int = 6000) -> list[Puxada]:
    """Executa a roleta aberta (segurando o Espaço quando é a vez do humano)."""
    inicio = len(OBS.puxadas)
    verificar(jogo.mesa.modo == ModoPartida.ROLETA, f"a roleta não abriu (modo {jogo.mesa.modo.name})")
    jogo.ate(
        lambda: not isinstance(jogo.estado, PartidaState) or jogo.estado.modo != ModoPartida.ROLETA,
        max_frames,
        "a roleta não terminou",
        agir=lambda: segurar_gatilho(jogo),
    )
    return OBS.puxadas[inicio:]


def ate_vez_do_humano(jogo: Jogo, max_frames: int = 3000) -> None:
    """Deixa o Diabo agir até o humano poder jogar uma carta (aceita apostas e avança a mão)."""

    def agir() -> None:
        segurar_gatilho(jogo)
        e = jogo.estado
        if isinstance(e, PartidaState) and e.modo == ModoPartida.JOGANDO and not e.bot_pensando:
            if e._aposta_pendente_humano() is not None:
                jogo.apertar(pygame.K_q)
            elif e.partida.estado_atual == EstadoPartida.FIM_DA_MAO:
                jogo.apertar(pygame.K_RETURN)

    jogo.ate(lambda: jogo.mesa._humano_pode_jogar_carta(), max_frames, "o humano não recebeu a vez",
             agir=agir)


# ==========================
# ITENS DO CHECKLIST
# ==========================
class Contexto:
    def __init__(self, args: argparse.Namespace, base: Path):
        self.args = args
        self.base = base
        self.rng = random.Random(args.semente)
        self.capturas: Optional[Path] = args.capturas
        if self.capturas is not None:
            self.capturas.mkdir(parents=True, exist_ok=True)

    def limpar_save(self) -> None:
        save_manager.SaveManager.apagar()


def item_teclado(ctx: Contexto) -> str:
    """Campanhas inteiras só com KEYDOWN/KEYUP, do menu até a morte ou a vitória final."""
    politicas = ["cartas", "aleatoria", "cartas", "aleatoria", "cartas", "aleatoria"]
    resultados: list[str] = []
    jogadas0, puxadas0, frames0 = OBS.jogadas, len(OBS.puxadas), OBS.frame
    for i in range(ctx.args.campanhas):
        ctx.limpar_save()
        tamanho = TAMANHOS[i % 2]
        jogo = Jogo(tamanho)
        menu_novo_jogo(jogo)
        politica = politicas[i % len(politicas)]
        resultados.append(jogar_campanha(jogo, Agente(random.Random(ctx.rng.random()), politica)))
        jogo.apertar(pygame.K_RETURN)
        verificar(isinstance(jogo.estado, MenuState), "a tela final não voltou ao menu")
        verificar("Continuar" not in textos_menu(jogo), "menu com Continuar depois do fim da campanha")
    # Uma campanha "lenta" a partir da fase 3, deixando o timer estourar.
    ctx.limpar_save()
    preparar_save.gravar("fase3", semente=ctx.args.semente)
    jogo = reabrir_e_continuar((1024, 720))
    timeouts0 = OBS.timeouts
    resultados.append(jogar_campanha(jogo, Agente(random.Random(1), "lenta")))
    verificar(OBS.timeouts > timeouts0, "a campanha lenta da fase 3 não teve timeout")
    return (
        f"{len(resultados)} campanhas ({resultados.count('morte')} mortes, "
        f"{resultados.count('vitoria')} vitórias finais), fases vistas {sorted(OBS.fases_vistas)}, "
        f"{OBS.jogadas - jogadas0} cartas, {len(OBS.puxadas) - puxadas0} puxadas, "
        f"{OBS.timeouts - timeouts0} timeouts na lenta, {OBS.frame - frames0} quadros; nenhum evento de mouse"
    )


def item_colisao(ctx: Contexto) -> str:
    """Carta só vale ao colidir; entradas ignoradas durante o voo (R8)."""
    ctx.limpar_save()
    jogo = Jogo()
    e = abrir_mesa(jogo, campanha_fixa(FORTE, FRACA))
    ate_vez_do_humano(jogo)
    e = jogo.mesa
    jogadas0 = OBS.jogadas
    jogo.apertar(pygame.K_RETURN)
    verificar(e.modo == ModoPartida.CARTA_EM_VOO, "Enter não pôs a carta em voo")
    voo = e.voo
    verificar(voo.carta in e.humano.mao, "a carta saiu da mão antes de colidir")
    verificar(OBS.jogadas == jogadas0, "jogar_carta foi chamada antes da colisão")
    save_antes = save_manager.SAVE_FILE.read_bytes()
    selecao, mao = e.indice_selecionado, list(e.humano.mao)
    for tecla in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_t, pygame.K_e,
                  pygame.K_b, pygame.K_f, pygame.K_q, pygame.K_n, pygame.K_ESCAPE, pygame.K_SPACE):
        jogo.apertar(tecla)
    alvo = e.sprites_humano[0].rect.center if e.sprites_humano else (10, 10)
    jogo.evento(pygame.MOUSEMOTION, pos=alvo, rel=(0, 0), buttons=(0, 0, 0))
    jogo.evento(pygame.MOUSEBUTTONDOWN, pos=alvo, button=1)
    jogo.evento(pygame.MOUSEBUTTONUP, pos=alvo, button=1)
    verificar(e.modo == ModoPartida.CARTA_EM_VOO and e.voo is voo, "uma entrada mudou o voo")
    verificar(e.indice_selecionado == selecao and e.humano.mao == mao, "uma entrada mudou a mão")
    verificar(save_manager.SAVE_FILE.read_bytes() == save_antes, "uma entrada mudou o save no voo")
    quadros = jogo.ate(lambda: OBS.jogadas > jogadas0, 120, "a carta não colidiu")
    verificar(OBS.jogadas == jogadas0 + 1, "mais de uma jogada efetivada")
    verificar(voo.carta not in e.humano.mao, "a carta não saiu da mão na colisão")
    return (
        f"colisão em {quadros} quadros; entradas no voo ignoradas; em todo o smoke: "
        f"{OBS.efetivados} cartas efetivadas, {OBS.jogadas_sem_colisao} sem colisão, "
        f"{OBS.jogadas_fora_do_voo} fora do voo"
    )


def item_lotes(ctx: Contexto) -> str:
    """Cada linha de R5.1 vira o número certo de puxadas na roleta, com o atirador e o alvo certos."""
    # (nome, mão j1, mão j2, ação no core, atirador humano?, alvo humano?, puxadas)
    def truco(nivel: int) -> Callable[[PartidaTruco], None]:
        return lambda p: (aceitar_truco_ate(p, nivel), jogar_ate_fim_da_mao(p))

    def envido(*cantos: TipoEnvido, resposta: RespostaAposta = RespostaAposta.QUERO,
               quem=lambda p: p.jogador1) -> Callable[[PartidaTruco], None]:
        def acao(p: PartidaTruco) -> None:
            p.cantar_envido(quem(p), cantos[0])
            for aumento in cantos[1:]:
                p.responder_envido(RespostaAposta.AUMENTAR, aumento=aumento)
            p.responder_envido(resposta)
        return acao

    def recusa_truco(p: PartidaTruco) -> None:
        p.pedir_truco(p.jogador1)
        p.responder_truco(RespostaAposta.NAO_QUERO, p.jogador2)

    casos = [
        ("mão perdida sem truco", FORTE, FRACA, jogar_ate_fim_da_mao, False, False, 1),
        ("mão perdida com Truco", FORTE, FRACA, truco(1), False, False, 2),
        ("mão perdida com Retruco", FORTE, FRACA, truco(2), False, False, 3),
        ("mão perdida com Vale Quatro", FORTE, FRACA, truco(3), False, False, 4),
        ("humano perdeu a mão", FRACA, FORTE, jogar_ate_fim_da_mao, True, True, 1),
        ("foi ao baralho", FRACA, FORTE, lambda p: p.ir_ao_baralho(p.jogador1), True, True, 1),
        ("foi ao baralho com Truco", FRACA, FORTE,
         lambda p: (aceitar_truco_ate(p, 1), p.ir_ao_baralho(p.jogador1)), True, True, 2),
        ("recusou Truco", FORTE, FRACA, recusa_truco, False, False, 1),
        ("Envido ganho pelo Diabo", ENVIDO_23, ENVIDO_33, envido(TipoEnvido.ENVIDO), False, True, 2),
        ("Real Envido ganho pelo Diabo", ENVIDO_23, ENVIDO_33, envido(TipoEnvido.REAL_ENVIDO), False, True, 3),
        ("Envido + Real Envido", ENVIDO_33, ENVIDO_23,
         envido(TipoEnvido.ENVIDO, TipoEnvido.REAL_ENVIDO), True, False, 5),
        ("recusou Envido", ENVIDO_33, ENVIDO_23,
         envido(TipoEnvido.ENVIDO, resposta=RespostaAposta.NAO_QUERO), False, False, 1),
        ("Flor sem Contraflor", FLOR_38, SEM_FLOR, lambda p: p.cantar_flor(p.jogador1), True, False, 3),
        ("Contraflor", FLOR_38, FLOR_35, lambda p: p.cantar_flor(p.jogador2), True, False, 3),
    ]
    jogo = Jogo()
    for nome, j1, j2, acao, atirador_h, alvo_h, puxadas in casos:
        ctx.limpar_save()
        c = campanha_fixa(j1, j2)
        e = abrir_mesa(jogo, c)
        no_core(lambda: acao(c.partida))
        e._pos_acao()
        feitas = rodar_roleta(jogo)
        verificar(len(feitas) == puxadas, f"{nome}: {len(feitas)} puxadas (esperava {puxadas})")
        for p in feitas:
            verificar((p.atirador_humano, p.alvo_humano) == (atirador_h, alvo_h),
                      f"{nome}: atirador/alvo errados ({p})")
            verificar(not p.disparou, f"{nome}: disparou numa câmara vazia")
        verificar(jogo.mesa.modo == ModoPartida.JOGANDO, f"{nome}: não voltou ao jogo depois da roleta")
    return f"{len(casos)} casos da tabela R5.1 conferidos na roleta (Falta Envido no item seguinte)"


def item_falta_envido(ctx: Contexto) -> str:
    """Falta Envido ganha: puxa até disparar."""
    ctx.limpar_save()
    jogo = Jogo()
    c = campanha_fixa(ENVIDO_33, ENVIDO_23, pontos=(0, 10), tambor=Tambor(6, [3], 0))
    e = abrir_mesa(jogo, c)
    no_core(lambda: (c.partida.cantar_envido(c.humano, TipoEnvido.FALTA_ENVIDO),
                     c.partida.responder_envido(RespostaAposta.QUERO)))
    e._pos_acao()
    feitas = rodar_roleta(jogo)
    verificar([p.disparou for p in feitas] == [False, False, False, True],
              f"puxadas da Falta Envido: {[p.disparou for p in feitas]}")
    verificar(all(p.origem == OrigemTiro.FALTA_ENVIDO and not p.alvo_humano for p in feitas),
              "lote da Falta Envido com alvo errado")
    jogo.ate(lambda: isinstance(jogo.estado, IntroFaseState), 600, "não foi para a próxima fase")
    verificar(jogo.estado.campanha.config.numero == 2, "a bala no Diabo não levou à fase 2")
    return "4 puxadas (bala na 4ª câmara), Diabo atingido, introdução da fase 2"


def item_desfechos(ctx: Contexto) -> str:
    """Bala no Diabo → próxima fase; bala em mim → save apagado e menu sem Continuar; fase 3 → vitória."""
    # Bala no Diabo
    ctx.limpar_save()
    preparar_save.gravar("bala-no-diabo", semente=1)
    jogo = reabrir_e_continuar()
    n0 = len(OBS.puxadas)
    jogo.ate(lambda: len(OBS.puxadas) > n0, 600, "o Diabo não puxou")
    verificar(OBS.puxadas[-1].disparou, "a bala não saiu")
    dados = ler_save()
    verificar(dados is not None and dados["campanha"]["indice_fase"] == 1,
              "no frame da bala, o save não estava na fase 2")
    ferido = False
    paineis: set[tuple[int, int]] = set()
    for _ in range(400):
        jogo.passo()
        if isinstance(jogo.estado, IntroFaseState):
            break
        ferido = ferido or jogo.mesa._expressao_diabo() is Expressao.FERIDO
        paineis.add(OBS.painel_fase)
    verificar(isinstance(jogo.estado, IntroFaseState), "não foi para a introdução da fase 2")
    verificar(ferido, "o Diabo não ficou ferido")
    # O HUD continua mostrando a mesa da fase 1, com a câmara que disparou contada.
    verificar(all(numero == 1 for numero, _ in paineis), f"o HUD mostrou outra fase no encerramento: {paineis}")
    verificar(max(c for _, c in paineis) >= 1, f"o HUD não contou a câmara disparada: {paineis}")
    jogo.capturar(ctx.capturas, "intro_fase2")
    jogo.apertar(pygame.K_RETURN)
    verificar(jogo.mesa.campanha.config.numero == 2, "a mesa não abriu na fase 2")

    # Bala em mim
    ctx.limpar_save()
    preparar_save.gravar("bala-em-mim", semente=1)
    jogo = reabrir_e_continuar()
    n0 = len(OBS.puxadas)
    jogo.ate(lambda: len(OBS.puxadas) > n0, 600, "o humano não puxou", agir=lambda: segurar_gatilho(jogo))
    verificar(OBS.puxadas[-1].disparou and OBS.puxadas[-1].alvo_humano, "a bala não saiu no humano")
    verificar(ler_save() is None, "no frame da bala, o save não foi apagado")
    jogo.ate(lambda: isinstance(jogo.estado, MorteState), 600, "não foi para a tela de morte")
    jogo.capturar(ctx.capturas, "morte")
    jogo.apertar(pygame.K_RETURN)
    verificar("Continuar" not in textos_menu(jogo), "menu com Continuar depois da morte")

    # Bala no Diabo na fase 3
    ctx.limpar_save()
    c = campanha_fixa(fase=2)
    preparar_save._bala_na_proxima(c)
    c.fila_lotes = [LoteTiros(c.diabo, c.diabo, 1, OrigemTiro.RECUSA_TRUCO)]
    save_manager.SaveManager.salvar(c.para_dict())
    jogo = reabrir_e_continuar()
    jogo.ate(lambda: isinstance(jogo.estado, VitoriaFinalState), 900, "não foi para a vitória final")
    verificar(ler_save() is None, "a vitória final não apagou o save")
    jogo.apertar(pygame.K_RETURN)
    verificar("Continuar" not in textos_menu(jogo), "menu com Continuar depois da vitória final")
    return "fase 2 salva no frame da bala no Diabo (busto ferido); morte apaga o save; vitória final apaga o save"


def item_tentos(ctx: Contexto) -> str:
    """Diabo a 12 → tiro final fatal; humano a 12 → próxima fase sem roleta (R3.3, R3.4)."""
    ctx.limpar_save()
    preparar_save.gravar("diabo-11", semente=2)
    jogo = reabrir_e_continuar()
    ate_vez_do_humano(jogo)
    n0 = len(OBS.puxadas)
    jogo.apertar(pygame.K_b)  # ir ao baralho: +1 tento para o Diabo
    jogo.ate(lambda: isinstance(jogo.estado, MorteState), 900, "o tiro final não matou",
             agir=lambda: segurar_gatilho(jogo))
    feitas = OBS.puxadas[n0:]
    verificar([(p.origem, p.disparou) for p in feitas] == [(OrigemTiro.TIRO_FINAL, True)],
              f"puxadas depois do 12 do Diabo: {feitas}")

    ctx.limpar_save()
    c = preparar_save.montar("humano-11", semente=2)
    c.tambor = Tambor(6, [5], 0)
    save_manager.SaveManager.salvar(c.para_dict())
    jogo = reabrir_e_continuar()
    n0 = len(OBS.puxadas)
    agente = Agente(random.Random(3), "cartas")
    paineis: set[tuple[int, int]] = set()

    def agir() -> None:
        agente.agir(jogo)
        if isinstance(jogo.estado, PartidaState) and jogo.estado.modo == ModoPartida.ENCERRANDO:
            paineis.add(OBS.painel_fase)

    jogo.ate(lambda: isinstance(jogo.estado, (IntroFaseState, MorteState)), 6000,
             "o humano não fechou 12", agir=agir)
    verificar(paineis and all(n == 1 for n, _ in paineis),
              f"no encerramento por tentos, o HUD mostrou: {paineis}")
    verificar(isinstance(jogo.estado, IntroFaseState) and jogo.estado.campanha.config.numero == 2,
              "humano a 12 não levou à fase 2")
    sem_lote = all(p.origem in (OrigemTiro.ENVIDO, OrigemTiro.FLOR) for p in OBS.puxadas[n0:])
    verificar(sem_lote, "a mão que fechou 12 gerou puxadas de fim de mão")
    return "Diabo a 12 → 1 puxada TIRO_FINAL fatal, sem o lote do baralho; humano a 12 → fase 2 sem roleta"


def item_timer(ctx: Contexto) -> str:
    """Tempo esgotado joga a carta mais fraca ou responde "Não quero"; o timer para na pausa e no voo."""
    detalhes = []
    # Carta mais fraca (fase 3, 6 s)
    ctx.limpar_save()
    jogo = Jogo()
    c = campanha_fixa(fase=2, semente=4)
    e = abrir_mesa(jogo, c)
    ate_vez_do_humano(jogo)
    esperada = min(e.humano.mao, key=obter_peso_carta)
    quadros = jogo.ate(lambda: e.voo is not None, 60 * 12, "o timer não lançou a carta")
    verificar(e.voo.carta == esperada, f"lançou {e.voo.carta}, a mais fraca era {esperada}")
    verificar(e.voo.jogador is e.humano, "o timeout lançou carta de outro jogador")
    timer_voo = e.timer_decisao
    jogo.passo()
    if e.modo == ModoPartida.CARTA_EM_VOO:
        verificar(e.timer_decisao == timer_voo, "o timer andou durante o voo")
    detalhes.append(f"carta mais fraca em {quadros / 60:.1f} s")

    # Pausa congela o timer
    ctx.limpar_save()
    jogo = Jogo()
    e = abrir_mesa(jogo, campanha_fixa(fase=1, semente=5))
    ate_vez_do_humano(jogo)
    jogo.ate(lambda: e.timer_decisao is not None and e.timer_decisao < 13, 900, "o timer da fase 2 não correu")
    jogo.apertar(pygame.K_ESCAPE)
    verificar(e.modo == ModoPartida.PAUSA, "Esc não pausou")
    antes = e.timer_decisao
    jogo.passo(300)
    verificar(e.timer_decisao == antes, "o timer andou na pausa")
    salvo = ler_save()["campanha"]["timer_restante"]
    verificar(salvo is not None and abs(salvo - antes) < 1e-6, f"a pausa salvou timer {salvo}, era {antes}")
    jogo.apertar(pygame.K_ESCAPE)
    detalhes.append("parado na pausa (5 s) e salvo")

    # Truco e Envido pendentes → Não quero
    for nome, canto, origem in (
        ("Truco", lambda p: p.pedir_truco(p.jogador2), OrigemTiro.RECUSA_TRUCO),
        ("Envido", lambda p: p.cantar_envido(p.jogador2, TipoEnvido.ENVIDO), OrigemTiro.RECUSA_ENVIDO),
    ):
        ctx.limpar_save()
        jogo = Jogo()
        c = campanha_fixa(fase=2, semente=6)
        e = abrir_mesa(jogo, c)
        ate_vez_do_humano(jogo)
        no_core(lambda: verificar(canto(c.partida), f"o Diabo não conseguiu cantar {nome}"))
        e._pos_acao()
        verificar(e._aposta_pendente_humano() is not None, f"{nome} não ficou pendente para o humano")
        quadros = jogo.ate(lambda: e.modo == ModoPartida.ROLETA, 60 * 12, f"o timer não recusou o {nome}")
        lote = c.lote_atual
        verificar(lote is not None and lote.origem == origem and lote.alvo is c.humano,
                  f"recusa do {nome} gerou o lote errado: {lote}")
        detalhes.append(f"Não quero ao {nome} em {quadros / 60:.1f} s")
    verificar(OBS.tiques_cedo == 0, f"{OBS.tiques_cedo} tiques antes dos 3 s finais")
    return "; ".join(detalhes)


def item_fechar_reabrir(ctx: Contexto) -> str:
    """Fechar e reabrir em JOGANDO, CARTA_EM_VOO, ROLETA e PAUSA."""
    # JOGANDO, no meio da mão (tambor sem bala ao alcance, para nenhum tiro encerrar o teste)
    ctx.limpar_save()
    save_manager.SaveManager.salvar(campanha_fixa(semente=21).para_dict())
    jogo = reabrir_e_continuar()
    ate_vez_do_humano(jogo)
    jogo.apertar(pygame.K_RETURN)
    jogo.ate(lambda: jogo.mesa.modo == ModoPartida.JOGANDO and not jogo.mesa.bot_pensando
             and jogo.mesa._decisao_do_humano(), 3000, "a mão não continuou",
             agir=lambda: segurar_gatilho(jogo))
    antes = foto(jogo.mesa.campanha)
    jogo.fechar()
    jogo = reabrir_e_continuar()
    verificar(foto(jogo.mesa.campanha) == antes, "JOGANDO: o estado mudou ao reabrir")
    verificar(jogo.mesa.modo == ModoPartida.JOGANDO, "JOGANDO: reabriu fora do jogo")

    # CARTA_EM_VOO
    ate_vez_do_humano(jogo)
    antes = foto(jogo.mesa.campanha)
    carta = jogo.mesa.humano.mao[jogo.mesa.indice_selecionado]
    jogo.apertar(pygame.K_RETURN)
    verificar(jogo.mesa.modo == ModoPartida.CARTA_EM_VOO, "Enter não lançou a carta")
    jogo.fechar()
    jogo = reabrir_e_continuar()
    verificar(foto(jogo.mesa.campanha) == antes, "CARTA_EM_VOO: o estado mudou ao reabrir")
    verificar(carta in jogo.mesa.humano.mao and jogo.mesa._humano_pode_jogar_carta(),
              "CARTA_EM_VOO: a carta não voltou à mão")

    # PAUSA
    jogo.apertar(pygame.K_ESCAPE)
    verificar(jogo.mesa.modo == ModoPartida.PAUSA, "Esc não pausou")
    antes = foto(jogo.mesa.campanha)
    jogo.capturar(ctx.capturas, "pausa")
    jogo.fechar()
    jogo = reabrir_e_continuar()
    verificar(foto(jogo.mesa.campanha) == antes and jogo.mesa.modo == ModoPartida.JOGANDO,
              "PAUSA: o estado mudou ao reabrir")
    jogo.apertar(pygame.K_ESCAPE)
    jogo.apertar(pygame.K_DOWN)
    jogo.apertar(pygame.K_RETURN)  # Salvar e voltar ao menu
    verificar(textos_menu(jogo)[0] == "Continuar", "Salvar e voltar ao menu sem Continuar")
    jogo.apertar(pygame.K_RETURN)
    verificar(foto(jogo.mesa.campanha) == antes, "Salvar e voltar ao menu: estado diferente")

    # ROLETA: 2 de 4 puxadas, fechando na animação do resultado
    ctx.limpar_save()
    jogo = Jogo()
    c = campanha_fixa()
    c.fila_lotes = [LoteTiros(c.humano, c.humano, 4, OrigemTiro.MAO_PERDIDA)]
    abrir_mesa(jogo, c)
    n0 = len(OBS.puxadas)
    jogo.ate(lambda: len(OBS.puxadas) >= n0 + 2, 1200, "as 2 puxadas não aconteceram",
             agir=lambda: segurar_gatilho(jogo))
    verificar(jogo.mesa.roleta.etapa == EtapaRoleta.RESULTADO, "não está na animação do resultado")
    jogo.fechar()
    jogo = reabrir_e_continuar()
    e = jogo.mesa
    verificar(e.modo == ModoPartida.ROLETA and e.roleta.etapa == EtapaRoleta.DESLIZANDO,
              f"ROLETA: reabriu em {e.modo.name}")
    verificar(e.campanha.puxadas_restantes == 2 and e.campanha.tambor.indice == 2,
              f"ROLETA: {e.campanha.puxadas_restantes} puxadas restantes, câmara {e.campanha.tambor.indice}")
    jogo.capturar(ctx.capturas, "roleta_humano")
    return "JOGANDO, CARTA_EM_VOO (carta de volta à mão), PAUSA (e Salvar e voltar ao menu) e ROLETA (2/4, câmaras 2/6)"


def item_fechar_apos_puxar(ctx: Contexto) -> str:
    """Fechar logo após puxar o gatilho não muda o resultado (R9.8)."""
    ctx.limpar_save()
    jogo = Jogo()
    c = campanha_fixa()
    c.fila_lotes = [LoteTiros(c.humano, c.humano, 3, OrigemTiro.MAO_PERDIDA)]
    abrir_mesa(jogo, c)
    n0 = len(OBS.puxadas)
    jogo.ate(lambda: len(OBS.puxadas) > n0, 600, "não puxou", agir=lambda: segurar_gatilho(jogo))
    indice, restantes = c.tambor.indice, c.puxadas_restantes
    jogo.fechar()
    jogo = reabrir_e_continuar()
    e = jogo.mesa
    verificar((e.campanha.tambor.indice, e.campanha.puxadas_restantes) == (indice, restantes),
              "o tambor voltou atrás ao reabrir")

    for cenario, esperado in (("bala-em-mim", "morte"), ("bala-no-diabo", "fase 2")):
        ctx.limpar_save()
        preparar_save.gravar(cenario, semente=1)
        jogo = reabrir_e_continuar()
        n0 = len(OBS.puxadas)
        jogo.ate(lambda: len(OBS.puxadas) > n0, 600, "não puxou", agir=lambda: segurar_gatilho(jogo))
        jogo.fechar()
        jogo = Jogo()
        textos = textos_menu(jogo)
        if esperado == "morte":
            verificar("Continuar" not in textos, "fechar após a bala no humano deixou um save")
        else:
            jogo.apertar(pygame.K_RETURN)
            verificar(isinstance(jogo.estado, IntroFaseState) and jogo.estado.campanha.config.numero == 2,
                      "fechar após a bala no Diabo não manteve a fase 2")
    return "câmara e puxadas mantidas; bala no humano continua morte; bala no Diabo continua fase 2"


def item_save_corrompido(ctx: Contexto) -> str:
    """Save inválido: aviso no menu, arquivo apagado e nada de Continuar."""
    valido = campanha_fixa().para_dict()
    valido = {"versao": save_manager.VERSAO_SAVE, **valido}

    def alterar(caminho: list, valor) -> bytes:
        dados = json.loads(json.dumps(valido))
        alvo = dados
        for chave in caminho[:-1]:
            alvo = alvo[chave]
        if valor is KeyError:
            del alvo[caminho[-1]]
        else:
            alvo[caminho[-1]] = valor
        return json.dumps(dados).encode()

    variantes = {
        "lixo": b"{{{ isto nao e json",
        "binario": b"\xff\xfe\x00\x01",
        "vazio": b"",
        "lista": b"[]",
        "truncado": json.dumps(valido).encode()[:200],
        "versao errada": alterar(["versao"], 99),
        "sem campanha": alterar(["campanha"], KeyError),
        "sem partida": alterar(["partida"], KeyError),
        "partida nula": alterar(["partida"], None),
        "fase 7": alterar(["campanha", "indice_fase"], 7),
        "resultado inventado": alterar(["campanha", "resultado"], "GANHOU"),
        "bala em texto": alterar(["campanha", "tambor", "balas"], ["x"]),
        "tambor já disparado": alterar(["campanha", "tambor"], {"camaras": 6, "balas": [1], "indice": 3}),
        "lote com jogador j9": alterar(["campanha", "fila_lotes"],
                                       [{"atirador": "j9", "alvo": "j1", "puxadas": 1,
                                         "origem": "MAO_PERDIDA", "fatal": False}]),
        "timer em texto": alterar(["campanha", "timer_restante"], "abc"),
        "carta inexistente": alterar(["partida", "mao_j1"], ["99_espadas"]),
        "estado inventado": alterar(["partida", "estado_atual"], "XYZ"),
        "vazas em número": alterar(["partida", "mao_atual"], 5),
        "pontos em texto": alterar(["partida", "pontos_jogador1"], "muitos"),
    }
    for nome, conteudo in variantes.items():
        save_manager.SAVE_DIR.mkdir(parents=True, exist_ok=True)
        save_manager.SAVE_FILE.write_bytes(conteudo)
        try:
            jogo = Jogo()
            jogo.passo(3)
        except Exception as erro:
            raise Falha(f"save '{nome}' derrubou o menu: {erro!r}") from erro
        menu = jogo.estado
        verificar(menu.mensagem == MenuState.MSG_SAVE_CORROMPIDO, f"save '{nome}' sem aviso no menu")
        verificar(not save_manager.SAVE_FILE.exists(), f"save '{nome}' não foi apagado")
        verificar("Continuar" not in textos_menu(jogo), f"save '{nome}' deixou Continuar")
    jogo.capturar(ctx.capturas, "menu_save_corrompido")
    return f"{len(variantes)} variantes (lixo, versão, campos faltando, tipos e ids errados): aviso, sem crash"


def item_outro_diretorio(ctx: Contexto) -> str:
    """Rodar o main.py de outro diretório carrega os assets e aponta o save para a raiz."""
    pasta = ctx.base / "outro_dir"
    pasta.mkdir()
    codigo = f"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"; os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, {str(RAIZ)!r})
import pygame
carregados = []
_load = pygame.image.load
def load(caminho, *a):
    s = _load(caminho, *a); carregados.append(str(caminho)); return s
pygame.image.load = load
from game import paths
from core.card import Carta
pygame.init(); pygame.display.set_mode((800, 600))
from game.asset_manager import AssetManager
AssetManager().obter_sprite_carta(Carta.de_id("1_espadas"))
n = [0]
def get():
    n[0] += 1
    return [pygame.event.Event(pygame.QUIT)] if n[0] > 30 else []
import main
pygame.event.get = get
try:
    main.main()
except SystemExit:
    pass
print("CWD=" + os.getcwd())
print("SAVE=" + str(paths.SAVE_FILE))
print("CARTAS=" + str(sum(1 for c in carregados if "cards" in c)))
print("QUADROS=" + str(n[0]))
"""
    proc = subprocess.run([sys.executable, "-c", codigo], cwd=pasta, capture_output=True,
                          text=True, timeout=120)
    verificar(proc.returncode == 0, f"main.py falhou fora da raiz:\n{proc.stderr[-800:]}")
    saida = dict(linha.split("=", 1) for linha in proc.stdout.splitlines() if "=" in linha)
    verificar(Path(saida["CWD"]).resolve() == pasta.resolve(), "o subprocesso não rodou no outro diretório")
    verificar(Path(saida["SAVE"]) == RAIZ / "save" / "save.json", f"save fora da raiz: {saida['SAVE']}")
    verificar(int(saida["CARTAS"]) >= 1, "o PNG da carta não carregou fora da raiz")
    verificar(not (pasta / "save").exists(), "criou save/ no diretório de execução")
    return f"main.py rodou {saida['QUADROS']} quadros em {pasta.name}/; PNG da carta carregado; save em <raiz>/save/"


def _rotulo_vaza(e: PartidaState, i: int) -> pygame.Rect:
    """Mesmo cálculo de _desenhar_centro_organico para o rótulo (e a etiqueta) da vaza i."""
    layout = e.layout
    vaza = e.partida.mao_atual.vazas[i]
    concluida = len(vaza.cartas_jogadas) == 2
    texto = f"{i + 1}ª" if concluida else f"{i + 1}ª VAZA"
    w, h = e.font_vaza_label.size(texto)
    rect = pygame.Rect(0, 0, w, h)
    rect.center = (layout.pontos_x_vazas[i], layout.y_rotulo_vaza)
    if concluida:
        w_tag = e._largura_tag_resultado_vaza(vaza)
        total = rect.width + 6 + w_tag
        x0, x1 = layout.faixa_central_x()
        rect.left = max(x0, min(layout.pontos_x_vazas[i] - total // 2, x1 - total))
        rect.width = total
        rect.height = max(rect.height, 22)
        rect.centery = layout.y_rotulo_vaza
    return rect


def _monte_vaza(e: PartidaState, i: int, sombra: bool = False) -> pygame.Rect:
    """Caixa das cartas giradas do monte; com `sombra`, inclui a sombra em (+3, +4)."""
    vaza = e.partida.mao_atual.vazas[i]
    if not vaza.cartas_jogadas:
        return e._rect_zona_vaza(i)
    rects = []
    for j in range(len(vaza.cartas_jogadas)):
        angulo = e.ANGULOS_VAZAS[i][j]
        carta = pygame.Surface((e.layout.carta_vaza_w, e.layout.carta_vaza_h))
        r = pygame.transform.rotate(carta, angulo).get_rect(center=e._centro_carta_na_vaza(i, j))
        rects.append(r.union(r.move(3, 4)) if sombra else r)
    return rects[0].unionall(rects[1:])


def rects_mesa(e: PartidaState) -> dict[str, pygame.Rect]:
    """Retângulos de tudo o que a checagem de sobreposição do Bloco 7 cobria."""
    L, H = e.manager.largura, e.manager.altura
    layout = e.layout
    col = layout.largura_coluna
    timer = e._rect_timer()
    rects = {
        "placa_diabo": pygame.Rect(20, 16, col, 72 + 4),
        "placa_humano": pygame.Rect(L - col - 20, 16, col, 72 + 4),
        "painel_fase": pygame.Rect(20, 96, col, 46),
        "placa_aposta": layout.placa_aposta().inflate(0, 4),
        "pensa": layout.aviso_pensando(),
        "busto": layout.busto(),
        "faixa": layout.faixa_mensagem(),
        "timer": timer.union(pygame.Rect(timer.x, timer.y - 18, 1, 18)),  # com "TEMPO n s" acima
    }
    for i, s in enumerate(e.sprites_bot):
        rects[f"carta_diabo_{i}"] = s.rect.copy()
    for i in range(3):
        rects[f"rotulo_{i}"] = _rotulo_vaza(e, i)
        rects[f"monte_{i}"] = _monte_vaza(e, i)
    botoes = list(e.botoes_acao) + list(e.botoes_resposta_aposta)
    if e.botao_proxima_mao:
        botoes.append(e.botao_proxima_mao)
    for i, b in enumerate(botoes):
        rects[f"botao_{i}"] = b.rect_base.copy()
    for i, s in enumerate(e.sprites_humano):
        rects[f"mao_{i}"] = pygame.Rect(s.pos_x_base, s.pos_y_base, s.rect.width, s.rect.height)
    if e.balao is not None:
        pos, largura_max = layout.balao()
        b = e.balao
        fonte = b.fonte()
        linhas = b._quebrar(largura_max - 2 * b.PADDING)
        largura = min(largura_max, max(fonte.size(l)[0] for l in linhas) + 2 * b.PADDING)
        altura = len(linhas) * fonte.get_linesize() + 2 * b.PADDING
        rects["balao"] = pygame.Rect(pos[0], pos[1], largura, altura)
        rects["_linhas_balao"] = pygame.Rect(0, 0, len(linhas), 1)
    w, h = e.font_dica.size("← / → escolher carta   ·   Enter jogar   ·   Esc pausa")
    rects["dica"] = pygame.Rect(L // 2 - w // 2, H - 9 - h // 2, w, h)
    return rects


def sobreposicoes(rects: dict[str, pygame.Rect]) -> list[str]:
    """Pares que se cruzam (grupos do mesmo tipo, como as cartas da mão, ficam de fora)."""
    nomes = [n for n in rects if not n.startswith("_")]
    achadas = []
    for a in range(len(nomes)):
        for b in range(a + 1, len(nomes)):
            na, nb = nomes[a], nomes[b]
            if na.rsplit("_", 1)[0] == nb.rsplit("_", 1)[0] and na[-1].isdigit() and nb[-1].isdigit():
                continue
            if rects[na].colliderect(rects[nb]):
                achadas.append(f"{na}×{nb}")
    return achadas


def item_sobreposicao(ctx: Contexto) -> str:
    """Mesa sem sobreposição em 800×600 e 1024×720, no início e no meio da mão."""
    texto_longo = ("Esse teu sete de espadas não te salva, gaúcho. Eu vejo a tua mão inteira "
                   "daqui, e o tambor também sabe onde mora a bala. Puxa logo esse gatilho.")
    resumo: list[str] = []
    sombras: list[str] = []
    for tamanho in TAMANHOS:
        jogo = Jogo(tamanho)
        for momento in ("inicio", "meio"):
            ctx.limpar_save()
            c = campanha_fixa(FORTE, FRACA, fase=1, semente=8)
            if momento == "meio":
                def montar() -> None:
                    aceitar_truco_ate(c.partida, 1)
                    for _ in range(2):
                        j = c.partida.jogador_vez
                        c.partida.jogar_carta(j, max(j.mao, key=obter_peso_carta))
                no_core(montar)
            e = abrir_mesa(jogo, c)
            # Pior caso: balão longo, "O Diabo pensa…" e timer na tela ao mesmo tempo.
            e.balao = BalaoFala(texto_longo)
            jogo.passo(2)
            e.bot_pensando = True
            e.timer_decisao = e.timer_decisao or 9.0
            e.timer_total = e.timer_total or 15.0
            rects = rects_mesa(e)
            achadas = sobreposicoes(rects)
            verificar(not achadas, f"{tamanho[0]}×{tamanho[1]} {momento}: {', '.join(achadas)}")
            linhas = rects["_linhas_balao"].width if "_linhas_balao" in rects else 0
            resumo.append(f"{tamanho[0]}×{tamanho[1]} {momento} ({len(rects) - 1} rects, balão {linhas} linhas)")
            # A sombra das cartas (translúcida) é medida à parte, só para registro.
            for i in range(3):
                monte = _monte_vaza(e, i, sombra=True)
                cruzam = [n for n, r in rects.items() if not n.startswith(("_", "monte", "rotulo"))
                          and monte.colliderect(r)]
                for n in cruzam:
                    px = monte.clip(rects[n])
                    sombras.append(f"{tamanho[0]}×{tamanho[1]} {momento}: sombra do monte {i + 1} × {n} "
                                   f"({px.width}×{px.height} px)")
            e.balao.tempo = 1.5  # já digitado, para a captura
            jogo.capturar(ctx.capturas, f"mesa_{momento}")
        # Roleta com o Diabo atirando e o disparo nele (captura)
        if ctx.capturas is not None:
            ctx.limpar_save()
            c = campanha_fixa(semente=9)
            preparar_save._bala_na_proxima(c)
            c.fila_lotes = [LoteTiros(c.diabo, c.diabo, 1, OrigemTiro.RECUSA_TRUCO)]
            e = abrir_mesa(jogo, c)
            jogo.ate(lambda: e.roleta.etapa == EtapaRoleta.ENGATILHANDO, 300, "o revólver não chegou")
            jogo.capturar(ctx.capturas, "roleta_diabo")
            n0 = len(OBS.puxadas)
            jogo.ate(lambda: len(OBS.puxadas) > n0, 300, "o Diabo não puxou")
            jogo.passo(3)
            jogo.capturar(ctx.capturas, "disparo_clarao")
            jogo.passo(40)
            jogo.capturar(ctx.capturas, "disparo_ferido")
    nota = f"; só sombras: {'; '.join(sombras)}" if sombras else "; nem as sombras encostam"
    return "zero sobreposições: " + "; ".join(resumo) + nota


def item_luz_expressoes(ctx: Contexto) -> str:
    """Luz diferente em cada fase e as quatro expressões do Diabo."""
    jogo = Jogo(desenhar=False)
    resumo = []
    for fase in range(3):
        ctx.limpar_save()
        e = abrir_mesa(jogo, campanha_fixa(fase=fase))
        curva = e.iluminacao.curva
        valores = []
        for _ in range(60 * 40):
            e.iluminacao.atualizar(DT)
            valores.append((curva.escurecimento, curva.em_queda))
        maximo = max(v for v, _ in valores)
        quedas = sum(1 for _, q in valores if q)
        resumo.append(f"fase {fase + 1} '{curva.luz}' alfa máx {maximo}, {quedas} quadros de queda")
        if fase == 0:
            verificar(maximo == 0 and quedas == 0, "a fase 1 escureceu")
        elif fase == 1:
            verificar(0 < maximo <= 45 and quedas == 0, "a luz da fase 2 não oscilou como deveria")
        else:
            verificar(quedas > 0 and maximo >= 150, "a fase 3 não piscou")
    faltando = set(Expressao) - OBS.expressoes
    verificar(not faltando, f"expressões nunca vistas: {sorted(x.value for x in faltando)}")
    vistas_luz = {k: max(v for v, _ in vs) for k, vs in OBS.luz.items() if vs}
    return "; ".join(resumo) + f"; nas partidas: {vistas_luz}; expressões: todas as 4"


def item_som(ctx: Contexto) -> str:
    """Sons cruzados com os eventos (espião); música na pausa e na roleta; jogo mudo sem erro."""
    nomes = [n for _, n, _ in OBS.sons]
    puxadas = len(OBS.puxadas)
    disparos = sum(1 for p in OBS.puxadas if p.disparou)
    verificar(nomes.count("disparo") == disparos, f"{nomes.count('disparo')} disparos para {disparos} balas")
    verificar(nomes.count("clique_vazio") == puxadas - disparos,
              f"{nomes.count('clique_vazio')} cliques para {puxadas - disparos} câmaras vazias")
    quadros_som = {(f, n) for f, n, _ in OBS.sons}
    for p in OBS.puxadas:
        verificar((p.frame, "disparo" if p.disparou else "clique_vazio") in quadros_som,
                  f"puxada sem som no mesmo quadro: {p}")
    verificar(nomes.count("engatilhar") == OBS.engatilhados,
              f"{nomes.count('engatilhar')} engatilhar para {OBS.engatilhados} entradas em ENGATILHANDO")
    verificar(OBS.engatilhar_sem_colisao == 0,
              f"{OBS.engatilhar_sem_colisao} transições DESLIZANDO→ENGATILHANDO sem colisão do revólver")
    verificar(nomes.count("carta") == OBS.efetivados, f"{nomes.count('carta')} sons de carta para {OBS.efetivados} cartas")
    risos = sum(1 for _, g in OBS.falas if g in (GatilhoFala.TIRO_VAZIO_DIABO, GatilhoFala.MORTE_JOGADOR))
    verificar(nomes.count("risada") == risos, f"{nomes.count('risada')} risadas para {risos} falas de risada")
    verificar(OBS.tiques_cedo == 0, f"{OBS.tiques_cedo} tiques antes dos 3 s finais")
    verificar(not OBS.volume_errado, f"volume da música: {OBS.volume_errado[:3]}")

    # Troca de faixa: menu em silêncio, intro da fase com a faixa dela.
    ctx.limpar_save()
    m0 = len(OBS.musica)
    jogo = Jogo()
    menu_novo_jogo(jogo)
    chamadas = [(n, getattr(a, "numero", a)) for _, n, a in OBS.musica[m0:]]
    verificar(chamadas[:2] == [("parar_musica", 800), ("tocar_musica_fase", 1)], f"música do menu/intro: {chamadas}")

    # Jogo mudo: sem arquivos de áudio e com o mixer falhando.
    vazia = ctx.base / "sem_audio"
    vazia.mkdir(exist_ok=True)
    dirs = (Audio.DIR_MUSICA, Audio.DIR_SFX)
    Audio.DIR_MUSICA = Audio.DIR_SFX = vazia
    try:
        ctx.limpar_save()
        jogo = Jogo()
        verificar(jogo.manager.audio.ativo, "o mixer dummy não iniciou")
        menu_novo_jogo(jogo)
        jogar_campanha(jogo, Agente(random.Random(11), "cartas"))
    finally:
        Audio.DIR_MUSICA, Audio.DIR_SFX = dirs
    init_original = pygame.mixer.init
    pygame.mixer.quit()

    def init_falhando(*args, **kwargs):
        raise pygame.error("mixer indisponível (simulado)")

    pygame.mixer.init = init_falhando
    try:
        ctx.limpar_save()
        jogo = Jogo()
        verificar(not jogo.manager.audio.ativo, "o Audio não percebeu o mixer falhando")
        menu_novo_jogo(jogo)
        jogar_campanha(jogo, Agente(random.Random(12), "cartas"))
    finally:
        pygame.mixer.init = init_original
        pygame.mixer.init()
    return (
        f"{len(OBS.sons)} sons conferidos ({nomes.count('engatilhar')} engatilhar, {puxadas - disparos} "
        f"cliques, {disparos} disparos, {nomes.count('carta')} cartas, {nomes.count('risada')} risadas, "
        f"{nomes.count('tique')} tiques); pausa 35% e roleta 50%; mudo sem arquivos e sem mixer"
    )


def item_cenarios(ctx: Contexto) -> str:
    """Cada cenário do tools/preparar_save.py abre pelo Continuar e roda sem erro."""
    abertos = []
    for nome in preparar_save.CENARIOS:
        ctx.limpar_save()
        preparar_save.gravar(nome, semente=3)
        jogo = reabrir_e_continuar()
        esperado = IntroFaseState if nome == "fase3" else PartidaState
        verificar(isinstance(jogo.estado, esperado), f"{nome}: abriu {type(jogo.estado).__name__}")
        if nome in ("falta-envido", "bala-no-diabo", "bala-em-mim"):
            verificar(jogo.mesa.modo == ModoPartida.ROLETA, f"{nome}: não abriu na roleta")
        jogo.passo(60)
        abertos.append(nome)
    return f"{len(abertos)} cenários abrem pelo Continuar"


def item_assets(ctx: Contexto) -> str:
    """Sprites de IA presentes em assets/: carregam no jogo (sem cair no fallback) e passam na checagem."""
    carregados: list[str] = []
    load_original = pygame.image.load

    def load(caminho, *args):
        s = load_original(caminho, *args)
        carregados.append(str(Path(caminho).resolve()))
        return s

    pygame.image.load = load
    try:
        avisos = preparar_sprites.checar_assets()
        presentes = preparar_sprites.arquivos_presentes()
        diabo = DiaboSprite()
        AssetManager()._carregar_imagem_mesa()
        am = AssetManager()
        am.obter_verso_carta()
        RoletaController._clarao_base = None
        RoletaController._clarao()
        from ui.revolver_sprite import RevolverSprite
        RevolverSprite(0, 0)
    finally:
        pygame.image.load = load_original
    falhas = []
    for tipo, caminho in presentes:
        if tipo == "diabo":
            if diabo.procedural:
                falhas.append(f"{caminho.name}: o busto caiu no procedural")
            continue
        if str(caminho.resolve()) not in carregados:
            falhas.append(f"{caminho.relative_to(RAIZ)} não foi carregado pelo jogo")
    verificar(not falhas, "; ".join(falhas))
    nomes = ", ".join(str(c.relative_to(RAIZ)) for _, c in presentes) or "nenhum (procedurais)"
    return f"carregados: {nomes}; {avisos} aviso(s) da checagem (ver acima)"


ITENS: list[tuple[str, str, Callable[[Contexto], str]]] = [
    ("1", "Partida inteira só no teclado", item_teclado),
    ("2", "Carta só vale ao colidir; entradas ignoradas no voo", item_colisao),
    ("3", "Cada linha da tabela R5.1 gera as puxadas certas", item_lotes),
    ("4", "Falta Envido puxa até disparar", item_falta_envido),
    ("5", "Bala no Diabo → próxima fase; bala em mim → save apagado", item_desfechos),
    ("6", "Diabo a 12 → tiro final fatal", item_tentos),
    ("7", "Timer: carta mais fraca / Não quero", item_timer),
    ("8", "Fechar e reabrir em JOGANDO, CARTA_EM_VOO, ROLETA e PAUSA", item_fechar_reabrir),
    ("9", "Fechar logo após puxar não muda o resultado", item_fechar_apos_puxar),
    ("10", "Save corrompido → aviso no menu, sem crash", item_save_corrompido),
    ("11", "Rodar de outro diretório", item_outro_diretorio),
    ("12", "800×600 (e 1024×720) sem sobreposição", item_sobreposicao),
    ("13", "Luz por fase e expressões do Diabo", item_luz_expressoes),
    ("14", "Som (espião) e jogo mudo", item_som),
    ("+", "Cenários do preparar_save.py", item_cenarios),
]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--campanhas", type=int, default=10, help="campanhas do item 1 (padrão 10)")
    parser.add_argument("--semente", type=int, default=2026)
    parser.add_argument("--capturas", type=Path, help="pasta para as capturas de tela")
    parser.add_argument("--assets", action="store_true", help="valida os sprites de assets/ (9.1)")
    parser.add_argument("--so", help="roda só os itens indicados, ex.: 1,8,12")
    args = parser.parse_args(argv)
    if args.assets and args.capturas is None:
        args.capturas = RAIZ / "capturas"

    save_raiz_existia = (RAIZ / "save").exists()
    base = Path(tempfile.mkdtemp(prefix="truco_smoke_"))
    save_manager.SAVE_DIR = base / "save"
    save_manager.SAVE_FILE = save_manager.SAVE_DIR / "save.json"
    for nome in ("music", "sfx"):
        origem = RAIZ / "assets" / nome
        destino = base / nome
        shutil.copytree(origem, destino) if origem.is_dir() else destino.mkdir()
    Audio.DIR_MUSICA, Audio.DIR_SFX = base / "music", base / "sfx"

    random.seed(args.semente)
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    instalar_espioes()
    ctx = Contexto(args, base)

    itens = list(ITENS)
    if args.assets:
        itens.append(("9.1", "Sprites de IA em assets/", item_assets))
    if args.so:
        escolhidos = set(args.so.split(","))
        itens = [i for i in itens if i[0] in escolhidos]

    falhas = 0
    inicio = time.time()
    try:
        for numero, titulo, funcao in itens:
            t0 = time.time()
            try:
                detalhe = funcao(ctx)
                status = "OK"
            except Falha as erro:
                detalhe, status = str(erro), "FALHA"
            except Exception:
                detalhe, status = traceback.format_exc(limit=6), "ERRO"
            if status != "OK":
                falhas += 1
            print(f"[{status:5}] {numero:>3}. {titulo} ({time.time() - t0:.0f} s)")
            print(f"         {detalhe}")
            sys.stdout.flush()
    finally:
        shutil.rmtree(base, ignore_errors=True)
        pygame.quit()
    sobrou = (RAIZ / "save").exists() and not save_raiz_existia
    if sobrou:
        print("[FALHA] o smoke test criou save/ na raiz do projeto")
        falhas += 1
    print(f"\n{len(itens) - falhas}/{len(itens)} itens OK em {time.time() - inicio:.0f} s"
          + (f"; capturas em {args.capturas}" if args.capturas else ""))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
