import importlib.util
import sqlite3
from pathlib import Path

import pytest

from financeiro.store import acesso, organizacao

_CAMINHO = Path(__file__).resolve().parents[2] / "scripts" / "sqlite_para_postgres.py"
_spec = importlib.util.spec_from_file_location("sqlite_para_postgres", _CAMINHO)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

GRANDE = 3_000_000_000  # acima de 2^31


@pytest.fixture
def origem():
    """SQLite com o jeito do banco antigo: ids do rowid, pai com id MAIOR que o filho, dinheiro grande."""
    c = sqlite3.connect(":memory:")
    c.executescript(
        f"""
        PRAGMA foreign_keys = OFF;
        CREATE TABLE bd (id INTEGER PRIMARY KEY, nome TEXT NOT NULL UNIQUE, sigla TEXT NOT NULL,
                         gestor TEXT NOT NULL DEFAULT '', onboarding_aberto INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE org (id INTEGER PRIMARY KEY, bd_id INTEGER NOT NULL REFERENCES bd (id),
                          tipo TEXT NOT NULL, nome TEXT NOT NULL, pai_id INTEGER,
                          gestor TEXT NOT NULL DEFAULT '', vigencia_ini TEXT NOT NULL,
                          vigencia_fim TEXT, codigo TEXT, UNIQUE (bd_id, id),
                          FOREIGN KEY (bd_id, pai_id) REFERENCES org (bd_id, id));
        CREATE TABLE empresa (id INTEGER PRIMARY KEY, bd_id INTEGER NOT NULL REFERENCES bd (id),
                              nome TEXT NOT NULL, tipo TEXT NOT NULL, codigo TEXT);
        CREATE TABLE cargo (id INTEGER PRIMARY KEY, bd_id INTEGER NOT NULL REFERENCES bd (id),
                            empresa_id INTEGER NOT NULL REFERENCES empresa (id), nome TEXT NOT NULL,
                            nivel TEXT NOT NULL, codigo TEXT);
        CREATE TABLE tarifa (id INTEGER PRIMARY KEY, bd_id INTEGER NOT NULL REFERENCES bd (id),
                             cargo_id INTEGER NOT NULL REFERENCES cargo (id),
                             liquida_centavos INTEGER NOT NULL, vigencia_ini TEXT NOT NULL,
                             vigencia_fim TEXT);
        CREATE TABLE sessao (token_hash TEXT PRIMARY KEY, usuario_id INTEGER);
        INSERT INTO bd VALUES (1, 'BD Um', 'BU', 'G', 1), (7, 'BD Dois', 'BD', '', 0);
        INSERT INTO org (id, bd_id, tipo, nome, pai_id, vigencia_ini)
            VALUES (5, 1, 'Squad', 'Squad', 9, '2025-01'), (9, 1, 'Tribo', 'Tribo', NULL, '2025-01');
        INSERT INTO empresa VALUES (3, 1, 'Própria', 'propria', NULL);
        INSERT INTO cargo VALUES (4, 1, 3, 'Dev', 'N8', NULL);
        INSERT INTO tarifa VALUES (2, 1, 4, {GRANDE}, '2026-01', NULL);
        INSERT INTO sessao VALUES ('abc', 1);
        """
    )
    yield c
    c.close()


def test_copia_na_ordem_das_chaves_e_confere_linha_a_linha(origem, conexao):
    copiadas = script.copiar(origem, conexao)

    assert copiadas == {"bd": 2, "cargo": 1, "empresa": 1, "org": 2, "tarifa": 1}
    assert script.conferir(origem, conexao) == []


def test_pai_com_id_maior_que_o_filho_entra_antes(origem, conexao):
    script.copiar(origem, conexao)

    pais = dict(conexao.execute("SELECT id, pai_id FROM org"))
    assert pais == {5: 9, 9: None}


def test_valor_acima_de_2_elevado_a_31_sobrevive(origem, conexao):
    script.copiar(origem, conexao)

    assert conexao.execute("SELECT liquida_centavos FROM tarifa").fetchone()[0] == GRANDE


def test_sessao_nao_e_copiada(origem, conexao):
    script.copiar(origem, conexao)

    assert conexao.execute("SELECT COUNT(*) FROM sessao").fetchone()[0] == 0


def test_depois_da_copia_o_proximo_id_passa_do_maior_copiado(origem, conexao):
    script.copiar(origem, conexao)
    script.acertar_sequencias(conexao)

    novo_bd = acesso.criar_bd(conexao, "BD Novo", "BN")
    nova_org = organizacao.criar_org(conexao, novo_bd, "Tribo", "T", None, "G", "2026-01")

    assert novo_bd == 8  # o maior copiado era 7
    assert nova_org == 10  # o maior copiado era 9


def test_conferir_acusa_linha_alterada(origem, conexao):
    script.copiar(origem, conexao)
    conexao.execute("UPDATE tarifa SET liquida_centavos = liquida_centavos + 1")

    problemas = script.conferir(origem, conexao)

    assert len(problemas) == 1 and problemas[0].startswith("tarifa:")
