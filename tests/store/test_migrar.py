import pytest

from financeiro import store


def _pasta(tmp_path, **arquivos):
    pasta = tmp_path / "migracoes"
    pasta.mkdir()
    for nome, sql in arquivos.items():
        (pasta / f"{nome}.sql").write_text(sql)
    return pasta


def test_banco_vazio_chega_a_ultima_versao(tmp_path):
    pasta = _pasta(
        tmp_path,
        **{
            "0001_pessoa": "CREATE TABLE pessoa (id INTEGER PRIMARY KEY, bd_id TEXT NOT NULL);",
            "0002_tema": "CREATE TABLE tema (id INTEGER PRIMARY KEY, bd_id TEXT NOT NULL);",
        },
    )
    conexao = store.abrir(tmp_path / "financeiro.db")

    versao = store.migrar(conexao, pasta)

    assert versao == 2
    tabelas = {r[0] for r in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"pessoa", "tema", "versao_esquema"} <= tabelas


def test_rodar_duas_vezes_nao_reaplica(tmp_path):
    pasta = _pasta(tmp_path, **{"0001_pessoa": "CREATE TABLE pessoa (id INTEGER PRIMARY KEY);"})
    conexao = store.abrir(tmp_path / "financeiro.db")

    store.migrar(conexao, pasta)
    versao = store.migrar(conexao, pasta)

    assert versao == 1
    assert conexao.execute("SELECT COUNT(*) FROM versao_esquema").fetchone()[0] == 1


def test_numero_fora_de_sequencia_e_recusado(tmp_path):
    pasta = _pasta(
        tmp_path,
        **{
            "0001_pessoa": "CREATE TABLE pessoa (id INTEGER PRIMARY KEY);",
            "0003_tema": "CREATE TABLE tema (id INTEGER PRIMARY KEY);",
        },
    )
    conexao = store.abrir(tmp_path / "financeiro.db")

    with pytest.raises(store.MigracaoInvalida):
        store.migrar(conexao, pasta)

    tabelas = {r[0] for r in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "pessoa" not in tabelas
