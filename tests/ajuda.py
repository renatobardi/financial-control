"""Cadastros de teste compartilhados entre os testes de regra e os de rota."""

from financeiro import organizacao
from financeiro.store import Conexao, cadastros, pessoas, portfolio


def cadastrar_ate_pessoa(conexao: Conexao, bd: int) -> int:
    """BD com organização, portfólio, cargo e uma pessoa; sem tarifa nem markup. Devolve o cargo."""
    tribo = organizacao.criar_tribo(conexao, bd, "Tribo", "G", "2026-01")
    squad = organizacao.criar_squad(conexao, bd, "Squad", tribo, "G", "2026-01")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Iniciativa")
    dem = portfolio.criar_demanda(conexao, bd, "D-01", ini, "Demanda", "OPEX", squad)
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    tema = portfolio.criar_tema(conexao, bd, "T-01", dem, "Tema", agrup)
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Pleno", "N8")
    pessoas.criar_pessoa(conexao, bd, "F1", "Ana", squad, cargo, tema, "2026-01", None)
    return cargo
