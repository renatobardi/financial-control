"""Visão geral: KPIs, curva do ano, iniciativas em risco, composição do gasto e avisos."""

from dataclasses import dataclass, field
from datetime import datetime

from financeiro import fechamento, forecast, orcamento, vigencia
from financeiro.store import Conexao, portfolio
from financeiro.store import cenarios as armazem_cenarios
from financeiro.store.cenarios import Cenario


@dataclass(frozen=True)
class Risco:
    nome: str
    orcamento: int
    realizado: int
    forecast: int

    @property
    def saldo(self) -> int:
        return orcamento.gap(self.orcamento, self.realizado + self.forecast)


@dataclass(frozen=True)
class Alerta:
    chave: str  # chave do catálogo: visao.alerta_<chave>
    params: dict = field(default_factory=dict)


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
    por_iniciativa: dict[int, list[int]] = {}
    por_origem = {"pessoas": 0, "compras": 0, "vagas": 0}
    for a in todos:
        valor = forecast.na_base(conexao, bd_id, a, base, cache)
        n = int(a.mes[5:]) - 1
        if a.realizado:
            por_mes_real[n] += valor
            fechados[n] = True
        else:
            por_mes_fc[n] += valor
        item = por_iniciativa.setdefault(a.iniciativa_id, [0, 0])
        item[0 if a.realizado else 1] += valor
        por_origem[a.origem] += valor

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
    revisao = forecast.revisao_escolhida(conexao, bd_id, revisao_id)
    orc_ini: dict[int, int] = {}
    if revisao is not None:
        for linha in orcamento.linhas(conexao, bd_id, revisao.id, agora):
            valor = linha.bruto_centavos if base == "bruto" else linha.liquido_centavos
            orc_ini[linha.iniciativa_id] = orc_ini.get(linha.iniciativa_id, 0) + valor
    riscos = [
        Risco(nomes.get(i, f"#{i}"), orc_ini.get(i, 0), r, f)
        for i, (r, f) in por_iniciativa.items()
        if orc_ini.get(i, 0) > 0
    ]
    for i, valor in orc_ini.items():
        if i not in por_iniciativa and valor > 0:
            riscos.append(Risco(nomes.get(i, f"#{i}"), valor, 0, 0))
    riscos.sort(key=lambda r: (r.saldo, r.nome))

    alertas = _alertas(conexao, bd_id, ano, agora, riscos, cenario)
    return Visao(
        ano, base, realizado, fc, total_orc,
        None if total_orc is None else orcamento.gap(total_orc, realizado + fc),
        budget, real_acum, fc_acum,
        [("Pessoas", por_origem["pessoas"]), ("Compras", por_origem["compras"]),
         ("Vagas", por_origem["vagas"])],
        riscos[:5], alertas,
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
    inicios = armazem_cenarios.inicios_de_vaga(conexao, bd_id, cenario.id)
    limite = vigencia.mes_anterior(hoje)
    for vaga_id, mes in inicios.items():
        if limite < mes <= _somar_meses(hoje, 2):
            alertas.append(Alerta("vaga_comecando", {"vaga": vaga_id, "mes": mes}))
    return alertas


def _somar_meses(mes: str, n: int) -> str:
    ano, numero = int(mes[:4]), int(mes[5:]) - 1 + n
    return f"{ano + numero // 12:04d}-{numero % 12 + 1:02d}"
