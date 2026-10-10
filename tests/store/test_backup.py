from financeiro import store


def test_backup_traz_o_que_ainda_esta_so_no_wal(tmp_path):
    conexao = store.abrir(tmp_path / "financeiro.db")
    conexao.execute("PRAGMA wal_autocheckpoint = 0")
    conexao.execute("CREATE TABLE pessoa (id INTEGER PRIMARY KEY, nome TEXT)")
    conexao.execute("INSERT INTO pessoa (nome) VALUES ('Ana')")
    conexao.commit()

    destino = tmp_path / "copia.db"
    store.backup(conexao, destino)

    copia = store.abrir(destino)
    assert copia.execute("SELECT nome FROM pessoa").fetchall() == [("Ana",)]
