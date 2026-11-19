import random
from enum import Enum, auto
from typing import Any, Optional
from core.diabo import JogadorDiabo
from core.fase import FASES, ConfigFase
from core.match import EstadoPartida, PartidaTruco
from core.player import Jogador, JogadorHumano
from core.revolver import Tambor
from core.roleta import LoteTiros, OrigemTiro


class SaveInvalido(ValueError):
    """Save ausente de chaves, corrompido ou incoerente (R9.7)."""


class ResultadoCampanha(Enum):
    EM_JOGO = auto()
    VITORIA_FASE = auto()
    MORTE = auto()
    VITORIA_FINAL = auto()


class Campanha:
    """Estado salvo do jogo: fase, tambor, partida e roleta; concentra as regras de fim de fase."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()
        self.humano = JogadorHumano()
        self.diabo = JogadorDiabo(taxa_blefe=FASES[0].taxa_blefe)
        self.iniciar_fase(0)

    @property
    def config(self) -> ConfigFase:
        return FASES[self.indice_fase]

    @property
    def eh_ultima_fase(self) -> bool:
        return self.indice_fase == len(FASES) - 1

    @classmethod
    def nova(cls, rng: Optional[random.Random] = None) -> "Campanha":
        """Campanha nova, na fase 1."""
        return cls(rng)

    def iniciar_fase(self, indice: int) -> None:
        """Nova PartidaTruco, tambor recarregado e taxa de blefe da fase (R2.4)."""
        if not 0 <= indice < len(FASES):
            raise ValueError(f"Fase inválida: {indice}")
        self.indice_fase = indice
        self.diabo.taxa_blefe = self.config.taxa_blefe
        for jogador in (self.humano, self.diabo):
            jogador.mao = []
            jogador.tentos = 0
        self.partida = PartidaTruco(self.humano, self.diabo)
        self.tambor = Tambor.carregar(self.config.balas, rng=self.rng)
        self.fila_lotes: list[LoteTiros] = []
        self.lote_atual: Optional[LoteTiros] = None
        self.puxadas_restantes: Optional[int] = None  # None = até disparar
        self.timer_restante: Optional[float] = None  # preenchido pela UI antes de salvar
        self.resultado = ResultadoCampanha.EM_JOGO

    # ==========================
    # ROLETA
    # ==========================
    def coletar_lotes(self) -> None:
        """Move os lotes gerados pela partida para a fila da campanha."""
        self.fila_lotes.extend(self.partida.consumir_lotes())

    def proximo_lote(self) -> Optional[LoteTiros]:
        """Retorna o lote ativo ou ativa o próximo da fila (None se não houver)."""
        if self.lote_atual is None and self.fila_lotes:
            self.lote_atual = self.fila_lotes.pop(0)
            self.puxadas_restantes = self.lote_atual.puxadas
        return self.lote_atual

    def puxar(self) -> bool:
        """Puxa o gatilho do lote ativo; True se disparou (e encerra a fase)."""
        lote = self.lote_atual
        if lote is None:
            raise RuntimeError("Nenhum lote de tiros ativo.")

        disparou = True if lote.fatal else self.tambor.puxar()
        if disparou:
            if lote.alvo is self.humano:
                self.resultado = ResultadoCampanha.MORTE
            else:
                self.resultado = self._resultado_vitoria()
            # R4.4: o resto do lote e a fila são descartados
            self._encerrar_lote()
            self.fila_lotes = []
            return True

        if self.puxadas_restantes is not None:
            self.puxadas_restantes -= 1
            if self.puxadas_restantes <= 0:
                self._encerrar_lote()
        return False

    def _encerrar_lote(self) -> None:
        self.lote_atual = None
        self.puxadas_restantes = None

    def _resultado_vitoria(self) -> ResultadoCampanha:
        if self.eh_ultima_fase:
            return ResultadoCampanha.VITORIA_FINAL
        return ResultadoCampanha.VITORIA_FASE

    # ==========================
    # FIM DE FASE
    # ==========================
    def verificar_fim_por_tentos(self) -> None:
        """Humano a 12: vence a fase. Diabo a 12: tiro final obrigatório e fatal (R3.3)."""
        if self.partida.estado_atual != EstadoPartida.FIM_DE_JOGO:
            return
        if self.resultado != ResultadoCampanha.EM_JOGO:
            return
        vencedor = self.partida.vencedor_partida
        if vencedor is self.humano:
            self.resultado = self._resultado_vitoria()
        elif vencedor is self.diabo:
            ja_enfileirado = any(
                lote.origem == OrigemTiro.TIRO_FINAL
                for lote in [self.lote_atual, *self.fila_lotes]
                if lote is not None
            )
            if not ja_enfileirado:
                self.fila_lotes.append(
                    LoteTiros(
                        atirador=self.humano,
                        alvo=self.humano,
                        puxadas=1,
                        origem=OrigemTiro.TIRO_FINAL,
                        fatal=True,
                    )
                )

    def avancar_fase(self) -> None:
        """Após VITORIA_FASE, inicia a próxima fase (ou marca VITORIA_FINAL na última)."""
        if self.resultado != ResultadoCampanha.VITORIA_FASE:
            return
        if self.eh_ultima_fase:
            self.resultado = ResultadoCampanha.VITORIA_FINAL
            return
        self.iniciar_fase(self.indice_fase + 1)

    # ==========================
    # SERIALIZAÇÃO (SAVE)
    # ==========================
    def _id(self, jogador: Jogador) -> str:
        return self.partida._id(jogador)

    def _lote_para_dict(self, lote: LoteTiros, puxadas: Optional[int]) -> dict[str, Any]:
        return {
            "atirador": self._id(lote.atirador),
            "alvo": self._id(lote.alvo),
            "puxadas": puxadas,
            "origem": lote.origem.name,
            "fatal": lote.fatal,
        }

    def _lote_de_dict(self, dados: dict[str, Any]) -> LoteTiros:
        atirador = self.partida._jogador(dados["atirador"])
        alvo = self.partida._jogador(dados["alvo"])
        if atirador is None or alvo is None:
            raise ValueError("Lote sem atirador ou alvo.")
        puxadas = dados["puxadas"]
        if puxadas is not None:
            puxadas = int(puxadas)
            if puxadas < 1:
                raise ValueError(f"Puxadas inválidas: {puxadas}")
        return LoteTiros(
            atirador=atirador,
            alvo=alvo,
            puxadas=puxadas,
            origem=OrigemTiro[dados["origem"]],
            fatal=bool(dados["fatal"]),
        )

    def para_dict(self) -> dict[str, Any]:
        """Serializa a campanha e a partida no formato do save (design §6, sem "versao")."""
        # Lotes ainda na partida (não coletados) também vão para a fila, por segurança.
        fila = self.fila_lotes + self.partida.lotes_pendentes
        return {
            "campanha": {
                "indice_fase": self.indice_fase,
                "resultado": self.resultado.name,
                "tambor": self.tambor.para_dict(),
                # No lote atual, "puxadas" guarda as puxadas restantes.
                "lote_atual": (
                    self._lote_para_dict(self.lote_atual, self.puxadas_restantes)
                    if self.lote_atual is not None
                    else None
                ),
                "fila_lotes": [self._lote_para_dict(lote, lote.puxadas) for lote in fila],
                "timer_restante": self.timer_restante,
            },
            "partida": self.partida.para_dict(),
        }

    @classmethod
    def de_dict(
        cls, dados: dict[str, Any], rng: Optional[random.Random] = None
    ) -> "Campanha":
        """Reconstrói a campanha salva; levanta SaveInvalido se os dados forem inválidos."""
        try:
            c = cls(rng)
            d = dados["campanha"]
            c.iniciar_fase(int(d["indice_fase"]))
            c.resultado = ResultadoCampanha[d["resultado"]]
            c.tambor = Tambor.de_dict(d["tambor"])
            c.partida = PartidaTruco.de_dict(dados["partida"], c.humano, c.diabo)

            lote = d["lote_atual"]
            if lote is not None:
                c.lote_atual = c._lote_de_dict(lote)
                c.puxadas_restantes = c.lote_atual.puxadas
            c.fila_lotes = [c._lote_de_dict(lote) for lote in d["fila_lotes"]]

            timer = d["timer_restante"]
            c.timer_restante = float(timer) if timer is not None else None
            return c
        except SaveInvalido:
            raise
        except (KeyError, ValueError, TypeError, IndexError, AttributeError) as erro:
            raise SaveInvalido(f"Save inválido: {erro!r}") from erro
