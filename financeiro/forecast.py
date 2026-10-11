"""Forecast: o que já foi realizado (meses fechados) mais o que se projeta para os meses abertos.

Para cada mês aberto, no cenário escolhido:
- o que já está lançado (horas das pessoas, compras) vale, com o fator do cenário;
- a pessoa ativa sem lançamento no mês entra com a capacidade do mês (8 h × dias úteis);
- a vaga aberta entra a partir do mês de início do cenário, com a capacidade do mês.
Mês fechado entra como realizado, sem fator (ADR-0003).
"""

from dataclasses import dataclass
from datetime import datetime

from financeiro import calendario, cenarios, consumo, custo, i18n, orcamento, treemap
from financeiro.cenarios import CenarioInvalido
from financeiro.store import Conexao, organizacao, pessoas, portfolio
from financeiro.store import cadastros as cadastros_store
from financeiro.store import cenarios as armazem
from financeiro.store import consumo as armazem_consumo
from financeiro.store.cenarios import Cenario


@dataclass(frozen=True)
class Atomo:
    mes: str
    origem: str  # pessoas | compras | vagas
    realizado: bool
    iniciativa_id: int
    tipo: str
    agrupamento_id: int | None
    org_id: int | None
    valor_centavos: int  # bruto
    ref_id: int | None = None
    demanda_id: int | None = None


@dataclass(frozen=True)
class Resumo:
    realizado: int
    forecast: int
    orcamento: int | None
    gap: int | None

    @property
    def total_ano(self) -> int:
        return self.realizado + self.forecast


def _fator(valor: int, fator_centesimos_pct: int) -> int:
    return (valor * fator_centesimos_pct + 5_000) // 10_000


def _proximo_mes(mes: str) -> str:
    ano, numero = int(mes[:4]), int(mes[5:])
    return f"{ano + 1}-01" if numero == 12 else f"{ano}-{numero + 1:02d}"


def _dividir(valor: int, agrupamentos: list[int | None]) -> list[tuple[int | None, int]]:
    """Reparte o valor em partes iguais entre os agrupamentos dos temas (resto no primeiro)."""
    if not agrupamentos:
        return [(None, valor)]
    parte, resto = divmod(valor, len(agrupamentos))
    return [(a, parte + (resto if i == 0 else 0)) for i, a in enumerate(agrupamentos)]


def atomos(
    conexao: Conexao, bd_id: int, ano: int, cenario: Cenario, agora: datetime
) -> list[Atomo]:
    mapa = armazem.mapa_temas(conexao, bd_id)
    agrupamentos_da_demanda: dict[int, list[int | None]] = {}
    for demanda, _ini, _tipo, agrup, _sq in mapa.values():
        agrupamentos_da_demanda.setdefault(demanda, []).append(agrup)
    detalhes = pessoas.listar_detalhe(conexao, bd_id)
    vagas = [v for v in pessoas.listar_vagas(conexao, bd_id) if v.estado == "aberta"]
    inicios = armazem.inicios_de_vaga(conexao, bd_id, cenario.id)
    resultado: list[Atomo] = []
    for numero in range(1, 13):
        mes = f"{ano:04d}-{numero:02d}"
        if armazem_consumo.mes_esta_fechado(conexao, bd_id, mes):
            for x in consumo.do_mes(conexao, bd_id, mes)[1]:
                partes = (
                    _dividir(x.bruto_centavos, agrupamentos_da_demanda.get(x.demanda_id, []))
                    if x.origem == "compras"
                    else [(x.agrupamento_id, x.bruto_centavos)]
                )
                for agrup, valor in partes:
                    resultado.append(
                        Atomo(mes, x.origem, True, x.iniciativa_id, x.tipo, agrup, x.org_id,
                              valor, x.pessoa_id or x.compra_id, x.demanda_id)
                    )  # fmt: skip
            continue
        com_lancamento: set[int] = set()
        for x in consumo.calcular(conexao, bd_id, mes).linhas:
            fator = cenario.fator_pessoas if x.origem == "pessoas" else cenario.fator_compras
            if x.origem == "pessoas" and x.pessoa_id is not None:
                com_lancamento.add(x.pessoa_id)
            total = _fator(x.bruto_centavos, fator)
            partes = (
                _dividir(total, agrupamentos_da_demanda.get(x.demanda_id, []))
                if x.origem == "compras"
                else [(x.agrupamento_id, total)]
            )
            for agrup, valor in partes:
                resultado.append(
                    Atomo(mes, x.origem, False, x.iniciativa_id, x.tipo, agrup, x.org_id, valor,
                          x.pessoa_id or x.compra_id, x.demanda_id)
                )  # fmt: skip
        capacidade = calendario.capacidade(conexao, bd_id, ano, numero)
        horas_custo: dict[int, int | None] = {}

        def bruto_por_hora(cargo_id: int, mes: str = mes, cache: dict = horas_custo) -> int | None:
            if cargo_id not in cache:
                try:
                    cache[cargo_id] = custo.custo_hora(conexao, bd_id, cargo_id, mes).bruta_centavos
                except custo.SemTarifa:
                    cache[cargo_id] = None
            return cache[cargo_id]

        for p in detalhes:
            ativa = p.admissao <= mes and (p.desligamento is None or p.desligamento >= mes)
            if not ativa or p.id in com_lancamento or p.tema_id not in mapa:
                continue
            hora = bruto_por_hora(p.cargo_id)
            if hora is None:
                continue
            demanda, iniciativa, tipo, agrup, _squad = mapa[p.tema_id]
            resultado.append(
                Atomo(mes, "pessoas", False, iniciativa, tipo, agrup, p.org_id,
                      _fator(capacidade * hora, cenario.fator_pessoas), p.id, demanda)
            )  # fmt: skip
        for v in vagas:
            inicio = inicios.get(v.id) or _proximo_mes(v.aberta_em)
            if mes < inicio or v.tema_id not in mapa:
                continue
            hora = bruto_por_hora(v.cargo_id)
            if hora is None:
                continue
            demanda, iniciativa, tipo, agrup, _squad = mapa[v.tema_id]
            resultado.append(
                Atomo(mes, "vagas", False, iniciativa, tipo, agrup, v.org_id,
                      _fator(capacidade * hora, cenario.fator_pessoas), v.id, demanda)
            )  # fmt: skip
    return resultado


def na_base(conexao: Conexao, bd_id: int, atomo: Atomo, base: str, cache: dict) -> int:
    if base == "bruto":
        return atomo.valor_centavos
    if atomo.mes not in cache:
        markup = cadastros_store.markup_vigente(conexao, bd_id, atomo.mes)
        cache[atomo.mes] = markup.centesimos_pct if markup else 0
    return orcamento.liquido_de(atomo.valor_centavos, cache[atomo.mes])


def revisao_escolhida(conexao: Conexao, bd_id: int, revisao_id: int | None):
    if revisao_id is None:
        return orcamento.vigente(conexao, bd_id)
    return next((r for r in orcamento.revisoes(conexao, bd_id) if r.id == revisao_id), None)


def orcamento_da_revisao(
    conexao: Conexao, bd_id: int, revisao_id: int | None, base: str, agora: datetime
) -> int | None:
    """Total do PDD da revisão (a vigente se não informada), na base pedida."""
    revisao = revisao_escolhida(conexao, bd_id, revisao_id)
    if revisao is None:
        return None
    return sum(
        x.bruto_centavos if base == "bruto" else x.liquido_centavos
        for x in orcamento.linhas(conexao, bd_id, revisao.id, agora)
    )


def resumo(
    conexao: Conexao,
    bd_id: int,
    ano: int,
    cenario: Cenario,
    base: str,
    agora: datetime,
    revisao_id: int | None = None,
) -> Resumo:
    """Realizado, forecast do cenário, orçamento da revisão e gap (orçamento − total do ano)."""
    cache: dict[str, int] = {}
    realizado = forecast = 0
    for a in atomos(conexao, bd_id, ano, cenario, agora):
        valor = na_base(conexao, bd_id, a, base, cache)
        if a.realizado:
            realizado += valor
        else:
            forecast += valor
    total_orcamento = orcamento_da_revisao(conexao, bd_id, revisao_id, base, agora)
    if total_orcamento is None:
        return Resumo(realizado, forecast, None, None)
    return Resumo(
        realizado, forecast, total_orcamento, orcamento.gap(total_orcamento, realizado + forecast)
    )


# ---------- composição do treemap: escala, elementos e o que cabe ----------

LARGURA_TREEMAP = 1000.0
ALTURA_TREEMAP = 560.0
_ARREDONDA_ESCALA = 1_000_000  # R$ 10.000,00 em centavos


@dataclass(frozen=True)
class Elemento:
    chave: str
    nome: str
    realizado: int
    forecast: int
    demandas: int = 0
    ordens: int = 0
    vagas: int = 0

    @property
    def total(self) -> int:
        return self.realizado + self.forecast


@dataclass(frozen=True)
class Composicao:
    meses: list[str]
    escala_nome: str
    escala_valor: int
    elementos: list[Elemento]
    incluidos: list[Elemento]
    soma_incluidos: int
    soma_realizado: int
    disponivel: int
    blocos: list
    periodo_rotulo: str = ""
    uso_centesimos_pct: int = 0  # incluído ÷ escala, em centésimos de ponto percentual
    escala_do_cenario: bool = False  # valor da escala informado, não o padrão


def _rotulo_periodo(ano: int, trimestres: int) -> str:
    marcados = [q + 1 for q in range(4) if trimestres & (1 << q)]
    if len(marcados) == 4:
        return f"Ano {ano}"
    return " · ".join(f"T{q}/{str(ano)[2:]}" for q in marcados)


def meses_do_periodo(ano: int, trimestres: int) -> list[str]:
    """Meses dos trimestres marcados no bit a bit (bit 0 = 1º trimestre)."""
    meses = []
    for q in range(4):
        if trimestres & (1 << q):
            meses += [f"{ano:04d}-{m:02d}" for m in range(q * 3 + 1, q * 3 + 4)]
    return meses


def _tribo_de(org_id: int | None, orgs: dict) -> int | None:
    org = orgs.get(org_id)
    if org is None:
        return None
    return org.id if org.tipo == "Tribo" else org.pai_id


def composicao(
    conexao: Conexao,
    bd_id: int,
    ano: int,
    cenario: Cenario,
    base: str,
    agora: datetime,
    revisao_id: int | None = None,
) -> Composicao:
    orgs = {o.id: o for o in organizacao.listar_orgs(conexao, bd_id)}
    agrupamentos = {a.id: a.nome for a in portfolio.listar_agrupamentos(conexao, bd_id)}
    meses = set(meses_do_periodo(ano, cenario.trimestres))
    cache: dict[str, int] = {}

    def na_escala(a: Atomo) -> bool:
        if cenario.escala_tipo == "PDD":
            return True
        if cenario.escala_tipo == "Agrupamento":
            return a.agrupamento_id == cenario.escala_ref
        if cenario.escala_tipo == "Squad":
            return a.org_id == cenario.escala_ref
        return _tribo_de(a.org_id, orgs) == cenario.escala_ref

    def chave_de(a: Atomo) -> int | None:
        if cenario.elemento_tipo == "Agrupamento":
            return a.agrupamento_id if a.agrupamento_id is not None else 0
        if cenario.elemento_tipo == "Squad":
            return a.org_id
        return _tribo_de(a.org_id, orgs)

    def nome_de(chave: int) -> str:
        if cenario.elemento_tipo == "Agrupamento":
            return agrupamentos.get(chave, "Sem agrupamento")
        return orgs[chave].nome if chave in orgs else "—"

    real: dict[int, int] = {}
    fc: dict[int, int] = {}
    demandas: dict[int, set] = {}
    ordens: dict[int, set] = {}
    vagas: dict[int, set] = {}
    total_periodo = total_na_escala = 0
    for a in atomos(conexao, bd_id, ano, cenario, agora):
        if a.mes not in meses:
            continue
        valor = na_base(conexao, bd_id, a, base, cache)
        total_periodo += valor
        if not na_escala(a):
            continue
        total_na_escala += valor
        chave = chave_de(a)
        if chave is None:
            continue
        (real if a.realizado else fc)[chave] = (real if a.realizado else fc).get(chave, 0) + valor
        if a.demanda_id is not None:
            demandas.setdefault(chave, set()).add(a.demanda_id)
        if a.origem == "compras" and a.ref_id is not None:
            ordens.setdefault(chave, set()).add(a.ref_id)
        if a.origem == "vagas" and a.ref_id is not None:
            vagas.setdefault(chave, set()).add(a.ref_id)
    chaves = sorted(set(real) | set(fc))
    elementos = sorted(
        (
            Elemento(
                str(k),
                nome_de(k),
                real.get(k, 0),
                fc.get(k, 0),
                len(demandas.get(k, ())),
                len(ordens.get(k, ())),
                len(vagas.get(k, ())),
            )  # fmt: skip
            for k in chaves
            if real.get(k, 0) + fc.get(k, 0) > 0
        ),
        key=lambda e: (-e.total, e.nome),
    )

    vigente = revisao_escolhida(conexao, bd_id, revisao_id)
    pdd_ano = orcamento_da_revisao(conexao, bd_id, revisao_id, base, agora) or 0
    pdd_periodo = pdd_ano * len(meses) // 12
    if cenario.escala_valor_centavos is not None:
        escala_valor = cenario.escala_valor_centavos
    elif cenario.escala_tipo == "PDD" or total_periodo == 0:
        escala_valor = pdd_periodo
    else:
        escala_valor = pdd_periodo * total_na_escala // total_periodo
    if cenario.escala_valor_centavos is None:
        escala_valor = (
            (escala_valor + _ARREDONDA_ESCALA // 2) // _ARREDONDA_ESCALA * _ARREDONDA_ESCALA
        )
    escala_nome = {
        "PDD": f"PDD {vigente.rotulo}" if vigente else "PDD",
        "Agrupamento": agrupamentos.get(cenario.escala_ref or 0, "—"),
        "Tribo": orgs[cenario.escala_ref].nome if cenario.escala_ref in orgs else "—",
        "Squad": orgs[cenario.escala_ref].nome if cenario.escala_ref in orgs else "—",
    }[cenario.escala_tipo]

    incluidos = [e for e in elementos if e.chave in cenario.incluidos]
    soma = sum(e.total for e in incluidos)
    disponivel = escala_valor - soma
    itens = [(e.chave, e.total) for e in incluidos]
    if disponivel > 0:
        itens.append(("__saldo", disponivel))
    blocos = treemap.layout(itens, LARGURA_TREEMAP, ALTURA_TREEMAP)
    uso = soma * 10_000 // escala_valor if escala_valor > 0 else 0
    return Composicao(
        sorted(meses), escala_nome, escala_valor, elementos, incluidos, soma,
        sum(e.realizado for e in incluidos), disponivel, blocos,
        _rotulo_periodo(ano, cenario.trimestres), uso,
        cenario.escala_valor_centavos is not None,
    )  # fmt: skip


def incluir(
    conexao: Conexao,
    bd_id: int,
    ano: int,
    cenario: Cenario,
    chave: str,
    base: str,
    agora: datetime,
) -> None:
    """Inclui o elemento no cenário se ele cabe no que resta da escala."""
    atual = composicao(conexao, bd_id, ano, cenario, base, agora)
    elemento = next((e for e in atual.elementos if e.chave == chave), None)
    if elemento is None:
        raise CenarioInvalido("Elemento não encontrado neste cenário e período.")
    if chave in cenario.incluidos:
        return
    if elemento.total > atual.disponivel + 100:  # tolerância de R$ 1,00
        restante = max(atual.disponivel, 0)
        raise CenarioInvalido(
            f"Não cabe: {elemento.nome} custa {i18n.moeda(elemento.total)} e restam "
            f"{i18n.moeda(restante)} na escala. Faltam {i18n.moeda(elemento.total - restante)}."
        )
    cenarios.atualizar(conexao, bd_id, cenario.id, incluidos=[*cenario.incluidos, chave])


def retirar(conexao: Conexao, bd_id: int, cenario: Cenario, chave: str) -> None:
    cenarios.atualizar(
        conexao, bd_id, cenario.id, incluidos=[c for c in cenario.incluidos if c != chave]
    )
