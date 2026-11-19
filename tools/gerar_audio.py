"""Gera os efeitos e as trilhas procedurais do jogo, só com a biblioteca padrão.

Uso (da raiz do projeto):
    python tools/gerar_audio.py                 # efeitos e música em assets/
    python tools/gerar_audio.py --so-efeitos
    python tools/gerar_audio.py --saida /tmp/x  # outra pasta (cria sfx/ e music/)

Efeitos: assets/sfx/{disparo,clique_vazio,engatilhar,tique,carta,risada}.wav (versionados).
Música: assets/music/fase{1,2,3}.wav, um drone em loop com batida de coração, já na
velocidade da fase (1.0×, 1.15×, 1.3×). Fica fora do git (`assets/music/` no .gitignore).
Uma faixa real em `fase{n}.ogg` tem prioridade sobre a gerada (game/audio.py).
"""

import argparse
import math
import random
import struct
import sys
import wave
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from core.fase import FASES  # noqa: E402

TAXA = 22050
DOIS_PI = 2 * math.pi


# ==========================
# BLOCOS BÁSICOS
# ==========================
def silencio(segundos: float) -> list[float]:
    return [0.0] * int(segundos * TAXA)


def ruido(n: int, rng: random.Random) -> list[float]:
    return [rng.uniform(-1.0, 1.0) for _ in range(n)]


def passa_baixa(x: list[float], corte_hz: float) -> list[float]:
    """Filtro de um polo."""
    a = math.exp(-DOIS_PI * corte_hz / TAXA)
    y, saida = 0.0, []
    for v in x:
        y = (1 - a) * v + a * y
        saida.append(y)
    return saida


def passa_alta(x: list[float], corte_hz: float) -> list[float]:
    baixa = passa_baixa(x, corte_hz)
    return [v - b for v, b in zip(x, baixa)]


def passa_banda(x: list[float], centro_hz: float, q: float) -> list[float]:
    """Biquad passa-banda (RBJ, ganho 0 dB no pico)."""
    w0 = DOIS_PI * centro_hz / TAXA
    alfa = math.sin(w0) / (2 * q)
    b0, b2 = alfa, -alfa
    a0, a1, a2 = 1 + alfa, -2 * math.cos(w0), 1 - alfa
    x1 = x2 = y1 = y2 = 0.0
    saida = []
    for v in x:
        y = (b0 * v + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1 = x1, v
        y2, y1 = y1, y
        saida.append(y)
    return saida


def somar(base: list[float], sinal: list[float], inicio_s: float, ganho: float = 1.0) -> None:
    """Mistura `sinal` em `base` a partir de `inicio_s` (corta o que passar do fim)."""
    i0 = int(inicio_s * TAXA)
    for i, v in enumerate(sinal):
        j = i0 + i
        if j >= len(base):
            break
        base[j] += v * ganho


def somar_em_loop(base: list[float], sinal: list[float], inicio: int, ganho: float) -> None:
    """Como `somar`, mas o que passa do fim volta ao começo (loop sem emenda)."""
    n = len(base)
    for i, v in enumerate(sinal):
        base[(inicio + i) % n] += v * ganho


def normalizar(x: list[float], pico: float) -> list[float]:
    maior = max((abs(v) for v in x), default=0.0)
    return x if maior == 0 else [v * pico / maior for v in x]


def gravar_wav(caminho: Path, amostras: list[float]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(
            b"".join(struct.pack("<h", int(max(-1.0, min(1.0, v)) * 32767)) for v in amostras)
        )


def estalo(rng: random.Random, freq: float, tau_ruido: float, tau_anel: float, dur: float) -> list[float]:
    """Estalo metálico: ruído curto agudo + um anel senoidal amortecido."""
    n = int(dur * TAXA)
    r = passa_alta(ruido(n, rng), 1500)
    return [
        r[i] * math.exp(-(i / TAXA) / tau_ruido)
        + 0.5 * math.sin(DOIS_PI * freq * i / TAXA) * math.exp(-(i / TAXA) / tau_anel)
        for i in range(n)
    ]


# ==========================
# EFEITOS (R11.2)
# ==========================
def efeito_disparo(rng: random.Random) -> list[float]:
    n = int(0.9 * TAXA)
    r = ruido(n, rng)
    estouro = passa_alta(r, 800)
    corpo = passa_baixa(r, 900)
    cauda = passa_baixa(r, 350)
    saida, fase = [], 0.0
    for i in range(n):
        t = i / TAXA
        fase += DOIS_PI * (50 + 110 * math.exp(-t / 0.03)) / TAXA  # baque que despenca
        ataque = min(1.0, t / 0.001)
        saida.append(
            ataque
            * (
                estouro[i] * math.exp(-t / 0.025)
                + 1.6 * corpo[i] * math.exp(-t / 0.16)
                + 0.9 * math.sin(fase) * math.exp(-t / 0.12)
                + 0.5 * cauda[i] * math.exp(-t / 0.35)
            )
        )
    return normalizar([math.tanh(1.8 * v) for v in saida], 0.95)


def efeito_clique_vazio(rng: random.Random) -> list[float]:
    base = silencio(0.25)
    somar(base, estalo(rng, 2600, 0.004, 0.025, 0.12), 0.0, 1.0)
    somar(base, estalo(rng, 1800, 0.003, 0.018, 0.10), 0.035, 0.55)
    return normalizar(base, 0.9)


def efeito_engatilhar(rng: random.Random) -> list[float]:
    base = silencio(0.45)
    for t in (0.0, 0.06, 0.12):  # catraca do tambor girando
        somar(base, estalo(rng, 3200, 0.002, 0.01, 0.05), t, 0.4)
    somar(base, estalo(rng, 1400, 0.005, 0.03, 0.15), 0.25, 1.0)  # o cão arma
    somar(base, estalo(rng, 1100, 0.004, 0.02, 0.12), 0.272, 0.6)
    return normalizar(base, 0.9)


def efeito_tique(rng: random.Random) -> list[float]:
    n = int(0.06 * TAXA)
    r = passa_alta(ruido(n, rng), 2000)
    return normalizar(
        [
            0.6 * r[i] * math.exp(-(i / TAXA) / 0.002)
            + math.sin(DOIS_PI * 1800 * i / TAXA) * math.exp(-(i / TAXA) / 0.010)
            + 0.6 * math.sin(DOIS_PI * 900 * i / TAXA) * math.exp(-(i / TAXA) / 0.012)
            for i in range(n)
        ],
        0.9,
    )


def efeito_carta(rng: random.Random) -> list[float]:
    n = int(0.22 * TAXA)
    r = ruido(n, rng)
    chiado = passa_alta(passa_baixa(r, 5000), 1200)
    baque = passa_baixa(r, 300)
    saida = []
    for i in range(n):
        t = i / TAXA
        env = min(1.0, t / 0.015) * math.exp(-max(0.0, t - 0.015) / 0.05)
        saida.append(chiado[i] * env + 1.5 * baque[i] * math.exp(-t / 0.03))
    return normalizar(saida, 0.8)


def _silaba(rng: random.Random, f0_ini: float, f0_fim: float, dur: float) -> list[float]:
    """Um "ha": aspiração curta + voz grave (dente de serra com subharmônico)."""
    n = int(dur * TAXA)
    voz, fase, fase_sub = [], 0.0, 0.0
    for i in range(n):
        t = i / TAXA
        f0 = f0_ini + (f0_fim - f0_ini) * (t / dur)
        f0 *= 1 + 0.02 * math.sin(DOIS_PI * 6 * t)  # vibrato
        fase += DOIS_PI * f0 / TAXA
        fase_sub += DOIS_PI * f0 / 2 / TAXA
        serra = sum(math.sin(k * fase) / k for k in range(1, 13))
        voz.append(serra + 0.35 * math.sin(fase_sub))
    # Formantes de "a" (700 e 1200 Hz) e um pouco do corpo grave.
    vogal = [
        a + 0.7 * b + 0.25 * c
        for a, b, c in zip(passa_banda(voz, 700, 4), passa_banda(voz, 1200, 5), voz)
    ]
    sopro = passa_alta(ruido(n, rng), 900)
    saida = []
    for i in range(n):
        t = i / TAXA
        env = min(1.0, t / 0.03) * min(1.0, (dur - t) / 0.06)
        h = math.exp(-t / 0.03)  # o "h" do começo
        saida.append(env * ((1 - 0.6 * h) * vogal[i] + 0.5 * h * sopro[i]))
    return saida


def efeito_risada(rng: random.Random) -> list[float]:
    base = silencio(1.75)
    inicios = (0.0, 0.23, 0.45, 0.66, 0.86)
    for k, t in enumerate(inicios):
        f = 135 - 11 * k
        somar(base, _silaba(rng, f, f - 12, 0.18), t, 1.0 - 0.08 * k)
    somar(base, _silaba(rng, 88, 58, 0.62), 1.08, 0.85)  # o "haaa" final, descendo
    return normalizar([math.tanh(1.5 * v) for v in normalizar(base, 1.0)], 0.9)


EFEITOS = {
    "disparo": efeito_disparo,
    "clique_vazio": efeito_clique_vazio,
    "engatilhar": efeito_engatilhar,
    "tique": efeito_tique,
    "carta": efeito_carta,
    "risada": efeito_risada,
}


# ==========================
# MÚSICA (R11.1)
# ==========================
BATIDAS_LOOP = 32


def _batimento(dur: float) -> list[float]:
    n = int(dur * TAXA)
    return [
        math.sin(DOIS_PI * (45 + 30 * math.exp(-(i / TAXA) / 0.02)) * i / TAXA)
        * math.exp(-(i / TAXA) / 0.08)
        for i in range(n)
    ]


def musica_fase(numero: int, velocidade: float, rng: random.Random) -> list[float]:
    """Loop de BATIDAS_LOOP batidas a 60·velocidade bpm, sem emenda audível.

    Toda senoide tem um número inteiro de ciclos no loop, e as batidas que passam
    do fim voltam ao começo.
    """
    batida = 1.0 / velocidade
    n = int(round(BATIDAS_LOOP * batida * TAXA))
    duracao = n / TAXA

    def q(freq: float) -> float:
        """Frequência ajustada para fechar o loop."""
        return max(1, round(freq * duracao)) / duracao

    # Drone: lá grave + quinta + oitava; da fase 2 em diante, uma segunda menor que bate.
    parciais = [(q(55.0), 1.0), (q(82.4), 0.45), (q(110.0), 0.3)]
    if numero >= 2:
        parciais.append((q(58.3), 0.35))
    if numero >= 3:
        parciais.append((q(155.6), 0.12))  # trítono agudo
    lfo = q(1.0 / (8 * batida))
    agudo = q(880.0 * (2 ** (1 / 12)))  # nota alta e dissonante, crescendo a cada 16 batidas
    inchaco = q(1.0 / (16 * batida))

    saida = []
    for i in range(n):
        t = i / TAXA
        drone = sum(a * math.sin(DOIS_PI * f * t) for f, a in parciais)
        drone *= 0.65 + 0.35 * math.sin(DOIS_PI * lfo * t)
        v = 0.5 * drone
        if numero >= 2:
            v += 0.05 * math.sin(DOIS_PI * agudo * t) * (0.5 - 0.5 * math.cos(DOIS_PI * inchaco * t))
        saida.append(v)

    # Vento: ruído grave bem baixo.
    vento = passa_baixa(ruido(n, rng), 220)
    for i in range(n):
        saida[i] += 0.6 * vento[i]

    # Coração ("tum-tum") a cada batida; mais forte nas fases altas.
    tum = _batimento(0.35)
    ganho = {1: 0.35, 2: 0.5, 3: 0.65}.get(numero, 0.5)
    for b in range(BATIDAS_LOOP):
        inicio = int(b * batida * TAXA)
        somar_em_loop(saida, tum, inicio, ganho)
        somar_em_loop(saida, tum, inicio + int(0.28 * batida * TAXA), ganho * 0.65)

    # Fase 3: tique metálico nos contratempos.
    if numero >= 3:
        chiado = passa_alta(ruido(int(0.04 * TAXA), rng), 4000)
        tique = [v * math.exp(-(i / TAXA) / 0.008) for i, v in enumerate(chiado)]
        for b in range(BATIDAS_LOOP):
            somar_em_loop(saida, tique, int((b + 0.5) * batida * TAXA), 0.18)

    return normalizar(saida, 0.8)


# ==========================
# CLI
# ==========================
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saida", type=Path, default=RAIZ / "assets", help="pasta base (sfx/ e music/)")
    parser.add_argument("--so-efeitos", action="store_true")
    parser.add_argument("--so-musica", action="store_true")
    args = parser.parse_args(argv)

    rng = random.Random(666)  # reprodutível
    if not args.so_musica:
        for nome, gerar in EFEITOS.items():
            caminho = args.saida / "sfx" / f"{nome}.wav"
            gravar_wav(caminho, gerar(rng))
            print(f"efeito  {caminho}")
    if not args.so_efeitos:
        for config in FASES:
            caminho = args.saida / "music" / f"fase{config.numero}.wav"
            gravar_wav(caminho, musica_fase(config.numero, config.velocidade_musica, rng))
            print(f"música  {caminho}  ({config.velocidade_musica:.2f}×)")


if __name__ == "__main__":
    main()
