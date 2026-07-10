"""
gerar_llms_txt.py — Camada 4 GEO: gera /llms.txt na raiz do blog.

llms.txt é um padrão emergente (proposto por Jeremy Howard) para motores
generativos mapearem o conteúdo canônico de um site sem rastrear tudo.

Fontes: config/blog.json (nome, descricao, url_completa) + artigos/indice.json.
Config-driven: o mesmo script serve os 5 blogs da rede sem alteração.

Uso:
  python3 scripts/gerar_llms_txt.py
Também importável: from gerar_llms_txt import gerar_llms_txt
"""

import json
from pathlib import Path

BASE        = Path(__file__).resolve().parent.parent
CONFIG_BLOG = BASE / "config" / "blog.json"
INDICE_JSON = BASE / "artigos" / "indice.json"
LLMS_TXT    = BASE / "llms.txt"


def _resumo_curto(resumo: str) -> str:
    """Primeira frase do resumo; se curta demais, usa até 200 chars."""
    resumo = (resumo or "").strip()
    primeira = resumo.split(". ")[0].rstrip(".")
    if len(primeira) < 30:
        return resumo[:200].rstrip()
    return primeira


def _descricao_blog(config: dict) -> str:
    desc = (config.get("descricao") or "").strip()
    if len(desc) >= 100:
        return desc
    tema = desc[0].lower() + desc[1:] if desc else "direito e contabilidade para empresas"
    return (f"Blog da SAFIE — consultoria jurídico-contábil para negócios digitais — "
            f"sobre {tema}. Artigos assinados pelos sócios.")


def gerar_llms_txt() -> Path:
    config = json.loads(CONFIG_BLOG.read_text(encoding="utf-8"))
    indice = json.loads(INDICE_JSON.read_text(encoding="utf-8"))
    nome     = config.get("nome", "SAFIE Blog")
    url_blog = config.get("url_completa", "").rstrip("/")

    linhas = [
        f"# {nome}",
        "",
        f"> {_descricao_blog(config)}",
        "",
        "> Nota: Este blog está em construção contínua. Alguns artigos podem ter títulos "
        "semelhantes por cobrir diferentes ângulos do mesmo tema; considere sempre a data "
        "e o resumo específicos ao consumir o conteúdo.",
        "",
        "## Artigos",
        "",
    ]
    for art in indice:
        slug   = art.get("slug", "")
        titulo = art.get("titulo", "")
        if not slug or not titulo:
            continue
        linhas.append(f"- [{titulo}]({url_blog}/artigos/{slug}): {_resumo_curto(art.get('resumo', ''))}")
    linhas += [
        "",
        "## Sobre",
        "",
        "- [Sobre a SAFIE](https://safie.com.br): consultoria jurídico-contábil para negócios digitais",
        "- [Contato](https://safie.com.br/contato)",
        "",
    ]
    LLMS_TXT.write_text("\n".join(linhas), encoding="utf-8")
    return LLMS_TXT


if __name__ == "__main__":
    path = gerar_llms_txt()
    conteudo = path.read_text(encoding="utf-8")
    print(f"Gerado: {path} ({path.stat().st_size} bytes, {conteudo.count(chr(10))} linhas)")
