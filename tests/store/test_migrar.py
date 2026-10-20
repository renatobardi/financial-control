import psycopg
import pytest

from financeiro import store


def _pasta(tmp_path, **arquivos):
    pasta = tmp_path / "migracoes"
    pasta.mkdir()
    for nome, sql in arquivos.items():
        (pasta / f"{nome}.sql").write_text(sql)
    return pasta


def _tabelas(conexao):
    linhas = conexao.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
    )
    return {linha[0] for linha in linhas}


def test_banco_vazio_chega_a_ultima_versao(tmp_path, conexao_vazia):
    pasta = _pasta(
        tmp_path,
        **{
            "0001_pessoa": "CREATE TABLE pessoa (id BIGINT PRIMARY KEY, bd_id TEXT NOT NULL);",
            "0002_tema": "CREATE TABLE tema (id BIGINT PRIMARY KEY, bd_id TEXT NOT NULL);",
        },
    )

    versao = store.migrar(conexao_vazia, pasta)

    assert versao == 2
    assert {"pessoa", "tema", "versao_esquema"} <= _tabelas(conexao_vazia)


def test_rodar_duas_vezes_nao_reaplica(tmp_path, conexao_vazia):
    pasta = _pasta(tmp_path, **{"0001_pessoa": "CREATE TABLE pessoa (id BIGINT PRIMARY KEY);"})

    store.migrar(conexao_vazia, pasta)
    versao = store.migrar(conexao_vazia, pasta)

    assert versao == 1
    assert conexao_vazia.execute("SELECT COUNT(*) FROM versao_esquema").fetchone()[0] == 1


def test_numero_fora_de_sequencia_e_recusado(tmp_path, conexao_vazia):
    pasta = _pasta(
        tmp_path,
        **{
            "0001_pessoa": "CREATE TABLE pessoa (id BIGINT PRIMARY KEY);",
            "0003_tema": "CREATE TABLE tema (id BIGINT PRIMARY KEY);",
        },
    )

    with pytest.raises(store.MigracaoInvalida):
        store.migrar(conexao_vazia, pasta)

    assert "pessoa" not in _tabelas(conexao_vazia)


def test_migracao_com_defeito_deixa_o_banco_como_estava(tmp_path, conexao_vazia, schema_de_teste):
    pasta = _pasta(tmp_path, **{"0001_pessoa": "CREATE TABLE pessoa (id BIGINT PRIMARY KEY);"})
    store.migrar(conexao_vazia, pasta)
    conexao_vazia.execute("INSERT INTO pessoa (id) VALUES (1)")
    conexao_vazia.commit()
    (pasta / "0002_tema.sql").write_text(
        "CREATE TABLE tema (id BIGINT PRIMARY KEY);\nINSERT INTO nao_existe VALUES (1);"
    )

    with pytest.raises(psycopg.errors.UndefinedTable):
        store.migrar(conexao_vazia, pasta)

    assert "tema" not in _tabelas(conexao_vazia)  # o DDL é transacional: nada ficou pela metade
    assert conexao_vazia.execute("SELECT MAX(versao) FROM versao_esquema").fetchone()[0] == 1
    assert conexao_vazia.execute("SELECT id FROM pessoa").fetchall() == [(1,)]


def test_versao_atual_acompanha_as_migracoes(tmp_path, conexao_vazia):
    pasta = _pasta(tmp_path, **{"0001_pessoa": "CREATE TABLE pessoa (id BIGINT PRIMARY KEY);"})
    assert store.versao_atual(conexao_vazia) == 0

    store.migrar(conexao_vazia, pasta)

    assert store.versao_atual(conexao_vazia) == 1


def test_duas_instancias_nao_migram_ao_mesmo_tempo(tmp_path, conexao_vazia, schema_de_teste):
    from tests.banco import URL_TESTE

    pasta = _pasta(tmp_path, **{"0001_pessoa": "CREATE TABLE pessoa (id BIGINT PRIMARY KEY);"})
    outra = store.abrir(URL_TESTE, schema=schema_de_teste)
    try:
        store.migrar(conexao_vazia, pasta)
        assert store.migrar(outra, pasta) == 1  # a segunda só confere a versão, não recria
    finally:
        outra.close()
