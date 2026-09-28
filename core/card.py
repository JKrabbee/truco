from dataclasses import dataclass
from enum import Enum


class Naipe(Enum):
    ESPADAS = ("Espadas", "⚔️", "#2C3E50")
    BASTOS = ("Bastos", "🪵", "#27AE60")
    OUROS = ("Ouros", "🪙", "#F1C40F")
    COPAS = ("Copas", "🏆", "#C0392B")

    def __init__(self, nome_exibicao: str, simbolo: str, cor: str):
        self.nome_exibicao = nome_exibicao
        self.simbolo = simbolo
        self.cor = cor

    def __str__(self) -> str:
        return self.nome_exibicao


VALORES_VALIDOS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)

NOMES_ESPECIAIS: dict[tuple[int, Naipe], str] = {
    (1, Naipe.ESPADAS): "Espadilha",
    (1, Naipe.BASTOS): "Bastilha",
    (7, Naipe.ESPADAS): "Manilha",
    (7, Naipe.OUROS): "Sete Belo",
}


@dataclass(frozen=True)
class Carta:
    valor_facial: int
    naipe: Naipe

    def __post_init__(self):
        if self.valor_facial not in VALORES_VALIDOS:
            raise ValueError(
                f"Valor facial inválido: {self.valor_facial}. Deve ser um dos valores: {VALORES_VALIDOS}"
            )

    @property
    def pontos_envido(self) -> int:
        """Pontuação da carta para cálculo de Envido e Flor."""
        if self.valor_facial <= 7:
            return self.valor_facial
        return 0

    @property
    def nome_completo(self) -> str:
        """Nome formatado da carta com nome especial quando aplicável."""
        nome_base = f"{self.valor_facial} de {self.naipe.nome_exibicao}"
        especial = NOMES_ESPECIAIS.get((self.valor_facial, self.naipe))
        if especial:
            return f"{nome_base} ({especial})"
        return nome_base

    def __str__(self) -> str:
        return self.nome_completo
