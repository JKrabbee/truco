import random
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Tambor:
    """Tambor do revólver: câmaras com bala em posições fixas, sem girar entre puxadas."""

    camaras: int
    balas: list[int]  # índices 0..camaras-1 com bala
    indice: int = 0  # próxima câmara a ser puxada

    @classmethod
    def carregar(
        cls, n_balas: int, camaras: int = 6, rng: Optional[random.Random] = None
    ) -> "Tambor":
        """Sorteia posições distintas para as balas."""
        if not 1 <= n_balas <= camaras:
            raise ValueError(f"Número de balas inválido: {n_balas} (câmaras: {camaras}).")
        rng = rng or random.Random()
        return cls(camaras, sorted(rng.sample(range(camaras), n_balas)))

    def puxar(self) -> bool:
        """Avança uma câmara; True se disparou."""
        if self.indice >= self.camaras:
            raise RuntimeError("Todas as câmaras já foram puxadas.")
        disparou = self.indice in self.balas
        self.indice += 1
        return disparou

    @property
    def disparadas(self) -> int:
        """Câmaras já puxadas, para o HUD ("3/6")."""
        return self.indice

    def para_dict(self) -> dict[str, Any]:
        return {"camaras": self.camaras, "balas": list(self.balas), "indice": self.indice}

    @classmethod
    def de_dict(cls, dados: dict[str, Any]) -> "Tambor":
        """Reconstrói o tambor validando a coerência das posições."""
        camaras = int(dados["camaras"])
        balas = sorted(int(b) for b in dados["balas"])
        indice = int(dados["indice"])
        if camaras < 1 or not balas or len(set(balas)) != len(balas):
            raise ValueError("Tambor inválido.")
        if any(not 0 <= b < camaras for b in balas):
            raise ValueError("Bala fora do tambor.")
        # Uma bala antes do índice já teria disparado e encerrado a fase.
        if not 0 <= indice <= balas[0]:
            raise ValueError(f"Índice de câmara inválido: {indice}")
        return cls(camaras, balas, indice)
