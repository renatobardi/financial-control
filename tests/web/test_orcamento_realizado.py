from financeiro import fechamento, orcamento
from financeiro.store import cadastros, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Editor"):
    """BD com ana (F0101, T-10), 100 h em jan (fechado) e 50 h em fev, R$ 193,00/h e 10%."""
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
    c.commit()
    entrar(ambiente)
    usuario = c.execute("SELECT id FROM usuario").fetchone()[0]
    fechamento.fechar(c, bd, "2026-01", usuario, ambiente.relogio())
    return bd, csrf_de(ambiente.cliente.get("/configuracoes").text)


def _iniciativa(ambiente, bd):
    return portfolio.listar_iniciativas(ambiente.conexao, bd)[0].id


def test_telas_sem_sessao_devolvem_401(ambiente):
    for caminho in ("/orcamento", "/orcamento/tabela", "/realizado", "/realizado/tabela"):
        assert ambiente.cliente.get(caminho).status_code == 401
    assert ambiente.cliente.post("/orcamento/revisoes", data={}).status_code == 401


def test_pdd_fluxo_nova_revisao_linha_aprovar_com_markup_congelado(ambiente):
    bd, csrf = _preparar(ambiente)
    ini = _iniciativa(ambiente, bd)

    nova = ambiente.cliente.post("/orcamento/revisoes", data={"csrf": csrf})
    rev = orcamento.rascunho(ambiente.conexao, bd).id
    linha = ambiente.cliente.post(
        f"/orcamento/{rev}/linhas",
        data={"csrf": csrf, "iniciativa_id": str(ini), "tipo": "CAPEX", "valor": "4.000.000,00"},
    )
    aprovada = ambiente.cliente.post(f"/orcamento/{rev}/aprovar", data={"csrf": csrf})

    assert nova.status_code == 200 and "Original" in nova.text
    assert linha.status_code == 200 and "R$ 4.000.000,00" in linha.text
    assert aprovada.status_code == 200
    assert "markup congelado em 10,00%" in aprovada.text
    editar = ambiente.cliente.post(
        f"/orcamento/{rev}/linhas",
        data={"csrf": csrf, "iniciativa_id": str(ini), "tipo": "OPEX", "valor": "1,00"},
    )
    assert editar.status_code == 409 and "só leitura" in editar.text


def test_valor_invalido_e_tipo_invalido_devolvem_400(ambiente):
    bd, csrf = _preparar(ambiente)
    ini = _iniciativa(ambiente, bd)
    ambiente.cliente.post("/orcamento/revisoes", data={"csrf": csrf})
    rev = orcamento.rascunho(ambiente.conexao, bd).id

    valor = ambiente.cliente.post(
        f"/orcamento/{rev}/linhas",
        data={"csrf": csrf, "iniciativa_id": str(ini), "tipo": "CAPEX", "valor": "muito"},
    )
    tipo = ambiente.cliente.post(
        f"/orcamento/{rev}/linhas",
        data={"csrf": csrf, "iniciativa_id": str(ini), "tipo": "INFRA", "valor": "1,00"},
    )

    assert valor.status_code == 400 and tipo.status_code == 400


def test_leitor_ve_o_pdd_e_o_realizado_mas_nao_edita(ambiente):
    bd, csrf = _preparar(ambiente, "Leitor")

    pdd = ambiente.cliente.get("/orcamento/tabela")
    real = ambiente.cliente.get("/realizado/tabela")
    criar = ambiente.cliente.post("/orcamento/revisoes", data={"csrf": csrf})

    assert pdd.status_code == 200 and real.status_code == 200
    assert 'action="/orcamento/revisoes"' not in pdd.text
    assert criar.status_code == 403


def test_realizado_mostra_so_mes_fechado_como_realizado_e_o_aberto_como_forecast(ambiente):
    _preparar(ambiente)

    resposta = ambiente.cliente.get("/realizado/tabela?ano=2026&dimensao=iniciativa")

    assert resposta.status_code == 200
    assert "R$ 21.230,00" in resposta.text  # jan fechado: 100 h × R$ 193,00 × 1,10
    assert "R$ 10.615,00" in resposta.text  # fev aberto: 50 h, forecast
    assert "meses fechados" in resposta.text


def test_filtro_de_origem_mostra_a_nota_de_reconciliacao(ambiente):
    bd, _ = _preparar(ambiente)
    demanda = ambiente.conexao.execute("SELECT id FROM demanda").fetchone()[0]
    ambiente.conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status) VALUES (?, 'OC9', 'OC', ?, 'emitida')",
        (bd, demanda),
    )
    compra_id = ambiente.conexao.execute("SELECT id FROM compra").fetchone()[0]
    ambiente.conexao.execute(
        "INSERT INTO compra_mes (bd_id, compra_id, mes, valor_liquido_centavos)"
        " VALUES (?, ?, '2026-03', 100000)",
        (bd, compra_id),
    )
    ambiente.conexao.commit()

    sem = ambiente.cliente.get("/realizado/tabela?ano=2026&dimensao=iniciativa&origem=todas")
    com = ambiente.cliente.get("/realizado/tabela?ano=2026&dimensao=iniciativa&origem=pessoas")

    assert "Ficam de fora" not in sem.text
    assert "Ficam de fora R$ 1.100,00" in com.text


def test_o_mesmo_gap_com_o_mesmo_sinal_no_pdd_e_no_realizado(ambiente):
    bd, csrf = _preparar(ambiente)
    ini = _iniciativa(ambiente, bd)
    ambiente.cliente.post("/orcamento/revisoes", data={"csrf": csrf})
    rev = orcamento.rascunho(ambiente.conexao, bd).id
    ambiente.cliente.post(
        f"/orcamento/{rev}/linhas",
        data={"csrf": csrf, "iniciativa_id": str(ini), "tipo": "CAPEX", "valor": "500,00"},
    )  # orçamento R$ 500: o total do ano (R$ 31.845,00) estoura
    ambiente.cliente.post(f"/orcamento/{rev}/aprovar", data={"csrf": csrf})

    pdd = ambiente.cliente.get("/orcamento/tabela")
    real = ambiente.cliente.get("/realizado/tabela?ano=2026&dimensao=iniciativa")

    gap = "−R$ 31.345,00"  # 500,00 − 31.845,00
    assert gap in pdd.text and gap in real.text
    assert orcamento.gap(50_000, 3_184_500) == -3_134_500


def test_pdd_de_um_bd_nao_aparece_em_outro(ambiente):
    bd, csrf = _preparar(ambiente)
    ambiente.cliente.post("/orcamento/revisoes", data={"csrf": csrf})
    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    entrar(ambiente, "bia@empresa.com")

    tabela = ambiente.cliente.get("/orcamento/tabela")

    assert "/orcamento?rev=" not in tabela.text
    assert "Ainda não há revisão" in tabela.text
