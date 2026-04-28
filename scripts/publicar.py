"""
publicar.py — Fase 3 do pipeline diário

Lê dados/artigo_gerado.json, gera o HTML do artigo a partir do template,
atualiza a home, as páginas de tema, o sitemap.xml e o índice de busca.
Depois faz commit + push no GitHub.

Uso:
  python3 scripts/publicar.py
  python3 scripts/publicar.py --sem-git   (só gera arquivos, não commita)
"""

import json
import re
import subprocess
import sys
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import os

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE          = Path(__file__).resolve().parent.parent
CONFIG_BLOG   = BASE / "config" / "blog.json"
CONFIG_TEMAS  = BASE / "config" / "temas.json"
ARTIGO_PATH   = BASE / "dados" / "artigo_gerado.json"
TEMPLATE_ART  = BASE / "templates" / "artigo.html"
TEMPLATE_TEMA = BASE / "templates" / "tema.html"
TEMPLATE_IMG  = BASE / "templates" / "imagem-artigo.svg"
ARTIGOS_DIR   = BASE / "artigos"
TEMAS_DIR     = BASE / "temas"
IMGS_DIR      = BASE / "assets" / "img" / "artigos"
INDICE_JSON   = BASE / "artigos" / "indice.json"
SITEMAP       = BASE / "sitemap.xml"
INDEX_HTML    = BASE / "index.html"
LOG_DIR       = BASE / "logs"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(exist_ok=True)
hoje = datetime.now().strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"publicacao_{hoje}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

load_dotenv(BASE / ".env")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


# ── Constantes ────────────────────────────────────────────────────────────────
MESES_ABREV = ["JAN","FEV","MAR","ABR","MAI","JUN","JUL","AGO","SET","OUT","NOV","DEZ"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def ler_json(caminho, padrao):
    p = Path(caminho)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Erro ao ler {caminho}: {e}")
    return padrao


def salvar_json(caminho, dados):
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def preencher_template(template: str, variaveis: dict) -> str:
    for chave, valor in variaveis.items():
        template = template.replace(f"{{{{{chave}}}}}", str(valor) if valor else "")
    return template


def data_amigavel(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        meses = ["janeiro","fevereiro","março","abril","maio","junho",
                 "julho","agosto","setembro","outubro","novembro","dezembro"]
        return f"{dt.day} de {meses[dt.month-1]} de {dt.year}"
    except Exception:
        return iso


def data_capa(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{dt.day:02d} {MESES_ABREV[dt.month-1]} {dt.year}"
    except Exception:
        return ""


def escapar_xml(texto: str) -> str:
    return (texto
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;"))


def quebrar_titulo(titulo: str) -> tuple:
    """Divide o título em até 3 linhas equilibradas respeitando palavras inteiras."""
    n = len(titulo)
    palavras = titulo.split()

    if n <= 25 or len(palavras) == 1:
        return titulo, "", ""

    if n <= 50:
        melhor = (float("inf"), 1)
        for i in range(1, len(palavras)):
            l1 = " ".join(palavras[:i])
            l2 = " ".join(palavras[i:])
            diff = abs(len(l1) - len(l2))
            if diff < melhor[0]:
                melhor = (diff, i)
        c = melhor[1]
        return " ".join(palavras[:c]), " ".join(palavras[c:]), ""

    alvo = n // 3
    melhor = (float("inf"), 1, 2)
    for i in range(1, len(palavras) - 1):
        for j in range(i + 1, len(palavras)):
            l1 = " ".join(palavras[:i])
            l2 = " ".join(palavras[i:j])
            l3 = " ".join(palavras[j:])
            if not l3:
                continue
            custo = (len(l1) - alvo) ** 2 + (len(l2) - alvo) ** 2 + (len(l3) - alvo) ** 2
            if custo < melhor[0]:
                melhor = (custo, i, j)
    _, i, j = melhor
    return " ".join(palavras[:i]), " ".join(palavras[i:j]), " ".join(palavras[j:])


# ── 0. Gerar imagem de capa ───────────────────────────────────────────────────

def gerar_imagem_capa(artigo: dict, config_blog: dict) -> tuple:
    """Gera o SVG de capa do artigo. Retorna (url_completa, url_relativa)."""
    if not TEMPLATE_IMG.exists():
        log.warning(f"Template de imagem não encontrado: {TEMPLATE_IMG}")
        return "", ""

    IMGS_DIR.mkdir(parents=True, exist_ok=True)

    slug      = artigo["slug"]
    titulo    = artigo["titulo"]
    tema      = artigo.get("tema_nome", "")
    data      = data_capa(artigo.get("data_iso", ""))
    nome_blog = config_blog.get("nome", "SAFIE Blog")
    url_blog  = config_blog.get("url_completa", "")
    iv        = config_blog.get("identidade_visual", {})
    cor_dest  = iv.get("cor_destaque_imagem", "#ff6b9d")
    cor_bco   = "#ffffff"

    l1, l2, l3 = quebrar_titulo(titulo)

    if l3:
        c1, c2, c3 = cor_bco, cor_bco, cor_dest
    elif l2:
        c1, c2, c3 = cor_bco, cor_dest, cor_dest
    else:
        c1, c2, c3 = cor_dest, cor_dest, cor_dest

    variaveis = {
        "TITULO_LINHA_1": escapar_xml(l1),
        "TITULO_LINHA_2": escapar_xml(l2),
        "TITULO_LINHA_3": escapar_xml(l3),
        "COR_LINHA_1":    c1,
        "COR_LINHA_2":    c2,
        "COR_LINHA_3":    c3,
        "CATEGORIA":      escapar_xml(tema.upper()),
        "DATA":           data,
        "NOME_BLOG":      escapar_xml(nome_blog),
    }

    svg = preencher_template(TEMPLATE_IMG.read_text(encoding="utf-8"), variaveis)
    destino = IMGS_DIR / f"{slug}.svg"
    destino.write_text(svg, encoding="utf-8")
    log.info(f"Imagem de capa gerada: {destino}")

    rel = f"/assets/img/artigos/{slug}.svg"
    return f"{url_blog}{rel}", rel


# ── 1. Gerar HTML do artigo ───────────────────────────────────────────────────

def gerar_html_artigo(artigo: dict, config_blog: dict, imagem_url: str = "", imagem_rel: str = "") -> Path:
    template = TEMPLATE_ART.read_text(encoding="utf-8")
    ano = datetime.now().strftime("%Y")
    nome_blog = config_blog.get("nome", "SAFIE Blog")

    bloco_imagem = (
        f'<img class="artigo-capa" src="{imagem_rel}" alt="{artigo["titulo"]}" '
        f'width="1200" height="630" loading="lazy">'
        if imagem_rel else ""
    )

    variaveis = {
        "TITULO":           artigo["titulo"],
        "META_TITULO":      artigo["meta_titulo"],
        "META_DESCRIPTION": artigo["meta_description"],
        "CANONICAL_URL":    artigo["canonical_url"],
        "OG_TYPE":          "article",
        "BLOG_NOME":        nome_blog,
        "DATA_ISO":         artigo["data_iso"],
        "DATA_FORMATADA":   artigo["data_formatada"],
        "TEMPO_LEITURA":    artigo["tempo_leitura"],
        "TEMA":             artigo["tema_nome"],
        "TEMA_SLUG":        artigo["tema_slug"],
        "RESUMO_EXECUTIVO": artigo["resumo_executivo"],
        "CONTEUDO":         artigo["conteudo"],
        "FAQ_HTML":         artigo["faq_html"],
        "REFERENCIAS_HTML": artigo["referencias_html"],
        "RELACIONADOS_HTML":artigo["relacionados_html"],
        "SCHEMA_JSON":      artigo["schema_json"],
        "PALAVRAS_CHAVE":  artigo.get("palavras_chave", ""),
        "ANO":              ano,
        "IMAGEM_CAPA_URL":  imagem_url,
        "IMAGEM_CAPA_REL":  imagem_rel,
        "IMAGEM_BLOCO":     bloco_imagem,
    }

    html = preencher_template(template, variaveis)

    destino = ARTIGOS_DIR / f"{artigo['slug']}.html"
    ARTIGOS_DIR.mkdir(exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    log.info(f"HTML do artigo gerado: {destino}")
    return destino


# ── 2. Atualizar índice de busca ──────────────────────────────────────────────

def atualizar_indice(artigo: dict):
    indice = ler_json(INDICE_JSON, [])
    slug = artigo["slug"]

    indice = [a for a in indice if a.get("slug") != slug]

    indice.insert(0, {
        "slug":     slug,
        "titulo":   artigo["titulo"],
        "resumo":   artigo["resumo_executivo"][:200],
        "tema":     artigo["tema_nome"],
        "tema_slug":artigo["tema_slug"],
        "data":     artigo["data_iso"],
    })

    indice = indice[:200]
    salvar_json(INDICE_JSON, indice)
    log.info(f"Índice de busca atualizado ({len(indice)} artigos)")


# ── 3. Atualizar home (index.html) ───────────────────────────────────────────

def card_artigo_html(artigo_idx: dict) -> str:
    data_fmt = data_amigavel(artigo_idx.get("data", ""))
    return (
        f'<div class="card-artigo" data-tema="{artigo_idx["tema_slug"]}">\n'
        f'  <span class="card-tema">{artigo_idx["tema"]}</span>\n'
        f'  <h2><a href="/artigos/{artigo_idx["slug"]}.html">{artigo_idx["titulo"]}</a></h2>\n'
        f'  <p class="card-resumo">{artigo_idx["resumo"]}</p>\n'
        f'  <div class="card-meta">\n'
        f'    <span class="card-data">{data_fmt}</span>\n'
        f'    <a class="card-link" href="/artigos/{artigo_idx["slug"]}.html">Ler artigo →</a>\n'
        f'  </div>\n'
        f'</div>\n'
    )


def atualizar_home(indice: list, config_blog: dict):
    # Home é JS-driven (v3): lê artigos/indice.json dinamicamente via home.js.
    # O indice.json já foi atualizado por atualizar_indice() — nada mais a fazer aqui.
    log.info(f"Home JS-driven: indice.json atualizado com {len(indice)} artigos.")
    return
    html_home = INDEX_HTML.read_text(encoding="utf-8")
    artigos_por_pagina = config_blog.get("artigos_por_pagina", 10)
    pagina = indice[:artigos_por_pagina]

    cards_html = "\n".join(card_artigo_html(a) for a in pagina)

    html_novo = re.sub(
        r"<!-- ARTIGOS_PLACEHOLDER.*?<!-- /ARTIGOS_PLACEHOLDER -->",
        f"<!-- ARTIGOS_PLACEHOLDER -->\n{cards_html}\n<!-- /ARTIGOS_PLACEHOLDER -->",
        html_home,
        flags=re.DOTALL,
    )

    if html_novo == html_home:
        html_novo = re.sub(
            r'(<div class="artigos-grid" id="artigos-grid">).*?(</div>)',
            f'\\1\n{cards_html}\n\\2',
            html_home,
            flags=re.DOTALL,
        )

    INDEX_HTML.write_text(html_novo, encoding="utf-8")
    log.info("Home (index.html) atualizada")


# ── 4. Atualizar página do tema ───────────────────────────────────────────────

def atualizar_pagina_tema(tema_slug: str, indice: list, config_temas: dict, config_blog: dict):
    artigos_tema = [a for a in indice if a.get("tema_slug") == tema_slug]
    nome_blog = config_blog.get("nome", "SAFIE Blog")

    tema_nome = tema_slug
    for t in config_temas.get("temas", []):
        if t["slug"] == tema_slug:
            tema_nome = t["nome"]
            break

    todos_temas_links = ""
    for t in config_temas.get("temas", []):
        todos_temas_links += (
            f'<li><a href="/temas/{t["slug"]}.html">{t["nome"]}</a></li>\n'
        )

    cards_html = "\n".join(card_artigo_html(a) for a in artigos_tema) if artigos_tema else (
        '<p style="color:var(--cinza);">Nenhum artigo publicado ainda neste tema.</p>'
    )

    template = TEMPLATE_TEMA.read_text(encoding="utf-8")
    html = preencher_template(template, {
        "TEMA_NOME":         tema_nome,
        "TEMA_SLUG":         tema_slug,
        "TOTAL_ARTIGOS":     len(artigos_tema),
        "ARTIGOS_LISTA":     cards_html,
        "TODOS_TEMAS_LINKS": todos_temas_links,
        "BLOG_NOME":         nome_blog,
        "ANO":               datetime.now().strftime("%Y"),
    })

    destino = TEMAS_DIR / f"{tema_slug}.html"
    TEMAS_DIR.mkdir(exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    log.info(f"Página de tema atualizada: {destino}")


# ── 5. Atualizar sitemap.xml ──────────────────────────────────────────────────

def atualizar_sitemap(artigo: dict, config_blog: dict):
    url_blog = config_blog.get("url_completa", "")
    url_artigo = f"{url_blog}/artigos/{artigo['slug']}.html"
    data_hoje = datetime.now().strftime("%Y-%m-%d")

    novo_url = (
        f"\n  <url>\n"
        f"    <loc>{url_artigo}</loc>\n"
        f"    <lastmod>{data_hoje}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n"
        f"    <priority>0.9</priority>\n"
        f"  </url>"
    )

    conteudo = SITEMAP.read_text(encoding="utf-8")

    if url_artigo in conteudo:
        log.info("Sitemap: URL já existe, pulando.")
        return

    if "<!-- Artigos" in conteudo:
        conteudo = conteudo.replace(
            "<!-- Artigos adicionados automaticamente pelo publicar.py -->",
            f"<!-- Artigos adicionados automaticamente pelo publicar.py -->{novo_url}"
        )
    else:
        conteudo = conteudo.replace("</urlset>", f"{novo_url}\n\n</urlset>")

    SITEMAP.write_text(conteudo, encoding="utf-8")
    log.info("Sitemap atualizado")


# ── 6. Git commit + push ──────────────────────────────────────────────────────

def git_commit_push(artigo: dict):
    data_fmt = datetime.now().strftime("%Y-%m-%d")
    msg = f"post: {data_fmt} — {artigo['titulo'][:60]}"

    def run(cmd):
        result = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
        if result.returncode != 0:
            log.warning(f"Git: {' '.join(cmd)} — {result.stderr.strip()}")
        return result.returncode == 0

    log.info("[Git] Adicionando arquivos...")
    run(["git", "add", "-A"])

    log.info(f"[Git] Commit: {msg}")
    ok = run(["git", "commit", "-m", msg])
    if not ok:
        log.info("[Git] Nada para commitar.")
        return

    if not GITHUB_REPO or not GITHUB_TOKEN:
        log.warning("[Git] GITHUB_REPO ou GITHUB_TOKEN não configurados. Push pulado.")
        return

    remote_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
    run(["git", "remote", "set-url", "origin", remote_url])

    log.info("[Git] Push para GitHub...")
    ok = run(["git", "push", "origin", "main"])
    if ok:
        log.info("[Git] Push concluído. Cloudflare Pages vai fazer o deploy automaticamente.")
    else:
        log.error("[Git] Falha no push. Verifique GITHUB_TOKEN e GITHUB_REPO no .env")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(sem_git: bool = False):
    log.info("=" * 60)
    log.info("PUBLICAR ARTIGO — início")

    artigo       = ler_json(ARTIGO_PATH, {})
    config_blog  = ler_json(CONFIG_BLOG, {})
    config_temas = ler_json(CONFIG_TEMAS, {"temas": []})

    if not artigo:
        log.error(f"Nenhum artigo encontrado em {ARTIGO_PATH}")
        sys.exit(1)

    log.info(f"Publicando: '{artigo['titulo']}'")

    # 0. Gerar imagem de capa
    imagem_url, imagem_rel = gerar_imagem_capa(artigo, config_blog)

    gerar_html_artigo(artigo, config_blog, imagem_url, imagem_rel)
    atualizar_indice(artigo)

    indice = ler_json(INDICE_JSON, [])

    atualizar_home(indice, config_blog)
    atualizar_pagina_tema(artigo["tema_slug"], indice, config_temas, config_blog)
    atualizar_sitemap(artigo, config_blog)

    if not sem_git:
        git_commit_push(artigo)
    else:
        log.info("[Git] Modo --sem-git: commit e push pulados.")

    log.info("=" * 60)
    log.info(f"PUBLICAÇÃO CONCLUÍDA: {artigo['canonical_url']}")
    log.info("=" * 60)

    return artigo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publica artigo no blog")
    parser.add_argument("--sem-git", action="store_true", help="Gera arquivos mas não faz commit/push")
    args = parser.parse_args()

    main(sem_git=args.sem_git)
