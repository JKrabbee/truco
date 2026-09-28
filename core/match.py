from enum import Enum, auto
from typing import Optional, Any
from core.card import Carta
from core.deck import Baralho
from core.player import Jogador, JogadorHumano, JogadorBot
from core.rules import (
    Mao,
    Vaza,
    TipoTruco,
    TipoEnvido,
    RespostaAposta,
    CalculadorEnvidoFlor,
)


class EstadoPartida(Enum):
    INICIO_RODADA = auto()
    DISPUTA_FLOR = auto()
    AGUARDANDO_ENVIDO = auto()
    AGUARDANDO_RESPOSTA_ENVIDO = auto()
    RESOLVENDO_ENVIDO = auto()
    JOGANDO_VAZA = auto()
    AGUARDANDO_RESPOSTA_TRUCO = auto()
    FIM_DA_MAO = auto()
    FIM_DE_JOGO = auto()


class PartidaTruco:
    """
    Gerenciador da partida de Truco Gaudério (1v1 até 24 tentos).
    Controla rodadas, alternância do 'mão', apostas e placar.
    """

    TENTOS_VITORIA = 24

    def __init__(self, jogador1: Jogador, jogador2: Jogador):
        self.jogador1 = jogador1
        self.jogador2 = jogador2
        self.baralho = Baralho()

        self.pontos_jogador1: int = 0
        self.pontos_jogador2: int = 0

        self.numero_rodada: int = 0
        self.indice_mao: int = 0  # 0: jogador1 é mão; 1: jogador2 é mão

        self.mao_atual: Optional[Mao] = None
        self.estado_atual: EstadoPartida = EstadoPartida.INICIO_RODADA

        # Controle de aposta de Truco da rodada
        self.nivel_truco: Optional[TipoTruco] = None
        self.valor_truco_atual: int = 1
        self.quem_pediu_truco: Optional[Jogador] = None
        self.quem_deve_responder_truco: Optional[Jogador] = None

        # Controle de Envido e Flor
        self.envido_disputado: bool = False
        self.flor_ocorrida: bool = False
        self.aposta_envido_atual: Optional[TipoEnvido] = None
        self.valor_envido_acumulado: int = 0
        self.valor_recusa_envido: int = 1
        self.quem_pediu_envido: Optional[Jogador] = None
        self.quem_deve_responder_envido: Optional[Jogador] = None

        # Turno atual de quem joga carta
        self.jogador_vez: Optional[Jogador] = None
        self.primeiro_a_jogar_na_vaza: Optional[Jogador] = None

        # Mensagem de histórico / log para a UI
        self.ultima_mensagem: str = "Partida iniciada."
        self.vencedor_partida: Optional[Jogador] = None

    @property
    def jogador_mao(self) -> Jogador:
        """Retorna quem é o 'mão' na rodada atual."""
        return self.jogador1 if self.indice_mao == 0 else self.jogador2

    @property
    def jogador_pe(self) -> Jogador:
        """Retorna quem é o 'pé' na rodada atual."""
        return self.jogador2 if self.indice_mao == 0 else self.jogador1

    def oponente_de(self, jogador: Jogador) -> Jogador:
        return self.jogador2 if jogador == self.jogador1 else self.jogador1

    def pontuacao_de(self, jogador: Jogador) -> int:
        return (
            self.pontos_jogador1 if jogador == self.jogador1 else self.pontos_jogador2
        )

    def adicionar_pontos(self, jogador: Jogador, pontos: int) -> None:
        """Adiciona tentos ao placar e atualiza o atributo do próprio jogador."""
        if jogador == self.jogador1:
            self.pontos_jogador1 += pontos
            self.jogador1.tentos = self.pontos_jogador1
        else:
            self.pontos_jogador2 += pontos
            self.jogador2.tentos = self.pontos_jogador2

        if self.pontos_jogador1 >= self.TENTOS_VITORIA:
            self.vencedor_partida = self.jogador1
            self.estado_atual = EstadoPartida.FIM_DE_JOGO
            self.ultima_mensagem = f"Fim de jogo! {self.jogador1.nome} venceu a peleja!"
        elif self.pontos_jogador2 >= self.TENTOS_VITORIA:
            self.vencedor_partida = self.jogador2
            self.estado_atual = EstadoPartida.FIM_DE_JOGO
            self.ultima_mensagem = f"Fim de jogo! {self.jogador2.nome} venceu a peleja!"

    def esta_nas_boas(self, jogador: Jogador) -> bool:
        """No Truco Gaudério, de 1 a 12 são as 'Más' e de 13 a 24 são as 'Boas'."""
        return self.pontuacao_de(jogador) >= 13

    def formatar_placar_tradicional(self, jogador: Jogador) -> str:
        pts = self.pontuacao_de(jogador)
        if pts <= 12:
            return f"Más ({pts}/12)"
        return f"Boas ({pts - 12}/12)"

    def iniciar_nova_rodada(self) -> None:
        """Distribui as cartas e prepara a nova mão."""
        if self.estado_atual == EstadoPartida.FIM_DE_JOGO:
            return

        self.numero_rodada += 1
        # Alterna quem é a mão a cada rodada após a primeira
        if self.numero_rodada > 1:
            self.indice_mao = 1 - self.indice_mao

        self.baralho.reiniciar()
        self.baralho.embaralhar()

        cartas_j1 = self.baralho.distribuir_mao(3)
        cartas_j2 = self.baralho.distribuir_mao(3)
        self.jogador1.receber_cartas(cartas_j1)
        self.jogador2.receber_cartas(cartas_j2)

        self.mao_atual = Mao(self.jogador_mao, self.jogador_pe)
        self.nivel_truco = None
        self.valor_truco_atual = 1
        self.quem_pediu_truco = None
        self.quem_deve_responder_truco = None

        self.envido_disputado = False
        self.flor_ocorrida = False
        self.aposta_envido_atual = None
        self.valor_envido_acumulado = 0
        self.valor_recusa_envido = 1
        self.quem_pediu_envido = None
        self.quem_deve_responder_envido = None

        self.jogador_vez = self.jogador_mao
        self.primeiro_a_jogar_na_vaza = self.jogador_mao

        self.estado_atual = EstadoPartida.AGUARDANDO_ENVIDO
        self.ultima_mensagem = (
            f"Rodada {self.numero_rodada}. É a vez de {self.jogador_vez.nome}."
        )

    # ==========================
    # SISTEMA DE FLOR
    # ==========================
    def pode_cantar_flor(self, jogador: Jogador) -> bool:
        """
        Verifica se o jogador pode cantar Flor na sua vez.
        No Truco Gaudério, o jogador com 3 cartas do mesmo naipe
        pode cantar Flor na 1ª vaza antes de jogar sua primeira carta (len(mao) == 3).
        Mesmo que o oponente tenha jogado primeiro, o jogador ainda pode cantar Flor!
        """
        if self.flor_ocorrida:
            return False
        if self.mao_atual is None or self.mao_atual.indice_vaza_atual > 0:
            return False
        if len(jogador.mao) < 3:
            return False
        if self.estado_atual not in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        ):
            return False
        return jogador.tem_flor()

    def cantar_flor(self, jogador: Jogador) -> bool:
        """Processa o canto de Flor do jogador."""
        if not self.pode_cantar_flor(jogador):
            return False

        oponente = self.oponente_de(jogador)
        self.flor_ocorrida = True
        self.envido_disputado = True  # Flor anula o envido

        # Se o oponente também tem Flor: Contraflor direta (6 tentos)
        if oponente.tem_flor():
            pts_jog = jogador.pontos_flor
            pts_op = oponente.pontos_flor
            if pts_jog > pts_op:
                vencedor, pts_venc = jogador, pts_jog
            elif pts_op > pts_jog:
                vencedor, pts_venc = oponente, pts_op
            else:
                # Empate: favorece a mão
                vencedor = self.jogador_mao
                pts_venc = self.jogador_mao.pontos_flor

            self.adicionar_pontos(vencedor, 6)
            self.ultima_mensagem = (
                f"Contraflor! {jogador.nome} ({pts_jog}) vs {oponente.nome} ({pts_op}). "
                f"{vencedor.nome} ganha 6 tentos com {pts_venc} pontos de flor!"
            )
        else:
            pts = jogador.pontos_flor
            self.adicionar_pontos(jogador, 3)
            self.ultima_mensagem = (
                f"Flor! {jogador.nome} cantou Flor ({pts} pts) e levou 3 tentos!"
            )

        if self.vencedor_partida:
            self.estado_atual = EstadoPartida.FIM_DE_JOGO
        else:
            self.estado_atual = EstadoPartida.JOGANDO_VAZA
        return True

    # ==========================
    # SISTEMA DE ENVIDO
    # ==========================
    def pode_cantar_envido(self, jogador: Jogador) -> bool:
        """
        Verifica se o jogador pode cantar Envido na sua vez.
        No Truco Gaudério, o Envido só pode ser cantado na 1ª vaza (índice 0),
        antes que ESTE jogador tenha jogado sua primeira carta (len(mao) == 3),
        e desde que o Envido ou Flor ainda não tenham sido disputados.
        Se o oponente jogou primeiro, o jogador ainda PODE cantar Envido!
        """
        if self.envido_disputado or self.flor_ocorrida:
            return False
        if self.mao_atual is None or self.mao_atual.indice_vaza_atual > 0:
            return False
        if len(jogador.mao) < 3:
            return False
        if self.estado_atual not in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        ):
            return False
        return True

    def cantar_envido(self, jogador: Jogador, tipo: TipoEnvido) -> bool:
        """Jogador canta Envido, Real Envido ou Falta Envido."""
        if self.flor_ocorrida or self.envido_disputado:
            return False
        if self.mao_atual is None or self.mao_atual.indice_vaza_atual > 0:
            return False  # Só pode cantar na 1ª vaza
        if self.aposta_envido_atual is None and not self.pode_cantar_envido(jogador):
            return False

        # Definir valores de aposta e recusa
        pts_faltando = max(
            1,
            self.TENTOS_VITORIA - max(self.pontos_jogador1, self.pontos_jogador2),
        )

        if tipo == TipoEnvido.ENVIDO:
            if self.aposta_envido_atual is None:
                self.valor_envido_acumulado = 2
                self.valor_recusa_envido = 1
            elif self.aposta_envido_atual == TipoEnvido.ENVIDO:
                self.valor_envido_acumulado += 2
                self.valor_recusa_envido = 2
        elif tipo == TipoEnvido.REAL_ENVIDO:
            if self.aposta_envido_atual is None:
                self.valor_envido_acumulado = 3
                self.valor_recusa_envido = 1
            else:
                self.valor_envido_acumulado += 3
                self.valor_recusa_envido = self.valor_envido_acumulado - 3
        elif tipo == TipoEnvido.FALTA_ENVIDO:
            self.valor_recusa_envido = max(1, self.valor_envido_acumulado)
            self.valor_envido_acumulado = pts_faltando

        self.aposta_envido_atual = tipo
        self.quem_pediu_envido = jogador
        self.quem_deve_responder_envido = self.oponente_de(jogador)
        self.estado_atual = EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO
        self.ultima_mensagem = f"{jogador.nome} cantou {tipo.value}!"
        return True

    def responder_envido(
        self,
        resposta: RespostaAposta,
        aumento: Optional[TipoEnvido] = None,
    ) -> None:
        """Processa a resposta do oponente ao pedido de Envido."""
        if self.estado_atual != EstadoPartida.AGUARDANDO_RESPOSTA_ENVIDO:
            return

        quem_responde = self.quem_deve_responder_envido
        quem_pediu = self.quem_pediu_envido

        if resposta == RespostaAposta.QUERO:
            self.envido_disputado = True
            p1 = self.jogador1.pontos_envido
            p2 = self.jogador2.pontos_envido
            vencedor, pts = CalculadorEnvidoFlor.comparar_envido(
                p1, self.jogador1, p2, self.jogador2, self.jogador_mao
            )
            self.adicionar_pontos(vencedor, self.valor_envido_acumulado)
            self.ultima_mensagem = (
                f"Envido aceito! {self.jogador1.nome}: {p1} pts x {self.jogador2.nome}: {p2} pts. "
                f"{vencedor.nome} vence e leva {self.valor_envido_acumulado} tento(s)!"
            )
            self.estado_atual = (
                EstadoPartida.FIM_DE_JOGO
                if self.vencedor_partida
                else EstadoPartida.JOGANDO_VAZA
            )

        elif resposta == RespostaAposta.NAO_QUERO:
            self.envido_disputado = True
            self.adicionar_pontos(quem_pediu, self.valor_recusa_envido)
            self.ultima_mensagem = (
                f"{quem_responde.nome} não quis o envido. "
                f"{quem_pediu.nome} leva {self.valor_recusa_envido} tento(s)!"
            )
            self.estado_atual = (
                EstadoPartida.FIM_DE_JOGO
                if self.vencedor_partida
                else EstadoPartida.JOGANDO_VAZA
            )

        elif resposta == RespostaAposta.AUMENTAR:
            if aumento is not None:
                self.cantar_envido(quem_responde, aumento)

    # ==========================
    # SISTEMA DE TRUCO
    # ==========================
    def pode_pedir_truco(self, jogador: Jogador) -> bool:
        """Verifica se o jogador pode cantar Truco, Retruco ou Vale Quatro."""
        if self.estado_atual not in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        ):
            return False
        # Não pode aumentar a própria aposta sucessivamente
        if self.quem_pediu_truco == jogador:
            return False
        if self.nivel_truco == TipoTruco.VALE_QUATRO:
            return False
        return True

    def pedir_truco(self, jogador: Jogador) -> bool:
        """Eleva a aposta para o próximo nível de Truco."""
        if not self.pode_pedir_truco(jogador):
            return False

        if self.nivel_truco is None:
            proximo = TipoTruco.TRUCO
        else:
            proximo = self.nivel_truco.proximo_nivel

        if proximo is None:
            return False

        # Se cantar truco, o envido não cantado prescreve
        self.envido_disputado = True

        self.nivel_truco = proximo
        self.quem_pediu_truco = jogador
        self.quem_deve_responder_truco = self.oponente_de(jogador)
        self.estado_atual = EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO
        self.ultima_mensagem = f"{jogador.nome} gritou {proximo.nome_exibicao.upper()}!"
        return True

    def responder_truco(
        self,
        resposta: RespostaAposta,
        jogador_resposta: Jogador,
    ) -> None:
        """Processa a resposta ao pedido de Truco."""
        if self.estado_atual != EstadoPartida.AGUARDANDO_RESPOSTA_TRUCO:
            return
        if jogador_resposta != self.quem_deve_responder_truco:
            return

        quem_pediu = self.quem_pediu_truco

        if resposta == RespostaAposta.QUERO:
            self.valor_truco_atual = self.nivel_truco.valor
            self.ultima_mensagem = f"{jogador_resposta.nome} disse QUERO! A mão vale {self.valor_truco_atual} tentos."
            self.estado_atual = EstadoPartida.JOGANDO_VAZA

        elif resposta == RespostaAposta.NAO_QUERO:
            # Recusou truco: quem pediu leva o valor do nível anterior
            valor_ganho = (
                1 if self.nivel_truco == TipoTruco.TRUCO else self.valor_truco_atual
            )
            self.adicionar_pontos(quem_pediu, valor_ganho)
            self.ultima_mensagem = f"{jogador_resposta.nome} correu do truco. {quem_pediu.nome} leva {valor_ganho} tento(s)!"
            self.finalizar_mao()

        elif resposta == RespostaAposta.AUMENTAR:
            # Tenta aumentar para o próximo nível
            proximo = self.nivel_truco.proximo_nivel
            if proximo is not None:
                self.nivel_truco = proximo
                self.quem_pediu_truco = jogador_resposta
                self.quem_deve_responder_truco = quem_pediu
                self.ultima_mensagem = f"{jogador_resposta.nome} aumentou para {proximo.nome_exibicao.upper()}!"
            else:
                # Já no máximo, trata como Quero
                self.valor_truco_atual = self.nivel_truco.valor
                self.estado_atual = EstadoPartida.JOGANDO_VAZA

    # ==========================
    # JOGADA DE CARTAS E VAZAS
    # ==========================
    def jogar_carta(self, jogador: Jogador, carta: Carta) -> bool:
        """Executa a jogada de uma carta na vaza atual."""
        if self.estado_atual not in (
            EstadoPartida.AGUARDANDO_ENVIDO,
            EstadoPartida.JOGANDO_VAZA,
        ):
            return False
        if jogador != self.jogador_vez:
            return False
        if carta not in jogador.mao:
            return False

        self.estado_atual = EstadoPartida.JOGANDO_VAZA
        jogador.remover_carta(carta)
        vaza_atual = self.mao_atual.vaza_atual
        vaza_atual.adicionar_jogada(jogador, carta)
        self.ultima_mensagem = f"{jogador.nome} jogou {carta.nome_completo}."

        # Se ambos jogaram na 1ª vaza ou já passamos dela, encerra a janela de envido
        if len(vaza_atual.cartas_jogadas) == 2 or self.mao_atual.indice_vaza_atual > 0:
            self.envido_disputado = True

        # Se ambos jogaram na vaza
        if len(vaza_atual.cartas_jogadas) == 2:
            vencedor_vaza = vaza_atual.resolver_vaza()
            if vaza_atual.empate:
                self.ultima_mensagem = f"Canguçu (empate) na {vaza_atual.indice}ª vaza!"
                # No empate, quem começou a vaza atual começa a próxima
                self.primeiro_a_jogar_na_vaza = self.primeiro_a_jogar_na_vaza
                self.jogador_vez = self.primeiro_a_jogar_na_vaza
            else:
                self.ultima_mensagem = (
                    f"{vencedor_vaza.nome} fez a {vaza_atual.indice}ª vaza."
                )
                self.primeiro_a_jogar_na_vaza = vencedor_vaza
                self.jogador_vez = vencedor_vaza

            # Verifica se a mão já tem um vencedor
            vencedor_mao = self.mao_atual.verificar_vencedor()
            if vencedor_mao is not None:
                self.adicionar_pontos(vencedor_mao, self.valor_truco_atual)
                self.ultima_mensagem = f"{vencedor_mao.nome} levou a rodada e ganhou {self.valor_truco_atual} tento(s)!"
                self.finalizar_mao()
            else:
                self.mao_atual.avancar_vaza()
        else:
            # Alterna para o segundo jogador na mesma vaza
            self.jogador_vez = self.oponente_de(jogador)

        return True

    def ir_ao_baralho(self, jogador: Jogador) -> None:
        """Jogador desiste da mão atual (vai ao baralho)."""
        oponente = self.oponente_de(jogador)
        self.adicionar_pontos(oponente, self.valor_truco_atual)
        self.ultima_mensagem = f"{jogador.nome} foi ao baralho. {oponente.nome} ganhou {self.valor_truco_atual} tento(s)!"
        self.finalizar_mao()

    def finalizar_mao(self) -> None:
        """Encerra a mão atual e define se o jogo acabou ou continua."""
        if self.vencedor_partida is not None:
            self.estado_atual = EstadoPartida.FIM_DE_JOGO
        else:
            self.estado_atual = EstadoPartida.FIM_DA_MAO

    def obter_estado_mesa_para_jogador(self, jogador: Jogador) -> dict[str, Any]:
        """Constrói o dicionário de contexto da mesa para auxiliar as decisões dos jogadores / IA."""
        vaza_atual = self.mao_atual.vaza_atual if self.mao_atual else None
        carta_oponente = None
        if vaza_atual and len(vaza_atual.cartas_jogadas) == 1:
            carta_oponente = vaza_atual.cartas_jogadas[0][1]

        resultado_v1 = None
        if self.mao_atual and len(self.mao_atual.vazas[0].cartas_jogadas) == 2:
            v1 = self.mao_atual.vazas[0]
            if v1.empate:
                resultado_v1 = "empatou"
            elif v1.vencedor == jogador:
                resultado_v1 = "venceu"
            else:
                resultado_v1 = "perdeu"

        return {
            "indice_vaza": (
                self.mao_atual.indice_vaza_atual + 1 if self.mao_atual else 1
            ),
            "carta_oponente_na_vaza": carta_oponente,
            "resultado_vaza_1": resultado_v1,
            "pontos_meus": self.pontuacao_de(jogador),
            "pontos_oponente": self.pontuacao_de(self.oponente_de(jogador)),
            "nivel_truco": self.nivel_truco,
            "valor_truco": self.valor_truco_atual,
            "envido_disponivel": not self.envido_disputado and not self.flor_ocorrida,
            "sou_mao": jogador == self.jogador_mao,
        }
