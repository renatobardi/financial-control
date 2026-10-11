"""Abas de Cadastros: o que cada uma lista, que formulários tem e o que cada ação grava.

Cada aba é dados (colunas, linhas, formulários) para um único template genérico; cada ação é
uma função `(conexao, bd_id, dados, mes_atual) -> chave do aviso` que levanta `ErroCadastro`.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field

from financeiro import calendario, custo, i18n, organizacao, vigencia
from financeiro.store import (
    Conexao,
    ErroDeIntegridade,
    cadastros,
    edicao,
    pessoas,
    portfolio,
)
from financeiro.store import calendario as armazem_calendario
from financeiro.store import organizacao as arvore_org

ABAS = (
    "organizacao",
    "iniciativas",
    "demandas",
    "temas",
    "agrupamentos",
    "empresas",
    "cargos",
    "fornecedores",
    "vagas",
    "markup",
    "calendario",
)
POR_PAGINA = 10
NIVEIS = ("E6", "N7", "N8", "N9", "N10", "N11", "N12")
TIPOS_EMPRESA = ("propria", "consultoria")
TIPOS_DEMANDA = ("CAPEX", "OPEX")


class ErroCadastro(Exception):
    def __init__(self, chave: str, status: int = 400):
        super().__init__(chave)
        self.chave = chave
        self.status = status


@dataclass
class Campo:
    nome: str
    rotulo: str  # chave do catálogo
    tipo: str = "texto"  # texto | mes | valor | numero | selecao
    opcoes: list[tuple[str, str]] = field(default_factory=list)  # (valor, texto exibido)
    opcional: bool = False


@dataclass
class Formulario:
    acao: str
    titulo: str  # chave do catálogo
    campos: list[Campo]
    enviar: str = "cadastros.salvar"


@dataclass
class AcaoLinha:
    acao: str
    rotulo: str  # chave do catálogo
    com_texto: str | None = None  # nome do campo de texto (ex.: renomear), valor inicial na linha
    confirmar: str | None = None  # chave do catálogo da pergunta de confirmação


@dataclass
class Aba:
    colunas: list[str]
    # (id, células, texto editável da linha[, ações permitidas na linha; ausente = todas])
    linhas: list[tuple]
    formularios: list[Formulario]
    acoes_linha: list[AcaoLinha] = field(default_factory=list)
    paginada: bool = True
    nota: str | None = None


# ---------- leitura dos campos do formulário ----------


def _texto(dados: dict[str, str], nome: str, opcional: bool = False) -> str:
    valor = dados.get(nome, "").strip()
    if not valor and not opcional:
        raise ErroCadastro("cadastros.erro_campo_obrigatorio")
    return valor


def _inteiro(dados: dict[str, str], nome: str, opcional: bool = False) -> int | None:
    valor = _texto(dados, nome, opcional)
    if not valor:
        return None
    if not valor.isdigit():
        raise ErroCadastro("cadastros.erro_campo_obrigatorio")
    return int(valor)


def _mes(dados: dict[str, str], nome: str) -> str:
    try:
        return vigencia.validar_mes(_texto(dados, nome))
    except ValueError as erro:
        raise ErroCadastro("cadastros.erro_mes") from erro


def _guardar(chamada: Callable[[], object]) -> None:
    """Converte as violações do banco em erro de cadastro com mensagem."""
    try:
        chamada()
    except ErroDeIntegridade as erro:
        raise ErroCadastro("cadastros.erro_duplicado_ou_invalido") from erro


# ---------- ações ----------


def _renomear(tabela: str):
    def agir(conexao: Conexao, bd_id: int, dados: dict[str, str], mes_atual: str) -> str:
        registro = _inteiro(dados, "id")
        _guardar(lambda: edicao.renomear(conexao, tabela, bd_id, registro, _texto(dados, "nome")))
        return "cadastros.ok_salvo"

    return agir


def _tribo(conexao, bd_id, dados, mes_atual):
    try:
        organizacao.criar_tribo(
            conexao,
            bd_id,
            _texto(dados, "nome"),
            _texto(dados, "gestor", True),
            _mes(dados, "inicio"),
        )
    except organizacao.OrganizacaoInvalida as erro:
        raise ErroCadastro("cadastros.erro_duplicado_ou_invalido") from erro
    return "cadastros.ok_salvo"


def _squad(conexao, bd_id, dados, mes_atual):
    try:
        organizacao.criar_squad(
            conexao,
            bd_id,
            _texto(dados, "nome"),
            _inteiro(dados, "tribo_id"),
            _texto(dados, "gestor", True),
            _mes(dados, "inicio"),
        )
    except organizacao.OrganizacaoInvalida as erro:
        raise ErroCadastro("cadastros.erro_duplicado_ou_invalido") from erro
    return "cadastros.ok_salvo"


def _gestor(conexao, bd_id, dados, mes_atual):
    try:
        organizacao.trocar_gestor(
            conexao, bd_id, _inteiro(dados, "org_id"), _texto(dados, "gestor"), _mes(dados, "mes")
        )
    except organizacao.OrganizacaoInvalida as erro:
        raise ErroCadastro("cadastros.erro_duplicado_ou_invalido") from erro
    return "cadastros.ok_salvo"


def _reorganizar(conexao, bd_id, dados, mes_atual):
    try:
        organizacao.reorganizar(
            conexao,
            bd_id,
            _inteiro(dados, "squad_id"),
            _inteiro(dados, "tribo_id"),
            _mes(dados, "mes"),
        )
    except organizacao.OrganizacaoInvalida as erro:
        raise ErroCadastro("cadastros.erro_reorganizacao") from erro
    return "cadastros.ok_salvo"


def _iniciativa(conexao, bd_id, dados, mes_atual):
    _guardar(
        lambda: portfolio.criar_iniciativa(
            conexao, bd_id, _texto(dados, "codigo"), _texto(dados, "nome")
        )
    )
    return "cadastros.ok_salvo"


def _demanda(conexao, bd_id, dados, mes_atual):
    tipo = _texto(dados, "tipo")
    if tipo not in TIPOS_DEMANDA:
        raise ErroCadastro("cadastros.erro_campo_obrigatorio")
    _guardar(
        lambda: portfolio.criar_demanda(
            conexao,
            bd_id,
            _texto(dados, "codigo"),
            _inteiro(dados, "iniciativa_id"),
            _texto(dados, "nome"),
            tipo,
            _inteiro(dados, "squad_id", True),
        )
    )
    return "cadastros.ok_salvo"


def _tema(conexao, bd_id, dados, mes_atual):
    _guardar(
        lambda: portfolio.criar_tema(
            conexao,
            bd_id,
            _texto(dados, "codigo"),
            _inteiro(dados, "demanda_id"),
            _texto(dados, "nome"),
            _inteiro(dados, "agrupamento_id"),
        )
    )
    return "cadastros.ok_salvo"


def _agrupamento(conexao, bd_id, dados, mes_atual):
    _guardar(lambda: portfolio.criar_agrupamento(conexao, bd_id, _texto(dados, "nome")))
    return "cadastros.ok_salvo"


def _empresa(conexao, bd_id, dados, mes_atual):
    tipo = _texto(dados, "tipo")
    if tipo not in TIPOS_EMPRESA:
        raise ErroCadastro("cadastros.erro_campo_obrigatorio")
    _guardar(lambda: cadastros.criar_empresa(conexao, bd_id, _texto(dados, "nome"), tipo))
    return "cadastros.ok_salvo"


def _cargo(conexao, bd_id, dados, mes_atual):
    nivel = _texto(dados, "nivel")
    if nivel not in NIVEIS:
        raise ErroCadastro("cadastros.erro_campo_obrigatorio")
    valor = dados.get("valor", "").strip()
    if valor:  # tarifa inicial: lê antes de criar, para não deixar cargo sem tarifa por erro
        try:
            centavos = i18n.ler_moeda(valor)
        except ValueError as erro:
            raise ErroCadastro("cadastros.erro_valor") from erro
        inicio = _mes(dados, "a_partir_de")
    cargo_id = []
    _guardar(
        lambda: cargo_id.append(
            cadastros.criar_cargo(
                conexao, bd_id, _inteiro(dados, "empresa_id"), _texto(dados, "nome"), nivel
            )
        )
    )
    if valor:
        _guardar(lambda: cadastros.definir_tarifa(conexao, bd_id, cargo_id[0], centavos, inicio))
    return "cadastros.ok_salvo"


def _definir(tabela: str, coluna: str, campo: str, validos: tuple[str, ...] | None = None):
    def agir(conexao, bd_id, dados, mes_atual):
        registro = _inteiro(dados, "id")
        if validos is not None:
            valor = _texto(dados, campo)
            if valor not in validos:
                raise ErroCadastro("cadastros.erro_campo_obrigatorio")
        else:
            valor = _inteiro(dados, campo)
        _guardar(lambda: edicao.definir(conexao, tabela, coluna, bd_id, registro, valor))
        return "cadastros.ok_salvo"

    return agir


def _editar_demanda(conexao, bd_id, dados, mes_atual):
    registro = _inteiro(dados, "id")
    tipo = dados.get("tipo", "").strip()
    iniciativa = dados.get("iniciativa_id", "").strip()
    if tipo:
        if tipo not in TIPOS_DEMANDA:
            raise ErroCadastro("cadastros.erro_campo_obrigatorio")
        _guardar(lambda: edicao.definir(conexao, "demanda", "tipo", bd_id, registro, tipo))
    if iniciativa:
        if not iniciativa.isdigit():
            raise ErroCadastro("cadastros.erro_campo_obrigatorio")
        _guardar(
            lambda: edicao.definir(
                conexao, "demanda", "iniciativa_id", bd_id, registro, int(iniciativa)
            )
        )
    return "cadastros.ok_salvo"


def _editar_markup(conexao, bd_id, dados, mes_atual):
    try:
        pct = i18n.ler_percentual(_texto(dados, "percentual"))
    except ValueError as erro:
        raise ErroCadastro("cadastros.erro_valor") from erro
    if not cadastros.alterar_markup_vigente(conexao, bd_id, pct):
        raise ErroCadastro("cadastros.erro_sem_markup", 409)
    return "cadastros.ok_salvo"


def _tarifa(conexao, bd_id, dados, mes_atual):
    try:
        valor = i18n.ler_moeda(_texto(dados, "valor"))
    except ValueError as erro:
        raise ErroCadastro("cadastros.erro_valor") from erro
    cargo = _inteiro(dados, "cargo_id")
    try:
        _guardar(
            lambda: cadastros.definir_tarifa(
                conexao, bd_id, cargo, valor, _mes(dados, "a_partir_de")
            )
        )
    except vigencia.VigenciaSobreposta as erro:
        raise ErroCadastro("cadastros.erro_vigencia", 409) from erro
    return "cadastros.ok_tarifa"


def _fornecedor(conexao, bd_id, dados, mes_atual):
    _guardar(lambda: portfolio.criar_fornecedor(conexao, bd_id, _texto(dados, "nome")))
    return "cadastros.ok_salvo"


def _vaga(conexao, bd_id, dados, mes_atual):
    _guardar(
        lambda: pessoas.abrir_vaga(
            conexao,
            bd_id,
            _texto(dados, "codigo"),
            _inteiro(dados, "org_id"),
            _inteiro(dados, "tema_id"),
            _inteiro(dados, "cargo_id"),
            _mes(dados, "aberta_em"),
        )
    )
    return "cadastros.ok_salvo"


def _preencher_vaga(conexao, bd_id, dados, mes_atual):
    try:
        pessoas.preencher_vaga(
            conexao, bd_id, _inteiro(dados, "vaga_id"), _inteiro(dados, "pessoa_id")
        )
    except pessoas.VagaNaoAberta as erro:
        raise ErroCadastro("cadastros.erro_vaga", 409) from erro
    return "cadastros.ok_salvo"


def _cancelar_vaga(conexao, bd_id, dados, mes_atual):
    try:
        pessoas.cancelar_vaga(conexao, bd_id, _inteiro(dados, "id"))
    except pessoas.VagaNaoAberta as erro:
        raise ErroCadastro("cadastros.erro_vaga", 409) from erro
    return "cadastros.ok_salvo"


def _markup(conexao, bd_id, dados, mes_atual):
    try:
        pct = i18n.ler_percentual(_texto(dados, "percentual"))
    except ValueError as erro:
        raise ErroCadastro("cadastros.erro_valor") from erro
    try:
        cadastros.definir_markup(conexao, bd_id, pct, _mes(dados, "a_partir_de"))
    except vigencia.VigenciaSobreposta as erro:
        raise ErroCadastro("cadastros.erro_vigencia", 409) from erro
    return "cadastros.ok_markup"


def _ano(dados: dict[str, str]) -> int:
    ano = _inteiro(dados, "ano")
    if not 2000 <= ano <= 2100:
        raise ErroCadastro("cadastros.erro_campo_obrigatorio")
    return ano


def _gerar_calendario(conexao, bd_id, dados, mes_atual):
    calendario.gerar(conexao, bd_id, _ano(dados))
    return "cadastros.ok_calendario"


def _ajustar_calendario(conexao, bd_id, dados, mes_atual):
    try:
        calendario.ajustar(
            conexao, bd_id, _ano(dados), _inteiro(dados, "mes"), _inteiro(dados, "horas"), mes_atual
        )
    except calendario.AjusteBloqueado as erro:
        raise ErroCadastro(f"cadastros.erro_calendario_{erro.motivo}", 409) from erro
    except ValueError as erro:
        raise ErroCadastro("cadastros.erro_campo_obrigatorio") from erro
    return "cadastros.ok_calendario"


def _feriado(conexao, bd_id, dados, mes_atual):
    try:
        data = dt.date.fromisoformat(_texto(dados, "data"))
    except ValueError as erro:
        raise ErroCadastro("cadastros.erro_data") from erro
    calendario.adicionar_feriado(conexao, bd_id, data, _texto(dados, "nome"))
    return "cadastros.ok_calendario"


ACOES: dict[tuple[str, str], Callable[..., str]] = {
    ("organizacao", "tribo"): _tribo,
    ("organizacao", "squad"): _squad,
    ("organizacao", "gestor"): _gestor,
    ("organizacao", "reorganizar"): _reorganizar,
    ("iniciativas", "nova"): _iniciativa,
    ("iniciativas", "renomear"): _renomear("iniciativa"),
    ("demandas", "nova"): _demanda,
    ("demandas", "renomear"): _renomear("demanda"),
    ("demandas", "editar"): _editar_demanda,
    ("temas", "nova"): _tema,
    ("temas", "renomear"): _renomear("tema"),
    ("temas", "editar"): _definir("tema", "agrupamento_id", "agrupamento_id"),
    ("agrupamentos", "nova"): _agrupamento,
    ("agrupamentos", "renomear"): _renomear("agrupamento"),
    ("empresas", "nova"): _empresa,
    ("empresas", "renomear"): _renomear("empresa"),
    ("empresas", "editar"): _definir("empresa", "tipo", "tipo", TIPOS_EMPRESA),
    ("cargos", "nova"): _cargo,
    ("cargos", "renomear"): _renomear("cargo"),
    ("cargos", "editar"): _definir("cargo", "nivel", "nivel", NIVEIS),
    ("cargos", "tarifa"): _tarifa,
    ("fornecedores", "nova"): _fornecedor,
    ("fornecedores", "renomear"): _renomear("fornecedor"),
    ("vagas", "nova"): _vaga,
    ("vagas", "preencher"): _preencher_vaga,
    ("vagas", "cancelar"): _cancelar_vaga,
    ("markup", "novo"): _markup,
    ("markup", "editar"): _editar_markup,
    ("calendario", "gerar"): _gerar_calendario,
    ("calendario", "ajustar"): _ajustar_calendario,
    ("calendario", "feriado"): _feriado,
}


# ---------- leitura das abas ----------


def _opcoes(itens, valor, texto) -> list[tuple[str, str]]:
    return [(str(valor(i)), texto(i)) for i in itens]


def _pesquisa(linhas, termo: str):
    termo = termo.strip().lower()
    if not termo:
        return linhas
    return [linha for linha in linhas if termo in " ".join(linha[1]).lower()]


def _montar_base(conexao: Conexao, bd_id: int, aba: str, ano: int, mes_atual: str) -> Aba:
    """Constrói o conteúdo da aba. Texto fixo vem do catálogo na hora de renderizar."""
    s = i18n.t
    if aba == "organizacao":
        orgs = arvore_org.listar_orgs(conexao, bd_id)
        nomes = {o.id: o.nome for o in orgs}
        tribos = [o for o in orgs if o.tipo == "Tribo"]
        squads = [o for o in orgs if o.tipo == "Squad"]
        linhas = []
        for o in sorted(orgs, key=lambda x: (x.tipo != "Tribo", x.id)):
            historico = " · ".join(
                f"{em}: {txt}" for em, txt in arvore_org.historico(conexao, bd_id, o.id)
            )
            linhas.append(
                (
                    o.id,
                    [
                        o.tipo,
                        o.nome,
                        nomes.get(o.pai_id, "—"),
                        o.gestor or "—",
                        o.inicio,
                        historico or "—",
                    ],
                    o.nome,
                )
            )
        tribo_ops = _opcoes(tribos, lambda x: x.id, lambda x: x.nome)
        return Aba(
            ["tipo", "nome", "tribo", "gestor", "vigencia", "historico"],
            linhas,
            [
                Formulario(
                    "tribo",
                    "cadastros.f_nova_tribo",
                    [
                        Campo("nome", "cadastros.c_nome"),
                        Campo("gestor", "cadastros.c_gestor", opcional=True),
                        Campo("inicio", "cadastros.c_inicio", "mes"),
                    ],
                ),
                Formulario(
                    "squad",
                    "cadastros.f_novo_squad",
                    [
                        Campo("nome", "cadastros.c_nome"),
                        Campo("tribo_id", "cadastros.c_tribo", "selecao", tribo_ops),
                        Campo("gestor", "cadastros.c_gestor", opcional=True),
                        Campo("inicio", "cadastros.c_inicio", "mes"),
                    ],
                ),
                Formulario(
                    "gestor",
                    "cadastros.f_trocar_gestor",
                    [
                        Campo(
                            "org_id",
                            "cadastros.c_unidade",
                            "selecao",
                            _opcoes(orgs, lambda x: x.id, lambda x: x.nome),
                        ),
                        Campo("gestor", "cadastros.c_gestor"),
                        Campo("mes", "cadastros.c_mes", "mes"),
                    ],
                ),
                Formulario(
                    "reorganizar",
                    "cadastros.f_reorganizar",
                    [
                        Campo(
                            "squad_id",
                            "cadastros.c_squad",
                            "selecao",
                            _opcoes(squads, lambda x: x.id, lambda x: x.nome),
                        ),
                        Campo("tribo_id", "cadastros.c_nova_tribo", "selecao", tribo_ops),
                        Campo("mes", "cadastros.c_mes", "mes"),
                    ],
                ),
            ],
        )
    if aba == "iniciativas":
        itens = portfolio.listar_iniciativas(conexao, bd_id)
        return Aba(
            ["codigo", "nome"],
            [(i.id, [i.codigo, i.nome], i.nome) for i in itens],
            [
                Formulario(
                    "nova",
                    "cadastros.f_nova_iniciativa",
                    [Campo("codigo", "cadastros.c_codigo"), Campo("nome", "cadastros.c_nome")],
                )
            ],
            [AcaoLinha("renomear", "cadastros.renomear", "nome")],
        )
    if aba == "demandas":
        itens = portfolio.listar_demandas(conexao, bd_id)
        squads = {o.id: o.nome for o in arvore_org.listar_orgs(conexao, bd_id)}
        ini = portfolio.listar_iniciativas(conexao, bd_id)
        return Aba(
            ["codigo", "nome", "iniciativa", "tipo", "squad"],
            [
                (
                    d.id,
                    [d.codigo, d.nome, d.iniciativa, d.tipo, squads.get(d.squad_id, "—")],
                    d.nome,
                )
                for d in itens
            ],
            [
                Formulario(
                    "nova",
                    "cadastros.f_nova_demanda",
                    [
                        Campo("codigo", "cadastros.c_codigo"),
                        Campo("nome", "cadastros.c_nome"),
                        Campo(
                            "iniciativa_id",
                            "cadastros.c_iniciativa",
                            "selecao",
                            _opcoes(ini, lambda x: x.id, lambda x: x.nome),
                        ),
                        Campo(
                            "tipo", "cadastros.c_tipo", "selecao", [(t, t) for t in TIPOS_DEMANDA]
                        ),
                        Campo(
                            "squad_id",
                            "cadastros.c_squad",
                            "selecao",
                            _opcoes(
                                [
                                    o
                                    for o in arvore_org.listar_orgs(conexao, bd_id)
                                    if o.tipo == "Squad"
                                ],
                                lambda x: x.id,
                                lambda x: x.nome,
                            ),
                            opcional=True,
                        ),
                    ],
                )
            ],
            [AcaoLinha("renomear", "cadastros.renomear", "nome")],
        )
    if aba == "temas":
        itens = portfolio.listar_temas(conexao, bd_id)
        dem = portfolio.listar_demandas(conexao, bd_id)
        agr = portfolio.listar_agrupamentos(conexao, bd_id)
        return Aba(
            ["codigo", "nome", "demanda", "iniciativa", "agrupamento"],
            [
                (t.id, [t.codigo, t.nome, t.demanda, t.iniciativa, t.agrupamento], t.nome)
                for t in itens
            ],
            [
                Formulario(
                    "nova",
                    "cadastros.f_novo_tema",
                    [
                        Campo("codigo", "cadastros.c_codigo"),
                        Campo("nome", "cadastros.c_nome"),
                        Campo(
                            "demanda_id",
                            "cadastros.c_demanda",
                            "selecao",
                            _opcoes(dem, lambda x: x.id, lambda x: f"{x.codigo} · {x.nome}"),
                        ),
                        Campo(
                            "agrupamento_id",
                            "cadastros.c_agrupamento",
                            "selecao",
                            _opcoes(agr, lambda x: x.id, lambda x: x.nome),
                        ),
                    ],
                )
            ],
            [AcaoLinha("renomear", "cadastros.renomear", "nome")],
        )
    if aba in ("agrupamentos", "fornecedores"):
        itens = (
            portfolio.listar_agrupamentos(conexao, bd_id)
            if aba == "agrupamentos"
            else portfolio.listar_fornecedores(conexao, bd_id)
        )
        titulo = (
            "cadastros.f_novo_agrupamento"
            if aba == "agrupamentos"
            else "cadastros.f_novo_fornecedor"
        )
        return Aba(
            ["nome"],
            [(i.id, [i.nome], i.nome) for i in itens],
            [Formulario("nova", titulo, [Campo("nome", "cadastros.c_nome")])],
            [AcaoLinha("renomear", "cadastros.renomear", "nome")],
        )
    if aba == "empresas":
        itens = cadastros.listar_empresas(conexao, bd_id)
        return Aba(
            ["nome", "tipo"],
            [(e.id, [e.nome, s(f"cadastros.tipo_{e.tipo}")], e.nome) for e in itens],
            [
                Formulario(
                    "nova",
                    "cadastros.f_nova_empresa",
                    [
                        Campo("nome", "cadastros.c_nome"),
                        Campo(
                            "tipo",
                            "cadastros.c_tipo",
                            "selecao",
                            [(t, s(f"cadastros.tipo_{t}")) for t in TIPOS_EMPRESA],
                        ),
                    ],
                )
            ],
            [AcaoLinha("renomear", "cadastros.renomear", "nome")],
        )
    if aba == "cargos":
        cargos = cadastros.listar_cargos(conexao, bd_id)
        empresas = cadastros.listar_empresas(conexao, bd_id)
        linhas = []
        for c in cargos:
            try:
                h = custo.custo_hora(conexao, bd_id, c.id, mes_atual)
                liquida, bruta = i18n.moeda(h.liquida_centavos), i18n.moeda(h.bruta_centavos)
            except custo.SemTarifa:
                liquida = bruta = "—"
            vigentes = cadastros.tarifas_do_cargo(conexao, bd_id, c.id)
            desde = vigentes[-1].inicio if vigentes else "—"
            linhas.append((c.id, [c.empresa, c.nome, c.nivel, liquida, bruta, desde], c.nome))
        return Aba(
            ["empresa", "cargo", "nivel", "tarifa_liquida", "tarifa_bruta", "vigencia"],
            linhas,
            [
                Formulario(
                    "nova",
                    "cadastros.f_novo_cargo",
                    [
                        Campo(
                            "empresa_id",
                            "cadastros.c_empresa",
                            "selecao",
                            _opcoes(empresas, lambda x: x.id, lambda x: x.nome),
                        ),
                        Campo("nome", "cadastros.c_nome"),
                        Campo("nivel", "cadastros.c_nivel", "selecao", [(n, n) for n in NIVEIS]),
                    ],
                ),
                Formulario(
                    "tarifa",
                    "cadastros.f_nova_tarifa",
                    [
                        Campo(
                            "cargo_id",
                            "cadastros.c_cargo",
                            "selecao",
                            _opcoes(cargos, lambda x: x.id, lambda x: f"{x.empresa} · {x.nome}"),
                        ),
                        Campo("valor", "cadastros.c_tarifa_liquida", "valor"),
                        Campo("a_partir_de", "cadastros.c_a_partir_de", "mes"),
                    ],
                ),
            ],
            [AcaoLinha("renomear", "cadastros.renomear", "nome")],
        )
    if aba == "vagas":
        itens = pessoas.listar_vagas(conexao, bd_id)
        orgs = {o.id: o.nome for o in arvore_org.listar_orgs(conexao, bd_id)}
        temas = {t.id: t.codigo for t in portfolio.listar_temas(conexao, bd_id)}
        cargos = {c.id: f"{c.nome} · {c.empresa}" for c in cadastros.listar_cargos(conexao, bd_id)}
        todas = pessoas.listar_pessoas(conexao, bd_id)
        nomes_pessoa = {p.id: p.nome for p in todas}
        abertas = [v for v in itens if v.estado == "aberta"]
        return Aba(
            ["codigo", "unidade", "tema", "cargo", "aberta_em", "estado", "pessoa"],
            [
                (
                    v.id,
                    [
                        v.codigo,
                        orgs.get(v.org_id, "—"),
                        temas.get(v.tema_id, "—"),
                        cargos.get(v.cargo_id, "—"),
                        v.aberta_em,
                        s(f"cadastros.estado_{v.estado}"),
                        nomes_pessoa.get(v.pessoa_id, "—"),
                    ],
                    v.codigo,
                    {"cancelar"} if v.estado == "aberta" else set(),
                )
                for v in itens
            ],
            [
                Formulario(
                    "nova",
                    "cadastros.f_nova_vaga",
                    [
                        Campo("codigo", "cadastros.c_codigo"),
                        Campo(
                            "org_id",
                            "cadastros.c_unidade",
                            "selecao",
                            _opcoes(
                                arvore_org.listar_orgs(conexao, bd_id),
                                lambda x: x.id,
                                lambda x: x.nome,
                            ),
                        ),
                        Campo(
                            "tema_id",
                            "cadastros.c_tema",
                            "selecao",
                            [(str(k), v) for k, v in temas.items()],
                        ),
                        Campo(
                            "cargo_id",
                            "cadastros.c_cargo",
                            "selecao",
                            [(str(k), v) for k, v in cargos.items()],
                        ),
                        Campo("aberta_em", "cadastros.c_aberta_em", "mes"),
                    ],
                ),
                Formulario(
                    "preencher",
                    "cadastros.f_preencher_vaga",
                    [
                        Campo(
                            "vaga_id",
                            "cadastros.c_vaga",
                            "selecao",
                            _opcoes(abertas, lambda x: x.id, lambda x: x.codigo),
                        ),
                        Campo(
                            "pessoa_id",
                            "cadastros.c_pessoa",
                            "selecao",
                            _opcoes(todas, lambda x: x.id, lambda x: f"{x.matricula} · {x.nome}"),
                        ),
                    ],
                ),
            ],
            [AcaoLinha("cancelar", "cadastros.cancelar_vaga", confirmar="confirmar.cancelar_vaga")],
        )
    if aba == "markup":
        itens = cadastros.listar_markups(conexao, bd_id)
        return Aba(
            ["percentual", "de", "ate"],
            [
                (
                    m.id,
                    [i18n.percentual(m.centesimos_pct), m.inicio, m.fim or s("cadastros.vigente")],
                    "",
                )
                for m in itens
            ],
            [
                Formulario(
                    "novo",
                    "cadastros.f_novo_markup",
                    [
                        Campo("percentual", "cadastros.c_percentual", "valor"),
                        Campo("a_partir_de", "cadastros.c_a_partir_de", "mes"),
                    ],
                )
            ],
            paginada=False,
        )
    if aba == "calendario":
        ajustados = [(m, calendario.horas_do_mes(conexao, bd_id, ano, m)) for m in range(1, 13)]
        linhas = [
            (None, [i18n.mes(ano, m), "—" if h is None else i18n.numero(h)], "")
            for m, h in ajustados
        ]
        extras = [f"{d} · {n}" for d, n in armazem_calendario.feriados_do_ano(conexao, bd_id, ano)]
        linhas += [(None, [s("cadastros.feriado_bd"), e], "") for e in extras]
        return Aba(
            ["mes", "horas"],
            linhas,
            [
                Formulario(
                    "gerar",
                    "cadastros.f_gerar_calendario",
                    [Campo("ano", "cadastros.c_ano", "numero")],
                ),
                Formulario(
                    "ajustar",
                    "cadastros.f_ajustar_calendario",
                    [
                        Campo("ano", "cadastros.c_ano", "numero"),
                        Campo("mes", "cadastros.c_mes_numero", "numero"),
                        Campo("horas", "cadastros.c_horas", "numero"),
                    ],
                ),
                Formulario(
                    "feriado",
                    "cadastros.f_feriado",
                    [Campo("data", "cadastros.c_data", "texto"), Campo("nome", "cadastros.c_nome")],
                ),
            ],
            paginada=False,
        )
    raise KeyError(aba)


def montar(conexao: Conexao, bd_id: int, aba: str, ano: int, mes_atual: str) -> Aba:
    """A aba com os formulários de edição de campo (tipo, nível, iniciativa, markup…)."""
    conteudo = _montar_base(conexao, bd_id, aba, ano, mes_atual)
    s = i18n.t
    if aba == "empresas":
        ops = _opcoes(cadastros.listar_empresas(conexao, bd_id), lambda x: x.id, lambda x: x.nome)
        conteudo.formularios.append(
            Formulario(
                "editar", "cadastros.f_editar_empresa",
                [Campo("id", "cadastros.c_empresa", "selecao", ops),
                 Campo("tipo", "cadastros.c_tipo", "selecao",
                       [(t, s(f"cadastros.tipo_{t}")) for t in TIPOS_EMPRESA])],
            )
        )  # fmt: skip
    elif aba == "cargos":
        ops = _opcoes(
            cadastros.listar_cargos(conexao, bd_id),
            lambda x: x.id,
            lambda x: f"{x.empresa} · {x.nome}",
        )
        nova = next(f for f in conteudo.formularios if f.acao == "nova")
        nova.campos += [
            Campo("valor", "cadastros.c_tarifa_inicial", "valor", opcional=True),
            Campo("a_partir_de", "cadastros.c_a_partir_de", "mes", opcional=True),
        ]
        conteudo.formularios.append(
            Formulario(
                "editar", "cadastros.f_editar_cargo",
                [Campo("id", "cadastros.c_cargo", "selecao", ops),
                 Campo("nivel", "cadastros.c_nivel", "selecao", [(n, n) for n in NIVEIS])],
            )
        )  # fmt: skip
    elif aba == "demandas":
        ops = _opcoes(
            portfolio.listar_demandas(conexao, bd_id),
            lambda x: x.id,
            lambda x: f"{x.codigo} · {x.nome}",
        )
        ini = _opcoes(
            portfolio.listar_iniciativas(conexao, bd_id), lambda x: x.id, lambda x: x.nome
        )
        conteudo.formularios.append(
            Formulario(
                "editar", "cadastros.f_editar_demanda",
                [Campo("id", "cadastros.c_demanda", "selecao", ops),
                 Campo("tipo", "cadastros.c_tipo", "selecao",
                       [(t, t) for t in TIPOS_DEMANDA], opcional=True),
                 Campo("iniciativa_id", "cadastros.c_iniciativa", "selecao", ini, opcional=True)],
            )
        )  # fmt: skip
    elif aba == "temas":
        ops = _opcoes(
            portfolio.listar_temas(conexao, bd_id),
            lambda x: x.id,
            lambda x: f"{x.codigo} · {x.nome}",
        )
        agr = _opcoes(
            portfolio.listar_agrupamentos(conexao, bd_id), lambda x: x.id, lambda x: x.nome
        )
        conteudo.formularios.append(
            Formulario(
                "editar", "cadastros.f_editar_tema",
                [Campo("id", "cadastros.c_tema", "selecao", ops),
                 Campo("agrupamento_id", "cadastros.c_agrupamento", "selecao", agr)],
            )
        )  # fmt: skip
    elif aba == "markup":
        conteudo.nota = s("cadastros.markup_nota")
        conteudo.formularios.append(
            Formulario(
                "editar", "cadastros.f_editar_markup",
                [Campo("percentual", "cadastros.c_percentual", "valor")],
            )
        )  # fmt: skip
    return conteudo


def paginar(linhas, pagina: int, termo: str):
    filtradas = _pesquisa(linhas, termo)
    total_paginas = max(1, -(-len(filtradas) // POR_PAGINA))
    pagina = min(max(pagina, 1), total_paginas)
    inicio = (pagina - 1) * POR_PAGINA
    return filtradas[inicio : inicio + POR_PAGINA], pagina, total_paginas
