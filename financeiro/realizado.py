"""Realizado por dimensão, origem e período (ADR-0003: só mês fechado é realizado)."""

from dataclasses import dataclass, field
from datetime import datetime

from financeiro import consumo, i18n, orcamento
from financeiro.store import Conexao, organizacao, portfolio

DIMENSOES = (
    "iniciativa",
    "iniciativa_tipo",
    "demanda",
    "tema",
    "agrupamento",
    "tipo",
    "squad",
    "tribo",
    "origem",
)
ORIGENS = ("todas", "pessoas", "compras")
BASES = ("bruto", "liquido")
_SEM = {
    "tema": "Sem tema",
    "agrupamento": "Sem agrupamento",
    "squad": "Sem unidade",
    "tribo": "Sem tribo",
}


@dataclass
class LinhaTabela:
    chave: object
    rotulo: str
    meses: list[int | None] = field(default_factory=lambda: [None] * 12)
    realizado: int = 0
    forecast: int = 0
    orcamento: int | None = None

    @property
    def total_ano(self) -> int:
        return self.realizado + self.forecast

    @property
    def gap(self) -> int | None:
        if self.orcamento is None:
            return None
        return orcamento.gap(self.orcamento, self.total_ano)


@dataclass
class Tabela:
    ano: int
    dimensao: str
    origem: str
    base: str
    linhas: list[LinhaTabela]
    total_realizado: int = 0
    total_forecast: int = 0
    nota: str | None = None


def _nomes(conexao: Conexao, bd_id: int) -> dict[str, dict[int, str]]:
    orgs = organizacao.listar_orgs(conexao, bd_id)
    por_id = {o.id: o for o in orgs}
    return {
        "iniciativa": {i.id: i.nome for i in portfolio.listar_iniciativas(conexao, bd_id)},
        "demanda": {d.id: d.nome for d in portfolio.listar_demandas(conexao, bd_id)},
        "tema": {t.id: t.nome for t in portfolio.listar_temas(conexao, bd_id)},
        "agrupamento": {a.id: a.nome for a in portfolio.listar_agrupamentos(conexao, bd_id)},
        "squad": {o.id: o.nome for o in orgs},
        "tribo": {o.id: (por_id[o.pai_id].nome if o.pai_id in por_id else o.nome) for o in orgs},
    }


def _chave(linha, dimensao: str):
    if dimensao == "origem":
        return linha.origem
    return {
        "iniciativa": linha.iniciativa_id,
        "iniciativa_tipo": (linha.iniciativa_id, linha.tipo),
        "demanda": linha.demanda_id,
        "tema": linha.tema_id,
        "agrupamento": linha.agrupamento_id,
        "tipo": linha.tipo,
        "squad": linha.org_id,
        "tribo": linha.org_id,
    }[dimensao]


def _rotulo(chave, dimensao: str, nomes: dict[str, dict[int, str]]) -> str:
    if dimensao == "origem":
        return "Pessoas" if chave == "pessoas" else "Compras"
    if dimensao == "tipo":
        return str(chave)
    if dimensao == "iniciativa_tipo":
        return f"{nomes['iniciativa'].get(chave[0], '#' + str(chave[0]))} · {chave[1]}"
    if chave is None:
        return _SEM[dimensao]
    return nomes[dimensao].get(chave, f"#{chave}")


def consultar(
    conexao: Conexao,
    bd_id: int,
    ano: int,
    dimensao: str,
    origem: str,
    base: str,
    agora: datetime,
) -> Tabela:
    if dimensao not in DIMENSOES or origem not in ORIGENS or base not in BASES:
        raise ValueError(f"consulta inválida: {dimensao!r}, {origem!r}, {base!r}")
    nomes = _nomes(conexao, bd_id)
    linhas: dict[object, LinhaTabela] = {}
    fora = 0  # valor das origens filtradas, para a nota de reconciliação
    for numero in range(1, 13):
        mes = f"{ano:04d}-{numero:02d}"
        estado, lancamentos = consumo.do_mes(conexao, bd_id, mes)
        for lancamento in lancamentos:
            valor = lancamento.bruto_centavos if base == "bruto" else lancamento.liquido_centavos
            if origem != "todas" and lancamento.origem != origem:
                fora += valor
                continue
            chave = _chave(lancamento, dimensao)
            linha = linhas.setdefault(chave, LinhaTabela(chave, _rotulo(chave, dimensao, nomes)))
            if estado == "realizado":
                linha.meses[numero - 1] = (linha.meses[numero - 1] or 0) + valor
                linha.realizado += valor
            else:
                linha.forecast += valor
        if estado == "realizado":
            for linha in linhas.values():
                if linha.meses[numero - 1] is None:
                    linha.meses[numero - 1] = 0

    if dimensao in ("iniciativa", "iniciativa_tipo"):
        vigente = orcamento.vigente(conexao, bd_id)
        if vigente is not None:
            for item in orcamento.linhas(conexao, bd_id, vigente.id, agora):
                chave = (
                    item.iniciativa_id
                    if dimensao == "iniciativa"
                    else (item.iniciativa_id, item.tipo)
                )
                rotulo = (
                    item.iniciativa
                    if dimensao == "iniciativa"
                    else f"{item.iniciativa} · {item.tipo}"
                )
                linha = linhas.setdefault(chave, LinhaTabela(chave, rotulo))
                valor = item.bruto_centavos if base == "bruto" else item.liquido_centavos
                linha.orcamento = (linha.orcamento or 0) + valor

    ordenadas = sorted(linhas.values(), key=lambda x: (-x.total_ano, x.rotulo))
    tabela = Tabela(ano, dimensao, origem, base, ordenadas)
    tabela.total_realizado = sum(x.realizado for x in ordenadas)
    tabela.total_forecast = sum(x.forecast for x in ordenadas)
    if fora:
        tabela.nota = (
            f"Esta tabela mostra só {origem}. Ficam de fora {i18n.moeda(fora)} "
            f"de {'compras' if origem == 'pessoas' else 'pessoas'} (realizado e forecast do ano)."
        )
    return tabela
