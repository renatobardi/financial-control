from fastapi import FastAPI

from financeiro import cli
from tests.banco import URL_TESTE, url_do_schema


def _servidor_falso():
    chamadas = []

    def servidor(app, *, host, port):
        chamadas.append((app, host, port))

    return servidor, chamadas


def test_servir_sobe_a_app_no_host_e_porta_padrao(capsys):
    servidor, chamadas = _servidor_falso()

    codigo = cli.main(["servir"], servidor=servidor)

    assert codigo == 0
    app, host, porta = chamadas[0]
    assert isinstance(app, FastAPI)
    assert (host, porta) == ("127.0.0.1", 8000)


def test_servir_aceita_porta(capsys):
    servidor, chamadas = _servidor_falso()

    cli.main(["servir", "--porta", "9000"], servidor=servidor)

    assert chamadas[0][2] == 9000


def test_sem_comando_ou_comando_desconhecido_lista_os_comandos(capsys):
    assert cli.main([]) == 2
    assert cli.main(["xpto"]) == 2
    saida = capsys.readouterr().err
    assert "servir" in saida and "criar-admin" in saida


def test_servir_aceita_host():
    servidor, chamadas = _servidor_falso()

    cli.main(["servir", "--host", "0.0.0.0"], servidor=servidor)

    assert chamadas[0][1] == "0.0.0.0"


# ---- comandos de implantação: criar-admin e semear ----


def _ambiente(schema, **extra):
    return {"FINANCEIRO_DATABASE_URL": url_do_schema(schema), **extra}


def _consultar(schema, sql, *params):
    from financeiro import store

    conexao = store.abrir(URL_TESTE, schema=schema)
    try:
        return conexao.execute(sql, params).fetchall()
    finally:
        conexao.close()


def test_criar_admin_cria_bd_usuario_e_papel_com_senha_do_ambiente(schema_de_teste, capsys):
    ambiente = _ambiente(schema_de_teste, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")

    codigo = cli.main(
        ["criar-admin", "--email", "renato@empresa.com", "--nome", "Renato", "--bd", "BD Mobility"],
        ambiente=ambiente,
    )

    assert codigo == 0
    assert _consultar(schema_de_teste, "SELECT nome FROM bd") == [("BD Mobility",)]
    papel = _consultar(
        schema_de_teste,
        "SELECT m.papel FROM membro m JOIN usuario u ON u.id = m.usuario_id WHERE u.email = %s",
        "renato@empresa.com",
    )
    assert papel == [("Admin",)]
    hash_guardado = _consultar(schema_de_teste, "SELECT senha_hash FROM usuario")[0][0]
    assert hash_guardado.startswith("scrypt$") and "uma-senha-forte-1" not in hash_guardado
    assert "uma-senha-forte-1" not in capsys.readouterr().out


def test_criar_admin_nao_imprime_nem_aceita_senha_curta_ou_ausente(schema_de_teste, capsys):
    argumentos = ["criar-admin", "--email", "a@empresa.com", "--nome", "A", "--bd", "BD"]

    sem_senha = cli.main(argumentos, ambiente=_ambiente(schema_de_teste))
    curta = cli.main(
        argumentos, ambiente=_ambiente(schema_de_teste, FINANCEIRO_ADMIN_SENHA="curta")
    )

    assert (sem_senha, curta) == (2, 2)
    erro = capsys.readouterr().err
    assert "FINANCEIRO_ADMIN_SENHA" in erro and "8 caracteres" in erro
    assert _consultar(schema_de_teste, "SELECT COUNT(*) FROM usuario") == [(0,)]


def test_criar_admin_repetido_nao_duplica_nem_troca_a_senha(schema_de_teste):
    argumentos = ["criar-admin", "--email", "a@empresa.com", "--nome", "A", "--bd", "BD"]
    cli.main(
        argumentos, ambiente=_ambiente(schema_de_teste, FINANCEIRO_ADMIN_SENHA="primeira-senha-1")
    )
    antes = _consultar(schema_de_teste, "SELECT senha_hash FROM usuario")

    codigo = cli.main(
        argumentos,
        ambiente=_ambiente(schema_de_teste, FINANCEIRO_ADMIN_SENHA="outra-senha-qualquer"),
    )

    assert codigo == 0
    assert _consultar(schema_de_teste, "SELECT senha_hash FROM usuario") == antes
    assert _consultar(schema_de_teste, "SELECT COUNT(*) FROM usuario") == [(1,)]
    assert _consultar(schema_de_teste, "SELECT COUNT(*) FROM membro") == [(1,)]


def test_criar_admin_exige_email_nome_e_bd(schema_de_teste, capsys):
    ambiente = _ambiente(schema_de_teste, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")

    assert cli.main(["criar-admin", "--email", "a@empresa.com"], ambiente=ambiente) == 2
    assert (
        cli.main(
            ["criar-admin", "--email", "sem-arroba", "--nome", "A", "--bd", "BD"], ambiente=ambiente
        )
        == 2
    )


def test_semear_carrega_dados_de_exemplo_e_recusa_banco_com_usuario(schema_de_teste, capsys):
    ambiente = _ambiente(schema_de_teste, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")

    primeira = cli.main(["semear"], ambiente=ambiente)
    segunda = cli.main(["semear"], ambiente=ambiente)

    assert primeira == 0 and segunda == 1
    assert "não está vazio" in capsys.readouterr().err
    assert _consultar(schema_de_teste, "SELECT COUNT(*) FROM pessoa")[0][0] >= 1
    assert _consultar(schema_de_teste, "SELECT COUNT(*) FROM iniciativa")[0][0] >= 1


def test_desativar_2fa_tira_a_verificacao_de_quem_perdeu_o_celular(schema_de_teste, capsys):
    from financeiro import doisfatores, store
    from financeiro.store import acesso

    ambiente = _ambiente(schema_de_teste, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")
    cli.main(
        ["criar-admin", "--email", "a@empresa.com", "--nome", "A", "--bd", "BD"], ambiente=ambiente
    )
    conexao = store.abrir(URL_TESTE, schema=schema_de_teste)
    usuario = acesso.achar_usuario_por_email(conexao, "a@empresa.com")
    doisfatores.iniciar_ativacao(conexao, usuario.id)
    conexao.execute("UPDATE segundo_fator SET ativo = 1")
    conexao.commit()
    conexao.close()

    codigo = cli.main(["desativar-2fa", "--email", "a@empresa.com"], ambiente=ambiente)

    assert codigo == 0
    assert _consultar(schema_de_teste, "SELECT COUNT(*) FROM segundo_fator") == [(0,)]
    assert "a@empresa.com" in capsys.readouterr().out


def test_desativar_2fa_de_email_desconhecido_falha(schema_de_teste, capsys):
    ambiente = _ambiente(schema_de_teste)

    codigo = cli.main(["desativar-2fa", "--email", "ninguem@empresa.com"], ambiente=ambiente)

    assert codigo == 1
    assert "ninguem@empresa.com" in capsys.readouterr().err
