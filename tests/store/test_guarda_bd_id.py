"""Guarda do ADR-0002: toda função de `store/` que toca tabela de dado recebe `bd_id`."""

import importlib
import importlib.util
import inspect
import pkgutil
import re
import types
from pathlib import Path

from financeiro import store

# Tabelas que não são de dado de um BD: controle do esquema e usuários (ADR-0002).
SEM_BD_ID = {
    "versao_esquema",
    "bd",
    "usuario",
    "sessao",
    "tentativa_login",
    "segundo_fator",
    "codigo_recuperacao",
    "sqlite_sequence",
}
# Funções que cruzam BDs de propósito (@entre_bds). Acrescentar uma exige decisão revisada aqui.
ENTRE_BDS_PERMITIDAS = {
    "financeiro.store.acesso.bds_do_usuario",
    "financeiro.store.acesso.bds_sem_vinculo",
    "financeiro.store.acesso.pedidos_do_usuario",
    # Excluir a conta e saber onde o usuário é o único Admin atuam sobre o usuário, em todos os BDs.
    "financeiro.store.acesso.excluir_conta",
    "financeiro.store.acesso.bds_em_que_e_ultimo_admin",
}
PASTA_MIGRACOES = Path(store.__file__).parent / "migracoes"


def tabelas_de_dado() -> set[str]:
    """Tabelas do esquema real, menos as que o ADR-0002 dispensa de `bd_id`."""
    conexao = store.abrir(":memory:")
    if PASTA_MIGRACOES.exists():
        store.migrar(conexao, PASTA_MIGRACOES)
    nomes = {r[0] for r in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return nomes - SEM_BD_ID


def modulos_do_store() -> list[types.ModuleType]:
    return [
        importlib.import_module(f"{store.__name__}.{info.name}")
        for info in pkgutil.iter_modules(store.__path__)
    ]


def violacoes(modulos: list[types.ModuleType], tabelas: set[str]) -> list[str]:
    """Funções públicas que citam uma tabela de dado sem ter `bd_id` na assinatura."""
    achadas = []
    for modulo in modulos:
        for nome, funcao in inspect.getmembers(modulo, inspect.isfunction):
            if nome.startswith("_") or funcao.__module__ != modulo.__name__:
                continue
            fonte = inspect.getsource(funcao)
            cita = any(
                re.search(rf"\b(?:FROM|JOIN|INTO|UPDATE)\s+{re.escape(t)}\b", fonte, re.I)
                for t in tabelas
            )
            if getattr(funcao, "__entre_bds__", False):
                continue
            if cita and "bd_id" not in inspect.signature(funcao).parameters:
                achadas.append(f"{modulo.__name__}.{nome}")
    return achadas


def test_funcoes_do_store_que_tocam_tabela_de_dado_recebem_bd_id():
    assert violacoes(modulos_do_store(), tabelas_de_dado()) == []


def test_toda_tabela_de_dado_tem_coluna_bd_id():
    conexao = store.abrir(":memory:")
    store.migrar(conexao, PASTA_MIGRACOES)
    sem_coluna = [
        tabela
        for tabela in sorted(tabelas_de_dado())
        if "bd_id" not in {c[1] for c in conexao.execute(f"PRAGMA table_info({tabela})")}
    ]

    assert sem_coluna == []


def test_funcoes_entre_bds_sao_so_as_permitidas():
    marcadas = {
        f"{modulo.__name__}.{nome}"
        for modulo in modulos_do_store()
        for nome, funcao in inspect.getmembers(modulo, inspect.isfunction)
        if getattr(funcao, "__entre_bds__", False) and funcao.__module__ == modulo.__name__
    }

    assert marcadas == ENTRE_BDS_PERMITIDAS


def test_guarda_pega_funcao_sem_bd_id(tmp_path):
    fonte = (
        "def listar_pessoas(conexao):\n"
        "    return conexao.execute('SELECT * FROM pessoa').fetchall()\n"
        "\n"
        "def listar_pessoas_do_bd(conexao, bd_id):\n"
        "    return conexao.execute('SELECT * FROM pessoa WHERE bd_id = ?', (bd_id,)).fetchall()\n"
    )
    (tmp_path / "falso.py").write_text(fonte)
    spec = importlib.util.spec_from_file_location("falso", tmp_path / "falso.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    assert violacoes([modulo], {"pessoa"}) == ["falso.listar_pessoas"]
