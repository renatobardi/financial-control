"""Editar a tarifa vigente de um cargo no lugar (pendência do lote 5 da #44)."""

from financeiro.store import acesso, cadastros
from tests.web.ajuda import csrf_de, entrar, semear
from tests.web.test_cargas import _cadastros


def _preparar(ambiente, papel="Admin"):
    _, ids = semear(ambiente, bds=(("O1", papel),))
    bd = ids["O1"]
    _cadastros(ambiente, bd)
    cargo = cadastros.listar_cargos(ambiente.conexao, bd)[0].id
    cadastros.definir_tarifa(ambiente.conexao, bd, cargo, 19300, "2026-01")
    entrar(ambiente)
    return bd, cargo, csrf_de(ambiente.cliente.get("/configuracoes").text)


def _corrigir(ambiente, csrf, **dados):
    return ambiente.cliente.post("/cadastros/cargos/tarifa_editar", data={"csrf": csrf, **dados})


def test_corrige_o_valor_da_vigente_sem_criar_outra_vigencia(ambiente):
    bd, cargo, csrf = _preparar(ambiente)
    c = ambiente.conexao

    resposta = _corrigir(ambiente, csrf, cargo_id=str(cargo), valor="210,50")

    assert resposta.status_code == 200
    tarifas = cadastros.tarifas_do_cargo(c, bd, cargo)
    assert [(t.liquida_centavos, t.inicio, t.fim) for t in tarifas] == [(21050, "2026-01", None)]


def test_corrige_so_a_vigente_e_mantem_as_anteriores(ambiente):
    bd, cargo, csrf = _preparar(ambiente)
    c = ambiente.conexao
    cadastros.definir_tarifa(c, bd, cargo, 25000, "2026-07")

    _corrigir(ambiente, csrf, cargo_id=str(cargo), valor="260,00")

    antiga, atual = cadastros.tarifas_do_cargo(c, bd, cargo)
    assert (antiga.liquida_centavos, antiga.fim) == (19300, "2026-06")
    assert (atual.liquida_centavos, atual.fim) == (26000, None)


def test_valor_invalido_e_cargo_sem_tarifa_sao_recusados(ambiente):
    bd, cargo, csrf = _preparar(ambiente)
    c = ambiente.conexao
    outra = cadastros.listar_empresas(c, bd)[0].id
    sem_tarifa = cadastros.criar_cargo(c, bd, outra, "Pleno", "N8")

    ruim = _corrigir(ambiente, csrf, cargo_id=str(cargo), valor="abc")
    vazio = _corrigir(ambiente, csrf, cargo_id=str(sem_tarifa), valor="100,00")

    assert ruim.status_code == 400
    assert vazio.status_code == 409
    assert cadastros.tarifas_do_cargo(c, bd, cargo)[0].liquida_centavos == 19300


def test_cargo_de_outro_bd_nao_muda(ambiente):
    bd, cargo, csrf = _preparar(ambiente)
    c = ambiente.conexao
    outro = acesso.criar_bd(c, "Outro", "OT")
    empresa = cadastros.criar_empresa(c, outro, "NTT", "consultoria")
    alheio = cadastros.criar_cargo(c, outro, empresa, "Dev", "N8")
    cadastros.definir_tarifa(c, outro, alheio, 10000, "2026-01")

    resposta = _corrigir(ambiente, csrf, cargo_id=str(alheio), valor="999,00")

    assert resposta.status_code == 409
    assert cadastros.tarifas_do_cargo(c, outro, alheio)[0].liquida_centavos == 10000


def test_leitor_nao_corrige_e_a_aba_oferece_o_formulario_ao_editor(ambiente):
    bd, cargo, csrf = _preparar(ambiente, papel="Leitor")

    recusa = _corrigir(ambiente, csrf, cargo_id=str(cargo), valor="1,00")

    assert recusa.status_code == 403
    assert cadastros.tarifas_do_cargo(ambiente.conexao, bd, cargo)[0].liquida_centavos == 19300


def test_a_aba_de_cargos_tem_o_formulario_de_corrigir_a_tarifa(ambiente):
    _preparar(ambiente)

    lista = ambiente.cliente.get("/cadastros/cargos/lista").text

    assert 'action="/cadastros/cargos/tarifa_editar"' in lista
