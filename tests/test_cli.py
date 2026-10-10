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


def test_comando_planejado_responde_nao_implementado(capsys):
    codigo = cli.main(["semear"])

    assert codigo == 2
    assert "ainda não implementado" in capsys.readouterr().err


def test_sem_comando_ou_comando_desconhecido_lista_os_comandos(capsys):
    assert cli.main([]) == 2
    assert cli.main(["xpto"]) == 2
    saida = capsys.readouterr().err
    assert "servir" in saida and "criar-admin" in saida
