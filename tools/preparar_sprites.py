"""Prepara sprites gerados por IA (ou desenhados) para o jogo, só com pygame.

Uso (da raiz do projeto):
    python tools/preparar_sprites.py diabo gerado.png --expressao calmo
    python tools/preparar_sprites.py revolver gerado.png
    python tools/preparar_sprites.py mesa gerada.png
    python tools/preparar_sprites.py verso gerado.png
    python tools/preparar_sprites.py clarao gerado.png
    python tools/preparar_sprites.py --checar        # só confere o que já está em assets/

Cada tipo é recortado na proporção certa, redimensionado e gravado no caminho que o jogo lê
(design §10). Fundos:
- diabo e revólver: fundo chapado magenta (#FF00FF) vira transparente, com as bordas sem
  o tom rosado;
- clarão: fundo preto vira transparente (o brilho define o alfa);
- mesa e verso: opacos, sem chave.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pygame  # noqa: E402
from game.paths import ASSETS  # noqa: E402

EXPRESSOES = ("calmo", "falando", "irritado", "ferido")
MAGENTA = (255, 0, 255)


@dataclass(frozen=True)
class TipoSprite:
    """Como preparar e conferir um tipo de sprite."""

    tamanho: tuple[int, int]
    chave: Optional[str]  # "magenta" | "preto" | None (opaco)
    recorte: str  # "cobrir" (corta o excesso no centro) | "conteudo" (ajusta ao desenho)
    escala_nitida: bool = False  # pixel art que o jogo amplia com `scale`


TIPOS: dict[str, TipoSprite] = {
    "diabo": TipoSprite((360, 260), "magenta", "cobrir"),
    "revolver": TipoSprite((300, 140), "magenta", "conteudo"),  # proporção 150×70 do sprite
    "mesa": TipoSprite((1600, 1200), None, "cobrir"),
    "verso": TipoSprite((670, 1082), None, "cobrir", escala_nitida=True),  # como as cartas
    "clarao": TipoSprite((256, 256), "preto", "cobrir"),
}


def caminho_asset(tipo: str, expressao: str = "calmo") -> Path:
    """Onde o jogo procura o sprite (design §10)."""
    return {
        "diabo": ASSETS / "diabo" / f"{expressao}.png",
        "revolver": ASSETS / "revolver.png",
        "mesa": ASSETS / "mesa.png",
        "verso": ASSETS / "cards" / "verso.png",
        "clarao": ASSETS / "fx" / "clarao.png",
    }[tipo]


# ==========================
# RECORTE E ESCALA
# ==========================
def recortar_proporcao(surf: pygame.Surface, proporcao: float) -> pygame.Surface:
    """Corta o excesso nas bordas (centralizado) até a proporção largura/altura pedida."""
    w, h = surf.get_size()
    if w / h > proporcao:
        nova_w = round(h * proporcao)
        rect = pygame.Rect((w - nova_w) // 2, 0, nova_w, h)
    else:
        nova_h = round(w / proporcao)
        rect = pygame.Rect(0, (h - nova_h) // 2, w, nova_h)
    return surf.subsurface(rect).copy()


def ajustar_ao_conteudo(surf: pygame.Surface, proporcao: float, margem: float = 0.03) -> pygame.Surface:
    """Recorta no desenho (pixels com alfa) e completa com transparente até a proporção."""
    caixa = surf.get_bounding_rect(min_alpha=8)
    if caixa.width == 0 or caixa.height == 0:
        return surf
    desenho = surf.subsurface(caixa).copy()
    w, h = caixa.size
    w_final = max(w, round(h * proporcao))
    h_final = max(h, round(w_final / proporcao))
    w_final = round(h_final * proporcao)
    w_final, h_final = round(w_final * (1 + 2 * margem)), round(h_final * (1 + 2 * margem))
    final = pygame.Surface((w_final, h_final), pygame.SRCALPHA)
    final.blit(desenho, desenho.get_rect(center=(w_final // 2, h_final // 2)))
    return final


def escalar(surf: pygame.Surface, tamanho: tuple[int, int], nitida: bool) -> pygame.Surface:
    """`scale` (nítido) para pixel art ampliada pelo jogo; `smoothscale` no resto (32 bits)."""
    if nitida:
        return pygame.transform.scale(surf, tamanho)
    return pygame.transform.smoothscale(surf, tamanho)


# ==========================
# FUNDO -> TRANSPARENTE
# ==========================
def com_alfa(surf: pygame.Surface) -> pygame.Surface:
    """Cópia em 32 bits com canal alfa (sem precisar de janela)."""
    final = pygame.Surface(surf.get_size(), pygame.SRCALPHA, 32)
    final.blit(surf, (0, 0))
    return final


def tirar_magenta(surf: pygame.Surface, tolerancia: int) -> pygame.Surface:
    """Pixels perto do magenta ficam transparentes (rápido, em C, via mask)."""
    final = com_alfa(surf)
    mascara = pygame.mask.from_threshold(
        final, MAGENTA + (255,), (tolerancia, tolerancia, tolerancia, 255)
    )
    fundo = mascara.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
    # Onde a máscara marcou fundo, zera tudo (cor e alfa).
    final.blit(fundo, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    return final


def limpar_borda_magenta(surf: pygame.Surface) -> None:
    """Tira o tom rosado dos pixels de borda (vizinhos de transparente), já no tamanho final."""
    w, h = surf.get_size()
    alfas = [[surf.get_at((x, y)).a for x in range(w)] for y in range(h)]
    for y in range(h):
        for x in range(w):
            a = alfas[y][x]
            if a == 0:
                continue
            borda = a < 255 or any(
                alfas[ny][nx] < 255
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                if 0 <= nx < w and 0 <= ny < h
            )
            if not borda:
                continue
            r, g, b, _ = surf.get_at((x, y))
            excesso = min(r, b) - g
            if excesso > 0:
                surf.set_at((x, y), (r - excesso, g, b - excesso, a))


def preto_para_alfa(surf: pygame.Surface) -> pygame.Surface:
    """Fundo preto vira transparente: alfa = canal mais forte, cor desmultiplicada."""
    w, h = surf.get_size()
    final = pygame.Surface((w, h), pygame.SRCALPHA, 32)
    for y in range(h):
        for x in range(w):
            r, g, b, a0 = surf.get_at((x, y))
            a = max(r, g, b) * a0 // 255
            if a <= 3:
                continue
            k = 255 / max(r, g, b)
            final.set_at((x, y), (min(255, round(r * k)), min(255, round(g * k)), min(255, round(b * k)), a))
    return final


# ==========================
# PREPARAR
# ==========================
def preparar(tipo: str, entrada: Path, tolerancia: int = 90, recorte: Optional[str] = None) -> pygame.Surface:
    """Carrega a imagem gerada e devolve o sprite pronto no tamanho do jogo."""
    cfg = TIPOS[tipo]
    surf = pygame.image.load(str(entrada))
    proporcao = cfg.tamanho[0] / cfg.tamanho[1]
    modo = recorte or cfg.recorte

    surf = tirar_magenta(surf, tolerancia) if cfg.chave == "magenta" else com_alfa(surf)

    if modo == "conteudo" and cfg.chave == "magenta":
        surf = ajustar_ao_conteudo(surf, proporcao)
    else:
        surf = recortar_proporcao(surf, proporcao)

    surf = escalar(surf, cfg.tamanho, cfg.escala_nitida)
    if cfg.chave == "magenta":
        limpar_borda_magenta(surf)
    elif cfg.chave == "preto":
        surf = preto_para_alfa(surf)
    return surf


# ==========================
# CHECAGEM (usada também por tools/smoke_test.py --assets)
# ==========================
def _cantos_transparentes(surf: pygame.Surface) -> bool:
    w, h = surf.get_size()
    lado = max(2, min(w, h) // 40)
    for cx, cy in ((0, 0), (w - lado, 0), (0, h - lado), (w - lado, h - lado)):
        for y in range(cy, cy + lado):
            for x in range(cx, cx + lado):
                if surf.get_at((x, y)).a > 10:
                    return False
    return True


def checar(tipo: str, surf: pygame.Surface) -> list[str]:
    """Avisos sobre um sprite já carregado (lista vazia = dentro do combinado)."""
    cfg = TIPOS[tipo]
    avisos: list[str] = []
    w, h = surf.get_size()
    esperado = cfg.tamanho[0] / cfg.tamanho[1]
    if abs(w / h - esperado) / esperado > 0.05:
        avisos.append(f"proporção {w}×{h} difere de {cfg.tamanho[0]}×{cfg.tamanho[1]}; o jogo vai deformar")
    if cfg.chave is None:
        return avisos
    if not surf.get_flags() & pygame.SRCALPHA:
        surf = com_alfa(surf)
    if not _cantos_transparentes(surf):
        avisos.append("cantos opacos: o fundo não está transparente")
        return avisos
    caixa = surf.get_bounding_rect(min_alpha=40)
    if caixa.width == 0:
        avisos.append("imagem toda transparente")
        return avisos
    if tipo == "diabo":
        if caixa.top > h / 3:
            avisos.append("o desenho começa abaixo do terço de cima (chifres e rosto devem ficar no alto)")
        if caixa.width < w * 0.35:
            avisos.append("busto estreito demais (menos de 35% da largura)")
    elif tipo == "revolver":
        if caixa.right < w * 0.9:
            avisos.append("a boca do cano não chega à borda direita (o clarão sai fora do cano)")
        if caixa.width < w * 0.75:
            avisos.append("revólver pequeno demais para o quadro")
    elif tipo == "clarao":
        cx, cy = caixa.center
        if abs(cx - w / 2) > w * 0.1 or abs(cy - h / 2) > h * 0.1:
            avisos.append("clarão fora do centro (o jogo o centraliza na ponta do cano)")
    return avisos


def arquivos_presentes() -> list[tuple[str, Path]]:
    """(tipo, caminho) de cada sprite de IA que existe em assets/."""
    presentes = []
    for tipo in TIPOS:
        if tipo == "diabo":
            for e in EXPRESSOES:
                if caminho_asset(tipo, e).is_file():
                    presentes.append((tipo, caminho_asset(tipo, e)))
        elif caminho_asset(tipo).is_file():
            presentes.append((tipo, caminho_asset(tipo)))
    return presentes


def checar_assets() -> int:
    """Confere todos os sprites presentes; devolve o número de avisos."""
    total = 0
    presentes = arquivos_presentes()
    if not presentes:
        print("Nenhum sprite de IA em assets/ (o jogo usa os procedurais).")
    for tipo, caminho in presentes:
        try:
            avisos = checar(tipo, pygame.image.load(str(caminho)))
        except pygame.error as erro:
            avisos = [f"não carrega: {erro}"]
        total += len(avisos)
        rel = caminho.relative_to(RAIZ)
        print(f"[{'OK' if not avisos else 'AVISO'}] {rel}")
        for aviso in avisos:
            print(f"        - {aviso}")
    if any(t == "diabo" for t, _ in presentes) and not caminho_asset("diabo").is_file():
        print("[AVISO] há expressões do diabo sem o calmo.png: o jogo ignora todas.")
        total += 1
    return total


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tipo", nargs="?", choices=sorted(TIPOS))
    parser.add_argument("entrada", nargs="?", type=Path, help="imagem gerada pela IA")
    parser.add_argument("--expressao", choices=EXPRESSOES, default="calmo")
    parser.add_argument("--saida", type=Path, help="padrão: o caminho que o jogo lê")
    parser.add_argument("--recorte", choices=("cobrir", "conteudo"))
    parser.add_argument("--tolerancia", type=int, default=90, help="distância do magenta (0–255)")
    parser.add_argument("--checar", action="store_true", help="só confere os sprites em assets/")
    args = parser.parse_args(argv)

    pygame.init()
    if args.checar:
        return 1 if checar_assets() else 0
    if args.tipo is None or args.entrada is None:
        parser.error("informe o tipo e a imagem de entrada (ou use --checar)")

    surf = preparar(args.tipo, args.entrada, args.tolerancia, args.recorte)
    saida = args.saida or caminho_asset(args.tipo, args.expressao)
    saida.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(saida))
    print(f"Gravado {saida} ({surf.get_width()}×{surf.get_height()})")
    for aviso in checar(args.tipo, surf):
        print(f"  aviso: {aviso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
