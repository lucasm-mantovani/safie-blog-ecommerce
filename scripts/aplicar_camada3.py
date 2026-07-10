"""
aplicar_camada3.py — Backfill da Camada 3 GEO nos artigos publicados.

Duas mudanças por artigo:
  (a) heading do bloco: <h2>Artigos relacionados</h2> → <h2>Continue lendo</h2>
  (b) conteúdo de .relacionados-lista: placeholder "Mais artigos em breve"
      → <ul> com 3 relacionados reais (mesma função do publicar.py — fonte única)

Uso:
  python3 scripts/aplicar_camada3.py --dry-run --esperado 83
  python3 scripts/aplicar_camada3.py --esperado 83

Idempotente: 2ª execução produz HTML byte-idêntico (índice inalterado).
Duas fases: analisa TODOS os artigos primeiro; qualquer erro aborta antes
de gravar qualquer arquivo (hard-fail).
"""

import argparse
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

BASE        = Path(__file__).resolve().parent.parent
ARTIGOS_DIR = BASE / "artigos"
INDICE_JSON = BASE / "artigos" / "indice.json"

# Fonte única do algoritmo: importa a função do publicar.py
# (import verificado sem side-effects: só constantes + logging local)
_spec = importlib.util.spec_from_file_location("publicar", Path(__file__).parent / "publicar.py")
_pub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_pub)
gerar_relacionados_html = _pub.gerar_relacionados_html

RE_H1      = re.compile(r'<h1 class="artigo-titulo"[^>]*>(.*?)</h1>', re.DOTALL)
RE_TEMA    = re.compile(r'<a class="artigo-tema" href="/temas/([^"]+?)(?:\.html)?">([^<]+)</a>')
# Aceita h2 (padrão atual) e h3 (template de abril/2026); normaliza para h2
RE_HEADING = re.compile(r'(<section class="relacionados">\s*)<h[23]>Artigos relacionados</h[23]>')
RE_LISTA   = re.compile(r'(<div class="relacionados-lista">)(.*?)(</div>)', re.DOTALL)


def analisar(path: Path, indice: list):
    """Fase 1: monta o novo HTML. Retorna (novo_html, info) ou levanta ValueError."""
    html = path.read_text(encoding="utf-8")
    slug = path.stem

    m_tema = RE_TEMA.search(html)
    if not m_tema:
        raise ValueError("tema_slug não extraível (link .artigo-tema ausente)")
    tema_slug = m_tema.group(1)

    m_h1 = RE_H1.search(html)
    titulo = re.sub(r"\s+", " ", m_h1.group(1)).strip() if m_h1 else ""

    m_lista = RE_LISTA.search(html)
    if not m_lista:
        raise ValueError("bloco .relacionados-lista não encontrado")
    # Checagem defensiva: a regex não pode ter alcançado a seção seguinte
    if "<section" in m_lista.group(2) or "Sobre os autores" in m_lista.group(2):
        raise ValueError("regex de .relacionados-lista capturou além do bloco (estrutura inesperada)")

    tem_heading_antigo = bool(RE_HEADING.search(html))
    if not tem_heading_antigo and "<h2>Continue lendo</h2>" not in html:
        raise ValueError("nem 'Artigos relacionados' nem 'Continue lendo' no bloco")

    artigo_fake = {"slug": slug, "tema_slug": tema_slug, "titulo": titulo}
    bloco_novo = gerar_relacionados_html(artigo_fake, indice)
    usou_fallback = any(a.get("slug") in bloco_novo and a.get("tema_slug") != tema_slug
                        for a in indice)

    novo_html = html
    if tem_heading_antigo:
        novo_html = RE_HEADING.sub(r"\g<1><h2>Continue lendo</h2>", novo_html, count=1)
    novo_html = RE_LISTA.sub(
        lambda m: m.group(1) + "\n        " + bloco_novo + "\n      " + m.group(3),
        novo_html, count=1)

    n_links = bloco_novo.count("<li>")
    info = {"slug": slug, "tema_slug": tema_slug, "links": n_links,
            "fallback": usou_fallback, "mudou": novo_html != html,
            "bloco_antes": m_lista.group(2).strip()[:120], "bloco_depois": bloco_novo}
    return novo_html, info


def main():
    parser = argparse.ArgumentParser(description="Backfill Camada 3 GEO (Continue lendo)")
    parser.add_argument("--dry-run", action="store_true", help="Analisa sem gravar")
    parser.add_argument("--esperado", type=int, default=83, help="Contagem esperada de artigos")
    args = parser.parse_args()

    indice = json.loads(INDICE_JSON.read_text(encoding="utf-8"))
    arquivos = sorted(p for p in ARTIGOS_DIR.glob("*.html")
                      if p.name not in ("index.html", "indice.html"))
    print(f"Artigos encontrados: {len(arquivos)} (esperado: {args.esperado}) | índice: {len(indice)}")
    if len(arquivos) != args.esperado:
        sys.exit(f"HARD-FAIL: contagem {len(arquivos)} != esperado {args.esperado}.")

    t0 = time.time()
    resultados, erros = [], []
    for path in arquivos:
        try:
            novo_html, info = analisar(path, indice)
            resultados.append((path, novo_html, info))
        except Exception as e:
            erros.append((path.name, str(e)))
            print(f"  [ERRO] {path.name}: {e}")

    n_fallback = sum(1 for _, _, i in resultados if i["fallback"])
    n_sem_3 = sum(1 for _, _, i in resultados if i["links"] != 3)
    print(f"\nAnalisados: {len(resultados)} OK, {len(erros)} com erro | fallback: {n_fallback} | com ≠3 links: {n_sem_3}")
    if erros:
        sys.exit(f"HARD-FAIL: {len(erros)} artigo(s) com erro — NADA foi gravado.")
    if len(resultados) != args.esperado:
        sys.exit("HARD-FAIL: contagem processada difere do esperado — NADA foi gravado.")

    if args.dry_run:
        print("\n[DRY-RUN] Nenhum arquivo gravado. Amostras:")
        amostras = [resultados[0], resultados[len(resultados)//2],
                    next(((p, h, i) for p, h, i in resultados if i["fallback"]), resultados[-1])]
        for path, _, info in amostras:
            print(f"\n── {info['slug']} (tema: {info['tema_slug']}, fallback: {info['fallback']}) ──")
            print(f"  ANTES : {info['bloco_antes']}")
            print(f"  DEPOIS: {info['bloco_depois']}")
        return

    gravados = 0
    for path, novo_html, info in resultados:
        if info["mudou"]:
            path.write_text(novo_html, encoding="utf-8")
            gravados += 1
    print(f"\nConcluído: {gravados}/{args.esperado} gravados ({args.esperado - gravados} já estavam corretos) em {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
