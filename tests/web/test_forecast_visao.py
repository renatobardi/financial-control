import re

from financeiro import cenarios, fechamento, orcamento
from financeiro.store import cadastros, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Editor"):
    """Ana (R$ 193,00/h, 10%) com 100 h em jan (fechado) e 50 h em fev; PDD de R$ 500 mil."""
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
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, %s, %s)",
            (bd, pessoa, tema, mes, horas),
        )
    c.commit()
    entrar(ambiente)
    usuario = c.execute("SELECT id FROM usuario").fetchone()[0]
    agora = ambiente.relogio()
    fechamento.fechar(c, bd, "2026-01", usuario, agora)
    rev = orcamento.nova_revisao(c, bd, agora)
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    orcamento.definir_linha(c, bd, rev.id, ini, "CAPEX", 50_000_000)
    orcamento.aprovar(c, bd, rev.id, agora)
    return bd, csrf_de(ambiente.cliente.get("/configuracoes").text)


def test_telas_sem_sessao_devolvem_401(ambiente):
    for caminho in (
        "/forecast",
        "/forecast/painel",
        "/visao-geral/kpis",
        "/visao-geral/curva",
        "/visao-geral/alertas",
        "/visao-geral/risco",
    ):
        assert ambiente.cliente.get(caminho).status_code == 401, caminho
    assert ambiente.cliente.post("/forecast/cenarios", data={}).status_code == 401


def test_visao_geral_e_a_raiz_com_blocos_lazy_e_cenarios_padrao(ambiente):
    _preparar(ambiente)

    pagina = ambiente.cliente.get("/")

    assert pagina.status_code == 200
    assert "Visão geral" in pagina.text
    for nome in ("Base", "Otimista", "Pessimista"):
        assert f">{nome}</option>" in pagina.text
    for bloco in ("kpis", "curva", "alertas", "risco"):
        assert f'hx-get="/visao-geral/{bloco}?' in pagina.text


def test_blocos_da_visao_geral_mostram_kpis_curva_e_risco(ambiente):
    _preparar(ambiente)

    kpis = ambiente.cliente.get("/visao-geral/kpis")
    curva = ambiente.cliente.get("/visao-geral/curva")
    risco = ambiente.cliente.get("/visao-geral/risco")

    assert "R$ 500.000,00" in kpis.text  # budget
    assert "R$ 21.230,00" in kpis.text  # realizado de jan
    assert "<svg" in curva.text and "polyline" in curva.text
    assert "<svg" in risco.text and "Alfa" in risco.text


def test_o_mesmo_cenario_da_o_mesmo_numero_na_forecast_e_na_visao_geral(ambiente):
    bd, _ = _preparar(ambiente)
    cenarios.garantir_padrao(ambiente.conexao, bd)
    pessimista = next(c for c in cenarios.listar(ambiente.conexao, bd) if c.nome == "Pessimista")

    visao = ambiente.cliente.get(f"/visao-geral/kpis?cenario={pessimista.id}")
    painel = ambiente.cliente.get(f"/forecast/painel?cenario={pessimista.id}")

    valores_visao = re.findall(r"R\$ [\d.]+,\d{2}", visao.text)
    assert len(valores_visao) >= 3
    for valor in valores_visao:
        assert valor in painel.text, valor


def test_cenarios_diferentes_mudam_o_forecast_na_tela(ambiente):
    bd, _ = _preparar(ambiente)
    cenarios.garantir_padrao(ambiente.conexao, bd)
    por_nome = {c.nome: c.id for c in cenarios.listar(ambiente.conexao, bd)}

    base = ambiente.cliente.get(f"/visao-geral/kpis?cenario={por_nome['Base']}")
    pess = ambiente.cliente.get(f"/visao-geral/kpis?cenario={por_nome['Pessimista']}")

    assert base.text != pess.text


def test_forecast_editor_cria_salva_inclui_e_retira(ambiente):
    bd, csrf = _preparar(ambiente)
    novo = ambiente.cliente.post("/forecast/cenarios", data={"csrf": csrf, "nome": "Meu cenário"})
    cenario = next(c for c in cenarios.listar(ambiente.conexao, bd) if c.nome == "Meu cenário")

    salvo = ambiente.cliente.post(
        f"/forecast/cenarios/{cenario.id}",
        data={
            "csrf": csrf, "nome": "Meu cenário 2", "fator_pessoas": "97,5", "fator_compras": "110",
            "tri": ["1", "2"], "escala_tipo": "PDD", "elemento_tipo": "Agrupamento",
            "escala_valor": "10.000.000,00",
        },
    )  # fmt: skip
    atual = cenarios.achar(ambiente.conexao, bd, cenario.id)

    assert novo.status_code == 200 and "Cenário criado." in novo.text
    assert salvo.status_code == 200 and "Cenário salvo." in salvo.text
    assert (atual.nome, atual.fator_pessoas, atual.fator_compras, atual.trimestres) == (
        "Meu cenário 2", 9750, 11000, 3,
    )  # fmt: skip
    assert atual.escala_valor_centavos == 1_000_000_000
    chave = re.search(r'name="chave" value="([^"]+)"', salvo.text).group(1)
    incluido = ambiente.cliente.post(
        f"/forecast/cenarios/{cenario.id}/incluir", data={"csrf": csrf, "chave": chave}
    )
    assert incluido.status_code == 200 and "Elemento incluído." in incluido.text
    retirado = ambiente.cliente.post(
        f"/forecast/cenarios/{cenario.id}/retirar", data={"csrf": csrf, "chave": chave}
    )
    assert cenarios.achar(ambiente.conexao, bd, cenario.id).incluidos == []
    assert retirado.status_code == 200


def test_incluir_o_que_nao_cabe_na_escala_devolve_409(ambiente):
    bd, csrf = _preparar(ambiente)
    cenarios.garantir_padrao(ambiente.conexao, bd)
    cid = cenarios.criar(
        ambiente.conexao, bd, "Apertado", 10000, 10000, escala_valor=1_000
    )  # R$ 10,00 de escala
    painel = ambiente.cliente.get(f"/forecast/painel?cenario={cid}")
    chave = re.search(r'name="chave" value="([^"]+)"', painel.text).group(1)

    resposta = ambiente.cliente.post(
        f"/forecast/cenarios/{cid}/incluir", data={"csrf": csrf, "chave": chave}
    )

    assert resposta.status_code == 409 and "Não cabe" in resposta.text and "Faltam" in resposta.text


def test_percentual_invalido_devolve_400(ambiente):
    bd, csrf = _preparar(ambiente)
    cenarios.garantir_padrao(ambiente.conexao, bd)
    base = cenarios.listar(ambiente.conexao, bd)[0]

    resposta = ambiente.cliente.post(
        f"/forecast/cenarios/{base.id}",
        data={"csrf": csrf, "nome": "x", "fator_pessoas": "muito", "fator_compras": "100"},
    )

    assert resposta.status_code == 400


def test_leitor_ve_a_forecast_mas_nao_edita(ambiente):
    bd, csrf = _preparar(ambiente, "Leitor")

    painel = ambiente.cliente.get("/forecast/painel")
    criar = ambiente.cliente.post("/forecast/cenarios", data={"csrf": csrf})

    assert painel.status_code == 200 and "Seu papel neste BD é Leitor" in painel.text
    assert 'hx-post="/forecast/cenarios"' not in painel.text
    assert criar.status_code == 403


def test_cenario_de_outro_bd_devolve_404(ambiente):
    bd, csrf = _preparar(ambiente)
    cenarios.garantir_padrao(ambiente.conexao, bd)
    alheio = cenarios.listar(ambiente.conexao, bd)[0].id
    ambiente.cliente.cookies.clear()
    semear(ambiente, email="bia@empresa.com", nome="Bia", bds=(("B2", "Admin"),))
    entrar(ambiente, "bia@empresa.com")
    csrf_bia = csrf_de(ambiente.cliente.get("/configuracoes").text)

    resposta = ambiente.cliente.post(
        f"/forecast/cenarios/{alheio}/duplicar", data={"csrf": csrf_bia}
    )

    assert resposta.status_code == 404


def test_tela_inicial_escolhida_vale_depois_do_login(ambiente):
    _, csrf = _preparar(ambiente)
    ambiente.cliente.post(
        "/configuracoes/preferencias",
        data={
            "csrf": csrf, "tema": "sistema", "formato_valor": "mil",
            "tela_inicial": "Forecast", "bd_padrao_id": "",
        },
    )  # fmt: skip
    ambiente.cliente.cookies.clear()

    resposta = entrar(ambiente)

    assert resposta.status_code == 303 and resposta.headers["location"] == "/forecast"


def test_graficos_sao_svg_inline_sem_biblioteca_de_javascript(ambiente):
    _preparar(ambiente)

    pagina = ambiente.cliente.get("/").text
    painel = ambiente.cliente.get("/forecast/painel").text

    assert "<svg" in painel
    for texto in (pagina, painel):
        assert "chart.js" not in texto.lower() and "d3.js" not in texto.lower()
        assert "<script src=" not in texto.replace('<script src="/static/htmx.min.js"', "")
