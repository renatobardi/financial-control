"""Motor de cargas: lê o arquivo, valida e grava em uma transação, relata e desfaz."""

from dataclasses import dataclass, field
from datetime import datetime

from financeiro import i18n
from financeiro.cargas import arquivo, layouts
from financeiro.store import Conexao, ErroDeIntegridade
from financeiro.store import cargas as armazem


class CargaInvalida(Exception):
    """A carga inteira é recusada (arquivo, layout, ou regra de desfazer/aprovar)."""

    def __init__(self, regra: str, mensagem: str):
        super().__init__(mensagem)
        self.regra = regra


@dataclass
class Rejeicao:
    linha: int
    regra: str
    mensagem: str
    dados: dict[str, str]
    aprovavel: bool
    grupo: str | None


@dataclass
class Relatorio:
    carga_id: int | None
    layout: str
    lidas: int
    inseridas: int
    atualizadas: int
    iguais: int
    rejeitadas: int
    horas: int
    valor_centavos: int
    rejeicoes: list[Rejeicao] = field(default_factory=list)


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def processar(
    conexao: Conexao,
    bd_id: int,
    chave_layout: str,
    conteudo: bytes,
    nome_arquivo: str,
    usuario_id: int,
    agora: datetime,
    *,
    aplicar: bool = True,
) -> Relatorio:
    """Carrega um CSV. Com `aplicar=False` é a pré-validação: relata e não grava nada."""
    layout = layouts.LAYOUTS.get(chave_layout)
    if layout is None:
        raise CargaInvalida("LAYOUT_DESCONHECIDO", f"Layout desconhecido: {chave_layout!r}.")
    try:
        linhas = arquivo.ler(conteudo, layout.colunas, layout.opcionais)
    except arquivo.ArquivoInvalido as erro:
        raise CargaInvalida(erro.regra, str(erro)) from erro

    conexao.commit()  # começa de uma transação limpa
    diario = armazem.Diario()
    ctx = layouts.Contexto(conexao, bd_id, diario, _iso(agora))
    try:
        resultados = layout.processar(ctx, linhas)
        contagens = {
            "lidas": len(resultados),
            "inseridas": sum(r.acao == "inserida" for r in resultados),
            "atualizadas": sum(r.acao == "atualizada" for r in resultados),
            "iguais": sum(r.acao == "igual" for r in resultados),
            "rejeitadas": sum(r.acao == "rejeitada" for r in resultados),
            "horas": sum(r.horas for r in resultados if r.acao != "rejeitada"),
            "valor_centavos": sum(r.valor_centavos for r in resultados if r.acao != "rejeitada"),
        }
        carga_id = None
        if aplicar:
            carga_id = armazem.criar_carga(
                conexao, bd_id, layout.nome, nome_arquivo, usuario_id, _iso(agora)
            )
            for r in resultados:
                if r.acao == "rejeitada":
                    armazem.gravar_rejeicao(
                        conexao, bd_id, carga_id, r.linha, r.regra, r.mensagem, r.dados,
                        r.aprovavel, r.grupo,
                    )  # fmt: skip
            armazem.gravar_diario(conexao, bd_id, carga_id, diario)
            armazem.fechar_relatorio(conexao, bd_id, carga_id, contagens)
            conexao.commit()
        else:
            conexao.rollback()
    except Exception:
        conexao.rollback()
        raise
    rejeicoes = [
        Rejeicao(r.linha, r.regra, r.mensagem, r.dados, r.aprovavel, r.grupo)
        for r in resultados
        if r.acao == "rejeitada"
    ]
    return Relatorio(carga_id, layout.nome, **contagens, rejeicoes=rejeicoes)


def aprovar_extras(conexao: Conexao, bd_id: int, carga_id: int, grupo: str, agora: datetime) -> int:
    """Aprova as horas acima do calendário de uma pessoa e mês e as grava como extras."""
    carga = armazem.achar_carga(conexao, bd_id, carga_id)
    if carga is None or carga.estado != "ativa":
        raise CargaInvalida("CARGA_INEXISTENTE", "Carga não encontrada ou já desfeita.")
    pendentes = [
        r
        for r in armazem.rejeicoes_da_carga(conexao, bd_id, carga_id)
        if r.grupo == grupo and r.aprovavel and not r.aprovada
    ]
    if not pendentes:
        raise CargaInvalida("SEM_PENDENCIA", "Não há horas extras pendentes neste grupo.")
    conexao.commit()
    diario = armazem.Diario()
    ctx = layouts.Contexto(conexao, bd_id, diario)
    try:
        total = 0
        for r in pendentes:
            d = r.dados
            mes = f"{int(d['ano']):04d}-{int(d['mes']):02d}"
            if armazem.mes_fechado(conexao, bd_id, mes):
                raise CargaInvalida(
                    "MES_FECHADO", f"{i18n.mes(int(d['ano']), int(d['mes']))} foi fechado."
                )
            pessoa = armazem.id_por(conexao, "pessoa", "matricula", bd_id, d["matricula"])
            tema = armazem.id_por(conexao, "tema", "codigo", bd_id, d["tema_codigo"])
            horas = int(d["horas"])
            armazem.upsert(
                conexao, ctx.diario, "alocacao", bd_id,
                {"pessoa_id": pessoa, "tema_id": tema, "mes": mes}, {"horas": horas, "extra": 1},
            )  # fmt: skip
            total += horas
        armazem.aprovar_rejeicoes(conexao, bd_id, carga_id, grupo)
        armazem.gravar_diario(conexao, bd_id, carga_id, diario)
        armazem.somar_na_carga(conexao, bd_id, carga_id, "inseridas", len(pendentes))
        armazem.somar_na_carga(conexao, bd_id, carga_id, "rejeitadas", -len(pendentes))
        armazem.somar_na_carga(conexao, bd_id, carga_id, "horas", total)
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    return total


def desfazer(conexao: Conexao, bd_id: int, carga_id: int, agora: datetime) -> None:
    """Volta o banco ao estado anterior à carga, se nada posterior depende dela."""
    carga = armazem.achar_carga(conexao, bd_id, carga_id)
    if carga is None:
        raise CargaInvalida("CARGA_INEXISTENTE", "Carga não encontrada neste BD.")
    if carga.estado == "desfeita":
        raise CargaInvalida("CARGA_JA_DESFEITA", "Esta carga já foi desfeita.")
    posteriores = armazem.cargas_posteriores_que_tocam(conexao, bd_id, carga_id)
    if posteriores:
        ids = ", ".join(f"#{i}" for i in posteriores)
        raise CargaInvalida(
            "CARGA_POSTERIOR",
            f"A carga {ids} (posterior) alterou os mesmos registros. Desfaça-a antes.",
        )
    mudancas = armazem.mudancas_da_carga(conexao, bd_id, carga_id)
    for m in mudancas:
        mes = armazem.mes_do_registro(conexao, bd_id, m.tabela, m.registro_id)
        if mes and armazem.mes_fechado(conexao, bd_id, mes):
            raise CargaInvalida(
                "MES_FECHADO",
                f"{i18n.mes(int(mes[:4]), int(mes[5:]))} já foi fechado: "
                "reabra o mês para desfazer.",
            )
    conexao.commit()
    try:
        for m in reversed(mudancas):
            armazem.restaurar(conexao, bd_id, m.tabela, m.registro_id, m.antes)
        armazem.marcar_desfeita(conexao, bd_id, carga_id, agora.strftime("%Y-%m-%dT%H:%M:%SZ"))
        conexao.commit()
    except ErroDeIntegridade as erro:
        conexao.rollback()
        raise CargaInvalida(
            "DEPENDENCIA", "Há registros que dependem do que esta carga criou."
        ) from erro
    except Exception:
        conexao.rollback()
        raise
