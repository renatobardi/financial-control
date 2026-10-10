from financeiro import compras, fechamento
from financeiro.store import cadastros, organizacao, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Editor"):
    """BD com ana (F0101, T-10) e R$ 193,00/h, markup 10%; 100 h em jan (fechado) e 50 em fev."""
    _, ids = semear(ambiente, bds=(("O1", papel),))
    bd = ids["O1"]
    c = ambiente.conexao
    tema, _ = _cadastros(ambiente, bd)
    cargo = c.execute("SELECT id FROM cargo").fetchone()[0]
    pessoa = c.execute("SELECT id FROM pessoa").fetchone()[0]
    cadastros.definir_tarifa(c, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(c, bd, 1000, "2026-01")
    for mes, horas in (("2026-01", 100), ("2026-02", 50)):
        c.execute(
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (?, ?, ?, ?, ?)",
            (bd, pessoa, tema, mes, horas),
        )
    portfolio.criar_fornecedor(c, bd, "Fornecedor A")
    c.commit()
    entrar(ambiente)
    usuario = c.execute("SELECT id FROM usuario").fetchone()[0]
    fechamento.fechar(c, bd, "2026-01", usuario, ambiente.relogio())
    return bd, usuario, csrf_de(ambiente.cliente.get("/configuracoes").text)


def _demanda(ambiente, bd):
    return portfolio.listar_demandas(ambiente.conexao, bd)[0].id


def test_telas_sem_sessao_devolvem_401(ambiente):
    for caminho in ("/pessoas", "/pessoas/lista", "/compras", "/compras/lista", "/compras/1"):
        assert ambiente.cliente.get(caminho).status_code == 401, caminho
    assert ambiente.cliente.post("/pessoas", data={}).status_code == 401
    assert ambiente.cliente.post("/compras", data={}).status_code == 401


# ---- Pessoas ----


def test_lista_de_pessoas_mostra_matricula_e_nome_e_o_total_nao_soma_os_meses(ambiente):
    _preparar(ambiente, "Leitor")

    pagina = ambiente.cliente.get("/pessoas")
    lista = ambiente.cliente.get("/pessoas/lista?de=2026-01&ate=2026-12")

    assert 'hx-get="/pessoas/lista' in pagina.text
    assert "F0101" in lista.text and "Ana Lima" in lista.text
    assert "pessoas distintas" in lista.text  # nota: total do ano não é a soma dos meses
    assert "150" in lista.text  # 100 h + 50 h
    assert "R$ 31.845,00" in lista.text  # custo: 150 h × R$ 193,00 × 1,10 (jan congelado)


def test_filtros_de_busca_e_unidade(ambiente):
    _preparar(ambiente)

    achou = ambiente.cliente.get("/pessoas/lista?de=2026-01&ate=2026-12&busca=ana")
    nao = ambiente.cliente.get("/pessoas/lista?de=2026-01&ate=2026-12&busca=zzz")

    assert "Ana Lima" in achou.text
    assert "Ana Lima" not in nao.text and "Ninguém ativo" in nao.text


def test_nova_pessoa_e_edicao_de_desligamento(ambiente):
    bd, _, csrf = _preparar(ambiente)
    squad = organizacao.listar_orgs(ambiente.conexao, bd)[1].id
    cargo = cadastros.listar_cargos(ambiente.conexao, bd)[0].id
    tema = portfolio.listar_temas(ambiente.conexao, bd)[0].id

    nova = ambiente.cliente.post(
        "/pessoas",
        data={
            "csrf": csrf, "matricula": "F0202", "nome": "Bruno Reis", "org_id": str(squad),
            "cargo_id": str(cargo), "tema_id": str(tema), "admissao": "2026-03",
        },
    )  # fmt: skip
    repetida = ambiente.cliente.post(
        "/pessoas",
        data={
            "csrf": csrf, "matricula": "F0202", "nome": "Outro", "org_id": str(squad),
            "cargo_id": str(cargo), "tema_id": str(tema), "admissao": "2026-03",
        },
    )  # fmt: skip

    assert nova.status_code == 200 and "Bruno Reis" in nova.text
    assert repetida.status_code == 400 and "Matrícula já cadastrada" in repetida.text
    bruno = [
        p
        for p in __import__("financeiro").store.pessoas.listar_pessoas(ambiente.conexao, bd)
        if p.matricula == "F0202"
    ][0]
    editada = ambiente.cliente.post(
        f"/pessoas/{bruno.id}", data={"csrf": csrf, "desligamento": "2026-06"}
    )
    assert editada.status_code == 200 and "2026-06" in editada.text


def test_leitor_ve_pessoas_mas_nao_cria_nem_edita(ambiente):
    _, _, csrf = _preparar(ambiente, "Leitor")

    lista = ambiente.cliente.get("/pessoas/lista?de=2026-01&ate=2026-12")
    criar = ambiente.cliente.post("/pessoas", data={"csrf": csrf, "matricula": "X"})

    assert 'hx-post="/pessoas"' not in lista.text
    assert criar.status_code == 403


# ---- Compras ----


def test_criar_ordem_prevista_emitir_e_ver_o_historico(ambiente):
    bd, _, csrf = _preparar(ambiente)
    demanda = _demanda(ambiente, bd)

    nova = ambiente.cliente.post(
        "/compras",
        data={"csrf": csrf, "tipo": "OS", "demanda_id": str(demanda), "descricao": "Extensão"},
    )
    ordem = compras.listar(ambiente.conexao, bd, 2026, ambiente.relogio())[0]
    sem_dados = ambiente.cliente.post(
        f"/compras/{ordem.id}", data={"csrf": csrf, "status": "emitida"}
    )
    fornecedor = portfolio.listar_fornecedores(ambiente.conexao, bd)[0].id
    emitida = ambiente.cliente.post(
        f"/compras/{ordem.id}",
        data={
            "csrf": csrf,
            "status": "emitida",
            "numero": "OS0042",
            "fornecedor_id": str(fornecedor),
        },
    )
    detalhe = ambiente.cliente.get(f"/compras/{ordem.id}/detalhe")

    assert nova.status_code == 200 and "Extensão" in nova.text
    assert sem_dados.status_code == 400 and "informe o número" in sem_dados.text
    assert emitida.status_code == 200
    assert "OS0042" in detalhe.text and "Fornecedor A" in detalhe.text
    assert (
        "criada como prevista por Ana" in detalhe.text
        and "status: prevista → emitida" in detalhe.text
    )


def test_valor_por_mes_forecast_editavel_e_realizado_so_leitura(ambiente):
    bd, usuario, csrf = _preparar(ambiente)
    demanda = _demanda(ambiente, bd)
    ordem = compras.criar_prevista(
        ambiente.conexao, bd, "OC", demanda, "Licenças", usuario, ambiente.relogio()
    )

    aberto = ambiente.cliente.post(
        f"/compras/{ordem}/valores", data={"csrf": csrf, "mes": "2026-02", "valor": "2.000,00"}
    )
    fechado = ambiente.cliente.post(
        f"/compras/{ordem}/valores", data={"csrf": csrf, "mes": "2026-01", "valor": "100,00"}
    )
    invalido = ambiente.cliente.post(
        f"/compras/{ordem}/valores", data={"csrf": csrf, "mes": "2026-03", "valor": "muito"}
    )

    assert aberto.status_code == 200 and "R$ 2.200,00" in aberto.text  # bruto: × 1,10
    assert fechado.status_code == 409 and "está fechado" in fechado.text
    assert invalido.status_code == 400


def test_lista_de_compras_com_busca_status_e_cancelada_zerada(ambiente):
    bd, usuario, csrf = _preparar(ambiente)
    demanda = _demanda(ambiente, bd)
    a = compras.criar_prevista(
        ambiente.conexao, bd, "OC", demanda, "Licenças", usuario, ambiente.relogio()
    )
    b = compras.criar_prevista(
        ambiente.conexao, bd, "OS", demanda, "Squad dev", usuario, ambiente.relogio()
    )
    compras.definir_valor(ambiente.conexao, bd, b, "2026-02", 100_000, usuario, ambiente.relogio())
    compras.editar(ambiente.conexao, bd, b, usuario, ambiente.relogio(), status="cancelada")

    todas = ambiente.cliente.get("/compras/lista?ano=2026")
    busca = ambiente.cliente.get("/compras/lista?ano=2026&busca=licen")
    canceladas = ambiente.cliente.get("/compras/lista?ano=2026&status=cancelada")

    assert "Licenças" in todas.text and "Squad dev" in todas.text
    assert "Licenças" in busca.text and "Squad dev" not in busca.text
    assert "Squad dev" in canceladas.text and "Licenças" not in canceladas.text
    assert a


def test_leitor_ve_compras_mas_nao_cria_nem_edita(ambiente):
    bd, usuario, csrf = _preparar(ambiente, "Leitor")
    ordem = compras.criar_prevista(
        ambiente.conexao, bd, "OC", _demanda(ambiente, bd), "X", usuario, ambiente.relogio()
    )

    detalhe = ambiente.cliente.get(f"/compras/{ordem}/detalhe")
    criar = ambiente.cliente.post("/compras", data={"csrf": csrf, "tipo": "OC"})
    editar = ambiente.cliente.post(f"/compras/{ordem}", data={"csrf": csrf, "status": "cancelada"})

    assert detalhe.status_code == 200 and f'action="/compras/{ordem}"' not in detalhe.text
    assert criar.status_code == 403 and editar.status_code == 403


def test_ordem_de_outro_bd_devolve_404(ambiente):
    bd, usuario, csrf = _preparar(ambiente)
    ordem = compras.criar_prevista(
        ambiente.conexao, bd, "OC", _demanda(ambiente, bd), "X", usuario, ambiente.relogio()
    )
    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    entrar(ambiente, "bia@empresa.com")
    csrf_bia = csrf_de(ambiente.cliente.get("/configuracoes").text)

    assert ambiente.cliente.get(f"/compras/{ordem}/detalhe").status_code == 404
    editar = ambiente.cliente.post(
        f"/compras/{ordem}", data={"csrf": csrf_bia, "status": "cancelada"}
    )
    assert editar.status_code == 404
