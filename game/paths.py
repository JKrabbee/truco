from pathlib import Path

# Caminhos absolutos, independentes do diretório de execução.
RAIZ = Path(__file__).resolve().parents[1]
ASSETS = RAIZ / "assets"
SAVE_DIR = RAIZ / "save"
SAVE_FILE = SAVE_DIR / "save.json"
