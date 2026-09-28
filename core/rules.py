from enum import Enum
from typing import Optional, TYPE_CHECKING
from core.card import Carta, Naipe

if TYPE_CHECKING:
    from core.player import Jogador


class TipoEnvido(Enum):
    ENVIDO = "Envido"
    REAL_ENVIDO = "Real Envido"
    FALTA_ENVIDO = "Falta Envido"


class TipoTruco(Enum):
    TRUCO = ("Truco", 2)
    RETRUCO = ("Retruco", 3)
    VALE_QUATRO = ("Vale Quatro", 4)

    def __init__(self, nome: str, valor: int):
        self.nome_exibicao = nome
        self.valor = valor

    @property
    def proximo_nivel(self) -> Optional["TipoTruco"]:
        if self == TipoTruco.TRUCO:
            return TipoTruco.RETRUCO
        if self == TipoTruco.RETRUCO:
            return TipoTruco.VALE_QUATRO
        return None


class RespostaAposta(Enum):
    QUERO = "Quero"
    NAO_QUERO = "Não Quero"
    AUMENTAR = "Aumentar"


# Lookup table de pesos das cartas do Truco Gaudério (1 a 14)
# 14: 1 de Espadas (Espadilha)
# 13: 1 de Bastos (Bastilha)
# 12: 7 de Espadas (Manilha)
# 11: 7 de Ouros (Sete Belo)
# 10: Todos os 3s
# 9: Todos os 2s
# 8: 1 de Copas e 1 de Ouros
# 7: Todos os 12s
# 6: Todos os 11s
# 5: Todos os 10s
# 4: 7 de Bastos e 7 de Copas
# 3: Todos os 6s
# 2: Todos os 5s
# 1: Todos os 4s

_MANILHAS_PESOS: dict[tuple[int, Naipe], int] = {
    (1, Naipe.ESPADAS): 14,
    (1, Naipe.BASTOS): 13,
    (7, Naipe.ESPADAS): 12,
    (7, Naipe.OUROS): 11,
}

_VALORES_COMUNS_PESOS: dict[int, int] = {
    3: 10,
    2: 9,
    12: 7,
    11: 6,
    10: 5,
    6: 3,
    5: 2,
    4: 1,
}


def obter_peso_carta(carta: Carta) -> int:
    """Retorna a força da carta de 1 a 14 no Truco Gaudério."""
    # 1. Verifica se é manilha
    if (carta.valor_facial, carta.naipe) in _MANILHAS_PESOS:
        return _MANILHAS_PESOS[(carta.valor_facial, carta.naipe)]

    # 2. Ases comuns (Copas e Ouros)
    if carta.valor_facial == 1:
        return 8

    # 3. Setes comuns (Copas e Bastos)
    if carta.valor_facial == 7:
        return 4

    # 4. Demais cartas
    return _VALORES_COMUNS_PESOS[carta.valor_facial]


def comparar_cartas(carta1: Carta, carta2: Carta) -> int:
    """Compara duas cartas. Retorna 1 se carta1 > carta2, -1 se carta2 > carta1, 0 se empate."""
    peso1 = obter_peso_carta(carta1)
    peso2 = obter_peso_carta(carta2)
    if peso1 > peso2:
        return 1
    if peso2 > peso1:
        return -1
    return 0


class Vaza:
    """Representa uma das 3 vazas jogadas em uma mão."""

    def __init__(self, indice: int):
        self.indice = indice  # 1, 2 ou 3
        self.cartas_jogadas: list[tuple["Jogador", Carta]] = []
        self.vencedor: Optional["Jogador"] = None
        self.empate: bool = False

    def adicionar_jogada(self, jogador: "Jogador", carta: Carta) -> None:
        self.cartas_jogadas.append((jogador, carta))

    def resolver_vaza(self) -> Optional["Jogador"]:
        """Compara as cartas jogadas e define o vencedor ou canguçu (empate)."""
        if len(self.cartas_jogadas) < 2:
            return None

        j1, c1 = self.cartas_jogadas[0]
        j2, c2 = self.cartas_jogadas[1]
        resultado = comparar_cartas(c1, c2)

        if resultado == 1:
            self.vencedor = j1
            self.empate = False
        elif resultado == -1:
            self.vencedor = j2
            self.empate = False
        else:
            self.vencedor = None
            self.empate = True

        return self.vencedor


class Mao:
    """Gerencia a disputa de melhor de 3 vazas e a regra do Canguçu."""

    def __init__(self, jogador_mao: "Jogador", jogador_pe: "Jogador"):
        self.jogador_mao = jogador_mao
        self.jogador_pe = jogador_pe
        self.vazas: list[Vaza] = [Vaza(1), Vaza(2), Vaza(3)]
        self.indice_vaza_atual: int = 0
        self.vencedor: Optional["Jogador"] = None

    @property
    def vaza_atual(self) -> Optional[Vaza]:
        if self.indice_vaza_atual < len(self.vazas):
            return self.vazas[self.indice_vaza_atual]
        return None

    def avancar_vaza(self) -> None:
        self.indice_vaza_atual += 1

    def verificar_vencedor(self) -> Optional["Jogador"]:
        """
        Aplica as regras do Truco Gaudério / Canguçu:
        - 2 vitórias ganha.
        - Empate na 1ª vaza: quem ganhar a 2ª leva a mão.
        - Empate na 1ª e 2ª: quem ganhar a 3ª leva a mão.
        - Empate na 2ª ou 3ª: quem venceu a 1ª vaza leva a mão.
        - Empate nas 3: o 'mão' ganha.
        """
        vazas_resolvidas = [v for v in self.vazas if len(v.cartas_jogadas) == 2]
        num_resolvidas = len(vazas_resolvidas)
        if num_resolvidas == 0:
            return None

        v1 = vazas_resolvidas[0]
        v2 = vazas_resolvidas[1] if num_resolvidas >= 2 else None
        v3 = vazas_resolvidas[2] if num_resolvidas >= 3 else None

        # Cenário 1: 1ª vaza empatou (Canguçu na 1ª)
        if v1.empate:
            if v2 is None:
                return None
            if not v2.empate:
                self.vencedor = v2.vencedor
                return self.vencedor
            # Empatou 1ª e 2ª
            if v3 is None:
                return None
            if not v3.empate:
                self.vencedor = v3.vencedor
                return self.vencedor
            # Empatou as 3 vazas: prioridade do jogador que é 'mão'
            self.vencedor = self.jogador_mao
            return self.vencedor

        # Cenário 2: 1ª vaza teve vencedor
        w1 = v1.vencedor

        if v2 is None:
            return None

        # Se a 2ª vaza empatou: quem ganhou a 1ª leva imediatamente
        if v2.empate:
            self.vencedor = w1
            return self.vencedor

        w2 = v2.vencedor
        # Mesmo vencedor na 1ª e 2ª
        if w1 == w2:
            self.vencedor = w1
            return self.vencedor

        # Placar 1 a 1: precisa da 3ª vaza
        if v3 is None:
            return None

        # Se a 3ª vaza empatou: quem venceu a 1ª vaza leva
        if v3.empate:
            self.vencedor = w1
            return self.vencedor

        self.vencedor = v3.vencedor
        return self.vencedor


class CalculadorEnvidoFlor:
    """Cálculos e regras de pontuação para Flor e Envido."""

    @staticmethod
    def tem_flor(cartas: list[Carta]) -> bool:
        """Retorna True se as 3 cartas forem do mesmo naipe."""
        if len(cartas) != 3:
            return False
        return cartas[0].naipe == cartas[1].naipe == cartas[2].naipe

    @classmethod
    def calcular_pontos_flor(cls, cartas: list[Carta]) -> int:
        """Pontuação da flor: soma dos pontos_envido das 3 cartas + 20."""
        if not cls.tem_flor(cartas):
            return 0
        return sum(c.pontos_envido for c in cartas) + 20

    @classmethod
    def calcular_pontos_envido(cls, cartas: list[Carta]) -> int:
        """
        Calcula os pontos de Envido de acordo com as regras:
        - 2 cartas do mesmo naipe: soma pontos + 20.
        - 3 cartas do mesmo naipe (caso calcule sem flor): maior soma de par + 20.
        - Todas de naipes diferentes: maior carta individual (pontos_envido).
        """
        if not cartas:
            return 0

        # Agrupar por naipe
        cartas_por_naipe: dict[Naipe, list[Carta]] = {}
        for c in cartas:
            cartas_por_naipe.setdefault(c.naipe, []).append(c)

        maior_envido = 0
        teve_mesmo_naipe = False

        for naipe, grupo in cartas_por_naipe.items():
            if len(grupo) >= 2:
                teve_mesmo_naipe = True
                # Se tiver 3 cartas do mesmo naipe, pega as duas de maior ponto de envido
                pontos_ordenados = sorted(
                    (c.pontos_envido for c in grupo), reverse=True
                )
                pontos_par = pontos_ordenados[0] + pontos_ordenados[1] + 20
                if pontos_par > maior_envido:
                    maior_envido = pontos_par

        if teve_mesmo_naipe:
            return maior_envido

        # Todas de naipes diferentes: maior valor individual
        return max(c.pontos_envido for c in cartas)

    @classmethod
    def comparar_envido(
        cls,
        pontos1: int,
        jogador1: "Jogador",
        pontos2: int,
        jogador2: "Jogador",
        jogador_mao: "Jogador",
    ) -> tuple["Jogador", int]:
        """
        Compara os pontos de envido de dois jogadores.
        Em caso de empate, o jogador que for o 'mão' vence.
        Retorna (jogador_vencedor, pontos_vencedor).
        """
        if pontos1 > pontos2:
            return jogador1, pontos1
        if pontos2 > pontos1:
            return jogador2, pontos2
        # Empate: prioridade do mão
        if jogador1 == jogador_mao:
            return jogador1, pontos1
        return jogador2, pontos2
