# Truco contra o Diabo

Truco Gaudério (baralho espanhol de 40 cartas, manilhas fixas, Envido e Flor) jogado numa mesa à luz de vela contra **o Diabo**. Cada aposta perdida vira puxadas de gatilho num revólver com bala no tambor. São três fases, cada uma mais rápida e mais escura que a anterior. Feito em Python com **pygame-ce**.

## Como executar

### Pré-requisitos
- Python 3.10 ou superior (desenvolvido e testado em **3.12**)
- pygame-ce 2.5 ou superior (instalado pelo `requirements.txt`)
- Nada mais: sem numpy nem ffmpeg

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

4. **Gere a música** (fica fora do git; veja [Áudio](#áudio)):
   ```bash
   python tools/gerar_audio.py
   ```

5. **Inicie o jogo** (funciona de qualquer diretório):
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
| Música | 1,0× | 1,15× | 1,3× |
| Luz | estável | oscila | pisca |

A IA do Diabo **não vê** a tua mão. Quando ele cita uma carta tua, é só intimidação.

### Timer (fases 2 e 3)
- A barra à direita da mão encolhe a cada decisão tua (jogar uma carta ou responder a uma aposta). Nos 3 s finais ela fica vermelha, e um tique-taque acelera.
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

## Áudio

- Cada fase tem a sua faixa, com fade na troca. A música baixa na pausa (35%) e na roleta (50%) e corta na bala. Há efeitos para engatilhar, clique vazio, disparo, tique do timer, risada do Diabo e carta na mesa.
- `python tools/gerar_audio.py` gera tudo só com a biblioteca padrão:
  - `assets/music/fase{1,2,3}.wav`: drones em loop, já na velocidade de cada fase. Ficam **fora do git** (`assets/music/` no `.gitignore`), então quem clona precisa rodar o script;
  - `assets/sfx/*.wav`: os efeitos, que já vêm versionados (o script os recria).
  - Opções: `--so-efeitos`, `--so-musica` e `--saida PASTA`.
- Para usar uma trilha própria, salve-a como `assets/music/fase{n}.ogg` **já acelerada** para a fase, por exemplo `ffmpeg -i trilha.ogg -filter:a atempo=1.15 fase2.ogg`. O `.ogg` tem prioridade sobre o `.wav`; o mesmo vale para `assets/sfx/{nome}.ogg`. Trilhas com direitos autorais ficam só na tua máquina.
- Sem mixer, sem placa de som ou sem os arquivos, o jogo roda mudo e sem erro.

## Sprites

O busto do Diabo, o revólver, a mesa, o verso das cartas e o clarão do tiro são **opcionais**: sem os PNGs, o jogo desenha versões procedurais. Para usar imagens próprias (por exemplo, geradas por IA com fundo chapado magenta, ou preto no clarão), o `tools/preparar_sprites.py` recorta, redimensiona, tira o fundo e grava no caminho que o jogo lê; `--checar` confere os PNGs presentes.

## Testes

Instale as dependências de desenvolvimento e rode o pytest da raiz do projeto:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

- `tests/` cobre a lógica de `core/` (tambor, lotes de tiros da tabela acima, campanha, serialização, falas, luz e tique), que não depende de pygame, e também o save (`test_save_manager.py`).
- `tests/test_audio.py` é a exceção: testa o fallback do áudio com `SDL_AUDIODRIVER=dummy` e pastas temporárias, sem placa de som.

### Smoke test

```bash
python tools/smoke_test.py
```

Joga campanhas inteiras sem janela (`SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`), só com eventos de teclado, e confere cada item automatizável do checklist de teste: colisão, puxadas, desfechos, timer, fechar e reabrir em cada modo, save corrompido, sobreposição em 800×600 e 1024×720, luz, expressões e sons (por espião). O save e o áudio vão para uma pasta temporária, então o teu `save/` não é tocado. Opções: `--campanhas N`, `--semente S`, `--capturas PASTA` (salva capturas de tela) e `--assets` (valida os sprites em `assets/`).

O que só se confere a olho ou ouvido (aparência, legibilidade e o som de verdade) continua manual. Para chegar rápido a situações raras (Falta Envido, Diabo a 11, última câmara), `tools/preparar_save.py` grava um save pronto:

```bash
python tools/preparar_save.py --listar
python tools/preparar_save.py diabo-11
```

## Estrutura

```text
core/    regras sem pygame: partida, tambor, lotes de tiros, campanha, falas, luz
game/    estados de tela, roleta, save, áudio, layout e assets
ui/      sprites e componentes de desenho (cartas, busto, revólver, balão, timer, HUD)
tools/   gerar_audio.py, preparar_sprites.py, preparar_save.py, smoke_test.py
tests/   pytest
```

## Tecnologias

- [Python](https://www.python.org/) 3.10+ (testado em 3.12)
- [pygame-ce](https://pyga.me/)
