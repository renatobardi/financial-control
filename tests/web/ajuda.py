import re

from financeiro import senha
from financeiro.store import acesso


def semear(
    ambiente, email="ana@empresa.com", nome="Ana", bds=(("O1", "Admin"),), senha_="correta-123"
):
    """Cria o usuário e os BDs informados (nome, papel). Devolve (usuario_id, {nome: bd_id})."""
    c = ambiente.conexao
    usuario = acesso.achar_usuario_por_email(c, email)
    usuario_id = (
        usuario.id if usuario else acesso.criar_usuario(c, email, nome, senha.gerar_hash(senha_))
    )
    ids = {}
    for nome_bd, papel in bds:
        existente = c.execute("SELECT id FROM bd WHERE nome = ?", (nome_bd,)).fetchone()
        bd_id = existente[0] if existente else acesso.criar_bd(c, nome_bd, nome_bd[:2].upper())
        acesso.adicionar_membro(c, bd_id, usuario_id, papel)
        ids[nome_bd] = bd_id
    return usuario_id, ids


def entrar(ambiente, email="ana@empresa.com", senha_="correta-123"):
    return ambiente.cliente.post("/login", data={"email": email, "senha": senha_})


def csrf_de(html: str) -> str:
    achado = re.search(r'name="csrf" value="([^"]+)"', html)
    assert achado, "página sem campo csrf"
    return achado.group(1)
