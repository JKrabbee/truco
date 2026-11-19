from typing import Optional
from core.player import JogadorBot
from core.rules import TipoEnvido


class JogadorDiabo(JogadorBot):
    """O Diabo: a IA do JogadorBot com a taxa de blefe da fase.

    Recebe só o estado da mesa (obter_estado_mesa_para_jogador), nunca a mão do jogador.
    """

    def __init__(self, taxa_blefe: float):
        super().__init__(nome="O Diabo", taxa_blefe=taxa_blefe)

    def escolher_aumento_envido(self, atual: TipoEnvido) -> Optional[TipoEnvido]:
        """Aumento que o Diabo canta ao responder AUMENTAR (None se já está na Falta)."""
        return atual.proximo_nivel
