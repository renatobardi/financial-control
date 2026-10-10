"""Leitura do CSV de carga: UTF-8, separador `;` ou `,`, cabeçalho exato. Falha antes de gravar."""

import csv
import io


class ArquivoInvalido(Exception):
    """O arquivo inteiro é recusado. `regra` é o código mostrado no relatório."""

    def __init__(self, regra: str, mensagem: str):
        super().__init__(mensagem)
        self.regra = regra


_SEPARADORES = (";", ",")


def _decodificar(conteudo: bytes) -> str:
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError as erro:
        raise ArquivoInvalido(
            "CSV_CODIFICACAO",
            "O arquivo não está em UTF-8. Salve o CSV como UTF-8 e envie de novo.",
        ) from erro


def _cabecalho_ok(celulas: list[str], colunas: tuple[str, ...], opcionais: tuple[str, ...]) -> bool:
    nomes = [c.strip() for c in celulas]
    permitidos = set(colunas) | set(opcionais)
    return set(colunas) <= set(nomes) <= permitidos and len(set(nomes)) == len(nomes)


def ler(
    conteudo: bytes, colunas: tuple[str, ...], opcionais: tuple[str, ...] = ()
) -> list[tuple[int, dict[str, str]]]:
    """Devolve `(número da linha no arquivo, {coluna: valor})` para cada linha com dado."""
    texto = _decodificar(conteudo)
    if not texto.strip():
        raise ArquivoInvalido("CSV_VAZIO", "O arquivo está vazio.")
    primeira = texto.splitlines()[0]
    escolhido = next(
        (s for s in _SEPARADORES if _cabecalho_ok(primeira.split(s), colunas, opcionais)), None
    )
    if escolhido is None:
        celulas = {c.strip() for sep in _SEPARADORES for c in primeira.split(sep)}
        faltando = [c for c in colunas if c not in celulas]
        sobrando = sorted(
            c for c in celulas if c and c not in colunas and c not in opcionais and len(c) < 40
        )
        partes = []
        if faltando:
            partes.append("faltam as colunas: " + ", ".join(faltando))
        if sobrando:
            partes.append("colunas desconhecidas: " + ", ".join(sobrando))
        detalhe = "; ".join(partes) or "separador inesperado (use ; ou ,)"
        esperado = ", ".join(colunas)
        raise ArquivoInvalido(
            "CSV_CABECALHO",
            f"Cabeçalho inválido ({detalhe}). Esperado, separado por ; ou ,: {esperado}.",
        )
    leitor = csv.reader(io.StringIO(texto), delimiter=escolhido)
    cabecalho = [c.strip() for c in next(leitor)]
    linhas = []
    for numero, celulas in enumerate(leitor, start=2):
        if not any(c.strip() for c in celulas):
            continue
        if len(celulas) != len(cabecalho):
            raise ArquivoInvalido(
                "CSV_LINHA",
                f"A linha {numero} tem {len(celulas)} colunas; o cabeçalho tem {len(cabecalho)}.",
            )
        linha = {c: v.strip() for c, v in zip(cabecalho, celulas, strict=True)}
        for opcional in opcionais:
            linha.setdefault(opcional, "")
        linhas.append((numero, linha))
    if not linhas:
        raise ArquivoInvalido("CSV_VAZIO", "O arquivo só tem o cabeçalho, sem linhas de dado.")
    return linhas
