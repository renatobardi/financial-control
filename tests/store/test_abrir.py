from financeiro import store


def test_abrir_usa_wal_e_chaves_estrangeiras(tmp_path):
    conexao = store.abrir(tmp_path / "financeiro.db")

    assert conexao.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1
