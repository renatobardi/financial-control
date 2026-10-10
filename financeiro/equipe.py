"""Pessoas: quem está ativo, em qual unidade e cargo, e quanto custa no período."""

from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from financeiro import consumo, vigencia
from financeiro.store import Conexao, ErroDeIntegridade, organizacao, pessoas


class EquipeInvalida(Exception):
    """A operação recusada, com a mensagem que vai para a tela."""


class AtivosAno(NamedTuple):
    por_mes: list[int]
    distintos: int  # pessoas distintas no ano: NÃO é a soma dos meses


@dataclass(frozen=True)
class LinhaPessoa:
    id: int
    matricula: str
    nome: str
    unidade: str
    cargo: str
    empresa: str
    vinculo: str
    tema: str
    desligamento: str | None
    meses_ativos: int
    horas: int
    custo_centavos: int


def _ativa(p: pessoas.PessoaDetalhe, mes: str) -> bool:
    return p.admissao <= mes and (p.desligamento is None or p.desligamento >= mes)


def _meses(de: str, ate: str) -> list[str]:
    vigencia.validar_mes(de)
    vigencia.validar_mes(ate)
    meses, atual = [], de
    while atual <= ate:
        meses.append(atual)
        ano, mes = int(atual[:4]), int(atual[5:])
        atual = f"{ano + 1}-01" if mes == 12 else f"{ano}-{mes + 1:02d}"
    return meses


def ativos_por_ano(conexao: Conexao, bd_id: int, ano: int) -> AtivosAno:
    todos = pessoas.listar_detalhe(conexao, bd_id)
    meses = [f"{ano:04d}-{m:02d}" for m in range(1, 13)]
    por_mes = [sum(_ativa(p, mes) for p in todos) for mes in meses]
    distintos = sum(any(_ativa(p, mes) for mes in meses) for p in todos)
    return AtivosAno(por_mes, distintos)


def listar(
    conexao: Conexao,
    bd_id: int,
    de: str,
    ate: str,
    agora: datetime,
    unidade_id: int | None = None,
    busca: str = "",
) -> list[LinhaPessoa]:
    meses = _meses(de, ate)
    orgs = {o.id: o for o in organizacao.listar_orgs(conexao, bd_id)}
    horas: dict[int, int] = {}
    custo: dict[int, int] = {}
    for mes in meses:
        for lancamento in consumo.do_mes(conexao, bd_id, mes)[1]:
            if lancamento.origem == "pessoas" and lancamento.pessoa_id is not None:
                chave = lancamento.pessoa_id
                horas[chave] = horas.get(chave, 0) + lancamento.horas
                custo[chave] = custo.get(chave, 0) + lancamento.bruto_centavos
    termo = busca.strip().lower()
    linhas = []
    for p in pessoas.listar_detalhe(conexao, bd_id):
        ativos = sum(_ativa(p, mes) for mes in meses)
        if ativos == 0:
            continue
        if unidade_id is not None:
            dona = orgs.get(p.org_id)
            if dona is None or unidade_id not in (dona.id, dona.pai_id):
                continue
        if termo and termo not in p.nome.lower() and termo not in p.matricula.lower():
            continue
        linhas.append(
            LinhaPessoa(
                p.id,
                p.matricula,
                p.nome,
                p.unidade,
                p.cargo,
                p.empresa,
                p.vinculo,
                p.tema,
                p.desligamento,
                ativos,
                horas.get(p.id, 0),
                custo.get(p.id, 0),
            )  # fmt: skip
        )
    return linhas


def nova_pessoa(
    conexao: Conexao,
    bd_id: int,
    matricula: str,
    nome: str,
    org_id: int,
    cargo_id: int,
    tema_id: int,
    admissao: str,
) -> int:
    if not matricula.strip() or not nome.strip():
        raise EquipeInvalida("Informe matrícula e nome.")
    try:
        vigencia.validar_mes(admissao)
    except ValueError as erro:
        raise EquipeInvalida("Informe o início no formato AAAA-MM.") from erro
    unidade = organizacao.achar_org(conexao, bd_id, org_id)
    if unidade is None or unidade.tipo != "Squad":
        raise EquipeInvalida("A unidade da pessoa precisa ser um squad deste BD.")
    try:
        return pessoas.criar_pessoa(
            conexao,
            bd_id,
            matricula.strip(),
            nome.strip(),
            org_id,
            cargo_id,
            tema_id,
            admissao,
            None,
        )
    except ErroDeIntegridade as erro:
        raise EquipeInvalida(
            "Matrícula já cadastrada, ou cargo ou tema não pertence a este BD."
        ) from erro


def editar(
    conexao: Conexao,
    bd_id: int,
    pessoa_id: int,
    org_id: int | None = None,
    cargo_id: int | None = None,
    tema_id: int | None = None,
    desligamento: str | None = None,
) -> None:
    """Muda squad, cargo, tema e desligamento. Mês fechado não muda: está congelado."""
    atual = next((p for p in pessoas.listar_detalhe(conexao, bd_id) if p.id == pessoa_id), None)
    if atual is None:
        raise EquipeInvalida("Pessoa não encontrada neste BD.")
    if desligamento:
        try:
            vigencia.validar_mes(desligamento)
        except ValueError as erro:
            raise EquipeInvalida("Informe o desligamento no formato AAAA-MM.") from erro
        if desligamento < atual.admissao:
            raise EquipeInvalida("O desligamento não pode ser anterior à admissão.")
    novo_org = org_id if org_id is not None else atual.org_id
    unidade = organizacao.achar_org(conexao, bd_id, novo_org)
    if unidade is None or unidade.tipo != "Squad":
        raise EquipeInvalida("A unidade da pessoa precisa ser um squad deste BD.")
    try:
        pessoas.atualizar_pessoa(
            conexao,
            bd_id,
            pessoa_id,
            novo_org,
            cargo_id if cargo_id is not None else atual.cargo_id,
            tema_id if tema_id is not None else atual.tema_id,
            (desligamento or None) if desligamento is not None else atual.desligamento,
        )
    except ErroDeIntegridade as erro:
        raise EquipeInvalida("Cargo ou tema não pertence a este BD.") from erro
