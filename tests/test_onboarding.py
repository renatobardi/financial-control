from datetime import UTC, datetime

import pytest

from financeiro import onboarding, organizacao, store
from financeiro.cargas import motor
from financeiro.store import acesso, cadastros, portfolio
from tests.ajuda import cadastrar_ate_pessoa

ORDEM = (
    "organizacao",
    "iniciativas",
    "demandas",
    "agrupamentos",
    "temas",
    "cargos",
    "tarifas",
    "pessoas",
    "orcamento",
    "compras",
    "calendario",
)


@pytest.fixture
def bd(conexao):
    return acesso.criar_bd(conexao, "BD Teste", "BT")


def _por_chave(conexao, bd_id):
    return {p.chave: p for p in onboarding.situacao(conexao, bd_id).passos}


def test_bd_vazio_lista_os_onze_passos_na_ordem_com_dependentes_bloqueados(conexao, bd):
    situacao = onboarding.situacao(conexao, bd)

    assert tuple(p.chave for p in situacao.passos) == ORDEM
    por_chave = {p.chave: p for p in situacao.passos}
    assert por_chave["organizacao"].estado == "pendente"
    assert por_chave["iniciativas"].estado == "pendente"
    assert por_chave["agrupamentos"].estado == "pendente"
    assert por_chave["demandas"].estado == "bloqueado"
    assert por_chave["demandas"].bloqueado_por == ("iniciativas",)
    assert por_chave["temas"].bloqueado_por == ("demandas", "agrupamentos")
    assert por_chave["pessoas"].bloqueado_por == ("organizacao", "temas", "cargos")
    assert all(p.contagem == 0 for p in situacao.passos)
    assert situacao.pronto is False
    assert situacao.feitos == 0
    assert situacao.total == 11


def _estados(conexao, bd_id):
    return {chave: p.estado for chave, p in _por_chave(conexao, bd_id).items()}


def test_cadastrar_na_ordem_destrava_cada_passo(conexao, bd):
    tribo = organizacao.criar_tribo(conexao, bd, "Tribo", "G", "2026-01")
    assert _estados(conexao, bd)["organizacao"] == "pendente"  # tribo sozinha não basta
    squad = organizacao.criar_squad(conexao, bd, "Squad", tribo, "G", "2026-01")
    assert _estados(conexao, bd)["organizacao"] == "feito"

    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Iniciativa")
    estados = _estados(conexao, bd)
    assert estados["iniciativas"] == "feito"
    assert estados["demandas"] == "pendente"
    assert estados["orcamento"] == "pendente"

    dem = portfolio.criar_demanda(conexao, bd, "D-01", ini, "Demanda", "OPEX", squad)
    assert _estados(conexao, bd)["demandas"] == "feito"
    assert _estados(conexao, bd)["temas"] == "bloqueado"  # falta agrupamento

    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    assert _estados(conexao, bd)["temas"] == "pendente"
    portfolio.criar_tema(conexao, bd, "T-01", dem, "Tema", agrup)
    assert _estados(conexao, bd)["temas"] == "feito"
    assert _estados(conexao, bd)["pessoas"] == "bloqueado"  # falta cargo

    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    assert _estados(conexao, bd)["cargos"] == "pendente"  # empresa sozinha não basta
    cadastros.criar_cargo(conexao, bd, empresa, "Pleno", "N8")
    estados = _estados(conexao, bd)
    assert estados["cargos"] == "feito"
    assert estados["tarifas"] == "pendente"
    assert estados["pessoas"] == "pendente"


def test_tarifas_so_ficam_feitas_com_tarifa_e_markup(conexao, bd):
    cargo = cadastrar_ate_pessoa(conexao, bd)

    cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    assert _estados(conexao, bd)["tarifas"] == "pendente"
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")

    assert _estados(conexao, bd)["tarifas"] == "feito"


def test_pessoas_nao_esperam_pelas_tarifas(conexao, bd):
    cadastrar_ate_pessoa(conexao, bd)

    estados = _estados(conexao, bd)

    assert estados["pessoas"] == "feito"
    assert estados["tarifas"] == "pendente"


def test_contagem_do_passo_e_isolada_por_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OU")
    cadastrar_ate_pessoa(conexao, outro)
    portfolio.criar_iniciativa(conexao, bd, "I-01", "Iniciativa")

    por_chave = _por_chave(conexao, bd)

    assert por_chave["iniciativas"].contagem == 1
    assert por_chave["pessoas"].contagem == 0
    assert _por_chave(conexao, outro)["pessoas"].contagem == 1


def test_pronto_so_com_os_oito_obrigatorios_feitos(conexao, bd):
    cargo = cadastrar_ate_pessoa(conexao, bd)
    assert onboarding.situacao(conexao, bd).pronto is False  # faltam tarifa e markup

    cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")

    situacao = onboarding.situacao(conexao, bd)
    assert situacao.pronto is True
    assert situacao.feitos == 8  # os três opcionais seguem pendentes


def test_apagar_o_unico_squad_volta_a_nao_pronto(conexao, bd):
    cargo = cadastrar_ate_pessoa(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")
    assert onboarding.situacao(conexao, bd).pronto is True

    conexao.execute("PRAGMA foreign_keys = OFF")
    conexao.execute("DELETE FROM org WHERE bd_id = ? AND tipo = 'Squad'", (bd,))

    assert onboarding.situacao(conexao, bd).pronto is False
    assert _estados(conexao, bd)["organizacao"] == "pendente"


def test_carga_de_portfolio_marca_iniciativas_demandas_agrupamentos_e_temas(conexao, bd):
    usuario = acesso.criar_usuario(conexao, "ana@empresa.com", "Ana", "h")
    csv = (
        b"iniciativa_codigo,iniciativa,demanda_codigo,demanda,tipo,tema_codigo,tema,agrupamento\n"
        b"I-01,Alfa,D-01,Motor,CAPEX,T-01,Regras,RTB\n"
    )

    motor.processar(conexao, bd, "portfolio", csv, "p.csv", usuario, datetime.now(UTC))

    estados = _estados(conexao, bd)
    for chave in ("iniciativas", "demandas", "agrupamentos", "temas"):
        assert estados[chave] == "feito"
    assert estados["pessoas"] == "bloqueado"


def test_passo_obrigatorio_nao_pode_ser_dispensado(conexao, bd):
    with pytest.raises(onboarding.PassoObrigatorio):
        onboarding.dispensar(conexao, bd, "pessoas")
    assert _estados(conexao, bd)["pessoas"] == "bloqueado"


def test_passo_desconhecido_e_recusado(conexao, bd):
    with pytest.raises(onboarding.PassoDesconhecido):
        onboarding.dispensar(conexao, bd, "inexistente")


def test_passo_opcional_dispensado_conta_como_resolvido_e_pode_ser_desfeito(conexao, bd):
    onboarding.dispensar(conexao, bd, "compras")

    situacao = onboarding.situacao(conexao, bd)
    assert {p.chave: p.estado for p in situacao.passos}["compras"] == "nao_se_aplica"
    assert situacao.feitos == 1

    onboarding.dispensar(conexao, bd, "compras", desfazer=True)

    assert onboarding.situacao(conexao, bd).feitos == 0
    assert _estados(conexao, bd)["compras"] == "bloqueado"


def test_dispensar_duas_vezes_nao_falha(conexao, bd):
    onboarding.dispensar(conexao, bd, "calendario")
    onboarding.dispensar(conexao, bd, "calendario")

    assert _estados(conexao, bd)["calendario"] == "nao_se_aplica"


def test_dispensa_e_isolada_por_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OU")

    onboarding.dispensar(conexao, bd, "calendario")

    assert _estados(conexao, outro)["calendario"] == "pendente"


def test_dado_cadastrado_vale_mais_que_a_dispensa(conexao, bd):
    onboarding.dispensar(conexao, bd, "orcamento")
    portfolio.criar_iniciativa(conexao, bd, "I-01", "Iniciativa")
    conexao.execute(
        "INSERT INTO pdd_revisao (bd_id, rotulo, criada_em) VALUES (?, 'Original', '2026-01-01')",
        (bd,),
    )

    assert _estados(conexao, bd)["orcamento"] == "feito"


def test_abrir_primeira_vez_so_devolve_verdadeiro_uma_vez_por_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OU")

    assert onboarding.abrir_primeira_vez(conexao, bd) is True
    assert onboarding.abrir_primeira_vez(conexao, bd) is False
    assert onboarding.abrir_primeira_vez(conexao, outro) is True


def test_bd_que_ja_existia_antes_da_funcionalidade_nasce_como_ja_aberto(tmp_path):
    antigas = tmp_path / "antigas"
    antigas.mkdir()
    for arquivo in store.PASTA_MIGRACOES.glob("*.sql"):
        if arquivo.name < "0013":
            (antigas / arquivo.name).write_text(arquivo.read_text())
    conexao = store.abrir(tmp_path / "f.db")
    store.migrar(conexao, antigas)
    antigo = acesso.criar_bd(conexao, "Antigo", "AN")

    store.migrar(conexao, store.PASTA_MIGRACOES)
    novo = acesso.criar_bd(conexao, "Novo", "NO")

    assert onboarding.abrir_primeira_vez(conexao, antigo) is False
    assert onboarding.abrir_primeira_vez(conexao, novo) is True


def _pendencias(conexao, bd_id):
    return {chave: p.pendencias for chave, p in _por_chave(conexao, bd_id).items()}


def test_tribo_sem_squad_aparece_como_pendencia_da_organizacao(conexao, bd):
    com_squad = organizacao.criar_tribo(conexao, bd, "Tribo A", "G", "2026-01")
    organizacao.criar_squad(conexao, bd, "Squad", com_squad, "G", "2026-01")
    organizacao.criar_tribo(conexao, bd, "Tribo B", "G", "2026-01")

    passo = _por_chave(conexao, bd)["organizacao"]

    assert passo.estado == "feito"
    assert passo.pendencias == ("Tribo B",)


def test_iniciativa_sem_demanda_aparece_como_pendencia_das_demandas(conexao, bd):
    tribo = organizacao.criar_tribo(conexao, bd, "Tribo", "G", "2026-01")
    squad = organizacao.criar_squad(conexao, bd, "Squad", tribo, "G", "2026-01")
    alfa = portfolio.criar_iniciativa(conexao, bd, "I-01", "Alfa")
    portfolio.criar_iniciativa(conexao, bd, "I-02", "Beta")
    portfolio.criar_demanda(conexao, bd, "D-01", alfa, "Demanda", "OPEX", squad)

    passo = _por_chave(conexao, bd)["demandas"]

    assert passo.estado == "feito"
    assert passo.pendencias == ("I-02 Beta",)


def test_demanda_sem_tema_aparece_como_pendencia_dos_temas(conexao, bd):
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Alfa")
    com_tema = portfolio.criar_demanda(conexao, bd, "D-01", ini, "Motor", "OPEX", None)
    portfolio.criar_demanda(conexao, bd, "D-02", ini, "Regras", "CAPEX", None)
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    portfolio.criar_tema(conexao, bd, "T-01", com_tema, "Tema", agrup)

    passo = _por_chave(conexao, bd)["temas"]

    assert passo.estado == "feito"
    assert passo.pendencias == ("D-02 Regras",)


def test_cargo_sem_tarifa_aparece_como_pendencia_das_tarifas(conexao, bd):
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    pleno = cadastros.criar_cargo(conexao, bd, empresa, "Pleno", "N8")
    cadastros.criar_cargo(conexao, bd, empresa, "Sênior", "N10")
    cadastros.definir_tarifa(conexao, bd, pleno, 12000, "2026-01")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")

    passo = _por_chave(conexao, bd)["tarifas"]

    assert passo.estado == "feito"
    assert passo.pendencias == ("Sênior (Própria)",)


def test_passo_que_nao_esta_feito_nao_mostra_pendencias(conexao, bd):
    organizacao.criar_tribo(conexao, bd, "Tribo B", "G", "2026-01")
    portfolio.criar_iniciativa(conexao, bd, "I-01", "Alfa")

    pendencias = _pendencias(conexao, bd)

    assert _estados(conexao, bd)["organizacao"] == "pendente"
    assert pendencias["organizacao"] == ()
    assert pendencias["demandas"] == ()


def test_pendencia_nao_muda_pronto_nem_bloqueio(conexao, bd):
    cargo = cadastrar_ate_pessoa(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")
    portfolio.criar_iniciativa(conexao, bd, "I-02", "Beta")  # sem demanda
    empresa = cadastros.criar_empresa(conexao, bd, "Consultoria", "consultoria")
    cadastros.criar_cargo(conexao, bd, empresa, "Dev", "N8")  # sem tarifa

    situacao = onboarding.situacao(conexao, bd)

    assert situacao.pronto is True
    assert situacao.feitos == 8
    assert _pendencias(conexao, bd)["demandas"] == ("I-02 Beta",)
    assert _pendencias(conexao, bd)["tarifas"] == ("Dev (Consultoria)",)


def test_bd_completo_nao_tem_pendencias(conexao, bd):
    cargo = cadastrar_ate_pessoa(conexao, bd)
    cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")

    assert all(p == () for p in _pendencias(conexao, bd).values())


def test_pendencias_sao_isoladas_por_bd(conexao, bd):
    outro = acesso.criar_bd(conexao, "Outro", "OU")
    cadastrar_ate_pessoa(conexao, outro)
    portfolio.criar_iniciativa(conexao, outro, "I-09", "Sem demanda")
    portfolio.criar_iniciativa(conexao, bd, "I-01", "Alfa")

    assert _pendencias(conexao, outro)["demandas"] == ("I-09 Sem demanda",)
    assert _pendencias(conexao, bd)["demandas"] == ()
