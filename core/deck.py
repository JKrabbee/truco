import random
from core.card import Carta, Naipe, VALORES_VALIDOS


class Baralho:
    """Representa o baralho espanhol de 40 cartas para o Truco Gaudério."""

    def __init__(self):
        self.cartas: list[Carta] = []
        self.reiniciar()

    def reiniciar(self) -> None:
        """Recria o baralho com as 40 cartas padrão."""
        self.cartas = [
            Carta(valor, naipe) for naipe in Naipe for valor in VALORES_VALIDOS
        ]

    def embaralhar(self) -> None:
        """Embaralha aleatoriamente as cartas restantes."""
        random.shuffle(self.cartas)

    def comprar_carta(self) -> Carta:
        """Remove e retorna a carta do topo do baralho."""
        if not self.cartas:
            raise IndexError("O baralho está vazio.")
        return self.cartas.pop()

    def distribuir_mao(self, quantidade: int = 3) -> list[Carta]:
        """Distribui uma mão com a quantidade de cartas especificada (padrão 3)."""
        if len(self.cartas) < quantidade:
            raise ValueError(
                f"Cartas insuficientes ({len(self.cartas)}) para distribuir {quantidade} cartas."
            )
        return [self.comprar_carta() for _ in range(quantidade)]

    def __len__(self) -> int:
        return len(self.cartas)

    def __iter__(self):
        return iter(self.cartas)
