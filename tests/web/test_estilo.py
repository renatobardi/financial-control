"""Critério (design) da #2: tokens, Inter self-hosted e modo escuro por classe como no Kubo."""

import re
from pathlib import Path

CSS = (Path(__file__).parents[2] / "financeiro/web/styles/input.css").read_text()

TOKENS = [
    "background", "foreground", "card", "card-foreground", "popover", "popover-foreground",
    "primary", "primary-foreground", "secondary", "secondary-foreground", "muted",
    "muted-foreground", "accent", "accent-foreground", "destructive", "border", "input", "ring",
    "sidebar", "sidebar-foreground", "sidebar-primary", "sidebar-primary-foreground",
    "sidebar-accent", "sidebar-accent-foreground", "sidebar-border",
]  # fmt: skip


def _bloco(seletor: str) -> str:
    achado = re.search(rf"^{re.escape(seletor)}\s*\{{(.*?)^\}}", CSS, re.DOTALL | re.MULTILINE)
    assert achado, f"bloco {seletor} ausente"
    return achado.group(1)


def test_modo_escuro_por_classe():
    assert "@custom-variant dark (&:is(.dark *));" in CSS


def test_tokens_claro_e_escuro_completos():
    for seletor in (":root", ".dark"):
        bloco = _bloco(seletor)
        assert [t for t in TOKENS if f"--{t}:" not in bloco] == []


def test_tokens_principais_iguais_aos_do_kubo():
    claro = _bloco(":root")
    assert "--primary: oklch(0.216 0.006 56.043);" in claro
    assert "--background: oklch(1 0 0);" in claro
    assert "--radius: 0.5rem;" in claro


def test_inter_self_hosted_sem_cdn():
    assert "url('/static/fonts/InterVariable.woff2')" in CSS
    assert "googleapis" not in CSS and "http" not in CSS.replace("https://", "")


def test_tailwind_varre_os_templates_do_app():
    assert '@source "../templates";' in CSS
