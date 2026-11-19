"""Grava um save pronto num cenário raro, para testar à mão ou gravar um vídeo.

Uso (da raiz do projeto):
    python tools/preparar_save.py --listar
    python tools/preparar_save.py diabo-11          # recusa se já houver save
    python tools/preparar_save.py fase2-tiros --forcar

Depois, abra o jogo e escolha **Continuar**. O save é montado pela própria `Campanha`
(`para_dict`) e gravado pelo `SaveManager`, então é um save válido como os do jogo.
"""

import argparse
import random
import sys
from pathlib import Path
from typing import Callable, Optional

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from core.campanha import Campanha  # noqa: E402
from core.card import Carta  # noqa: E402
from core.revolver import Tambor  # noqa: E402
from core.roleta import LoteTiros, OrigemTiro  # noqa: E402
from game.save_manager import SaveManager  # noqa: E402


def _campanha(indice_fase: int, rng: random.Random) -> Campanha:
    """Campanha na fase pedida, com a 1ª mão já distribuída."""
    c = Campanha.nova(rng)
    c.iniciar_fase(indice_fase)
    c.partida.iniciar_nova_rodada()
    return c


def _placar(c: Campanha, humano: int, diabo: int) -> None:
    p = c.partida
    p.pontos_jogador1 = c.humano.tentos = humano
    p.pontos_jogador2 = c.diabo.tentos = diabo


def _dar_mao(c: Campanha, humano: list[str], diabo: list[str]) -> None:
    """Troca as mãos distribuídas por mãos fixas, mantendo o baralho coerente."""
    p = c.partida
    c.humano.receber_cartas([Carta.de_id(i) for i in humano])
    c.diabo.receber_cartas([Carta.de_id(i) for i in diabo])
    usadas = set(c.humano.mao) | set(c.diabo.mao)
    p.baralho.reiniciar()
    p.baralho.cartas = [carta for carta in p.baralho.cartas if carta not in usadas]


def _bala_na_proxima(c: Campanha) -> None:
    """A próxima puxada dispara (bala na câmara atual)."""
    i = c.tambor.indice
    c.tambor = Tambor(c.tambor.camaras, [i], i)


def fase2_tiros(rng: random.Random) -> Campanha:
    """Fase 2 com 3 câmaras já puxadas e placar 5 × 7 (passo 3 do vídeo)."""
    c = _campanha(1, rng)
    _placar(c, 5, 7)
    c.tambor = Tambor(6, [rng.randint(3, 5)], 3)
    return c


def fase3(rng: random.Random) -> Campanha:
    """Início da fase 3 (abre pela introdução): timer de 6 s, leitura de mente e 2 balas."""
    c = Campanha.nova(rng)
    c.iniciar_fase(2)
    return c


def falta_envido(rng: random.Random) -> Campanha:
    """Falta Envido ganha por você e ainda não puxada: o Diabo puxa até a bala sair."""
    c = _campanha(0, rng)
    c.fila_lotes = [LoteTiros(c.humano, c.diabo, None, OrigemTiro.FALTA_ENVIDO)]
    return c


def diabo_11(rng: random.Random) -> Campanha:
    """Diabo com 11 tentos: qualquer tento dele (ex.: você ir ao baralho com B) leva ao tiro final."""
    c = _campanha(0, rng)
    _placar(c, 3, 11)
    return c


def humano_11(rng: random.Random) -> Campanha:
    """Você com 11 tentos e mão forte: vencer a mão encerra a fase por tentos."""
    c = _campanha(0, rng)
    _placar(c, 11, 4)
    _dar_mao(c, ["1_espadas", "1_bastos", "7_espadas"], ["4_copas", "5_ouros", "6_bastos"])
    return c


def bala_no_diabo(rng: random.Random) -> Campanha:
    """Lote de 1 puxada do Diabo contra ele mesmo, com a bala na câmara: você passa de fase."""
    c = _campanha(0, rng)
    _bala_na_proxima(c)
    c.fila_lotes = [LoteTiros(c.diabo, c.diabo, 1, OrigemTiro.RECUSA_TRUCO)]
    return c


def bala_em_mim(rng: random.Random) -> Campanha:
    """Lote de 1 puxada sua contra você, com a bala na câmara: você morre e o save some."""
    c = _campanha(0, rng)
    _bala_na_proxima(c)
    c.fila_lotes = [LoteTiros(c.humano, c.humano, 1, OrigemTiro.MAO_PERDIDA)]
    return c


def mao_com_flor(rng: random.Random) -> Campanha:
    """Você é mão com Flor e o Diabo sem: F gera 3 puxadas suas no Diabo (bala na última câmara)."""
    c = _campanha(0, rng)  # na 1ª rodada o humano é a mão
    _dar_mao(c, ["7_copas", "6_copas", "5_copas"], ["1_espadas", "2_bastos", "3_ouros"])
    c.tambor = Tambor(6, [5], 0)
    return c


CENARIOS: dict[str, Callable[[random.Random], Campanha]] = {
    "fase2-tiros": fase2_tiros,
    "fase3": fase3,
    "falta-envido": falta_envido,
    "diabo-11": diabo_11,
    "humano-11": humano_11,
    "bala-no-diabo": bala_no_diabo,
    "bala-em-mim": bala_em_mim,
    "mao-com-flor": mao_com_flor,
}


def montar(nome: str, semente: Optional[int] = None) -> Campanha:
    """Campanha do cenário (sem gravar)."""
    return CENARIOS[nome](random.Random(semente))


def gravar(nome: str, semente: Optional[int] = None) -> None:
    """Monta o cenário e grava no save do jogo."""
    SaveManager.salvar(montar(nome, semente).para_dict())


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cenario", nargs="?", choices=sorted(CENARIOS))
    parser.add_argument("--listar", action="store_true", help="mostra os cenários")
    parser.add_argument("--forcar", action="store_true", help="sobrescreve um save existente")
    parser.add_argument("--semente", type=int)
    args = parser.parse_args(argv)

    if args.listar or args.cenario is None:
        for nome, funcao in CENARIOS.items():
            print(f"  {nome:14} {funcao.__doc__}")
        return 0
    if SaveManager.existe() and not args.forcar:
        print("Já existe um save; use --forcar para sobrescrevê-lo.")
        return 1
    gravar(args.cenario, args.semente)
    print(f"Save '{args.cenario}' gravado. Abra o jogo e escolha Continuar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
