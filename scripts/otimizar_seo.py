"""
otimizar_seo.py — Agente de SEO/GEO do pipeline SAFIE Blogs
Lê dados/artigo_gerado.json, valida e otimiza campos de SEO, e grava de volta.
Roda entre gerar_artigo.py e publicar.py no pipeline diário.
"""

import json
import re
import logging
import sys
from pathlib import Path

BASE        = Path(__file__).resolve().parent.parent
ARTIGO_PATH = BASE / "dados" / "artigo_gerado.json"
CONFIG_BLOG = BASE / "config" / "blog.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

STOPWORDS = {
    "e", "o", "a", "os", "as", "de", "da", "do", "das", "dos", "no", "na", "nos", "nas",
    "para", "que", "com", "em", "por", "um", "uma", "uns", "umas", "é", "são", "se",
    "ao", "à", "ou", "mas", "mais", "seu", "sua", "seus", "suas", "este", "esta",
    "esse", "essa", "como", "não", "foi", "ser", "ter", "tem", "há", "já", "pelo",
    "pela", "pelos", "pelas", "entre", "sobre", "após", "desde", "até",
}

MAX_TITULO_CHARS = 45
MAX_DESC_CHARS   = 155
MAX_KEYWORDS     = 8


def limpar_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", "", texto).strip()


def gerar_palavras_chave(titulo: str, tema: str) -> str:
    texto = f"{titulo} {tema}".lower()
    texto = re.sub(r"[^\w\s]", " ", texto)
    palavras = [w for w in texto.split() if len(w) > 3 and w not in STOPWORDS]
    vistas, unicas = set(), []
    for p in palavras:
        if p not in vistas:
            vistas.add(p)
            unicas.append(p)
    return ", ".join(unicas[:MAX_KEYWORDS])


def validar_titulo(titulo: str, blog_nome: str) -> str:
    sufixo = f" | {blog_nome}"
    titulo_completo = titulo + sufixo
    if len(titulo_completo) <= 60:
        return titulo
    # Truncar para que titulo + sufixo caiba em 60 chars
    max_titulo = 60 - len(sufixo)
    truncado = titulo[:max_titulo].rsplit(" ", 1)[0]
    log.warning(f"Título truncado ({len(titulo)} → {len(truncado)} chars): '{truncado}'")
    return truncado


def validar_meta_description(desc: str) -> str:
    desc = limpar_html(desc)
    if len(desc) <= MAX_DESC_CHARS:
        return desc
    truncado = desc[:MAX_DESC_CHARS].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    log.warning(f"Meta description truncada: {len(desc)} → {len(truncado)} chars")
    return truncado


def main():
    if not ARTIGO_PATH.exists():
        log.error(f"Arquivo não encontrado: {ARTIGO_PATH}")
        sys.exit(1)

    artigo = json.loads(ARTIGO_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_BLOG.read_text(encoding="utf-8")) if CONFIG_BLOG.exists() else {}
    blog_nome = config.get("nome", "SAFIE Blog")

    log.info("=== SEO/GEO: iniciando otimização ===")

    # 1. Validar título (total com sufixo ≤ 60 chars)
    titulo_original = artigo.get("titulo", "")
    titulo_ok = validar_titulo(titulo_original, blog_nome)
    if titulo_ok != titulo_original:
        artigo["titulo"] = titulo_ok
    log.info(f"Title ({len(titulo_ok + ' | ' + blog_nome)} chars): {titulo_ok} | {blog_nome}")

    # 2. Gerar palavras-chave
    palavras_chave = gerar_palavras_chave(titulo_ok, artigo.get("tema_nome", ""))
    artigo["palavras_chave"] = palavras_chave
    log.info(f"Keywords: {palavras_chave}")

    # 3. Validar meta_description (≤ 155 chars)
    desc_ok = validar_meta_description(artigo.get("meta_description", ""))
    if desc_ok != artigo.get("meta_description", ""):
        artigo["meta_description"] = desc_ok
    log.info(f"Meta description ({len(desc_ok)} chars) ✓")

    # 4. Alertas de auditoria (não bloqueiam o pipeline)
    canonical = artigo.get("canonical_url", "")
    blog_url  = config.get("url_completa", "")
    if blog_url and canonical and not canonical.startswith(blog_url):
        log.warning(f"Canonical URL diverge do domínio: {canonical}")

    # 5. Gravar artigo otimizado
    ARTIGO_PATH.write_text(json.dumps(artigo, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("=== SEO/GEO: concluído ===")


if __name__ == "__main__":
    main()
