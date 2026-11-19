import random
from enum import Enum, auto
from typing import Optional
from core.card import Carta
from core.fase import ConfigFase


class GatilhoFala(Enum):
    """Situações em que o Diabo pode falar (R6.5)."""

    INICIO_MAO = auto()
    PEDE_TRUCO = auto()
    CANTA_ENVIDO = auto()
    TURNO_JOGADOR = auto()
    ANTES_PUXAR = auto()
    TIRO_VAZIO_DIABO = auto()
    TIRO_VAZIO_JOGADOR = auto()
    MORTE_JOGADOR = auto()
    MORTE_DIABO = auto()


# Banco de frases por gatilho. As confiantes valem para mão forte e fraca (R6.4).
FRASES: dict[GatilhoFala, tuple[str, ...]] = {
    GatilhoFala.INICIO_MAO: (
        "Mais uma mão. Mais uma chance de errar.",
        "Embaralhei com carinho. Pra ti.",
        "Vamos ver até onde vai tua sorte.",
        "Tu sente o frio? Sou eu.",
    ),
    GatilhoFala.PEDE_TRUCO: (
        "Truco. E não é blefe… ou é?",
        "Aceita, se tiver coragem.",
        "Essa mão já é minha.",
        "Tu vai correr. Eu sei.",
    ),
    GatilhoFala.CANTA_ENVIDO: (
        "Envido. Conta os teus pontos, se souber.",
        "Meus pontos queimam, criatura.",
        "Quer apostar a alma no envido?",
    ),
    GatilhoFala.TURNO_JOGADOR: (
        "Tá demorando. Medo?",
        "Tu vai correr. Eu sei.",
        "Qualquer carta serve pra perder.",
        "Escuta o relógio. Tic. Tac.",
        "Pensa bem. Ou não pensa.",
    ),
    GatilhoFala.ANTES_PUXAR: (
        "Puxa. Devagar.",
        "Seis câmaras. Quantas ainda vazias?",
        "O gatilho tá frio. Esquenta ele.",
        "Que o tambor decida.",
    ),
    GatilhoFala.TIRO_VAZIO_DIABO: (
        "Hah. Ainda não é minha hora.",
        "O tambor gosta de mim.",
        "Vazio. Como a tua esperança.",
    ),
    GatilhoFala.TIRO_VAZIO_JOGADOR: (
        "Sorte. Ela acaba.",
        "Respira. Enquanto pode.",
        "O tambor tem paciência. Eu também.",
    ),
    GatilhoFala.MORTE_JOGADOR: (
        "Eu avisei.",
        "Tua alma agora joga do meu lado.",
        "Fim da mesa, criatura.",
    ),
    GatilhoFala.MORTE_DIABO: (
        "Isso… não estava nas cartas.",
        "Tu vai me ver de novo.",
        "Impossível…",
    ),
}

# Leitura de mente: {carta} é o nome_completo de uma carta real da mão do jogador.
FRASES_LEITURA: tuple[str, ...] = (
    "Esse teu {carta} não te salva.",
    "Eu sei o que tu tem aí… {carta}.",
    "Joga o {carta}. Eu espero.",
    "Segurando o {carta} com essa força toda?",
    "O {carta} treme na tua mão.",
)

# Só nos gatilhos de provocação: citar carta após um tiro ou morte soaria estranho.
GATILHOS_LEITURA: frozenset[GatilhoFala] = frozenset(
    {
        GatilhoFala.INICIO_MAO,
        GatilhoFala.PEDE_TRUCO,
        GatilhoFala.CANTA_ENVIDO,
        GatilhoFala.TURNO_JOGADOR,
        GatilhoFala.ANTES_PUXAR,
    }
)


class FalasDiabo:
    """Escolhe as falas do Diabo. Único componente que vê a mão do jogador, só para texto."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def escolher(
        self, gatilho: GatilhoFala, config: ConfigFase, mao_jogador: list[Carta]
    ) -> Optional[str]:
        """Com prob. config.chance_leitura (se leitura_mente) devolve uma frase com
        carta.nome_completo de uma carta sorteada de mao_jogador; senão uma frase do banco
        do gatilho, ou None."""
        if (
            config.leitura_mente
            and gatilho in GATILHOS_LEITURA
            and mao_jogador
            and self.rng.random() < config.chance_leitura
        ):
            carta = self.rng.choice(mao_jogador)
            return self.rng.choice(FRASES_LEITURA).format(carta=carta.nome_completo)

        banco = FRASES.get(gatilho)
        if not banco:
            return None
        return self.rng.choice(banco)


class RitmoFalas:
    """Cadência das falas no turno do jogador na fase 3 (R6.6).

    A primeira fala vem ATRASO_INICIAL_S depois de a decisão começar; as seguintes, a cada
    4–6 s sorteados. Nunca com outro balão na tela nem antes de INTERVALO_MIN_S desde a
    última fala. O tempo só passa por , chamado enquanto o timer do jogador corre.
    """

    ATRASO_INICIAL_S = 2.0
    INTERVALO_MIN_S = 4.0
    INTERVALO_MAX_S = 6.0

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.proxima: Optional[float] = None  # None = inativo
        self.desde_ultima: float = float("inf")

    @staticmethod
    def ativo_na_fase(config: ConfigFase) -> bool:
        """Só a última fase (A Leitura) fala durante o turno do jogador."""
        return config.numero >= 3

    @property
    def ativo(self) -> bool:
        return self.proxima is not None

    def iniciar_decisao(self) -> None:
        """Começa a contar para a primeira fala da decisão."""
        self.proxima = self.ATRASO_INICIAL_S

    def parar(self) -> None:
        self.proxima = None

    def registrar_fala(self) -> None:
        """Qualquer fala (de qualquer gatilho) reinicia o intervalo mínimo."""
        self.desde_ultima = 0.0

    def avancar(self, dt: float, balao_visivel: bool) -> bool:
        """Avança o relógio; True quando é hora de uma fala TURNO_JOGADOR."""
        if self.proxima is None:
            return False
        self.desde_ultima += dt
        self.proxima -= dt
        if self.proxima > 0 or balao_visivel or self.desde_ultima < self.INTERVALO_MIN_S:
            return False
        self.proxima = self.rng.uniform(self.INTERVALO_MIN_S, self.INTERVALO_MAX_S)
        self.desde_ultima = 0.0
        return True
