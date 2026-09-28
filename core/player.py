import random
from abc import ABC, abstractmethod
from typing import Any, Optional
from core.card import Carta
from core.rules import (
    CalculadorEnvidoFlor,
    RespostaAposta,
    TipoTruco,
    TipoEnvido,
    obter_peso_carta,
)


class Jogador(ABC):
    """Classe base abstrata para todos os jogadores do Truco."""

    def __init__(self, nome: str):
        self.nome = nome
        self.mao: list[Carta] = []
        self.tentos: int = 0

    def receber_cartas(self, novas_cartas: list[Carta]) -> None:
        """Atribui novas cartas à mão do jogador."""
        self.mao = list(novas_cartas)

    def remover_carta(self, carta: Carta) -> Carta:
        """Remove e retorna a carta jogada da mão."""
        if carta not in self.mao:
            raise ValueError(f"Carta {carta} não está na mão de {self.nome}.")
        self.mao.remove(carta)
        return carta

    def tem_flor(self) -> bool:
        """Verifica se o jogador possui flor."""
        return CalculadorEnvidoFlor.tem_flor(self.mao)

    @property
    def pontos_envido(self) -> int:
        """Calcula os pontos de envido com as cartas atuais."""
        return CalculadorEnvidoFlor.calcular_pontos_envido(self.mao)

    @property
    def pontos_flor(self) -> int:
        """Calcula os pontos de flor caso tenha flor."""
        return CalculadorEnvidoFlor.calcular_pontos_flor(self.mao)

    @abstractmethod
    def decidir_jogada(self, estado_mesa: dict[str, Any]) -> Carta:
        """Define qual carta jogar com base no estado atual da mesa."""
        pass

    @abstractmethod
    def responder_aposta(
        self, tipo_aposta: Any, estado_mesa: dict[str, Any]
    ) -> RespostaAposta:
        """Responde a uma aposta (Truco ou Envido)."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(nome='{self.nome}', tentos={self.tentos})"


class JogadorHumano(Jogador):
    """Jogador controlado por um ser humano via interface gráfica."""

    def __init__(self, nome: str = "Você"):
        super().__init__(nome)
        self.acao_pendente: Optional[Carta] = None
        self.resposta_aposta_pendente: Optional[RespostaAposta] = None

    def definir_jogada(self, carta: Carta) -> None:
        """Armazena a carta selecionada pelo usuário na UI."""
        self.acao_pendente = carta

    def definir_resposta_aposta(self, resposta: RespostaAposta) -> None:
        """Armazena a resposta de aposta do usuário."""
        self.resposta_aposta_pendente = resposta

    def decidir_jogada(self, estado_mesa: dict[str, Any]) -> Carta:
        if self.acao_pendente is not None and self.acao_pendente in self.mao:
            carta = self.acao_pendente
            self.acao_pendente = None
            return carta
        raise RuntimeError("Nenhuma jogada foi selecionada pelo jogador humano.")

    def responder_aposta(
        self, tipo_aposta: Any, estado_mesa: dict[str, Any]
    ) -> RespostaAposta:
        if self.resposta_aposta_pendente is not None:
            resp = self.resposta_aposta_pendente
            self.resposta_aposta_pendente = None
            return resp
        raise RuntimeError(
            "Nenhuma resposta de aposta selecionada pelo jogador humano."
        )


class JogadorBot(Jogador):
    """IA do oponente para o Truco Gaudério com heurísticas e blefe."""

    def __init__(self, nome: str = "Gaudério Bot", taxa_blefe: float = 0.12):
        super().__init__(nome)
        self.taxa_blefe = taxa_blefe

    def decidir_jogada(self, estado_mesa: dict[str, Any]) -> Carta:
        if not self.mao:
            raise IndexError(f"{self.nome} não possui cartas na mão.")

        # Ordenar cartas da mão por força (do menor para o maior peso)
        cartas_ordenadas = sorted(self.mao, key=obter_peso_carta)

        vaza_atual = estado_mesa.get("indice_vaza", 1)
        carta_oponente = estado_mesa.get("carta_oponente_na_vaza")
        resultado_vaza_1 = estado_mesa.get(
            "resultado_vaza_1"
        )  # 'venceu', 'perdeu', 'empatou'

        # 3ª Vaza: só tem 1 carta (ou joga a mais forte restante)
        if vaza_atual == 3 or len(cartas_ordenadas) == 1:
            return cartas_ordenadas[-1]

        # 1ª Vaza
        if vaza_atual == 1:
            if carta_oponente is None:
                # É o primeiro a jogar: se tem 3 cartas, joga a média para disputar iniciativa sem gastar a mais alta
                if len(cartas_ordenadas) >= 2:
                    return cartas_ordenadas[1]
                return cartas_ordenadas[-1]
            else:
                # Oponente já jogou: tenta matar com a menor carta possível
                peso_oponente = obter_peso_carta(carta_oponente)
                cartas_que_matam = [
                    c for c in cartas_ordenadas if obter_peso_carta(c) > peso_oponente
                ]
                if cartas_que_matam:
                    return cartas_que_matam[0]  # Menor carta que mata
                # Não mata: descarta a mais fraca
                return cartas_ordenadas[0]

        # 2ª Vaza
        if vaza_atual == 2:
            if carta_oponente is None:
                # Primeiro a jogar na 2ª vaza
                if resultado_vaza_1 == "venceu":
                    # Se ganhou a primeira, entra com a mais forte para tentar fechar 2x0
                    return cartas_ordenadas[-1]
                elif resultado_vaza_1 == "empatou":
                    # Canguçu na 1ª: quem levar a 2ª leva a mão, joga a mais forte
                    return cartas_ordenadas[-1]
                else:
                    # Perdeu a 1ª: precisa vencer a 2ª para sobreviver
                    return cartas_ordenadas[-1]
            else:
                peso_oponente = obter_peso_carta(carta_oponente)
                cartas_que_matam = [
                    c for c in cartas_ordenadas if obter_peso_carta(c) > peso_oponente
                ]
                if cartas_que_matam:
                    # Se matar, joga para matar (ou empatar se necessário)
                    return cartas_que_matam[0]
                # Se não mata, joga a mais baixa (ou a única que tem)
                return cartas_ordenadas[0]

        return cartas_ordenadas[0]

    def responder_aposta(
        self, tipo_aposta: Any, estado_mesa: dict[str, Any]
    ) -> RespostaAposta:
        """Decisão de resposta de Truco ou Envido."""
        # Se for aposta de Envido
        if isinstance(tipo_aposta, TipoEnvido) or str(tipo_aposta).startswith("Envido"):
            pontos = self.pontos_envido
            # 28+ é muito bom no Envido
            if pontos >= 28:
                if pontos >= 31 and random.random() < 0.4:
                    return RespostaAposta.AUMENTAR
                return RespostaAposta.QUERO
            elif pontos >= 24:
                return (
                    RespostaAposta.QUERO
                    if random.random() < 0.65
                    else RespostaAposta.NAO_QUERO
                )
            else:
                # Pontuação baixa: blefe ocasional
                if random.random() < self.taxa_blefe:
                    return RespostaAposta.QUERO
                return RespostaAposta.NAO_QUERO

        # Se for aposta de Truco / Retruco / Vale Quatro
        pesos = [obter_peso_carta(c) for c in self.mao]
        peso_medio = sum(pesos) / len(pesos) if pesos else 0

        # Chance de blefe
        blefe = random.random() < self.taxa_blefe

        if tipo_aposta == TipoTruco.TRUCO:
            if peso_medio >= 9.0 or (pesos and max(pesos) >= 12):
                if peso_medio >= 11.0 and random.random() < 0.5:
                    return RespostaAposta.AUMENTAR
                return RespostaAposta.QUERO
            elif peso_medio >= 6.0:
                return (
                    RespostaAposta.QUERO
                    if random.random() < 0.70
                    else RespostaAposta.NAO_QUERO
                )
            else:
                return RespostaAposta.QUERO if blefe else RespostaAposta.NAO_QUERO

        elif tipo_aposta == TipoTruco.RETRUCO:
            if peso_medio >= 10.0 or (pesos and max(pesos) >= 13):
                if peso_medio >= 12.0 and random.random() < 0.35:
                    return RespostaAposta.AUMENTAR
                return RespostaAposta.QUERO
            elif peso_medio >= 7.5:
                return (
                    RespostaAposta.QUERO
                    if random.random() < 0.55
                    else RespostaAposta.NAO_QUERO
                )
            else:
                return RespostaAposta.QUERO if blefe else RespostaAposta.NAO_QUERO

        elif tipo_aposta == TipoTruco.VALE_QUATRO:
            if peso_medio >= 11.0 or (pesos and max(pesos) == 14):
                return RespostaAposta.QUERO
            return RespostaAposta.QUERO if blefe else RespostaAposta.NAO_QUERO

        return RespostaAposta.QUERO

    def quer_pedir_truco(self, nivel_atual: Optional[TipoTruco]) -> bool:
        """Heurística para o Bot tomar iniciativa de pedir Truco/Aumento."""
        if not self.mao:
            return False
        pesos = [obter_peso_carta(c) for c in self.mao]
        peso_medio = sum(pesos) / len(pesos)

        # Se tem manilha ou cartas altas
        if nivel_atual is None:
            if peso_medio >= 8.5 or max(pesos) >= 12:
                return random.random() < 0.65
            return random.random() < self.taxa_blefe
        elif nivel_atual == TipoTruco.TRUCO:
            if peso_medio >= 10.5 or max(pesos) >= 13:
                return random.random() < 0.50
            return random.random() < (self.taxa_blefe * 0.5)
        return False
