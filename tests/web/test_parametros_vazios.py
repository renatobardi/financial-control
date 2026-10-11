"""O navegador manda `rev=` vazio quando o campo está em branco: tem de valer como ausente."""

from tests.web.ajuda import entrar, semear


def _logado(ambiente):
    semear(ambiente, bds=(("O1", "Admin"),))
    entrar(ambiente)


def test_blocos_da_visao_geral_aceitam_parametros_vazios(ambiente):
    _logado(ambiente)

    for bloco in ("kpis", "curva", "alertas", "risco"):
        r = ambiente.cliente.get(f"/visao-geral/{bloco}?cenario=&base=bruto&rev=")
        assert r.status_code == 200, (bloco, r.status_code)


def test_raiz_e_telas_aceitam_parametros_vazios(ambiente):
    _logado(ambiente)

    assert ambiente.cliente.get("/?cenario=&base=bruto&rev=").status_code == 200
    assert ambiente.cliente.get("/orcamento/tabela?rev=&comparar=&base=bruto").status_code == 200
    assert ambiente.cliente.get("/orcamento?rev=&comparar=").status_code == 200
    assert ambiente.cliente.get("/forecast/painel?cenario=&rev=&base=bruto").status_code == 200
    assert ambiente.cliente.get("/forecast?cenario=&rev=").status_code == 200
    assert ambiente.cliente.get("/realizado/tabela?ano=&dimensao=iniciativa").status_code == 200
    assert ambiente.cliente.get("/realizado?ano=").status_code == 200
    assert ambiente.cliente.get("/compras/lista?ano=&busca=&status=").status_code == 200
    assert ambiente.cliente.get("/cadastros/calendario/lista?ano=").status_code == 200
    assert ambiente.cliente.get("/fechamento/grade?ano=").status_code == 200


def test_valor_nao_numerico_continua_recusado(ambiente):
    _logado(ambiente)

    assert ambiente.cliente.get("/visao-geral/kpis?rev=abc").status_code == 422
