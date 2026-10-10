import json

import pytest

from financeiro.cargas import motor
from financeiro.store import cargas as armazem
from tests.cargas.conftest import AGORA

HORAS = "matricula;tema_codigo;ano;mes;horas\n"


def _carga(base, texto, layout="horas", aplicar=True, arquivo="horas_set.csv"):
    return motor.processar(
        base.conexao, base.bd, layout, texto.encode(), arquivo, base.usuario, AGORA, aplicar=aplicar
    )


def _alocacoes(base):
    return base.conexao.execute(
        "SELECT t.codigo, a.mes, a.horas, a.extra FROM alocacao a"
        " JOIN tema t ON t.id = a.tema_id ORDER BY t.codigo, a.mes"
    ).fetchall()


def test_horas_validas_sao_gravadas_e_o_relatorio_conta(base):
    rel = _carga(base, HORAS + "F0101;T-10;2026;9;120\nF0101;T-11;2026;9;40\n")

    assert (rel.lidas, rel.inseridas, rel.atualizadas, rel.iguais, rel.rejeitadas) == (
        2,
        2,
        0,
        0,
        0,
    )
    assert rel.horas == 160
    assert _alocacoes(base) == [("T-10", "2026-09", 120, 0), ("T-11", "2026-09", 40, 0)]


def test_carga_repetida_nao_duplica_linhas(base):
    texto = HORAS + "F0101;T-10;2026;9;120\n"
    _carga(base, texto)

    segunda = _carga(base, texto)

    assert (segunda.inseridas, segunda.atualizadas, segunda.iguais) == (0, 0, 1)
    assert _alocacoes(base) == [("T-10", "2026-09", 120, 0)]


def test_valor_diferente_na_mesma_chave_atualiza(base):
    _carga(base, HORAS + "F0101;T-10;2026;9;120\n")

    rel = _carga(base, HORAS + "F0101;T-10;2026;9;100\n")

    assert (rel.inseridas, rel.atualizadas) == (0, 1)
    assert _alocacoes(base) == [("T-10", "2026-09", 100, 0)]


def test_mes_fechado_e_rejeitado_com_mes_fechado(base):
    base.conexao.execute(
        "INSERT INTO mes_fechado (bd_id, mes, fechado_em) VALUES (?, '2026-08', 'x')", (base.bd,)
    )
    base.conexao.commit()

    rel = _carga(base, HORAS + "F0101;T-10;2026;8;160\nF0101;T-10;2026;9;120\n")

    assert (rel.inseridas, rel.rejeitadas) == (1, 1)
    rejeicao = armazem.rejeicoes_da_carga(base.conexao, base.bd, rel.carga_id)[0]
    assert (rejeicao.regra, rejeicao.linha) == ("MES_FECHADO", 2)
    assert "2026-08" in rejeicao.mensagem or "ago/2026" in rejeicao.mensagem
    assert _alocacoes(base) == [("T-10", "2026-09", 120, 0)]


def test_tema_e_pessoa_inexistentes_sao_rejeitados_com_a_regra(base):
    rel = _carga(base, HORAS + "F9999;T-10;2026;9;10\nF0101;T-88;2026;9;10\n")

    regras = [r.regra for r in armazem.rejeicoes_da_carga(base.conexao, base.bd, rel.carga_id)]
    assert regras == ["PESSOA_INEXISTENTE", "TEMA_INEXISTENTE"]
    assert rel.inseridas == 0 and _alocacoes(base) == []


def test_horas_invalidas_sao_rejeitadas(base):
    rel = _carga(
        base, HORAS + "F0101;T-10;2026;9;abc\nF0101;T-10;2026;13;10\nF0101;T-10;2026;9;-5\n"
    )

    regras = [r.regra for r in armazem.rejeicoes_da_carga(base.conexao, base.bd, rel.carga_id)]
    assert regras == ["VALOR_INVALIDO", "MES_INVALIDO", "VALOR_INVALIDO"]


def test_horas_acima_do_calendario_ficam_pendentes_de_aprovacao(base):
    # set/2026 = 21 dias úteis = 168 h. A pessoa tem 210 h no mês.
    rel = _carga(base, HORAS + "F0101;T-10;2026;9;120\nF0101;T-11;2026;9;90\n")

    rejeicoes = armazem.rejeicoes_da_carga(base.conexao, base.bd, rel.carga_id)
    assert [r.regra for r in rejeicoes] == ["HORAS_ACIMA_CAL", "HORAS_ACIMA_CAL"]
    assert all(r.aprovavel and not r.aprovada for r in rejeicoes)
    assert "210h" in rejeicoes[0].mensagem and "168h" in rejeicoes[0].mensagem
    assert "42h" in rejeicoes[0].mensagem
    assert _alocacoes(base) == []


def test_aprovar_as_horas_extras_grava_com_marca_de_extra(base):
    rel = _carga(base, HORAS + "F0101;T-10;2026;9;120\nF0101;T-11;2026;9;90\n")
    grupo = armazem.rejeicoes_da_carga(base.conexao, base.bd, rel.carga_id)[0].grupo

    motor.aprovar_extras(base.conexao, base.bd, rel.carga_id, grupo, AGORA)

    assert _alocacoes(base) == [("T-10", "2026-09", 120, 1), ("T-11", "2026-09", 90, 1)]
    assert all(r.aprovada for r in armazem.rejeicoes_da_carga(base.conexao, base.bd, rel.carga_id))
    with pytest.raises(motor.CargaInvalida):
        motor.aprovar_extras(base.conexao, base.bd, rel.carga_id, grupo, AGORA)


def test_desfazer_volta_o_banco_ao_estado_anterior_a_carga(base):
    _carga(base, HORAS + "F0101;T-10;2026;9;100\n")
    antes = _alocacoes(base)
    rel = _carga(base, HORAS + "F0101;T-10;2026;9;120\nF0101;T-11;2026;9;30\n")
    assert _alocacoes(base) != antes

    motor.desfazer(base.conexao, base.bd, rel.carga_id, AGORA)

    assert _alocacoes(base) == antes
    assert armazem.achar_carga(base.conexao, base.bd, rel.carga_id).estado == "desfeita"


def test_nao_desfaz_carga_se_outra_posterior_mexeu_nos_mesmos_registros(base):
    primeira = _carga(base, HORAS + "F0101;T-10;2026;9;100\n")
    _carga(base, HORAS + "F0101;T-10;2026;9;90\n")

    with pytest.raises(motor.CargaInvalida) as erro:
        motor.desfazer(base.conexao, base.bd, primeira.carga_id, AGORA)

    assert "posterior" in str(erro.value)
    assert _alocacoes(base) == [("T-10", "2026-09", 90, 0)]


def test_nao_desfaz_carga_que_mexeu_em_mes_que_depois_fechou(base):
    rel = _carga(base, HORAS + "F0101;T-10;2026;9;100\n")
    base.conexao.execute(
        "INSERT INTO mes_fechado (bd_id, mes, fechado_em) VALUES (?, '2026-09', 'x')", (base.bd,)
    )
    base.conexao.commit()

    with pytest.raises(motor.CargaInvalida) as erro:
        motor.desfazer(base.conexao, base.bd, rel.carga_id, AGORA)

    assert "fechado" in str(erro.value)


def test_pre_validacao_nao_grava_nada_mas_devolve_o_relatorio(base):
    rel = _carga(base, HORAS + "F0101;T-10;2026;9;120\nF9999;T-10;2026;9;1\n", aplicar=False)

    assert (rel.inseridas, rel.rejeitadas) == (1, 1)
    assert rel.carga_id is None
    assert _alocacoes(base) == []
    assert base.conexao.execute("SELECT COUNT(*) FROM carga").fetchone()[0] == 0


def test_arquivo_invalido_falha_sem_gravar_nada(base):
    with pytest.raises(motor.CargaInvalida) as erro:
        _carga(base, "matricula\ttema_codigo\tano\tmes\thoras\nF0101\tT-10\t2026\t9\t10\n")

    assert erro.value.regra == "CSV_CABECALHO"
    assert base.conexao.execute("SELECT COUNT(*) FROM carga").fetchone()[0] == 0
    with pytest.raises(motor.CargaInvalida) as erro:
        motor.processar(
            base.conexao,
            base.bd,
            "horas",
            (HORAS + "F0101;Tê-10;2026;9;1\n").encode("latin-1"),
            "x.csv",
            base.usuario,
            AGORA,
        )
    assert erro.value.regra == "CSV_CODIFICACAO"


def test_layout_desconhecido_e_recusado(base):
    with pytest.raises(motor.CargaInvalida):
        _carga(base, HORAS, layout="xpto")


def test_carga_de_um_bd_nao_enxerga_cadastro_de_outro(base):
    from financeiro.store import acesso

    outro = acesso.criar_bd(base.conexao, "Outro", "OT")

    rel = motor.processar(
        base.conexao,
        outro,
        "horas",
        (HORAS + "F0101;T-10;2026;9;10\n").encode(),
        "x.csv",
        base.usuario,
        AGORA,
    )

    assert rel.inseridas == 0 and rel.rejeitadas == 1
    assert (
        json.loads(base.conexao.execute("SELECT dados_json FROM carga_rejeicao").fetchone()[0])[
            "matricula"
        ]
        == "F0101"
    )
