"""
aplicar_geo_camada2.py — Backfill da Camada 2 GEO nos artigos publicados.

Reconstrói o JSON-LD (BlogPosting + FAQPage + BreadcrumbList) de cada artigo:
- author vira Person (default do blog) com sameAs
- publisher vira Organization SAFIE com logo + sameAs
- mainEntityOfPage adicionado
- dateModified = timestamp deste backfill; datePublished original preservado
- FAQ mainEntity original preservado
Também atualiza <meta name="keywords"> (com entidades reais do corpo, via
otimizar_seo.gerar_palavras_chave) e o alt da capa (título + tema).

Uso:
  python3 scripts/aplicar_geo_camada2.py --dry-run   # analisa e mostra amostras, não grava
  python3 scripts/aplicar_geo_camada2.py             # aplica

Idempotente: reprocessar um artigo já migrado só atualiza dateModified.
Duas fases: analisa TODOS os artigos primeiro; qualquer erro aborta antes de
gravar qualquer arquivo (hard-fail).
"""

import argparse
import importlib.util
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE        = Path(__file__).resolve().parent.parent
ARTIGOS_DIR = BASE / "artigos"
CONFIG_BLOG = BASE / "config" / "blog.json"

# Reusa o gerador de keywords do pipeline (mesma lógica do otimizar_seo.py)
_spec = importlib.util.spec_from_file_location("otimizar_seo", Path(__file__).parent / "otimizar_seo.py")
_seo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_seo)

AUTOR_BACKFILL = {
    "@type": "Person",
    "name": "Ítalo Cunha",
    "sameAs": [
        "https://www.linkedin.com/in/italo-cunha-cwb/",
        "https://www.instagram.com/euitalocunha/"
    ],
}
PUBLISHER = {
    "@type": "Organization",
    "name": "SAFIE",
    "url": "https://safie.com.br",
    "logo": {
        "@type": "ImageObject",
        "url": "https://consultoria.safie.com.br/wp-content/uploads/2025/11/cropped-2-1-1024x292.webp"
    },
    "sameAs": [
        "https://www.instagram.com/safiegroup/",
        "https://www.instagram.com/safiecontabilidade/"
    ],
}

TS_BACKFILL = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%dT%H:%M:%S-03:00")

RE_JSONLD   = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
RE_H1       = re.compile(r'<h1 class="artigo-titulo"[^>]*>(.*?)</h1>', re.DOTALL)
RE_TEMA     = re.compile(r'<a class="artigo-tema" href="/temas/([^"]+?)(?:\.html)?">([^<]+)</a>')
RE_CORPO    = re.compile(r'<div class="artigo-corpo"[^>]*>(.*?)</div>\s*<!-- FAQ -->', re.DOTALL)
RE_KEYWORDS = re.compile(r'(<meta name="keywords" content=")([^"]*)(")')
RE_ALT      = re.compile(r'(<img class="artigo-capa"[^>]*?alt=")([^"]*)(")')


def analisar(path: Path, url_blog: str):
    """Fase 1: extrai tudo e monta o resultado. Retorna (novo_html, info) ou levanta ValueError."""
    html = path.read_text(encoding="utf-8")
    slug = path.stem
    avisos = []

    m_ld = RE_JSONLD.search(html)
    if not m_ld:
        raise ValueError("sem bloco JSON-LD para substituir")
    dados = json.loads(m_ld.group(1))
    lista = dados if isinstance(dados, list) else [dados]
    bp_old  = next((d for d in lista if d.get("@type") == "BlogPosting"), None)
    faq_old = next((d for d in lista if d.get("@type") == "FAQPage"), None)
    if not bp_old or not bp_old.get("datePublished"):
        raise ValueError("datePublished não extraível do JSON-LD")

    m_h1 = RE_H1.search(html)
    if not m_h1:
        raise ValueError("h1 .artigo-titulo não encontrado")
    titulo = re.sub(r"\s+", " ", m_h1.group(1)).strip()

    m_tema = RE_TEMA.search(html)
    if not m_tema:
        raise ValueError("link de tema (.artigo-tema) não encontrado")
    tema_slug, tema_nome = m_tema.group(1), m_tema.group(2).strip()

    m_corpo = RE_CORPO.search(html)
    corpo = m_corpo.group(1) if m_corpo else ""
    if not m_corpo:
        avisos.append("corpo não localizado (keywords só de título+tema)")

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": titulo,
            "description": bp_old.get("description", ""),
            "datePublished": bp_old["datePublished"],
            "dateModified": TS_BACKFILL,
            "mainEntityOfPage": {"@type": "WebPage", "@id": f"{url_blog}/artigos/{slug}"},
            "author": AUTOR_BACKFILL,
            "publisher": PUBLISHER,
            "url": f"{url_blog}/artigos/{slug}",
            "articleSection": tema_nome,
            "inLanguage": "pt-BR",
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": (faq_old or {}).get("mainEntity", []),
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Início", "item": url_blog},
                {"@type": "ListItem", "position": 2, "name": tema_nome, "item": f"{url_blog}/temas/{tema_slug}"},
                {"@type": "ListItem", "position": 3, "name": titulo, "item": f"{url_blog}/artigos/{slug}"},
            ],
        },
    ]
    if faq_old is None:
        avisos.append("FAQPage ausente no JSON-LD antigo (mainEntity vazio no novo)")

    bloco_novo = ('<script type="application/ld+json">\n'
                  + json.dumps(schema, ensure_ascii=False, indent=2)
                  + "\n  </script>")
    novo_html = html[:m_ld.start()] + bloco_novo + html[m_ld.end():]

    keywords = _seo.gerar_palavras_chave(titulo, tema_nome, corpo)
    if RE_KEYWORDS.search(novo_html):
        novo_html = RE_KEYWORDS.sub(lambda m: m.group(1) + keywords + m.group(3), novo_html, count=1)
    else:
        avisos.append("meta keywords não encontrada")

    alt_novo = f"{titulo} — capa ilustrativa do artigo sobre {tema_nome}"
    if RE_ALT.search(novo_html):
        novo_html = RE_ALT.sub(lambda m: m.group(1) + alt_novo + m.group(3), novo_html, count=1)
    else:
        avisos.append("capa (alt) não encontrada")

    info = {"slug": slug, "titulo": titulo, "tema": tema_nome,
            "datePublished": bp_old["datePublished"], "keywords": keywords,
            "avisos": avisos, "jsonld_antigo": lista, "jsonld_novo": schema}
    return novo_html, info


def main():
    parser = argparse.ArgumentParser(description="Backfill Camada 2 GEO")
    parser.add_argument("--dry-run", action="store_true", help="Analisa sem gravar")
    parser.add_argument("--esperado", type=int, default=81, help="Contagem esperada de artigos")
    args = parser.parse_args()

    url_blog = json.loads(CONFIG_BLOG.read_text(encoding="utf-8")).get(
        "url_completa", "https://ecommerce.safie.blog.br")

    arquivos = sorted(p for p in ARTIGOS_DIR.glob("*.html")
                      if p.name not in ("index.html", "indice.html"))
    print(f"Artigos encontrados: {len(arquivos)} (esperado: {args.esperado})")
    if len(arquivos) != args.esperado:
        sys.exit(f"HARD-FAIL: contagem {len(arquivos)} != esperado {args.esperado}. "
                 f"Se um artigo novo foi publicado hoje, reexecutar com --esperado {len(arquivos)}.")

    t0 = time.time()
    resultados, erros = [], []
    for path in arquivos:
        try:
            novo_html, info = analisar(path, url_blog)
            resultados.append((path, novo_html, info))
            for a in info["avisos"]:
                print(f"  [aviso] {path.name}: {a}")
        except Exception as e:
            erros.append((path.name, str(e)))
            print(f"  [ERRO] {path.name}: {e}")

    print(f"\nAnalisados: {len(resultados)} OK, {len(erros)} com erro")
    if erros:
        sys.exit(f"HARD-FAIL: {len(erros)} artigo(s) com erro — NADA foi gravado.")
    if len(resultados) != args.esperado:
        sys.exit("HARD-FAIL: contagem processada difere do esperado — NADA foi gravado.")

    if args.dry_run:
        print(f"\n[DRY-RUN] Nenhum arquivo gravado. dateModified que seria aplicado: {TS_BACKFILL}")
        for path, _, info in (resultados[0], resultados[len(resultados)//2], resultados[-1]):
            antigo_bp = next(d for d in info["jsonld_antigo"] if d.get("@type") == "BlogPosting")
            print(f"\n── AMOSTRA {info['slug']} ──")
            print(f"  ANTES : author={antigo_bp.get('author')} | dateModified={antigo_bp.get('dateModified')} "
                  f"| mainEntityOfPage={'presente' if antigo_bp.get('mainEntityOfPage') else 'ausente'} "
                  f"| blocos={[d.get('@type') for d in info['jsonld_antigo']]}")
            novo_bp = info["jsonld_novo"][0]
            print(f"  DEPOIS: author={novo_bp['author']['name']} (Person, {len(novo_bp['author']['sameAs'])} sameAs) "
                  f"| dateModified={novo_bp['dateModified']} | datePublished={novo_bp['datePublished']} "
                  f"| blocos={[d.get('@type') for d in info['jsonld_novo']]}")
            print(f"  keywords novas: {info['keywords']}")
        return

    for path, novo_html, _ in resultados:
        path.write_text(novo_html, encoding="utf-8")
        print(f"  modificado: {path.name}")
    print(f"\nConcluído: {len(resultados)}/{args.esperado} artigos gravados em {time.time()-t0:.1f}s")
    print(f"dateModified aplicado: {TS_BACKFILL}")


if __name__ == "__main__":
    main()
