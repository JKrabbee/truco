# Truco Gaudério 2D

Jogo 2D do tradicional Truco Gaudério (baralho espanhol com manilhas fixas, Envido e Flor) contra IA, desenvolvido em Python utilizando **pygame-ce**.

## 🚀 Como executar

### Pré-requisitos
- Python 3.10 ou superior
- Git

### Passo a passo

1. **Clone o repositório:**
   ```bash
   git clone git@github.com:JKrabbee/truco.git
   cd truco
   ```

2. **Crie e ative o ambiente virtual:**
   - **Linux / macOS:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows:**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\activate
     ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Inicie o jogo:**
   ```bash
   python main.py
   ```

## 🎮 Como jogar

- **Jogar cartas**: Clique na carta desejada da sua mão para jogá-la na vaza.
- **Ações e cantos**: Use os botões na parte inferior para cantar Truco, Envido ou Flor, e para responder aos pedidos do adversário (Quero, Não Quero, Aumentar).
- **Objetivo**: A partida termina quando um dos jogadores atinge 12 tentos.

## 🛠️ Tecnologias

- [Python 3.12](https://www.python.org/)
- [pygame-ce](https://pyga.me/)
