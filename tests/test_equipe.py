from datetime import UTC, datetime

import pytest

from financeiro import equipe, fechamento, senha
from financeiro.store import acesso, cadastros, organizacao, pessoas, portfolio

AGORA = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@pytest.fixture
def base(conexao):
    bd = acesso.criar_bd(conexao, "BD", "B")
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", senha.gerar_hash("x"))
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "Tribo D&C", None, "G", "2025-01")
    s1 = organizacao.criar_org(conexao, bd, "Squad", "Squad A", tribo, "G", "2025-01")
    s2 = organizacao.criar_org(conexao, bd, "Squad", "Squad B", tribo, "G", "2025-01")
    propria = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    ntt = cadastros.criar_empresa(conexao, bd, "NTT", "consultoria")
    c_prop = cadastros.criar_cargo(conexao, bd, propria, "Sênior", "N9")
    c_ntt = cadastros.criar_cargo(conexao, bd, ntt, "Dev", "N8")
    cadastros.definir_tarifa(conexao, bd, c_prop, 19300, "2026-01")
    cadastros.definir_tarifa(conexao, bd, c_ntt, 13500, "2026-01")
    cadastros.definir_markup(conexao, bd, 1000, "2026-01")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-1", "Ini")
    dem = portfolio.criar_demanda(conexao, bd, "D-1", ini, "Dem", "OPEX", s1)
    tema = portfolio.criar_tema(conexao, bd, "T-1", dem, "Tema", agrup)
    ana = pessoas.criar_pessoa(conexao, bd, "F1", "Ana Lima", s1, c_prop, tema, "2025-01", None)
    bia = pessoas.criar_pessoa(conexao, bd, "T1", "Bia Reis", s2, c_ntt, tema, "2026-02", "2026-03")
    for pessoa, mes, horas in ((ana, "2026-01", 100), (ana, "2026-02", 100), (bia, "2026-02", 80)):
        conexao.execute(
            "INSERT INTO alocacao (bd_id, pessoa_id, tema_id, mes, horas) VALUES (%s, %s, %s, %s, %s)",
            (bd, pessoa, tema, mes, horas),
        )
    conexao.commit()
    return SimpleNamespaceLike(conexao, bd, usuario, s1, s2, tribo, c_prop, c_ntt, tema, ana, bia)


class SimpleNamespaceLike:
    def __init__(self, conexao, bd, usuario, s1, s2, tribo, c_prop, c_ntt, tema, ana, bia):
        self.conexao, self.bd, self.usuario = conexao, bd, usuario
        self.s1, self.s2, self.tribo = s1, s2, tribo
        self.c_prop, self.c_ntt, self.tema, self.ana, self.bia = c_prop, c_ntt, tema, ana, bia


def test_pessoas_ativas_por_mes_e_o_total_do_ano_nao_e_a_soma_dos_meses(base):
    # Ana: jan..dez. Bia: fev e mar. Mar tem as duas; o ano tem 2 pessoas, não a soma dos meses.
    resultado = equipe.ativos_por_ano(base.conexao, base.bd, 2026)

    assert resultado.por_mes[:4] == [1, 2, 2, 1]
    assert resultado.distintos == 2
    assert sum(resultado.por_mes) != resultado.distintos


def test_listagem_do_periodo_com_horas_custo_e_meses_ativos(base):
    linhas = equipe.listar(base.conexao, base.bd, "2026-01", "2026-03", AGORA)

    por_matricula = {linha.matricula: linha for linha in linhas}
    ana, bia = por_matricula["F1"], por_matricula["T1"]
    assert (ana.meses_ativos, ana.horas) == (3, 200)
    assert ana.custo_centavos == 200 * 21_230  # R$ 193,00 × 1,10 por hora
    assert (bia.meses_ativos, bia.horas, bia.vinculo) == (2, 80, "consultoria")
    assert bia.custo_centavos == 80 * 14_850  # R$ 135,00 × 1,10 por hora
    assert ana.vinculo == "propria"


def test_listagem_filtra_por_unidade_e_busca(base):
    so_s2 = equipe.listar(base.conexao, base.bd, "2026-01", "2026-12", AGORA, unidade_id=base.s2)
    por_nome = equipe.listar(base.conexao, base.bd, "2026-01", "2026-12", AGORA, busca="ana")
    por_tribo = equipe.listar(
        base.conexao, base.bd, "2026-01", "2026-12", AGORA, unidade_id=base.tribo
    )

    assert [p.matricula for p in so_s2] == ["T1"]
    assert [p.matricula for p in por_nome] == ["F1"]
    assert sorted(p.matricula for p in por_tribo) == ["F1", "T1"]  # a tribo inclui os squads


def test_quem_nao_esta_ativo_no_periodo_nao_aparece(base):
    linhas = equipe.listar(base.conexao, base.bd, "2026-06", "2026-12", AGORA)

    assert [p.matricula for p in linhas] == ["F1"]  # Bia saiu em mar


def test_custo_de_mes_fechado_segue_o_congelado(base):
    fechamento.fechar(base.conexao, base.bd, "2026-01", base.usuario, AGORA)
    cadastros.definir_tarifa(base.conexao, base.bd, base.c_prop, 30000, "2026-02")

    jan = equipe.listar(base.conexao, base.bd, "2026-01", "2026-01", AGORA)[0]

    assert jan.custo_centavos == 100 * 21_230


def test_nova_pessoa_valida_matricula_unidade_e_mes(base):
    novo = equipe.nova_pessoa(
        base.conexao, base.bd, "F9", "Caio Dias", base.s1, base.c_prop, base.tema, "2026-10"
    )

    assert novo > 0
    with pytest.raises(equipe.EquipeInvalida):
        equipe.nova_pessoa(
            base.conexao, base.bd, "F9", "Outro", base.s1, base.c_prop, base.tema, "2026-10"
        )
    with pytest.raises(equipe.EquipeInvalida):
        equipe.nova_pessoa(
            base.conexao, base.bd, "F10", "X", base.tribo, base.c_prop, base.tema, "2026-10"
        )  # a unidade precisa ser um squad
    with pytest.raises(equipe.EquipeInvalida):
        equipe.nova_pessoa(
            base.conexao, base.bd, "F11", "Y", base.s1, base.c_prop, base.tema, "2026-13"
        )


def test_editar_muda_squad_cargo_e_desligamento(base):
    equipe.editar(
        base.conexao, base.bd, base.ana, org_id=base.s2, cargo_id=base.c_ntt, desligamento="2026-12"
    )

    ana = [p for p in equipe.listar(base.conexao, base.bd, "2026-12", "2026-12", AGORA)][0]
    assert (ana.unidade, ana.cargo, ana.desligamento) == ("Squad B", "Dev", "2026-12")
    with pytest.raises(equipe.EquipeInvalida):
        equipe.editar(base.conexao, base.bd, base.ana, desligamento="2024-01")  # antes da admissão


def test_pessoa_de_outro_bd_nao_e_listada_nem_editada(base):
    outro = acesso.criar_bd(base.conexao, "Outro", "OT")

    assert equipe.listar(base.conexao, outro, "2026-01", "2026-12", AGORA) == []
    with pytest.raises(equipe.EquipeInvalida):
        equipe.editar(base.conexao, outro, base.ana, desligamento="2026-12")
