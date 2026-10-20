from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from financeiro import senha
from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def base(conexao):
    """BD com organização, cargos, portfólio, pessoas e uma compra, já cadastrados."""
    bd = acesso.criar_bd(conexao, "BD", "B")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "Tribo D&C", None, "G", "2025-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "Squad A", tribo, "G", "2025-01")
    conexao.execute("UPDATE org SET codigo = 'o3' WHERE id = %s", (squad,))
    propria = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    ntt = cadastros.criar_empresa(conexao, bd, "NTT", "consultoria")
    conexao.execute("UPDATE empresa SET codigo = 'PROP' WHERE id = %s", (propria,))
    conexao.execute("UPDATE empresa SET codigo = 'NTT' WHERE id = %s", (ntt,))
    c5 = cadastros.criar_cargo(conexao, bd, propria, "Specialist II", "N11")
    c6 = cadastros.criar_cargo(conexao, bd, ntt, "Developer Pleno", "N8")
    conexao.execute("UPDATE cargo SET codigo = 'c5' WHERE id = %s", (c5,))
    conexao.execute("UPDATE cargo SET codigo = 'c6' WHERE id = %s", (c6,))
    cadastros.definir_tarifa(conexao, bd, c6, 12960, "2025-01")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Alfa")
    dem = portfolio.criar_demanda(conexao, bd, "D-101", ini, "Motor de regras", "CAPEX", squad)
    t10 = portfolio.criar_tema(conexao, bd, "T-10", dem, "Regras", agrup)
    t11 = portfolio.criar_tema(conexao, bd, "T-11", dem, "Modelos", agrup)
    ana = pessoas.criar_pessoa(conexao, bd, "F0101", "Ana Lima", squad, c5, t10, "2025-01", None)
    forn = portfolio.criar_fornecedor(conexao, bd, "Fornecedor A")
    conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, fornecedor_id, demanda_id, status)"
        " VALUES (%s, 'OC0001', 'OC', %s, %s, 'emitida')",
        (bd, forn, dem),
    )
    conexao.execute(
        "INSERT INTO compra (bd_id, numero, tipo, demanda_id, status)"
        " VALUES (%s, 'OC0003', 'OC', %s, 'cancelada')",
        (bd, dem),
    )
    conexao.commit()
    return SimpleNamespace(
        conexao=conexao,
        bd=bd,
        usuario=usuario,
        squad=squad,
        c5=c5,
        c6=c6,
        ana=ana,
        t10=t10,
        t11=t11,
    )
