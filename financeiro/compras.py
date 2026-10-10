"""Compras (OC/OS): ordem ligada a uma demanda, com status, valor por mês e histórico."""

from dataclasses import dataclass
from datetime import datetime

from financeiro import consumo, custo, i18n, vigencia
from financeiro.store import Conexao, ErroDeIntegridade, acesso, cadastros
from financeiro.store import compras as armazem
from financeiro.store import consumo as armazem_consumo
from financeiro.store.compras import Compra, Historico

STATUS = ("prevista", "emitida", "cancelada")
TIPOS = ("OC", "OS")

__all__ = ["Compra", "Historico", "ComprasInvalido"]


class ComprasInvalido(Exception):
    """A operação recusada, com a mensagem que vai para a tela."""


@dataclass(frozen=True)
class LinhaCompra:
    id: int
    numero: str
    sem_numero: bool
    tipo: str
    fornecedor: str | None
    descricao: str
    demanda: str
    status: str
    realizado_centavos: int
    forecast_centavos: int


@dataclass(frozen=True)
class MesCompra:
    mes: str
    estado: str  # realizado | forecast
    liquido_centavos: int
    bruto_centavos: int


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _rotulo(mes: str) -> str:
    return i18n.mes(int(mes[:4]), int(mes[5:]))


def _autor(conexao: Conexao, usuario_id: int) -> str:
    usuario = acesso.achar_usuario(conexao, usuario_id)
    return usuario.nome if usuario else "—"


def achar(conexao: Conexao, bd_id: int, compra_id: int) -> Compra | None:
    return armazem.achar_compra(conexao, bd_id, compra_id)


def historico(conexao: Conexao, bd_id: int, compra_id: int) -> list[Historico]:
    return armazem.listar_historico(conexao, bd_id, compra_id)


def criar_prevista(
    conexao: Conexao,
    bd_id: int,
    tipo: str,
    demanda_id: int,
    descricao: str,
    usuario_id: int,
    agora: datetime,
) -> int:
    if tipo not in TIPOS:
        raise ComprasInvalido("Tipo da ordem: OC ou OS.")
    try:
        conexao.commit()
        compra_id = armazem.criar_compra(
            conexao, bd_id, armazem.proximo_numero_previsto(conexao, bd_id), tipo, None,
            demanda_id, "prevista", descricao.strip(),
        )  # fmt: skip
        armazem.registrar_historico(
            conexao, bd_id, compra_id, _iso(agora), usuario_id,
            f"criada como prevista por {_autor(conexao, usuario_id)}",
        )  # fmt: skip
        conexao.commit()
    except ErroDeIntegridade as erro:
        conexao.rollback()
        raise ComprasInvalido("Demanda não encontrada neste BD.") from erro
    return compra_id


def editar(
    conexao: Conexao,
    bd_id: int,
    compra_id: int,
    usuario_id: int,
    agora: datetime,
    *,
    status: str | None = None,
    numero: str | None = None,
    fornecedor_id: int | None = None,
    demanda_id: int | None = None,
    descricao: str | None = None,
    tipo: str | None = None,
) -> None:
    atual = armazem.achar_compra(conexao, bd_id, compra_id)
    if atual is None:
        raise ComprasInvalido("Ordem não encontrada neste BD.")
    if atual.status == "cancelada":
        raise ComprasInvalido("Ordem cancelada não muda mais.")
    novo_status = status or atual.status
    if novo_status not in STATUS:
        raise ComprasInvalido(f"Status inválido: {novo_status!r}.")
    novo_numero = (numero.strip() if numero else None) or atual.numero
    novo_fornecedor = fornecedor_id if fornecedor_id is not None else atual.fornecedor_id
    novo_tipo = tipo or atual.tipo
    if novo_tipo not in TIPOS:
        raise ComprasInvalido("Tipo da ordem: OC ou OS.")
    if novo_status == "emitida" and (novo_numero.startswith("PREV-") or novo_fornecedor is None):
        raise ComprasInvalido("Para emitir, informe o número da ordem e o fornecedor.")
    if novo_status == "cancelada":
        fechados = [
            m
            for m in armazem.meses_com_valor(conexao, bd_id, compra_id)
            if armazem_consumo.mes_esta_fechado(conexao, bd_id, m)
        ]
        if fechados:
            raise ComprasInvalido(
                f"A ordem tem valor em {_rotulo(fechados[0])}, que está fechado: "
                "reabra o mês para cancelar."
            )
    mudancas = []
    if novo_status != atual.status:
        mudancas.append(f"status: {atual.status} → {novo_status}")
    if novo_numero != atual.numero:
        mudancas.append(f"número: {novo_numero}")
    if novo_fornecedor != atual.fornecedor_id:
        mudancas.append("fornecedor alterado")
    nova_demanda = demanda_id if demanda_id is not None else atual.demanda_id
    if nova_demanda != atual.demanda_id:
        mudancas.append("demanda alterada")
    nova_descricao = descricao.strip() if descricao is not None else atual.descricao
    if nova_descricao != atual.descricao:
        mudancas.append("descrição alterada")
    conexao.commit()
    try:
        armazem.atualizar_compra(
            conexao, bd_id, compra_id, novo_numero, novo_tipo, novo_fornecedor,
            nova_demanda, novo_status, nova_descricao,
        )  # fmt: skip
        if mudancas:
            armazem.registrar_historico(
                conexao, bd_id, compra_id, _iso(agora), usuario_id,
                f"{', '.join(mudancas)} por {_autor(conexao, usuario_id)}",
            )  # fmt: skip
        conexao.commit()
    except ErroDeIntegridade as erro:
        conexao.rollback()
        raise ComprasInvalido(
            "Número já usado por outra ordem, ou fornecedor e demanda de outro BD."
        ) from erro


def definir_valor(
    conexao: Conexao,
    bd_id: int,
    compra_id: int,
    mes: str,
    liquido_centavos: int,
    usuario_id: int,
    agora: datetime,
) -> None:
    """Valor líquido do mês. Só mês aberto (forecast); realizado é só leitura."""
    atual = armazem.achar_compra(conexao, bd_id, compra_id)
    if atual is None:
        raise ComprasInvalido("Ordem não encontrada neste BD.")
    if atual.status == "cancelada":
        raise ComprasInvalido("Ordem cancelada não recebe valor.")
    try:
        vigencia.validar_mes(mes)
    except ValueError as erro:
        raise ComprasInvalido("Informe o mês no formato AAAA-MM.") from erro
    if isinstance(liquido_centavos, bool) or not isinstance(liquido_centavos, int):
        raise TypeError("valor em centavos inteiros")
    if liquido_centavos < 0:
        raise ComprasInvalido("O valor não pode ser negativo.")
    if armazem_consumo.mes_esta_fechado(conexao, bd_id, mes):
        raise ComprasInvalido(f"{_rotulo(mes)} está fechado: o realizado é só leitura.")
    armazem.gravar_valor(conexao, bd_id, compra_id, mes, liquido_centavos)
    armazem.registrar_historico(
        conexao, bd_id, compra_id, _iso(agora), usuario_id,
        f"valor de {_rotulo(mes)}: {i18n.moeda(liquido_centavos)} líquido por "
        f"{_autor(conexao, usuario_id)}",
    )  # fmt: skip
    conexao.commit()


def listar(
    conexao: Conexao,
    bd_id: int,
    ano: int,
    agora: datetime,
    busca: str = "",
    status: str | None = None,
) -> list[LinhaCompra]:
    realizado: dict[int, int] = {}
    forecast: dict[int, int] = {}
    for numero in range(1, 13):
        estado, linhas = consumo.do_mes(conexao, bd_id, f"{ano:04d}-{numero:02d}")
        destino = realizado if estado == "realizado" else forecast
        for linha in linhas:
            if linha.origem == "compras" and linha.compra_id is not None:
                destino[linha.compra_id] = destino.get(linha.compra_id, 0) + linha.bruto_centavos
    termo = busca.strip().lower()
    resultado = []
    for c in armazem.listar_compras(conexao, bd_id):
        if status and c.status != status:
            continue
        texto = " ".join(filter(None, [c.numero, c.fornecedor, c.descricao, c.demanda])).lower()
        if termo and termo not in texto:
            continue
        resultado.append(
            LinhaCompra(
                c.id,
                c.numero,
                c.sem_numero,
                c.tipo,
                c.fornecedor,
                c.descricao,
                c.demanda,
                c.status,
                realizado.get(c.id, 0),
                forecast.get(c.id, 0),
            )  # fmt: skip
        )
    return resultado


def valores_por_mes(conexao: Conexao, bd_id: int, compra_id: int, ano: int) -> list[MesCompra]:
    congelados = armazem.valores_congelados(conexao, bd_id, compra_id)
    abertos = armazem.valores_liquidos(conexao, bd_id, compra_id)
    meses = []
    for numero in range(1, 13):
        mes = f"{ano:04d}-{numero:02d}"
        if armazem_consumo.mes_esta_fechado(conexao, bd_id, mes):
            liquido, bruto = congelados.get(mes, (0, 0))
            meses.append(MesCompra(mes, "realizado", liquido, bruto))
            continue
        liquido = abertos.get(mes, 0)
        markup = cadastros.markup_vigente(conexao, bd_id, mes)
        bruto = custo.bruta(liquido, markup.centesimos_pct if markup else 0)
        meses.append(MesCompra(mes, "forecast", liquido, bruto))
    return meses
