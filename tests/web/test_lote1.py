"""Lote 1 da #44: correções de comportamento revisadas contra o protótipo."""

import re

from financeiro import compras, fechamento, orcamento
from financeiro.store import cadastros, organizacao, pessoas, portfolio
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Admin"):
    _, ids = semear(ambiente, bds=(("O1", papel),))
    bd = ids["O1"]
    c = ambiente.conexao
    tema, _ = _cadastros(ambiente, bd)
    cadastros.definir_markup(c, bd, 1000, "2026-01")
    entrar(ambiente)
    usuario = c.execute("SELECT id FROM usuario").fetchone()[0]
    return bd, usuario, csrf_de(ambiente.cliente.get("/configuracoes").text)


# ---- editar pessoa ----


def test_editar_pessoa_muda_nome_squad_cargo_e_tema_pela_tela(ambiente):
    bd, _, csrf = _preparar(ambiente)
    c = ambiente.conexao
    tribo = organizacao.listar_orgs(c, bd)[0].id
    outro_squad = organizacao.criar_org(c, bd, "Squad", "Squad B", tribo, "G", "2025-01")
    empresa = cadastros.listar_empresas(c, bd)[0].id
    outro_cargo = cadastros.criar_cargo(c, bd, empresa, "Master", "N10")
    pessoa = pessoas.listar_pessoas(c, bd)[0]

    resposta = ambiente.cliente.post(
        f"/pessoas/{pessoa.id}",
        data={
            "csrf": csrf, "nome": "Ana L. Souza", "org_id": str(outro_squad),
            "cargo_id": str(outro_cargo), "desligamento": "",
        },
    )  # fmt: skip

    assert resposta.status_code == 200
    atual = pessoas.achar_pessoa(c, bd, pessoa.id)
    assert (atual.nome, atual.org, atual.cargo) == ("Ana L. Souza", "Squad B", "Master")


def test_pessoa_na_tela_traz_campos_de_nome_squad_cargo_e_tema(ambiente):
    _preparar(ambiente)

    lista = ambiente.cliente.get("/pessoas/lista?de=2026-01&ate=2026-12").text

    for campo in ('name="nome"', 'name="org_id"', 'name="cargo_id"', 'name="tema_id"'):
        assert campo in lista, campo


# ---- cancelar ordem ----


def test_cancelar_ordem_tem_botao_com_confirmacao_e_cancela(ambiente):
    bd, usuario, csrf = _preparar(ambiente)
    demanda = portfolio.listar_demandas(ambiente.conexao, bd)[0].id
    ordem = compras.criar_prevista(
        ambiente.conexao, bd, "OC", demanda, "X", usuario, ambiente.relogio()
    )

    detalhe = ambiente.cliente.get(f"/compras/{ordem}/detalhe").text
    resposta = ambiente.cliente.post(
        f"/compras/{ordem}", data={"csrf": csrf, "status": "cancelada"}
    )

    assert "Cancelar ordem" in detalhe
    assert f'hx-post="/compras/{ordem}/cancelar"' in detalhe
    assert 'hx-confirm="' in detalhe
    assert resposta.status_code == 200
    assert compras.achar(ambiente.conexao, bd, ordem).status == "cancelada"


def test_rota_cancelar_ordem_cancela_e_registra_no_historico(ambiente):
    bd, usuario, csrf = _preparar(ambiente)
    demanda = portfolio.listar_demandas(ambiente.conexao, bd)[0].id
    ordem = compras.criar_prevista(
        ambiente.conexao, bd, "OC", demanda, "X", usuario, ambiente.relogio()
    )

    resposta = ambiente.cliente.post(f"/compras/{ordem}/cancelar", data={"csrf": csrf})

    assert resposta.status_code == 200
    assert "Ordem cancelada: saiu do forecast." in resposta.text
    assert "status: prevista → cancelada" in resposta.text


# ---- confirmação ----


def test_acoes_destrutivas_pedem_confirmacao(ambiente):
    bd, usuario, csrf = _preparar(ambiente)
    c = ambiente.conexao
    ini = portfolio.listar_iniciativas(c, bd)[0].id
    agora = ambiente.relogio()
    rev = orcamento.nova_revisao(c, bd, agora)
    orcamento.definir_linha(c, bd, rev.id, ini, "CAPEX", 100_000)

    pdd = ambiente.cliente.get("/orcamento/tabela").text
    fech = ambiente.cliente.get("/fechamento/grade?ano=2026").text
    fechamento.fechar(c, bd, "2026-01", usuario, agora)
    reabrir = ambiente.cliente.get("/fechamento/grade?ano=2026").text

    for texto, rota in (
        (pdd, "/aprovar"), (pdd, "/descartar"), (pdd, "/linhas/remover"),
        (fech, "/fechar"), (reabrir, "/reabrir"),
    ):  # fmt: skip
        formulario = re.search(rf'<form[^>]*{re.escape(rota)}"[^>]*>', texto)
        assert formulario, rota
        assert "hx-confirm=" in formulario.group(0), rota


def test_desfazer_carga_e_remover_membro_pedem_confirmacao(ambiente):
    bd, _, csrf = _preparar(ambiente)
    texto = "matricula;tema_codigo;ano;mes;horas\nF0101;T-10;2026;9;100\n"
    ambiente.cliente.post(
        "/cargas", data={"csrf": csrf, "layout": "horas"},
        files={"arquivo": ("h.csv", texto.encode(), "text/csv")},
    )  # fmt: skip

    relatorio = ambiente.cliente.get("/cargas/1").text
    config = ambiente.cliente.get("/configuracoes?aba=membros").text

    desfazer = re.search(r'<form[^>]*/desfazer"[^>]*>', relatorio)
    remover = re.search(r'<form[^>]*/remover"[^>]*>', config)
    assert desfazer and "hx-confirm=" in desfazer.group(0)
    assert remover and "hx-confirm=" in remover.group(0)


# ---- calendário ----


def test_calendario_nao_ajusta_mes_passado_nem_com_carga(ambiente):
    bd, _, csrf = _preparar(ambiente)
    c = ambiente.conexao
    pessoa = pessoas.listar_pessoas(c, bd)[0].id
    tema = portfolio.listar_temas(c, bd)[0].id
    c.execute(
        "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, '2026-12', 10)",
        (bd, pessoa, tema),
    )
    c.commit()

    passado = ambiente.cliente.post(
        "/cadastros/calendario/ajustar",
        data={"csrf": csrf, "ano": "2026", "mes": "9", "horas": "100"},
    )
    com_carga = ambiente.cliente.post(
        "/cadastros/calendario/ajustar",
        data={"csrf": csrf, "ano": "2026", "mes": "12", "horas": "100"},
    )
    livre = ambiente.cliente.post(
        "/cadastros/calendario/ajustar",
        data={"csrf": csrf, "ano": "2026", "mes": "11", "horas": "100"},
    )

    assert passado.status_code == 409 and "mês passado" in passado.text
    assert com_carga.status_code == 409 and "já tem carga" in com_carga.text
    assert livre.status_code == 200


# ---- vagas ----


def test_cancelar_vaga_so_aparece_nas_abertas(ambiente):
    bd, _, csrf = _preparar(ambiente)
    c = ambiente.conexao
    squad = organizacao.listar_orgs(c, bd)[1].id
    tema = portfolio.listar_temas(c, bd)[0].id
    cargo = cadastros.listar_cargos(c, bd)[0].id
    v1 = pessoas.abrir_vaga(c, bd, "V-1", squad, tema, cargo, "2026-08")
    pessoas.abrir_vaga(c, bd, "V-2", squad, tema, cargo, "2026-08")
    pessoas.cancelar_vaga(c, bd, v1)

    lista = ambiente.cliente.get("/cadastros/vagas/lista").text

    assert lista.count("/cadastros/vagas/cancelar") == 2  # uma no <form> e outra no hx-post
