"""Lote 3 da #44: Fechamento com botão principal e valor no log, Cargas e login."""

from financeiro import fechamento
from financeiro.store import cadastros
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Admin"):
    _, ids = semear(ambiente, bds=(("O1", papel),))
    bd = ids["O1"]
    c = ambiente.conexao
    _cadastros(ambiente, bd)
    cargo = c.execute("SELECT id FROM cargo").fetchone()[0]
    cadastros.definir_tarifa(c, bd, cargo, 19300, "2026-01")
    cadastros.definir_markup(c, bd, 1000, "2026-01")
    entrar(ambiente)
    return bd, csrf_de(ambiente.cliente.get("/configuracoes").text)


def _enviar(ambiente, csrf, texto, acao=""):
    return ambiente.cliente.post(
        f"/cargas{acao}",
        data={"csrf": csrf, "layout": "horas"},
        files={"arquivo": ("horas.csv", texto.encode(), "text/csv")},
    )


# ---- Fechamento ----


def test_fechamento_tem_botao_principal_resumo_e_valor_no_log(ambiente):
    bd, csrf = _preparar(ambiente)

    grade = ambiente.cliente.get("/fechamento/grade?ano=2026").text
    assert "0 de 12 meses fechados" in grade
    assert "Fechar jan/2026" in grade  # botão principal, além do cartão do mês
    assert 'data-principal="fechar"' in grade

    resposta = ambiente.cliente.post(
        "/fechamento/2026-01/fechar", data={"csrf": csrf, "ano": "2026"}
    )

    assert "1 de 12 meses fechados" in resposta.text
    assert "congelado" in resposta.text
    assert 'data-principal="fechar"' in resposta.text  # agora o botão é de fev


def test_ano_todo_fechado_mostra_ano_fechado(ambiente):
    bd, csrf = _preparar(ambiente)
    usuario = ambiente.conexao.execute("SELECT id FROM usuario").fetchone()[0]
    for mes in range(1, 13):
        fechamento.fechar(ambiente.conexao, bd, f"2026-{mes:02d}", usuario, ambiente.relogio())

    grade = ambiente.cliente.get("/fechamento/grade?ano=2026").text

    assert "12 de 12 meses fechados" in grade and "Ano fechado" in grade


def test_log_do_fechamento_mostra_o_valor_congelado(ambiente):
    bd, csrf = _preparar(ambiente)
    c = ambiente.conexao
    pessoa = c.execute("SELECT id FROM pessoa").fetchone()[0]
    tema = c.execute("SELECT id FROM tema").fetchone()[0]
    c.execute(
        "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (?, ?, ?, '2026-01', 100)",
        (bd, pessoa, tema),
    )
    c.commit()

    resposta = ambiente.cliente.post(
        "/fechamento/2026-01/fechar", data={"csrf": csrf, "ano": "2026"}
    )

    assert 'title="R$ 21.230,00"' in resposta.text  # 100 h × R$ 193,00 × 1,10 no log


# ---- Cargas ----


def test_rejeicoes_mostram_matricula_tema_mes_e_horas(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(
        ambiente, csrf, "matricula;tema_codigo;ano;mes;horas\nF9999;T-10;2026;9;176\n"
    )

    for rotulo in ("Matrícula", "Tema", "Mês", "Horas"):
        assert f">{rotulo}</th>" in resposta.text, rotulo
    assert "F9999" in resposta.text and "T-10" in resposta.text and "set/2026" in resposta.text
    assert "176" in resposta.text


def test_resumo_da_carga_mostra_liquido_e_bruto(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(
        ambiente, csrf, "matricula;tema_codigo;ano;mes;horas\nF0101;T-10;2026;1;100\n"
    )

    assert "Valor líquido" in resposta.text and "Valor bruto" in resposta.text
    assert 'title="R$ 19.300,00"' in resposta.text  # 100 h × R$ 193,00
    assert 'title="R$ 21.230,00"' in resposta.text  # com markup de 10%


def test_relatorio_tem_botao_para_fechar(ambiente):
    _, csrf = _preparar(ambiente)

    resposta = _enviar(ambiente, csrf, "matricula;tema_codigo;ano;mes;horas\nF0101;T-10;2026;1;1\n")

    assert "Fechar relatório" in resposta.text


# ---- login ----


def test_login_tem_logo_senha_com_olho_e_os_textos_do_prototipo(ambiente):
    html = ambiente.cliente.get("/login").text

    assert 'data-logo="marca"' in html
    assert "data-alternar-senha" in html
    assert "Acesse o controle financeiro do seu business domain." in html
    assert 'placeholder="voce@empresa.com"' in html
    assert "Não tem conta?" in html


def test_conta_e_escolha_de_bd_seguem_os_textos_do_prototipo(ambiente):
    conta = ambiente.cliente.get("/conta").text
    assert "Use seu e-mail corporativo. O acesso a um BD é liberado pelo admin dele." in conta
    assert 'data-logo="marca"' in conta
    assert "Já tem conta?" in conta

    semear(ambiente, bds=())
    entrar(ambiente)
    bds = ambiente.cliente.get("/bds").text
    assert "ainda não está vinculada a um business domain" in bds
    assert "ana@empresa.com" in bds
