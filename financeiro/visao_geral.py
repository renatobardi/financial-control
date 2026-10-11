"""Visão geral: KPIs, curva do ano, iniciativas em risco, composição do gasto e avisos."""

from dataclasses import dataclass, field
from datetime import datetime

from financeiro import fechamento, forecast, orcamento, vigencia
from financeiro.store import Conexao, portfolio
from financeiro.store import cenarios as armazem_cenarios
from financeiro.store import consumo as armazem_consumo
from financeiro.store.cenarios import Cenario


@dataclass(frozen=True)
class Risco:
    nome: str
    orcamento: int
    realizado: int
    forecast: int
    tipo: str = ""

    @property
    def projetado_pct(self) -> int | None:
        """Percentual do orçamento que o realizado mais o forecast consomem."""
        if not self.orcamento:
            return None
        return (self.realizado + self.forecast) * 100 // self.orcamento

    @property
    def saldo(self) -> int:
        return orcamento.gap(self.orcamento, self.realizado + self.forecast)


# Tag, atalho (rótulo e URL) de cada tipo de alerta, como no protótipo.
_ATALHOS = {
    "mes_para_fechar": ("atrasado", "Fechar", "/fechamento"),
    "prazo_fechamento": ("em_breve", "Fechar", "/fechamento"),
    "cargas_pendentes": ("carga", "Ver", "/cargas"),
    "iniciativa_estourada": ("estouro", "Forecast", "/forecast"),
    "vaga_comecando": ("vaga", "Vagas", "/cadastros?aba=vagas"),
    "ordens_previstas": ("ordem", "Compras", "/compras?status=prevista"),
    "pdd_rascunho": ("pdd", "Orçamento", "/orcamento"),
}


@dataclass(frozen=True)
class Alerta:
    chave: str  # chave do catálogo: visao.alerta_<chave>
    params: dict = field(default_factory=dict)

    @property
    def tag(self) -> str:
        return _ATALHOS[self.chave][0]

    @property
    def atalho(self) -> str:
        return _ATALHOS[self.chave][1]

    @property
    def url(self) -> str:
        return _ATALHOS[self.chave][2]


@dataclass(frozen=True)
class Visao:
    ano: int
    base: str
    realizado: int
    forecast: int
    orcamento: int | None
    gap: int | None
    curva_budget: list[int]
    curva_realizado: list[int | None]
    curva_forecast: list[int | None]
    composicao: list[tuple[str, int]]
    risco: list[Risco]
    alertas: list[Alerta]
    por_tipo: list[tuple[str, int]] = field(default_factory=list)
    por_agrupamento: list[tuple[str, int]] = field(default_factory=list)

    @property
    def total_ano(self) -> int:
        return self.realizado + self.forecast

    @property
    def executado_pct(self) -> int | None:
        """Percentual do orçamento já realizado, em centésimos de ponto percentual."""
        if not self.orcamento:
            return None
        return self.realizado * 10_000 // self.orcamento


def visao(
    conexao: Conexao,
    bd_id: int,
    ano: int,
    cenario: Cenario,
    base: str,
    agora: datetime,
    revisao_id: int | None = None,
) -> Visao:
    todos = forecast.atomos(conexao, bd_id, ano, cenario, agora)
    cache: dict[str, int] = {}
    por_mes_real = [0] * 12
    por_mes_fc = [0] * 12
    fechados = [False] * 12
    por_iniciativa: dict[tuple[int, str], list[int]] = {}
    por_origem = {"pessoas": 0, "compras": 0, "vagas": 0}
    tipo_valor: dict[str, int] = {}
    agrup_valor: dict[int | None, int] = {}
    for a in todos:
        valor = forecast.na_base(conexao, bd_id, a, base, cache)
        n = int(a.mes[5:]) - 1
        if a.realizado:
            por_mes_real[n] += valor
            fechados[n] = True
        else:
            por_mes_fc[n] += valor
        item = por_iniciativa.setdefault((a.iniciativa_id, a.tipo), [0, 0])
        item[0 if a.realizado else 1] += valor
        por_origem[a.origem] += valor
        tipo_valor[a.tipo] = tipo_valor.get(a.tipo, 0) + valor
        agrup_valor[a.agrupamento_id] = agrup_valor.get(a.agrupamento_id, 0) + valor

    realizado, fc = sum(por_mes_real), sum(por_mes_fc)
    total_orc = forecast.orcamento_da_revisao(conexao, bd_id, revisao_id, base, agora)

    budget = [(total_orc or 0) * (n + 1) // 12 for n in range(12)]
    acumulado, real_acum = 0, []
    for n in range(12):
        acumulado += por_mes_real[n]
        real_acum.append(acumulado if fechados[n] else None)
    ultimo_fechado = max((n for n in range(12) if fechados[n]), default=-1)
    fc_acum: list[int | None] = []
    corrente = 0
    for n in range(12):
        corrente += por_mes_real[n] + por_mes_fc[n]
        fc_acum.append(corrente if n >= max(ultimo_fechado, 0) and (n > ultimo_fechado) else None)
    if ultimo_fechado >= 0:
        fc_acum[ultimo_fechado] = real_acum[ultimo_fechado]

    nomes = {i.id: i.nome for i in portfolio.listar_iniciativas(conexao, bd_id)}
    agrupamentos = {a.id: a.nome for a in portfolio.listar_agrupamentos(conexao, bd_id)}
    revisao = forecast.revisao_escolhida(conexao, bd_id, revisao_id)
    orc_ini: dict[tuple[int, str], int] = {}
    if revisao is not None:
        for linha in orcamento.linhas(conexao, bd_id, revisao.id, agora):
            valor = linha.bruto_centavos if base == "bruto" else linha.liquido_centavos
            chave = (linha.iniciativa_id, linha.tipo)
            orc_ini[chave] = orc_ini.get(chave, 0) + valor
    riscos = [
        Risco(nomes.get(i, f"#{i}"), orc_ini.get((i, t), 0), r, f, t)
        for (i, t), (r, f) in por_iniciativa.items()
        if orc_ini.get((i, t), 0) > 0
    ]
    for (i, t), valor in orc_ini.items():
        if (i, t) not in por_iniciativa and valor > 0:
            riscos.append(Risco(nomes.get(i, f"#{i}"), valor, 0, 0, t))
    riscos.sort(key=lambda r: (r.saldo, r.nome))

    alertas = _alertas(conexao, bd_id, ano, agora, riscos, cenario)
    return Visao(
        ano, base, realizado, fc, total_orc,
        None if total_orc is None else orcamento.gap(total_orc, realizado + fc),
        budget, real_acum, fc_acum,
        [("Pessoas", por_origem["pessoas"]), ("Compras", por_origem["compras"]),
         ("Vagas", por_origem["vagas"])],
        riscos[:5], alertas,
        sorted(tipo_valor.items()),
        sorted(
            ((agrupamentos.get(a, "Sem agrupamento"), v) for a, v in agrup_valor.items()),
            key=lambda x: -x[1],
        ),
    )  # fmt: skip


def _alertas(
    conexao: Conexao, bd_id: int, ano: int, agora: datetime, riscos: list[Risco], cenario: Cenario
) -> list[Alerta]:
    alertas: list[Alerta] = []
    hoje = agora.strftime("%Y-%m")
    for m in fechamento.situacao(conexao, bd_id, ano, agora):
        if m.pode_fechar and m.mes < hoje:
            alertas.append(Alerta("mes_para_fechar", {"mes": m.mes}))
            break
    pendentes = fechamento.cargas_com_rejeicao_pendente(conexao, bd_id)
    if pendentes:
        alertas.append(Alerta("cargas_pendentes", {"n": pendentes}))
    for r in riscos:
        if r.saldo < 0:
            alertas.append(Alerta("iniciativa_estourada", {"nome": r.nome}))
    previstas = armazem_consumo.ordens_previstas(conexao, bd_id)
    if previstas:
        alertas.append(Alerta("ordens_previstas", {"n": previstas}))
    if orcamento.rascunho(conexao, bd_id) is not None:
        alertas.append(Alerta("pdd_rascunho"))
    inicios = armazem_cenarios.inicios_de_vaga(conexao, bd_id, cenario.id)
    limite = vigencia.mes_anterior(hoje)
    for vaga_id, mes in inicios.items():
        if limite < mes <= _somar_meses(hoje, 2):
            alertas.append(Alerta("vaga_comecando", {"vaga": vaga_id, "mes": mes}))
    return alertas


def _somar_meses(mes: str, n: int) -> str:
    ano, numero = int(mes[:4]), int(mes[5:]) - 1 + n
    return f"{ano + numero // 12:04d}-{numero % 12 + 1:02d}"
