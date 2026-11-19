# Truco contra o Diabo

Truco Gaudério (baralho espanhol de 40 cartas, manilhas fixas, Envido e Flor) jogado numa mesa à luz de vela contra **o Diabo**. Cada aposta perdida vira puxadas de gatilho num revólver com bala no tambor. São três fases, cada uma mais rápida e mais escura que a anterior. Feito em Python com **pygame-ce**.

## Como executar

### Pré-requisitos
- Python 3.10 ou superior
- pygame-ce 2.5 ou superior (instalado pelo `requirements.txt`)

### Passo a passo

1. **Clone o repositório:**
   ```bash
   git clone git@github.com:JKrabbee/truco.git
   cd truco
   ```

2. **Crie e ative o ambiente virtual:**
   - Linux / macOS:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - Windows:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\activate
     ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Inicie o jogo** (funciona de qualquer diretório):
   ```bash
   python main.py
   ```

A janela abre em 1024×720, aceita redimensionamento e tem mínimo de 800×600.

## Regras

### A partida
- Truco Gaudério normal contra o Diabo: Envido, Real Envido, Falta Envido, Flor, Truco, Retruco e Vale Quatro, com os tentos somados como sempre.
- Cada fase é uma partida até **12 tentos**.

### O revólver
Há **um único revólver** com 6 câmaras. As balas ficam em posições sorteadas ao carregar, e o tambor **não gira** entre as puxadas: cada puxada avança uma câmara, então a próxima é sempre mais perigosa. O HUD mostra quantas câmaras já foram puxadas ("câmaras 3/6"), mas nunca onde está a bala.

Toda aposta perdida gera um **lote de puxadas**:

| Evento | Quem atira | Em quem | Puxadas |
|---|---|---|---|
| Perdeu a mão sem truco aceito | quem perdeu | em si mesmo | 1 |
| Perdeu a mão com Truco / Retruco / Vale Quatro aceito | quem perdeu | em si mesmo | 2 / 3 / 4 |
| Foi ao baralho | quem foi | em si mesmo | o valor do truco em jogo |
| Recusou Truco, Retruco ou Vale Quatro | quem recusou | em si mesmo | 1 |
| Ganhou Envido / Real Envido aceito | o vencedor | no outro | 2 / 3 (somados se encadeados) |
| Ganhou Falta Envido aceita | o vencedor | no outro | **até a bala sair** |
| Recusou Envido | quem recusou | em si mesmo | 1 |
| Cantou Flor (o outro sem Flor) / ganhou a Contraflor | quem cantou / o vencedor | no outro | 3 |

Os lotes de Envido e Flor são executados assim que o canto se resolve. Os de fim de mão, depois da última vaza.

### Como vencer e como perder
- **Você vence a fase** se a bala sair com o Diabo como alvo, ou se você chegar a 12 tentos.
- **Você morre** se a bala sair com você como alvo, ou se o Diabo chegar a 12 tentos. Nesse caso há um tiro final, sempre fatal.
- Se a mão que leva alguém a 12 tentos também gerou um lote, os tentos decidem e o lote não é executado.
- A morte apaga o save. Vencer a fase 3 mostra a vitória final e também apaga o save.

### As três fases

| | Fase 1 — O Convite | Fase 2 — O Blefe | Fase 3 — A Leitura |
|---|---|---|---|
| Blefe do Diabo | nunca | às vezes (35%) | muito (50%) |
| Tempo por decisão | sem limite | 15 s | 6 s |
| O Diabo cita cartas da tua mão | não | às vezes | com frequência, também durante o teu turno |
| Balas no tambor | 1 | 1 | 2 |
| Luz | estável | oscila | pisca |

A IA do Diabo **não vê** a tua mão. Quando ele cita uma carta tua, é só intimidação.

### Timer (fases 2 e 3)
- A barra à direita da mão encolhe a cada decisão tua (jogar uma carta ou responder a uma aposta). Nos 3 s finais ela fica vermelha.
- **Tempo esgotado:** com uma aposta pendente, o jogo responde "Não quero" por você (e isso gera o lote de castigo); na vez de jogar, ele joga a tua **carta mais fraca**.
- O timer para na roleta, na pausa, durante o voo da carta e enquanto o Diabo digita uma provocação no início da mão ou num canto dele.
- Ao reabrir um save, o timer volta com o tempo que restava (no mínimo 2 s).

## Controles

O jogo inteiro funciona só no teclado. O mouse continua funcionando em paralelo (botões e clique na carta).

| Tecla | Ação |
|---|---|
| ← / → | Escolher a carta da mão |
| Enter | Jogar a carta escolhida |
| T | Truco / Retruco / Vale Quatro. Com truco pendente para você: **aumentar** (só se houver próximo nível) |
| E / R / X | Cantar Envido / Real Envido / Falta Envido. Com envido pendente para você, **aumentam** a aposta: E e R só sobre Envido; X sobre Envido ou Real Envido |
| F | Flor |
| Q / N | Quero / Não quero |
| B | Ir ao baralho |
| Espaço (segurar ~1 s) | Puxar o gatilho na roleta. Soltar antes zera a barra, e cada puxada exige soltar e apertar de novo |
| Enter / Espaço | Avançar telas (introdução da fase, próxima mão, morte, vitória) |
| Esc | Pausa, inclusive durante a roleta (antes da bala sair) |
| ↑ / ↓ e Enter | Navegar no menu e na pausa |

As teclas só agem quando a ação é válida no momento. Na vez do Diabo e com a carta em voo, elas são ignoradas.

## Save

- O jogo salva sozinho em `save/save.json`, na raiz do projeto, seja qual for o diretório de onde foi aberto. Salva no início de cada mão, a cada carta, canto ou resposta, a cada puxada, na troca de fase, ao pausar e ao fechar a janela.
- **Continuar** só aparece no menu com um save válido. **Novo jogo** com save existente pede confirmação.
- A puxada é salva **antes** da animação: fechar o jogo depois de puxar o gatilho não muda o resultado.
- Fechar durante o voo de uma carta devolve a carta à mão, porque a jogada só vale quando a carta toca a mesa.
- Um save corrompido é descartado com um aviso no menu, sem derrubar o jogo.
- A escrita é atômica (arquivo `.tmp` + `os.replace`). A pasta `save/` está no `.gitignore`.

## Sprites

O busto do Diabo, o revólver, a mesa, o verso das cartas e o clarão do tiro são **opcionais**: sem os PNGs, o jogo desenha versões procedurais. Para usar imagens próprias (por exemplo, geradas por IA com fundo chapado magenta, ou preto no clarão), o `tools/preparar_sprites.py` recorta, redimensiona, tira o fundo e grava no caminho que o jogo lê; `--checar` confere os PNGs presentes.

## Estrutura

```text
core/    regras sem pygame: partida, tambor, lotes de tiros, campanha, falas, luz
game/    estados de tela, roleta, save, layout e assets
ui/      sprites e componentes de desenho (cartas, busto, revólver, balão, timer, HUD)
tools/   preparar_sprites.py, preparar_save.py
```

## Tecnologias

- [Python](https://www.python.org/) 3.10+
- [pygame-ce](https://pyga.me/)
