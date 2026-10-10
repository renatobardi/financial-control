from financeiro import store


def test_abrir_usa_wal_e_chaves_estrangeiras(tmp_path):
    conexao = store.abrir(tmp_path / "financeiro.db")

    assert conexao.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conexao.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_conexao_pode_ser_usada_por_outra_thread(tmp_path):
    import threading

    conexao = store.abrir(tmp_path / "financeiro.db")
    resultado = []

    def usar():
        resultado.append(conexao.execute("SELECT 1").fetchone()[0])

    fio = threading.Thread(target=usar)
    fio.start()
    fio.join()

    assert resultado == [1]
