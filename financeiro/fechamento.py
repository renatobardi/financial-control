"""Fechamento mensal: manual, em ordem, reversível, com log. Só mês fechado é realizado."""

from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from financeiro import custo, i18n, vigencia
from financeiro.store import Conexao
from financeiro.store import cadastros as cadastros_store
from financeiro.store import fechamento as armazem
from financeiro.store.fechamento import EntradaLog


class FechamentoInvalido(Exception):
    """Base das recusas de fechar ou reabrir; a mensagem vai para a tela."""


class MesJaFechado(FechamentoInvalido):
    pass


class MesAnteriorAberto(FechamentoInvalido):
    pass


class ReaberturaInvalida(FechamentoInvalido):
    pass


class Totais(NamedTuple):
    estado: str  # realizado (mês fechado) | forecast (mês aberto)
    horas: int
    pessoas_centavos: int
    compras_centavos: int
    sem_tarifa_horas: int

    @property
    def total_centavos(self) -> int:
        return self.pessoas_centavos + self.compras_centavos


@dataclass(frozen=True)
class MesSituacao:
    mes: str
    estado: str  # fechado | aberto
    pode_fechar: bool
    pode_reabrir: bool
    totais: Totais
    pessoas: int
    ordens: int


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _rotulo(mes: str) -> str:
    return i18n.mes(int(mes[:4]), int(mes[5:]))


def meses_fechados(conexao: Conexao, bd_id: int) -> list[str]:
    return armazem.meses_fechados(conexao, bd_id)


def mes_inicial(conexao: Conexao, bd_id: int, agora: datetime | None = None) -> str:
    """Primeiro mês do BD que pode ser fechado: janeiro do ano do primeiro dado."""
    ano = armazem.primeiro_ano_com_dados(conexao, bd_id)
    if ano is None:
        ano = (agora or datetime.now()).year
    return f"{ano:04d}-01"


def _calcular(conexao: Conexao, bd_id: int, mes: str) -> Totais:
    """Valor do mês pelas tarifas e pelo markup vigentes agora (o que o forecast usa)."""
    pessoas = 0
    horas_total = 0
    sem_tarifa = 0
    for cargo_id, horas in armazem.horas_por_cargo(conexao, bd_id, mes):
        horas_total += horas
        try:
            pessoas += horas * custo.custo_hora(conexao, bd_id, cargo_id, mes).bruta_centavos
        except custo.SemTarifa:
            sem_tarifa += horas
    liquido, _ordens = armazem.compras_liquidas(conexao, bd_id, mes)
    markup = cadastros_store.markup_vigente(conexao, bd_id, mes)
    compras = custo.bruta(liquido, markup.centesimos_pct if markup else 0)
    return Totais("forecast", horas_total, pessoas, compras, sem_tarifa)


def totais_do_mes(conexao: Conexao, bd_id: int, mes: str) -> Totais:
    """Mês fechado: o que foi congelado, como realizado. Mês aberto: o cálculo, como forecast."""
    congelado = armazem.congelado_do_mes(conexao, bd_id, mes)
    if congelado is not None:
        return Totais(
            "realizado", congelado.horas, congelado.pessoas_centavos, congelado.compras_centavos, 0
        )
    return _calcular(conexao, bd_id, mes)


def fechar(
    conexao: Conexao,
    bd_id: int,
    mes: str,
    usuario_id: int,
    agora: datetime,
    motivo: str = "",
) -> Totais:
    vigencia.validar_mes(mes)
    fechados = armazem.meses_fechados(conexao, bd_id)
    if mes in fechados:
        raise MesJaFechado(f"{_rotulo(mes)} já está fechado.")
    inicial = mes_inicial(conexao, bd_id, agora)
    anterior = vigencia.mes_anterior(mes)
    if mes < inicial:
        raise MesAnteriorAberto(
            f"{_rotulo(mes)} é anterior ao primeiro mês do BD ({_rotulo(inicial)})."
        )
    if mes != inicial and anterior not in fechados:
        raise MesAnteriorAberto(f"Feche antes {_rotulo(anterior)}: os meses fecham em ordem.")
    calculado = _calcular(conexao, bd_id, mes)
    conexao.commit()
    try:
        congelado = armazem.Congelado(
            calculado.horas, calculado.pessoas_centavos, calculado.compras_centavos
        )
        armazem.fechar_mes(conexao, bd_id, mes, _iso(agora), congelado)
        armazem.registrar_log(
            conexao, bd_id, mes, "fechou", usuario_id, _iso(agora), motivo.strip()
        )
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return Totais("realizado", *calculado[1:])


def reabrir(
    conexao: Conexao, bd_id: int, mes: str, usuario_id: int, agora: datetime, motivo: str
) -> None:
    vigencia.validar_mes(mes)
    fechados = armazem.meses_fechados(conexao, bd_id)
    if mes not in fechados:
        raise ReaberturaInvalida(f"{_rotulo(mes)} não está fechado.")
    if mes != fechados[-1]:
        raise ReaberturaInvalida(
            f"Só o último mês fechado pode ser reaberto ({_rotulo(fechados[-1])})."
        )
    if not motivo.strip():
        raise ReaberturaInvalida("Informe o motivo da reabertura.")
    conexao.commit()
    try:
        armazem.reabrir_mes(conexao, bd_id, mes)
        armazem.registrar_log(
            conexao, bd_id, mes, "reabriu", usuario_id, _iso(agora), motivo.strip()
        )
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise


def log(conexao: Conexao, bd_id: int) -> list[EntradaLog]:
    return armazem.listar_log(conexao, bd_id)


def situacao(
    conexao: Conexao, bd_id: int, ano: int, agora: datetime | None = None
) -> list[MesSituacao]:
    fechados = armazem.meses_fechados(conexao, bd_id)
    ultimo = fechados[-1] if fechados else None
    inicial = mes_inicial(conexao, bd_id, agora)
    meses = []
    for numero in range(1, 13):
        mes = f"{ano:04d}-{numero:02d}"
        fechado = mes in fechados
        anterior_ok = mes == inicial or vigencia.mes_anterior(mes) in fechados
        _liquido, ordens = armazem.compras_liquidas(conexao, bd_id, mes)
        meses.append(
            MesSituacao(
                mes=mes,
                estado="fechado" if fechado else "aberto",
                pode_fechar=(not fechado) and mes >= inicial and anterior_ok,
                pode_reabrir=fechado and mes == ultimo,
                totais=totais_do_mes(conexao, bd_id, mes),
                pessoas=armazem.pessoas_com_horas(conexao, bd_id, mes),
                ordens=ordens,
            )
        )
    return meses


def cargas_com_rejeicao_pendente(conexao: Conexao, bd_id: int) -> int:
    return armazem.cargas_com_rejeicao_pendente(conexao, bd_id)
