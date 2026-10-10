"""Os seis layouts de carga: colunas, regras de validação e o que cada linha grava."""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from financeiro import calendario, i18n, vigencia
from financeiro.store import Conexao
from financeiro.store import cargas as armazem


class Rejeita(Exception):
    """Uma linha não entra: regra (código) e mensagem para o relatório."""

    def __init__(self, regra: str, mensagem: str, aprovavel: bool = False):
        super().__init__(mensagem)
        self.regra = regra
        self.mensagem = mensagem
        self.aprovavel = aprovavel


@dataclass
class Contexto:
    conexao: Conexao
    bd_id: int
    diario: armazem.Diario


@dataclass
class Resultado:
    linha: int
    dados: dict[str, str]
    acao: str  # inserida | atualizada | igual | rejeitada
    regra: str = ""
    mensagem: str = ""
    horas: int = 0
    valor_centavos: int = 0
    aprovavel: bool = False
    grupo: str | None = None


@dataclass(frozen=True)
class Layout:
    chave: str
    nome: str
    colunas: tuple[str, ...]
    opcionais: tuple[str, ...]
    processar: Callable[[Contexto, list[tuple[int, dict[str, str]]]], list[Resultado]]


# ---------- leitura de valores ----------


def _mes(ano: str, mes: str) -> str:
    if not (ano.isdigit() and mes.isdigit() and len(ano) == 4 and 1 <= int(mes) <= 12):
        raise Rejeita("MES_INVALIDO", f"Ano {ano!r} e mês {mes!r} não formam um mês válido.")
    return f"{int(ano):04d}-{int(mes):02d}"


def _mes_texto(texto: str, coluna: str) -> str:
    try:
        return vigencia.validar_mes(texto)
    except ValueError as erro:
        raise Rejeita("MES_INVALIDO", f"{coluna} {texto!r} não está no formato AAAA-MM.") from erro


def _rotulo_mes(mes: str) -> str:
    return i18n.mes(int(mes[:4]), int(mes[5:]))


def _dinheiro(texto: str) -> int:
    limpo = texto.strip()
    if re.fullmatch(r"\d+\.\d{1,2}", limpo):  # exportação com ponto decimal: 1234.56
        limpo = limpo.replace(".", ",")
    try:
        return i18n.ler_moeda(limpo)
    except ValueError as erro:
        raise Rejeita("VALOR_INVALIDO", f"Valor {texto!r} não é um valor em reais.") from erro


def _achar(ctx: Contexto, tabela: str, coluna: str, valor: str) -> int | None:
    return armazem.id_por(ctx.conexao, tabela, coluna, ctx.bd_id, valor)


def _exigir_aberto(ctx: Contexto, mes: str) -> None:
    if armazem.mes_fechado(ctx.conexao, ctx.bd_id, mes):
        raise Rejeita(
            "MES_FECHADO",
            f"{_rotulo_mes(mes)} está fechado. Reabra em Fechamento para carregar.",
        )


def _por_linha(
    ctx: Contexto,
    linhas: list[tuple[int, dict[str, str]]],
    aplicar: Callable[[Contexto, dict[str, str]], tuple[str, int, int]],
) -> list[Resultado]:
    """Aplica uma função por linha; `Rejeita` vira linha rejeitada no relatório."""
    resultados = []
    for numero, dados in linhas:
        try:
            acao, horas, valor = aplicar(ctx, dados)
        except Rejeita as r:
            resultados.append(
                Resultado(numero, dados, "rejeitada", r.regra, r.mensagem, aprovavel=r.aprovavel)
            )
        else:
            resultados.append(Resultado(numero, dados, acao, horas=horas, valor_centavos=valor))
    return resultados


# ---------- horas realizadas ----------


def _horas(ctx: Contexto, linhas: list[tuple[int, dict[str, str]]]) -> list[Resultado]:
    resultados: dict[int, Resultado] = {}
    validas: list[tuple[int, dict[str, str], int, int, str, int]] = []
    for numero, d in linhas:
        try:
            pessoa = _achar(ctx, "pessoa", "matricula", d["matricula"])
            if pessoa is None:
                raise Rejeita("PESSOA_INEXISTENTE", f"Matrícula {d['matricula']} não cadastrada.")
            tema = _achar(ctx, "tema", "codigo", d["tema_codigo"])
            if tema is None:
                raise Rejeita("TEMA_INEXISTENTE", f"Tema {d['tema_codigo']} não cadastrado.")
            mes = _mes(d["ano"], d["mes"])
            if not d["horas"].isdigit():
                raise Rejeita("VALOR_INVALIDO", f"Horas {d['horas']!r} não é um inteiro positivo.")
            _exigir_aberto(ctx, mes)
        except Rejeita as r:
            resultados[numero] = Resultado(numero, d, "rejeitada", r.regra, r.mensagem)
        else:
            validas.append((numero, d, pessoa, tema, mes, int(d["horas"])))

    ultima: dict[tuple[int, int, str], int] = {}
    for numero, _d, pessoa, tema, mes, _h in validas:
        ultima[(pessoa, tema, mes)] = numero
    uteis = []
    for item in validas:
        numero, d, pessoa, tema, mes, _h = item
        if ultima[(pessoa, tema, mes)] != numero:
            resultados[numero] = Resultado(
                numero,
                d,
                "rejeitada",
                "LINHA_DUPLICADA",
                "Mesma pessoa, tema e mês em outra linha: vale a última.",
            )
        else:
            uteis.append(item)

    grupos: dict[tuple[int, str], list] = {}
    for item in uteis:
        grupos.setdefault((item[2], item[4]), []).append(item)
    for (pessoa, mes), itens in grupos.items():
        temas = [i[3] for i in itens]
        no_arquivo = sum(i[5] for i in itens)
        outros = armazem.horas_dos_outros_temas(ctx.conexao, ctx.bd_id, pessoa, mes, temas)
        total = no_arquivo + outros
        capacidade = calendario.capacidade(ctx.conexao, ctx.bd_id, int(mes[:4]), int(mes[5:]))
        if total > capacidade:
            detalhe = " · ".join(f"{i[1]['tema_codigo']} {i[5]}h" for i in itens)
            grupo = f"{itens[0][1]['matricula']}|{mes}"
            mensagem = (
                f"{total}h ({detalhe}) > {capacidade}h do calendário. "
                f"Excedente {total - capacidade}h."
            )
            for numero, d, *_ in itens:
                resultados[numero] = Resultado(
                    numero, d, "rejeitada", "HORAS_ACIMA_CAL", mensagem, aprovavel=True, grupo=grupo
                )
            continue
        for numero, d, pessoa_id, tema_id, mes_item, horas in itens:
            acao = armazem.upsert(
                ctx.conexao,
                ctx.diario,
                "alocacao",
                ctx.bd_id,
                {"pessoa_id": pessoa_id, "tema_id": tema_id, "mes": mes_item},
                {"horas": horas, "extra": 0},
            )
            resultados[numero] = Resultado(numero, d, acao, horas=horas)
    return [resultados[n] for n, _ in linhas]


# ---------- compras realizadas ----------


def _compra(ctx: Contexto, d: dict[str, str]) -> tuple[str, int, int]:
    compra = armazem.achar(ctx.conexao, "compra", ctx.bd_id, {"numero": d["ordem_numero"]})
    if compra is None:
        raise Rejeita("ORDEM_INEXISTENTE", f"Ordem {d['ordem_numero']} não cadastrada.")
    if compra["status"] == "cancelada":
        raise Rejeita("ORDEM_CANCELADA", f"Ordem {d['ordem_numero']} está cancelada.")
    mes = _mes(d["ano"], d["mes"])
    valor = _dinheiro(d["valor_liquido"])
    _exigir_aberto(ctx, mes)
    acao = armazem.upsert(
        ctx.conexao,
        ctx.diario,
        "compra_mes",
        ctx.bd_id,
        {"compra_id": compra["id"], "mes": mes},
        {"valor_liquido_centavos": valor},
    )
    return acao, 0, valor


def _compras(ctx, linhas):
    return _por_linha(ctx, linhas, _compra)


# ---------- orçamento PDD ----------


def _revisao_rascunho(ctx: Contexto) -> int:
    existente = ctx.conexao.execute(
        "SELECT id FROM pdd_revisao WHERE bd_id = ? AND estado = 'rascunho' ORDER BY id DESC",
        (ctx.bd_id,),
    ).fetchone()
    if existente:
        return existente[0]
    total = ctx.conexao.execute(
        "SELECT COUNT(*) FROM pdd_revisao WHERE bd_id = ?", (ctx.bd_id,)
    ).fetchone()[0]
    rotulo = "Original" if total == 0 else f"T{total}"
    return armazem.inserir(
        ctx.conexao,
        ctx.diario,
        "pdd_revisao",
        ctx.bd_id,
        {"rotulo": rotulo, "estado": "rascunho", "criada_em": "carga"},
    )


def _pdd(ctx: Contexto, d: dict[str, str]) -> tuple[str, int, int]:
    iniciativa = _achar(ctx, "iniciativa", "codigo", d["iniciativa_numero"])
    if iniciativa is None:
        raise Rejeita(
            "INICIATIVA_INEXISTENTE", f"Iniciativa {d['iniciativa_numero']} não cadastrada."
        )
    if d["tipo"] not in ("CAPEX", "OPEX"):
        raise Rejeita("TIPO_INVALIDO", f"Tipo {d['tipo']!r}: use CAPEX ou OPEX.")
    valor = _dinheiro(d["valor_bruto"])
    acao = armazem.upsert(
        ctx.conexao,
        ctx.diario,
        "pdd_linha",
        ctx.bd_id,
        {"revisao_id": _revisao_rascunho(ctx), "iniciativa_id": iniciativa, "tipo": d["tipo"]},
        {"valor_bruto_centavos": valor},
    )
    return acao, 0, valor


def _orcamento_pdd(ctx, linhas):
    return _por_linha(ctx, linhas, _pdd)


# ---------- pessoas ----------


def _pessoa(ctx: Contexto, d: dict[str, str]) -> tuple[str, int, int]:
    org = _achar(ctx, "org", "codigo", d["org_codigo"])
    if org is None:
        raise Rejeita("ORG_INEXISTENTE", f"Organização {d['org_codigo']} não cadastrada.")
    cargo = _achar(ctx, "cargo", "codigo", d["cargo_codigo"])
    if cargo is None:
        raise Rejeita("CARGO_INEXISTENTE", f"Cargo {d['cargo_codigo']} não cadastrado.")
    admissao = _mes_texto(d["vig_ini"], "vig_ini")
    desligamento = _mes_texto(d["desligamento"], "desligamento") if d["desligamento"] else None
    if desligamento and desligamento < admissao:
        raise Rejeita("MES_INVALIDO", "Desligamento anterior à admissão.")
    existente = armazem.achar(ctx.conexao, "pessoa", ctx.bd_id, {"matricula": d["matricula"]})
    valores: dict[str, object] = {
        "nome": d["nome"], "org_id": org, "cargo_id": cargo,
        "admissao": admissao, "desligamento": desligamento,
    }  # fmt: skip
    if d["tema_codigo"]:
        tema = _achar(ctx, "tema", "codigo", d["tema_codigo"])
        if tema is None:
            raise Rejeita("TEMA_INEXISTENTE", f"Tema {d['tema_codigo']} não cadastrado.")
        valores["tema_id"] = tema
    elif existente is None:
        raise Rejeita(
            "TEMA_INEXISTENTE", "Pessoa nova precisa da coluna tema_codigo com um tema cadastrado."
        )
    acao = armazem.upsert(
        ctx.conexao, ctx.diario, "pessoa", ctx.bd_id, {"matricula": d["matricula"]}, valores
    )
    return acao, 0, 0


def _pessoas(ctx, linhas):
    return _por_linha(ctx, linhas, _pessoa)


# ---------- tarifas ----------


def _tarifa(ctx: Contexto, d: dict[str, str]) -> tuple[str, int, int]:
    if _achar(ctx, "empresa", "codigo", d["empresa_codigo"]) is None:
        raise Rejeita("EMPRESA_INEXISTENTE", f"Empresa {d['empresa_codigo']} não cadastrada.")
    cargo_id = _achar(ctx, "cargo", "codigo", d["cargo_codigo"])
    cargo = armazem.achar(ctx.conexao, "cargo", ctx.bd_id, {"id": cargo_id}) if cargo_id else None
    empresa = armazem.achar(ctx.conexao, "empresa", ctx.bd_id, {"codigo": d["empresa_codigo"]})
    if cargo is None or cargo["empresa_id"] != empresa["id"]:
        raise Rejeita(
            "CARGO_INEXISTENTE",
            f"Cargo {d['cargo_codigo']} não cadastrado para {d['empresa_codigo']}.",
        )
    if cargo["nivel"] != d["nivel"]:
        raise Rejeita(
            "NIVEL_DIVERGENTE",
            f"Nível {d['nivel']} difere do cadastro do cargo ({cargo['nivel']}).",
        )
    inicio = _mes_texto(d["vig_ini"], "vig_ini")
    valor = _dinheiro(d["valor_hora_liquido"])
    existentes = ctx.conexao.execute(
        "SELECT id, liquida_centavos, vigencia_ini, vigencia_fim FROM tarifa"
        " WHERE bd_id = ? AND cargo_id = ? ORDER BY vigencia_ini",
        (ctx.bd_id, cargo["id"]),
    ).fetchall()
    for _id, liquida, ini, _fim in existentes:
        if ini == inicio and liquida == valor:
            return "igual", 0, 0
    if existentes and inicio <= existentes[-1][2]:
        raise Rejeita(
            "VIGENCIA_RETROATIVA",
            f"Vigência {inicio} não é posterior à última do cargo ({existentes[-1][2]}).",
        )
    if existentes and existentes[-1][3] is None and existentes[-1][1] == valor:
        return "igual", 0, 0  # o valor vigente já é este
    if existentes and existentes[-1][3] is None:
        aberta = armazem.achar(ctx.conexao, "tarifa", ctx.bd_id, {"id": existentes[-1][0]})
        armazem.alterar(
            ctx.conexao,
            ctx.diario,
            "tarifa",
            ctx.bd_id,
            aberta,
            {"vigencia_fim": vigencia.mes_anterior(inicio)},
        )
    armazem.inserir(
        ctx.conexao,
        ctx.diario,
        "tarifa",
        ctx.bd_id,
        {"cargo_id": cargo["id"], "liquida_centavos": valor, "vigencia_ini": inicio},
    )
    return "inserida", 0, 0


def _tarifas(ctx, linhas):
    return _por_linha(ctx, linhas, _tarifa)


# ---------- portfólio ----------

_FORCA = {"inserida": 2, "atualizada": 1, "igual": 0}


def _portfolio(ctx: Contexto, d: dict[str, str]) -> tuple[str, int, int]:
    if d["tipo"] not in ("CAPEX", "OPEX"):
        raise Rejeita("TIPO_INVALIDO", f"Tipo {d['tipo']!r}: use CAPEX ou OPEX.")
    demanda = armazem.achar(ctx.conexao, "demanda", ctx.bd_id, {"codigo": d["demanda_codigo"]})
    if demanda is not None:
        dona = armazem.achar(ctx.conexao, "iniciativa", ctx.bd_id, {"id": demanda["iniciativa_id"]})
        if dona["codigo"] != d["iniciativa_codigo"]:
            raise Rejeita(
                "DEMANDA_EM_OUTRA_INICIATIVA",
                f"Demanda {d['demanda_codigo']} já pertence à iniciativa {dona['codigo']}.",
            )
    acoes = []
    acoes.append(
        armazem.upsert(
            ctx.conexao, ctx.diario, "agrupamento", ctx.bd_id, {"nome": d["agrupamento"]}, {}
        )
    )
    acoes.append(
        armazem.upsert(
            ctx.conexao,
            ctx.diario,
            "iniciativa",
            ctx.bd_id,
            {"codigo": d["iniciativa_codigo"]},
            {"nome": d["iniciativa"]},
        )
    )
    iniciativa = _achar(ctx, "iniciativa", "codigo", d["iniciativa_codigo"])
    acoes.append(
        armazem.upsert(
            ctx.conexao,
            ctx.diario,
            "demanda",
            ctx.bd_id,
            {"codigo": d["demanda_codigo"]},
            {"nome": d["demanda"], "tipo": d["tipo"], "iniciativa_id": iniciativa},
        )
    )
    demanda_id = _achar(ctx, "demanda", "codigo", d["demanda_codigo"])
    agrupamento = _achar(ctx, "agrupamento", "nome", d["agrupamento"])
    acoes.append(
        armazem.upsert(
            ctx.conexao,
            ctx.diario,
            "tema",
            ctx.bd_id,
            {"codigo": d["tema_codigo"]},
            {"nome": d["tema"], "demanda_id": demanda_id, "agrupamento_id": agrupamento},
        )
    )
    return max(acoes, key=lambda a: _FORCA[a]), 0, 0


def _portfolio_cadeia(ctx, linhas):
    return _por_linha(ctx, linhas, _portfolio)


LAYOUTS: dict[str, Layout] = {
    "horas": Layout(
        "horas", "Horas realizadas", ("matricula", "tema_codigo", "ano", "mes", "horas"), (), _horas
    ),
    "compras": Layout(
        "compras",
        "Compras realizadas",
        ("ordem_numero", "ano", "mes", "valor_liquido"),
        (),
        _compras,
    ),
    "pdd": Layout(
        "pdd", "Orçamento PDD", ("iniciativa_numero", "tipo", "valor_bruto"), (), _orcamento_pdd
    ),
    "pessoas": Layout(
        "pessoas", "Pessoas",
        ("matricula", "nome", "org_codigo", "cargo_codigo", "vig_ini"),
        ("tema_codigo", "desligamento"),
        _pessoas,
    ),
    "tarifas": Layout(
        "tarifas", "Tarifas",
        ("empresa_codigo", "cargo_codigo", "nivel", "valor_hora_liquido", "vig_ini"), (), _tarifas,
    ),
    "portfolio": Layout(
        "portfolio", "Portfólio",
        ("iniciativa_codigo", "iniciativa", "demanda_codigo", "demanda", "tipo",
         "tema_codigo", "tema", "agrupamento"),
        (), _portfolio_cadeia,
    ),
}  # fmt: skip

__all__ = ["LAYOUTS", "Layout", "Resultado", "Contexto", "Rejeita", "field"]
