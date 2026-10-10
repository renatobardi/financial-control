"""Implantação: primeiro Admin e dados de exemplo. Sem SQL: usa o store."""

from financeiro import senha as senhas
from financeiro.store import Conexao, acesso, cadastros, organizacao, pessoas, portfolio

SENHA_MINIMA = 8


class AdministracaoInvalida(Exception):
    """A operação foi recusada; a mensagem vai para o terminal."""


def _validar(email: str, nome: str, bd_nome: str, senha: str | None) -> None:
    if "@" not in email or not nome.strip() or not bd_nome.strip():
        raise AdministracaoInvalida("Informe e-mail válido, nome e BD.")
    if not senha or len(senha) < SENHA_MINIMA:
        raise AdministracaoInvalida(
            f"Defina FINANCEIRO_ADMIN_SENHA com pelo menos {SENHA_MINIMA} caracteres."
        )


def criar_admin(conexao: Conexao, email: str, nome: str, bd_nome: str, senha: str | None) -> str:
    """Cria o BD (se faltar), o usuário e o papel Admin. Repetir não muda a senha.

    Devolve `criado` ou `existente`.
    """
    _validar(email, nome, bd_nome, senha)
    bd_id = acesso.achar_bd_por_nome(conexao, bd_nome.strip())
    if bd_id is None:
        bd_id = acesso.criar_bd(conexao, bd_nome.strip(), bd_nome.strip()[:2].upper())
    usuario = acesso.achar_usuario_por_email(conexao, email.strip())
    situacao = "existente"
    if usuario is None:
        usuario_id = acesso.criar_usuario(
            conexao, email.strip(), nome.strip(), senhas.gerar_hash(senha)
        )
        situacao = "criado"
    else:
        usuario_id = usuario.id
        if usuario.senha_hash is None:  # conta pendente de convite: ativa com a senha dada
            acesso.definir_senha(conexao, usuario_id, senhas.gerar_hash(senha))
            situacao = "criado"
    if acesso.papel_do(conexao, bd_id, usuario_id) != "Admin":
        acesso.convidar(conexao, bd_id, email.strip(), "Admin")
    return situacao


def semear(conexao: Conexao, senha: str | None) -> None:
    """Dados de exemplo para desenvolvimento. Recusa banco que já tem usuário."""
    if acesso.contar_usuarios(conexao) > 0:
        raise AdministracaoInvalida("O banco não está vazio: a semente só roda em banco novo.")
    _validar("demo@exemplo.com", "Demo", "BD Exemplo", senha)
    bd = acesso.criar_bd(conexao, "BD Exemplo", "BE")
    demo = acesso.criar_usuario(conexao, "demo@exemplo.com", "Demo", senhas.gerar_hash(senha))
    acesso.adicionar_membro(conexao, bd, demo, "Admin")
    tribo = organizacao.criar_org(conexao, bd, "Tribo", "Tribo Exemplo", None, "Gestor", "2026-01")
    squad = organizacao.criar_org(conexao, bd, "Squad", "Squad Exemplo", tribo, "Gestor", "2026-01")
    conexao.execute("UPDATE org SET codigo = 'o1' WHERE id = ?", (squad,))
    empresa = cadastros.criar_empresa(conexao, bd, "Própria", "propria")
    conexao.execute("UPDATE empresa SET codigo = 'PROP' WHERE id = ?", (empresa,))
    cargo = cadastros.criar_cargo(conexao, bd, empresa, "Pleno", "N8")
    conexao.execute("UPDATE cargo SET codigo = 'c1' WHERE id = ?", (cargo,))
    cadastros.definir_tarifa(conexao, bd, cargo, 12000, "2026-01")
    cadastros.definir_markup(conexao, bd, 1050, "2026-01")
    agrup = portfolio.criar_agrupamento(conexao, bd, "RTB")
    ini = portfolio.criar_iniciativa(conexao, bd, "I-01", "Iniciativa Exemplo")
    dem = portfolio.criar_demanda(conexao, bd, "D-01", ini, "Demanda Exemplo", "OPEX", squad)
    tema = portfolio.criar_tema(conexao, bd, "T-01", dem, "Tema Exemplo", agrup)
    pessoas.criar_pessoa(
        conexao, bd, "F0001", "Pessoa Exemplo", squad, cargo, tema, "2026-01", None
    )
