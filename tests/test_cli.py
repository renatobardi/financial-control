from fastapi import FastAPI

from financeiro import cli


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


# ---- comandos de implantação: criar-admin, semear e backup ----


def _ambiente(tmp_path, **extra):
    return {"FINANCEIRO_BD": str(tmp_path / "f.db"), **extra}


def _consultar(tmp_path, sql, *params):
    from financeiro import store

    conexao = store.abrir(tmp_path / "f.db")
    try:
        return conexao.execute(sql, params).fetchall()
    finally:
        conexao.close()


def test_criar_admin_cria_bd_usuario_e_papel_com_senha_do_ambiente(tmp_path, capsys):
    ambiente = _ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")

    codigo = cli.main(
        ["criar-admin", "--email", "renato@empresa.com", "--nome", "Renato", "--bd", "BD Mobility"],
        ambiente=ambiente,
    )

    assert codigo == 0
    assert _consultar(tmp_path, "SELECT nome FROM bd") == [("BD Mobility",)]
    papel = _consultar(
        tmp_path,
        "SELECT m.papel FROM membro m JOIN usuario u ON u.id = m.usuario_id WHERE u.email = ?",
        "renato@empresa.com",
    )
    assert papel == [("Admin",)]
    hash_guardado = _consultar(tmp_path, "SELECT senha_hash FROM usuario")[0][0]
    assert hash_guardado.startswith("scrypt$") and "uma-senha-forte-1" not in hash_guardado
    assert "uma-senha-forte-1" not in capsys.readouterr().out


def test_criar_admin_nao_imprime_nem_aceita_senha_curta_ou_ausente(tmp_path, capsys):
    argumentos = ["criar-admin", "--email", "a@empresa.com", "--nome", "A", "--bd", "BD"]

    sem_senha = cli.main(argumentos, ambiente=_ambiente(tmp_path))
    curta = cli.main(argumentos, ambiente=_ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="curta"))

    assert (sem_senha, curta) == (2, 2)
    erro = capsys.readouterr().err
    assert "FINANCEIRO_ADMIN_SENHA" in erro and "8 caracteres" in erro
    assert _consultar(tmp_path, "SELECT COUNT(*) FROM usuario") == [(0,)]


def test_criar_admin_repetido_nao_duplica_nem_troca_a_senha(tmp_path):
    argumentos = ["criar-admin", "--email", "a@empresa.com", "--nome", "A", "--bd", "BD"]
    cli.main(argumentos, ambiente=_ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="primeira-senha-1"))
    antes = _consultar(tmp_path, "SELECT senha_hash FROM usuario")

    codigo = cli.main(
        argumentos, ambiente=_ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="outra-senha-qualquer")
    )

    assert codigo == 0
    assert _consultar(tmp_path, "SELECT senha_hash FROM usuario") == antes
    assert _consultar(tmp_path, "SELECT COUNT(*) FROM usuario") == [(1,)]
    assert _consultar(tmp_path, "SELECT COUNT(*) FROM membro") == [(1,)]


def test_criar_admin_exige_email_nome_e_bd(tmp_path, capsys):
    ambiente = _ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")

    assert cli.main(["criar-admin", "--email", "a@empresa.com"], ambiente=ambiente) == 2
    assert (
        cli.main(
            ["criar-admin", "--email", "sem-arroba", "--nome", "A", "--bd", "BD"], ambiente=ambiente
        )
        == 2
    )


def test_semear_carrega_dados_de_exemplo_e_recusa_banco_com_usuario(tmp_path, capsys):
    ambiente = _ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")

    primeira = cli.main(["semear"], ambiente=ambiente)
    segunda = cli.main(["semear"], ambiente=ambiente)

    assert primeira == 0 and segunda == 1
    assert "não está vazio" in capsys.readouterr().err
    assert _consultar(tmp_path, "SELECT COUNT(*) FROM pessoa")[0][0] >= 1
    assert _consultar(tmp_path, "SELECT COUNT(*) FROM iniciativa")[0][0] >= 1


def test_backup_gera_copia_consistente_e_nao_sobrescreve(tmp_path, capsys):
    ambiente = _ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")
    cli.main(["semear"], ambiente=ambiente)
    destino = tmp_path / "copia.db"

    primeiro = cli.main(["backup", "--destino", str(destino)], ambiente=ambiente)
    segundo = cli.main(["backup", "--destino", str(destino)], ambiente=ambiente)

    assert primeiro == 0 and segundo == 1
    from financeiro import store

    copia = store.abrir(destino)
    assert copia.execute("SELECT COUNT(*) FROM pessoa").fetchone()[0] >= 1
    assert copia.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert "já existe" in capsys.readouterr().err


def test_desativar_2fa_tira_a_verificacao_de_quem_perdeu_o_celular(tmp_path, capsys):
    from financeiro import doisfatores, store
    from financeiro.store import acesso

    ambiente = _ambiente(tmp_path, FINANCEIRO_ADMIN_SENHA="uma-senha-forte-1")
    cli.main(
        ["criar-admin", "--email", "a@empresa.com", "--nome", "A", "--bd", "BD"], ambiente=ambiente
    )
    conexao = store.abrir(tmp_path / "f.db")
    usuario = acesso.achar_usuario_por_email(conexao, "a@empresa.com")
    doisfatores.iniciar_ativacao(conexao, usuario.id)
    conexao.execute("UPDATE segundo_fator SET ativo = 1")
    conexao.commit()
    conexao.close()

    codigo = cli.main(["desativar-2fa", "--email", "a@empresa.com"], ambiente=ambiente)

    assert codigo == 0
    assert _consultar(tmp_path, "SELECT COUNT(*) FROM segundo_fator") == [(0,)]
    assert "a@empresa.com" in capsys.readouterr().out


def test_desativar_2fa_de_email_desconhecido_falha(tmp_path, capsys):
    ambiente = _ambiente(tmp_path)

    codigo = cli.main(["desativar-2fa", "--email", "ninguem@empresa.com"], ambiente=ambiente)

    assert codigo == 1
    assert "ninguem@empresa.com" in capsys.readouterr().err
