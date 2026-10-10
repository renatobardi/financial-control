from financeiro.cargas import motor
from financeiro.store import cargas as armazem
from tests.cargas.conftest import AGORA


def _carga(base, layout, texto):
    return motor.processar(
        base.conexao, base.bd, layout, texto.encode(), f"{layout}.csv", base.usuario, AGORA
    )


def _regras(base, rel):
    return [r.regra for r in armazem.rejeicoes_da_carga(base.conexao, base.bd, rel.carga_id)]


# ---- Compras realizadas ----


def test_compras_gravam_o_valor_liquido_do_mes(base):
    rel = _carga(base, "compras", "ordem_numero;ano;mes;valor_liquido\nOC0001;2026;9;1.234,56\n")

    assert (rel.inseridas, rel.rejeitadas, rel.valor_centavos) == (1, 0, 123456)
    linha = base.conexao.execute("SELECT mes, valor_liquido_centavos FROM compra_mes").fetchone()
    assert linha == ("2026-09", 123456)


def test_compras_aceitam_ponto_decimal_de_exportacao(base):
    rel = _carga(base, "compras", "ordem_numero;ano;mes;valor_liquido\nOC0001;2026;9;1234.56\n")

    assert rel.valor_centavos == 123456


def test_compras_rejeitam_ordem_inexistente_cancelada_e_valor_ruim(base):
    texto = (
        "ordem_numero;ano;mes;valor_liquido\n"
        "OC9999;2026;9;10,00\nOC0003;2026;9;10,00\nOC0001;2026;9;dez\n"
    )

    rel = _carga(base, "compras", texto)

    assert _regras(base, rel) == ["ORDEM_INEXISTENTE", "ORDEM_CANCELADA", "VALOR_INVALIDO"]


def test_compras_em_mes_fechado_sao_rejeitadas(base):
    base.conexao.execute(
        "INSERT INTO mes_fechado (bd_id, mes, fechado_em) VALUES (?, '2026-08', 'x')", (base.bd,)
    )
    base.conexao.commit()

    rel = _carga(base, "compras", "ordem_numero;ano;mes;valor_liquido\nOC0001;2026;8;10,00\n")

    assert _regras(base, rel) == ["MES_FECHADO"]


# ---- Orçamento PDD ----


def test_pdd_grava_na_revisao_rascunho_e_cria_a_original(base):
    rel = _carga(
        base,
        "pdd",
        "iniciativa_numero;tipo;valor_bruto\nI-01;CAPEX;1.500.000,00\nI-01;OPEX;200000\n",
    )

    assert (rel.inseridas, rel.rejeitadas) == (2, 0)
    revisao = base.conexao.execute("SELECT rotulo, estado FROM pdd_revisao").fetchall()
    assert revisao == [("Original", "rascunho")]
    valores = base.conexao.execute(
        "SELECT tipo, valor_bruto_centavos FROM pdd_linha ORDER BY tipo"
    ).fetchall()
    assert valores == [("CAPEX", 150000000), ("OPEX", 20000000)]


def test_pdd_rejeita_iniciativa_inexistente_e_tipo_invalido(base):
    rel = _carga(
        base, "pdd", "iniciativa_numero;tipo;valor_bruto\nI-99;CAPEX;10,00\nI-01;INFRA;10,00\n"
    )

    assert _regras(base, rel) == ["INICIATIVA_INEXISTENTE", "TIPO_INVALIDO"]


def test_pdd_repetido_nao_duplica(base):
    texto = "iniciativa_numero;tipo;valor_bruto\nI-01;CAPEX;100,00\n"
    _carga(base, "pdd", texto)

    rel = _carga(base, "pdd", texto)

    assert rel.iguais == 1
    assert base.conexao.execute("SELECT COUNT(*) FROM pdd_linha").fetchone()[0] == 1
    assert base.conexao.execute("SELECT COUNT(*) FROM pdd_revisao").fetchone()[0] == 1


# ---- Pessoas ----


def test_pessoas_criam_e_atualizam_por_matricula(base):
    texto = (
        "matricula;nome;org_codigo;cargo_codigo;vig_ini;tema_codigo\n"
        "F0202;Bruno Reis;o3;c5;2026-01;T-10\n"
        "F0101;Ana L. Souza;o3;c5;2025-01;T-10\n"
    )

    rel = _carga(base, "pessoas", texto)

    assert (rel.inseridas, rel.atualizadas) == (1, 1)
    nomes = dict(base.conexao.execute("SELECT matricula, nome FROM pessoa").fetchall())
    assert nomes == {"F0101": "Ana L. Souza", "F0202": "Bruno Reis"}


def test_pessoas_rejeitam_org_cargo_e_tema_inexistentes(base):
    texto = (
        "matricula;nome;org_codigo;cargo_codigo;vig_ini;tema_codigo\n"
        "F1;A;o99;c5;2026-01;T-10\nF2;B;o3;c99;2026-01;T-10\nF3;C;o3;c5;2026-01;T-99\n"
        "F4;D;o3;c5;2026-13;T-10\n"
    )

    rel = _carga(base, "pessoas", texto)

    assert _regras(base, rel) == [
        "ORG_INEXISTENTE",
        "CARGO_INEXISTENTE",
        "TEMA_INEXISTENTE",
        "MES_INVALIDO",
    ]


def test_pessoa_nova_exige_tema_mas_a_existente_mantem_o_dela(base):
    sem_tema = (
        "matricula;nome;org_codigo;cargo_codigo;vig_ini\n"
        "F0303;Nova;o3;c5;2026-01\nF0101;Ana Lima;o3;c5;2025-01\n"
    )

    rel = _carga(base, "pessoas", sem_tema)

    assert _regras(base, rel) == ["TEMA_INEXISTENTE"]
    assert rel.iguais == 1


# ---- Tarifas ----


def test_tarifa_nova_vigencia_encerra_a_anterior(base):
    texto = (
        "empresa_codigo;cargo_codigo;nivel;valor_hora_liquido;vig_ini\nNTT;c6;N8;135,00;2026-02\n"
    )

    rel = _carga(base, "tarifas", texto)

    assert (rel.inseridas, rel.rejeitadas) == (1, 0)
    linhas = base.conexao.execute(
        "SELECT liquida_centavos, vigencia_ini, vigencia_fim FROM tarifa ORDER BY vigencia_ini"
    ).fetchall()
    assert linhas == [(12960, "2025-01", "2026-01"), (13500, "2026-02", None)]


def test_tarifa_retroativa_cargo_inexistente_e_nivel_divergente(base):
    texto = (
        "empresa_codigo;cargo_codigo;nivel;valor_hora_liquido;vig_ini\n"
        "NTT;c6;N8;100,00;2024-12\nNTT;c9;N8;100,00;2026-02\nNTT;c6;N11;100,00;2026-02\n"
    )

    rel = _carga(base, "tarifas", texto)

    assert _regras(base, rel) == ["VIGENCIA_RETROATIVA", "CARGO_INEXISTENTE", "NIVEL_DIVERGENTE"]


def test_tarifa_repetida_e_igual(base):
    texto = (
        "empresa_codigo;cargo_codigo;nivel;valor_hora_liquido;vig_ini\nNTT;c6;N8;129,60;2025-01\n"
    )

    rel = _carga(base, "tarifas", texto)

    assert (rel.iguais, rel.inseridas) == (1, 0)


def test_desfazer_tarifa_reabre_a_vigencia_anterior(base):
    texto = (
        "empresa_codigo;cargo_codigo;nivel;valor_hora_liquido;vig_ini\nNTT;c6;N8;135,00;2026-02\n"
    )
    rel = _carga(base, "tarifas", texto)

    motor.desfazer(base.conexao, base.bd, rel.carga_id, AGORA)

    linhas = base.conexao.execute(
        "SELECT liquida_centavos, vigencia_ini, vigencia_fim FROM tarifa"
    ).fetchall()
    assert linhas == [(12960, "2025-01", None)]


# ---- Portfólio ----


PORTFOLIO = (
    "iniciativa_codigo;iniciativa;demanda_codigo;demanda;tipo;tema_codigo;tema;agrupamento\n"
)


def test_portfolio_cria_a_cadeia_iniciativa_demanda_tema(base):
    rel = _carga(
        base,
        "portfolio",
        PORTFOLIO + "I-02;Beta;D-201;Cobrança digital;OPEX;T-20;Jornada;Gravity\n",
    )

    assert rel.rejeitadas == 0
    tema = base.conexao.execute(
        "SELECT t.codigo, d.nome, d.tipo, i.nome, a.nome FROM tema t"
        " JOIN demanda d ON d.id = t.demanda_id JOIN iniciativa i ON i.id = d.iniciativa_id"
        " JOIN agrupamento a ON a.id = t.agrupamento_id WHERE t.codigo = 'T-20'"
    ).fetchone()
    assert tema == ("T-20", "Cobrança digital", "OPEX", "Beta", "Gravity")


def test_portfolio_repetido_nao_duplica_e_nome_novo_atualiza(base):
    linha = "I-02;Beta;D-201;Cobrança;OPEX;T-20;Jornada;Gravity\n"
    _carga(base, "portfolio", PORTFOLIO + linha)

    repetida = _carga(base, "portfolio", PORTFOLIO + linha)
    renomeada = _carga(
        base, "portfolio", PORTFOLIO + "I-02;Beta 2;D-201;Cobrança;OPEX;T-20;Jornada;Gravity\n"
    )

    assert repetida.iguais == 1 and repetida.inseridas == 0
    assert renomeada.atualizadas == 1
    assert base.conexao.execute("SELECT COUNT(*) FROM iniciativa").fetchone()[0] == 2


def test_portfolio_rejeita_tipo_invalido_e_demanda_em_outra_iniciativa(base):
    texto = (
        PORTFOLIO
        + "I-02;Beta;D-301;X;INFRA;T-30;Y;RTB\n"
        + "I-02;Beta;D-101;Motor;CAPEX;T-31;Z;RTB\n"
    )

    rel = _carga(base, "portfolio", texto)

    assert _regras(base, rel) == ["TIPO_INVALIDO", "DEMANDA_EM_OUTRA_INICIATIVA"]
