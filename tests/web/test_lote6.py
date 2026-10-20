"""Lote 6 da #44: Cadastros com filtros, calendário editável e indicadores por item."""

from financeiro import cenarios, orcamento
from financeiro.store import cadastros, organizacao, pessoas, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Admin"):
    _, ids = semear(ambiente, bds=(("O1", papel),))
    bd = ids["O1"]
    c = ambiente.conexao
    tema, tema2 = _cadastros(ambiente, bd)
    cargo = c.execute("SELECT id FROM cargo").fetchone()[0]
    cadastros.definir_tarifa(c, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(c, bd, 1000, "2026-01")
    entrar(ambiente)
    return bd, csrf_de(ambiente.cliente.get("/configuracoes").text)


def _lista(ambiente, aba, query=""):
    return ambiente.cliente.get(f"/cadastros/{aba}/lista{query}").text


# ---- filtros ----


def test_demandas_filtram_por_tipo_pelos_chips(ambiente):
    bd, _ = _preparar(ambiente)
    c = ambiente.conexao
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    portfolio.criar_demanda(c, bd, "D-OPEX", ini, "Sustentação", "OPEX", None)

    todas = _lista(ambiente, "demandas")
    so_opex = _lista(ambiente, "demandas", "?filtro=OPEX")

    assert 'data-chip="OPEX"' in todas  # chips renderizados
    assert ">D-OPEX</td>" in todas and ">D-1</td>" in todas
    assert ">D-OPEX</td>" in so_opex and ">D-1</td>" not in so_opex


def test_vagas_filtram_por_estado(ambiente):
    bd, _ = _preparar(ambiente)
    c = ambiente.conexao
    squad = organizacao.listar_orgs(c, bd)[1].id
    tema = portfolio.listar_temas(c, bd)[0].id
    cargo = cadastros.listar_cargos(c, bd)[0].id
    v1 = pessoas.abrir_vaga(c, bd, "V-ABERTA", squad, tema, cargo, "2026-08")
    v2 = pessoas.abrir_vaga(c, bd, "V-CANC", squad, tema, cargo, "2026-08")
    pessoas.cancelar_vaga(c, bd, v2)

    abertas = _lista(ambiente, "vagas", "?filtro=aberta")

    assert ">V-ABERTA</td>" in abertas and ">V-CANC</td>" not in abertas
    assert v1


def test_temas_filtram_por_agrupamento_e_cargos_por_empresa(ambiente):
    bd, _ = _preparar(ambiente)
    c = ambiente.conexao
    gravity = portfolio.criar_agrupamento(c, bd, "Gravity")
    dem = portfolio.listar_demandas(c, bd)[0].id
    portfolio.criar_tema(c, bd, "T-GRAV", dem, "Jornada", gravity)
    ntt = cadastros.criar_empresa(c, bd, "NTT", "consultoria")
    cadastros.criar_cargo(c, bd, ntt, "Developer", "N8")

    temas = _lista(ambiente, "temas", f"?filtro={gravity}")
    cargos = _lista(ambiente, "cargos", f"?filtro={ntt}")

    assert ">T-GRAV</td>" in temas and ">T-10</td>" not in temas
    assert ">Developer</td>" in cargos and ">Sênior</td>" not in cargos


def test_organizacao_filtra_por_nivel(ambiente):
    bd, _ = _preparar(ambiente)
    organizacao.criar_org(ambiente.conexao, bd, "Tribo", "Tribo-Z", None, "G", "2025-01")

    squads = _lista(ambiente, "organizacao", "?filtro=Squad")

    assert ">Tribo-Z</td>" not in squads
    assert ">Tribo-Z</td>" in _lista(ambiente, "organizacao")


# ---- indicadores por item ----


def test_iniciativas_mostram_budget_realizado_forecast_saldo_e_percentual(ambiente):
    bd, _ = _preparar(ambiente)
    c = ambiente.conexao
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    rev = orcamento.nova_revisao(c, bd, ambiente.relogio())
    orcamento.definir_linha(c, bd, rev.id, ini, "CAPEX", 1_000_000)
    orcamento.aprovar(c, bd, rev.id, ambiente.relogio())

    lista = _lista(ambiente, "iniciativas")

    for coluna in ("Budget", "Realizado", "Forecast", "Saldo", "% consumido"):
        assert f">{coluna}</th>" in lista, coluna
    assert 'title="R$ 10.000,00"' in lista  # budget da iniciativa


def test_demandas_empresas_agrupamentos_e_fornecedores_mostram_contagens(ambiente):
    bd, _ = _preparar(ambiente)
    portfolio.criar_fornecedor(ambiente.conexao, bd, "Fornecedor A")

    assert ">Temas</th>" in _lista(ambiente, "demandas")
    assert ">Cargos</th>" in _lista(ambiente, "empresas")
    assert ">Pessoas ativas</th>" in _lista(ambiente, "empresas")
    assert ">Temas</th>" in _lista(ambiente, "agrupamentos")
    assert ">OC/OS ativas</th>" in _lista(ambiente, "fornecedores")


def test_unidades_mostram_pessoas_e_custo(ambiente):
    _preparar(ambiente)

    lista = _lista(ambiente, "organizacao")

    assert ">Pessoas</th>" in lista and ">Custo</th>" in lista


def test_vagas_mostram_o_inicio_por_cenario(ambiente):
    bd, _ = _preparar(ambiente)
    c = ambiente.conexao
    squad = organizacao.listar_orgs(c, bd)[1].id
    tema = portfolio.listar_temas(c, bd)[0].id
    cargo = cadastros.listar_cargos(c, bd)[0].id
    vaga = pessoas.abrir_vaga(c, bd, "V-1", squad, tema, cargo, "2026-08")
    cenarios.garantir_padrao(c, bd)
    base = cenarios.listar(c, bd)[0]
    cenarios.definir_inicio_vaga(c, bd, base.id, vaga, "2026-10")

    lista = _lista(ambiente, "vagas")

    assert ">Início por cenário</th>" in lista
    assert "Base out/2026" in lista


# ---- calendário ----


def test_calendario_tem_chips_de_ano_e_campo_por_mes_editavel(ambiente):
    _preparar(ambiente)

    cal = _lista(ambiente, "calendario", "?ano=2027")

    assert 'data-ano="2026"' in cal and 'data-ano="2027"' in cal
    assert cal.count('name="horas"') >= 12  # um campo por mês


def test_calendario_mostra_mes_bloqueado_com_o_motivo(ambiente):
    bd, _ = _preparar(ambiente)
    c = ambiente.conexao
    pessoa = pessoas.listar_pessoas(c, bd)[0].id
    tema = portfolio.listar_temas(c, bd)[0].id
    c.execute(
        "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, '2026-12', 10)",
        (bd, pessoa, tema),
    )
    c.commit()

    cal = _lista(ambiente, "calendario", "?ano=2026")

    assert "já tem carga" in cal
    assert "mês passado" in cal


def test_calendario_sem_dados_oferece_criar(ambiente):
    _preparar(ambiente)

    cal = _lista(ambiente, "calendario", "?ano=2031")

    assert "Criar calendário 2031" in cal


# ---- histórico ----


def test_historico_de_vigencias_fica_recolhido(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    tribo = organizacao.listar_orgs(c, bd)[0].id
    organizacao_mod = __import__("financeiro.organizacao", fromlist=["x"])
    organizacao_mod.trocar_gestor(c, bd, tribo, "Marina", "2026-05")

    lista = _lista(ambiente, "organizacao")

    assert "<details" in lista and "Histórico de vigências" in lista
