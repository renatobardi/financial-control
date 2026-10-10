import re

from financeiro.web.templates import ambiente


def _renderizar_fonte(fonte: str, **contexto) -> str:
    return ambiente().from_string(fonte).render(**contexto)


def test_bloco_lazy_carrega_ao_aparecer_com_esqueleto():
    html = _renderizar_fonte(
        '{% from "_macros.html" import bloco_lazy %}{{ bloco_lazy("/fragmentos/resumo") }}'
    )

    assert 'hx-get="/fragmentos/resumo"' in html
    assert 'hx-trigger="load"' in html
    assert "animate-pulse" in html
    assert 'aria-busy="true"' in html


def test_bloco_lazy_abaixo_da_dobra_usa_revealed():
    html = _renderizar_fonte(
        '{% from "_macros.html" import bloco_lazy %}'
        '{{ bloco_lazy("/fragmentos/pdd", gatilho="revealed") }}'
    )

    assert 'hx-trigger="revealed"' in html


def test_bloco_lazy_escapa_a_url():
    html = _renderizar_fonte(
        '{% from "_macros.html" import bloco_lazy %}{{ bloco_lazy(url) }}', url='/x"><script>'
    )

    assert "<script>" not in html


def test_botao_e_badge_usam_texto_do_catalogo():
    html = _renderizar_fonte(
        '{% from "_macros.html" import botao, badge %}'
        '{{ botao("fechamento.titulo") }}'
        '{{ badge("fechamento.mes_fechado", tom="destaque", mes="out/2026") }}'
    )

    assert "Fechamento mensal" in html
    assert "Mês out/2026 fechado." in html
    assert "bg-primary/10" in html


def test_formatadores_ficam_disponiveis_nos_templates():
    html = _renderizar_fonte("{{ moeda(123456) }} {{ mes(2026, 10) }} {{ numero(1000) }}")

    assert html == "R$ 1.234,56 out/2026 1.000"


# Guarda (critério qa da #2): texto visível só vem do catálogo i18n.
_JINJA = re.compile(r"\{#.*?#\}|\{%.*?%\}|\{\{.*?\}\}", re.DOTALL)
_ATRIBUTO_VISIVEL = re.compile(r"""\b(?:title|alt|placeholder|aria-label)="([^"]*)\"""")


def texto_fora_do_catalogo(fonte: str) -> list[str]:
    """Trechos de texto literal visível: nós de texto fora de `{{ }}` e atributos como title."""
    sem_jinja = _JINJA.sub("\x00", fonte)
    sem_script = re.sub(r"<(script|style)\b.*?</\1>", "", sem_jinja, flags=re.DOTALL | re.I)
    achados = []
    for atributo in _ATRIBUTO_VISIVEL.findall(sem_script):
        if re.search(r"[^\W\d_]", atributo.replace("\x00", "")):
            achados.append(atributo.strip())
    sem_tags = re.sub(r"<[^>]*>", "\x01", sem_script)
    for trecho in sem_tags.replace("\x00", " ").split("\x01"):
        if re.search(r"[^\W\d_]", trecho):
            achados.append(trecho.strip())
    return achados


def test_guarda_pega_texto_solto_no_template():
    assert texto_fora_do_catalogo('<button title="Salvar">{{ t("a.b") }}</button>') == ["Salvar"]
    assert texto_fora_do_catalogo("<p>Olá mundo</p>") == ["Olá mundo"]
    assert (
        texto_fora_do_catalogo('<p class="x">{{ t("a.b") }}</p><span>{{ moeda(1) }}</span>') == []
    )


def test_nenhum_template_tem_texto_fora_do_catalogo():
    from financeiro.web import templates

    pasta = templates.PASTA
    achados = {
        str(arquivo.relative_to(pasta)): texto_fora_do_catalogo(arquivo.read_text())
        for arquivo in pasta.rglob("*.html")
    }

    assert {nome: textos for nome, textos in achados.items() if textos} == {}
