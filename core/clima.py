"""Clima da mesa sem pygame: curva da luz por fase (R2.2), humor do Diabo (R1.1)
e o ritmo do tique-taque do timer (R10.2).

A UI (`ui/iluminacao.py`, `ui/diabo_sprite.py`, `ui/timer_bar.py`) só desenha ou toca o que estas classes decidem,
para que o comportamento seja testável com pytest.
"""

import math
import random
from enum import Enum
from typing import Optional


class CurvaLuz:
    """Escurecimento extra da cena (alfa 0..255) e intensidade do foco, por `config.luz`.

    - "estavel": constante;
    - "oscila": senoide lenta;
    - "pisca": senoide mais rápida e quedas aleatórias curtas (80–150 ms), às vezes duplas.
    Só escurece: nunca clareia acima da luz base.
    """

    PERIODO_OSCILA_S = 3.5
    ALFA_OSCILA = 45
    VARIACAO_FOCO_OSCILA = 0.15

    PERIODO_PISCA_S = 2.0
    ALFA_PISCA = 35
    VARIACAO_FOCO_PISCA = 0.10
    ALFA_QUEDA = 150
    QUEDA_MIN_S = 0.08
    QUEDA_MAX_S = 0.15
    INTERVALO_QUEDA_MIN_S = 1.2
    INTERVALO_QUEDA_MAX_S = 3.5
    CHANCE_QUEDA_DUPLA = 0.30
    PAUSA_DUPLA_MIN_S = 0.06
    PAUSA_DUPLA_MAX_S = 0.10

    MODOS = ("estavel", "oscila", "pisca")

    def __init__(self, luz: str, rng: Optional[random.Random] = None):
        if luz not in self.MODOS:
            raise ValueError(f"luz desconhecida: {luz!r}")
        self.luz = luz
        self.rng = rng or random.Random()
        self.tempo = 0.0
        # Quedas (só "pisca"): tempo até a próxima, duração restante e se vem outra logo após.
        self.ate_proxima_queda = self._sortear_intervalo()
        self.queda_restante = 0.0
        self.dupla_pendente = False
        self.proxima_eh_segunda = False

    def _sortear_intervalo(self) -> float:
        return self.rng.uniform(self.INTERVALO_QUEDA_MIN_S, self.INTERVALO_QUEDA_MAX_S)

    def _iniciar_queda(self) -> None:
        self.queda_restante = self.rng.uniform(self.QUEDA_MIN_S, self.QUEDA_MAX_S)

    def avancar(self, dt: float) -> None:
        self.tempo += dt
        if self.luz != "pisca":
            return
        restante = dt
        # Consome o dt em etapas, para um quadro longo não pular uma queda inteira.
        while restante > 0:
            if self.queda_restante > 0:
                passo = min(restante, self.queda_restante)
                self.queda_restante -= passo
                restante -= passo
                if self.queda_restante <= 0:
                    self.queda_restante = 0.0
                    if self.dupla_pendente:
                        # A segunda queda da dupla vem logo depois.
                        self.dupla_pendente = False
                        self.proxima_eh_segunda = True
                        self.ate_proxima_queda = self.rng.uniform(
                            self.PAUSA_DUPLA_MIN_S, self.PAUSA_DUPLA_MAX_S
                        )
                    else:
                        self.ate_proxima_queda = self._sortear_intervalo()
            else:
                passo = min(restante, self.ate_proxima_queda)
                self.ate_proxima_queda -= passo
                restante -= passo
                if self.ate_proxima_queda <= 0:
                    if self.proxima_eh_segunda:
                        self.proxima_eh_segunda = False
                    else:
                        self.dupla_pendente = self.rng.random() < self.CHANCE_QUEDA_DUPLA
                    self._iniciar_queda()

    def _onda(self, periodo: float) -> float:
        """0..1, começando no 0 (luz cheia)."""
        return 0.5 - 0.5 * math.cos(2 * math.pi * self.tempo / periodo)

    @property
    def em_queda(self) -> bool:
        return self.queda_restante > 0

    @property
    def escurecimento(self) -> int:
        """Alfa (0..255) de uma camada preta sobre a cena."""
        if self.luz == "oscila":
            return round(self.ALFA_OSCILA * self._onda(self.PERIODO_OSCILA_S))
        if self.luz == "pisca":
            if self.em_queda:
                return self.ALFA_QUEDA
            return round(self.ALFA_PISCA * self._onda(self.PERIODO_PISCA_S))
        return 0

    @property
    def foco(self) -> float:
        """Intensidade do foco de luz sobre a mesa (1.0 = cheio)."""
        if self.luz == "oscila":
            return 1.0 - self.VARIACAO_FOCO_OSCILA * self._onda(self.PERIODO_OSCILA_S)
        if self.luz == "pisca":
            if self.em_queda:
                return 0.0
            return 1.0 - self.VARIACAO_FOCO_PISCA * self._onda(self.PERIODO_PISCA_S)
        return 1.0


class Expressao(Enum):
    """Expressões do busto; o valor é o nome do PNG em assets/diabo/."""

    CALMO = "calmo"
    FALANDO = "falando"
    IRRITADO = "irritado"
    FERIDO = "ferido"


class HumorDiabo:
    """Escolhe a expressão do Diabo com prioridade ferido > irritado > falando > calmo.

    - `ferir()`: a bala o acertou; vale até a troca de tela;
    - `irritar()`: irritação temporária (ex.: o humano sobreviveu a um tiro);
    - `contrariado` em `expressao`: irritação contínua dada pelo contexto
      (ex.: um lote em que ele é o alvo, ou a mesa perdida por tentos).
    """

    DURACAO_IRRITADO_S = 2.0

    def __init__(self) -> None:
        self.ferido = False
        self.irritado_restante = 0.0

    def ferir(self) -> None:
        self.ferido = True

    def irritar(self, duracao: Optional[float] = None) -> None:
        d = self.DURACAO_IRRITADO_S if duracao is None else duracao
        self.irritado_restante = max(self.irritado_restante, d)

    def avancar(self, dt: float) -> None:
        self.irritado_restante = max(0.0, self.irritado_restante - dt)

    def expressao(self, falando: bool, contrariado: bool = False) -> Expressao:
        if self.ferido:
            return Expressao.FERIDO
        if contrariado or self.irritado_restante > 0:
            return Expressao.IRRITADO
        if falando:
            return Expressao.FALANDO
        return Expressao.CALMO


class RitmoTique:
    """Tique-taque dos últimos segundos do timer (R10.2), acelerando até o zero.

    Silêncio até faltarem ULTIMOS_S; aí o primeiro tique sai na hora e o intervalo
    cai linearmente de INTERVALO_INICIAL_S a INTERVALO_FINAL_S (~10 tiques em 3 s).
    A intensidade (0..1, para o volume) cresce de INTENSIDADE_MIN a 1.0.
    """

    ULTIMOS_S = 3.0
    INTERVALO_INICIAL_S = 0.5
    INTERVALO_FINAL_S = 0.15
    INTENSIDADE_MIN = 0.5

    def __init__(self) -> None:
        self.ate_proximo: Optional[float] = None  # None = ainda fora da janela

    def reiniciar(self) -> None:
        """Nova decisão: volta ao silêncio."""
        self.ate_proximo = None

    @classmethod
    def _fracao(cls, restante: float) -> float:
        """0 no começo da janela, 1 no zero."""
        return 1.0 - max(0.0, min(1.0, restante / cls.ULTIMOS_S))

    @classmethod
    def intervalo(cls, restante: float) -> float:
        f = cls._fracao(restante)
        return cls.INTERVALO_INICIAL_S + (cls.INTERVALO_FINAL_S - cls.INTERVALO_INICIAL_S) * f

    @classmethod
    def intensidade(cls, restante: float) -> float:
        return cls.INTENSIDADE_MIN + (1.0 - cls.INTENSIDADE_MIN) * cls._fracao(restante)

    def avancar(self, dt: float, restante: float) -> Optional[float]:
        """Avança o relógio; devolve a intensidade quando é hora de um tique, senão None.

        No máximo um tique por chamada; com o tempo esgotado, não toca.
        """
        if restante > self.ULTIMOS_S:
            self.ate_proximo = None
            return None
        if restante <= 0:
            return None
        if self.ate_proximo is None:
            self.ate_proximo = self.intervalo(restante)
            return self.intensidade(restante)
        self.ate_proximo -= dt
        if self.ate_proximo > 0:
            return None
        self.ate_proximo += self.intervalo(restante)
        if self.ate_proximo <= 0:
            # Um quadro longo não acumula tiques atrasados: recomeça o intervalo.
            self.ate_proximo = self.intervalo(restante)
        return self.intensidade(restante)
