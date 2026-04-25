"""
gerar_artigo.py — Fase 2 do pipeline diário

Lê dados/noticia_selecionada.json e gera um artigo completo via Claude API.
Salva o resultado em dados/artigo_gerado.json.

Uso:
  python3 scripts/gerar_artigo.py
  python3 scripts/gerar_artigo.py --noticia dados/noticia_selecionada.json
"""

import json
import os
import sys
import re
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE           = Path(__file__).resolve().parent.parent
CONFIG_BLOG    = BASE / "config" / "blog.json"
CONFIG_TEMAS   = BASE / "config" / "temas.json"
NOTICIA_PATH   = BASE / "dados" / "noticia_selecionada.json"
ARTIGO_PATH    = BASE / "dados" / "artigo_gerado.json"
LOG_DIR        = BASE / "logs"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(exist_ok=True)
hoje = datetime.now().strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"geracao_{hoje}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Credenciais ───────────────────────────────────────────────────────────────
load_dotenv(BASE / ".env")
load_dotenv(Path.home() / ".zshrc", override=False)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# ── Helpers ───────────────────────────────────────────────────────────────────

def ler_json(caminho, padrao):
    if Path(caminho).exists():
        try:
            return json.loads(Path(caminho).read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Erro ao ler {caminho}: {e}")
    return padrao


def salvar_json(caminho, dados):
    Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def gerar_slug(titulo: str) -> str:
    slug = titulo.lower()
    for de, para in [("ã","a"),("â","a"),("á","a"),("à","a"),("ê","e"),("é","e"),("è","e"),
                     ("í","i"),("ì","i"),("ô","o"),("ó","o"),("õ","o"),("ò","o"),
                     ("ú","u"),("ù","u"),("ç","c"),("ñ","n")]:
        slug = slug.replace(de, para)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug[:80]


def contar_palavras(texto: str) -> int:
    return len(texto.split())


def estimar_tempo_leitura(texto: str) -> int:
    return max(1, round(contar_palavras(texto) / 200))


# ── System prompt — lido do config ───────────────────────────────────────────

def construir_system_prompt(config_blog: dict) -> str:
    nome      = config_blog.get("nome", "SAFIE Blog")
    descricao = config_blog.get("descricao", "direito e contabilidade para empresas")
    url       = config_blog.get("url_completa", "")

    return f"""Você é um especialista em {descricao} no Brasil, escrevendo para o blog {nome} ({url}).

Seus artigos seguem o estilo SAFIE: técnico, direto, acessível para empresários e profissionais (não apenas advogados), sem juridiquês excessivo, sem clichês como "no mundo dinâmico" ou "cada vez mais".

Regras obrigatórias:
- Tom institucional, sério, mas compreensível
- Nunca use travessão (—) — use vírgulas, parênteses ou ponto-e-vírgula
- Dados e números concretos sempre que possível
- Citar a fonte original com atribuição clara
- Mínimo 800 palavras, máximo 1.500 palavras no corpo do artigo
- Português brasileiro correto"""


# ── Prompt de geração ─────────────────────────────────────────────────────────

def montar_prompt(noticia: dict, config_blog: dict) -> str:
    nome_blog    = config_blog.get("nome", "SAFIE Blog")
    tema_nome    = noticia.get("tema_nome", "")
    titulo_fonte = noticia.get("titulo", "")
    url_fonte    = noticia.get("url", "")
    fonte_nome   = noticia.get("fonte", "")
    resumo_fonte = noticia.get("resumo", "")
    origem       = noticia.get("origem", "rss")
    data_hoje    = datetime.now().strftime("%d/%m/%Y")

    if origem == "evergreen":
        contexto = f"""Este artigo é do tipo evergreen (atemporal). Escreva sobre o tema "{tema_nome}" de forma completa e educativa, sem mencionar nenhum evento específico recente."""
        referencia = ""
    else:
        contexto = f"""Baseie o artigo na seguinte notícia:

Título da notícia: {titulo_fonte}
Fonte: {fonte_nome}
URL: {url_fonte}
Trecho/resumo: {resumo_fonte[:500] if resumo_fonte else '(sem resumo disponível)'}

Apresente a notícia como ponto de partida e aprofunde a análise jurídica e contábil."""
        referencia = f"\n- Fonte original: [{fonte_nome}]({url_fonte})" if url_fonte else ""

    return f"""Escreva um artigo completo para o blog {nome_blog} sobre o tema "{tema_nome}".

Data de publicação: {data_hoje}

{contexto}

Retorne APENAS um objeto JSON válido, sem markdown, sem texto fora do JSON.

{{
  "titulo": "(máximo 60 caracteres, palavra-chave principal do tema, em português)",
  "meta_description": "(máximo 155 caracteres, resumo atraente para o Google)",
  "resumo_executivo": "(2 a 3 frases diretas, sem quebra de linha literal)",
  "introducao": "(2 a 3 parágrafos em HTML com tags <p>; use aspas simples dentro do HTML)",
  "contexto_juridico": "(3 a 4 parágrafos em HTML com <p> e <h2>; use aspas simples dentro do HTML)",
  "impacto_pratico": "(2 a 3 parágrafos em HTML com <p>; use aspas simples dentro do HTML)",
  "consideracoes_finais": "(1 a 2 parágrafos em HTML com <p>)",
  "faq": [
    {{"pergunta": "...", "resposta": "..."}},
    {{"pergunta": "...", "resposta": "..."}},
    {{"pergunta": "...", "resposta": "..."}}
  ],
  "referencias": ["{referencia.strip()}"]
}}

Regras obrigatorias:
- Titulo: maximo 60 caracteres
- meta_description: maximo 155 caracteres
- FAQ: entre 3 e 5 perguntas reais que usuarios fariam ao Google ou a uma IA
- Todo o conteudo em portugues brasileiro
- Nao use travessao (use virgulas ou parenteses)
- Paragrafos curtos: maximo 3 linhas cada
- CRITICO PARA JSON VALIDO: nenhuma string pode conter quebra de linha literal. Use apenas uma linha por campo de texto. Em HTML use <br> se precisar de quebra dentro de uma tag"""


# ── Chamada à API do Claude ───────────────────────────────────────────────────

def chamar_claude(prompt: str, system_prompt: str) -> str:
    import time as _time

    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY não configurada.")
        sys.exit(1)

    log.info("[Claude] Gerando artigo...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    for tentativa in range(1, 4):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            resposta = message.content[0].text
            log.info(f"[Claude] Tokens usados — input: {message.usage.input_tokens}, output: {message.usage.output_tokens}")
            return resposta
        except anthropic.APIStatusError as e:
            if e.status_code == 529 and tentativa < 3:
                espera = 60 * tentativa
                log.warning(f"[Claude] API sobrecarregada. Tentativa {tentativa}/3. Aguardando {espera}s...")
                _time.sleep(espera)
            else:
                raise


# ── Parse da resposta JSON ────────────────────────────────────────────────────

def extrair_json(texto: str) -> dict:
    texto = texto.strip()

    # Remove blocos markdown se houver
    if "```" in texto:
        linhas = texto.split("\n")
        linhas = [l for l in linhas if not l.strip().startswith("```")]
        texto = "\n".join(linhas)

    inicio = texto.find("{")
    fim    = texto.rfind("}") + 1
    if inicio == -1 or fim == 0:
        raise ValueError("JSON não encontrado na resposta do Claude")

    json_str = texto[inicio:fim]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Tenta sanitizar: remove quebras de linha literais dentro de strings JSON
        import re
        # Substitui newlines dentro de strings por espaço
        def sanitizar_string_json(m):
            return m.group(0).replace("\n", " ").replace("\r", " ")
        json_str_limpo = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', sanitizar_string_json, json_str, flags=re.DOTALL)
        return json.loads(json_str_limpo)


# ── Montagem do artigo ────────────────────────────────────────────────────────

def montar_artigo_completo(dados_claude: dict, noticia: dict, config_blog: dict) -> dict:
    data_iso  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _meses    = ["janeiro","fevereiro","março","abril","maio","junho",
                 "julho","agosto","setembro","outubro","novembro","dezembro"]
    _now      = datetime.now()
    data_fmt  = f"{_now.day} de {_meses[_now.month - 1]} de {_now.year}"
    ano       = str(_now.year)
    titulo    = dados_claude.get("titulo", noticia.get("titulo", ""))
    slug_data = datetime.now().strftime("%Y-%m-%d")
    slug      = f"{slug_data}-{gerar_slug(titulo)}"
    url_blog  = config_blog.get("url_completa", "")
    nome_blog = config_blog.get("nome", "SAFIE Blog")

    corpo_html = (
        dados_claude.get("introducao", "") +
        "\n\n<h2>Contexto jurídico e regulatório</h2>\n" +
        dados_claude.get("contexto_juridico", "") +
        "\n\n<h2>Impacto prático</h2>\n" +
        dados_claude.get("impacto_pratico", "") +
        "\n\n<h2>Considerações finais</h2>\n" +
        dados_claude.get("consideracoes_finais", "")
    )

    faq_html = ""
    for item in dados_claude.get("faq", []):
        pergunta = item.get("pergunta", "")
        resposta = item.get("resposta", "")
        faq_html += (
            f'<div class="faq-item" itemscope itemtype="https://schema.org/Question">\n'
            f'  <p class="faq-pergunta" itemprop="name">{pergunta}</p>\n'
            f'  <div class="faq-resposta" itemscope itemtype="https://schema.org/Answer">'
            f'<span itemprop="text">{resposta}</span></div>\n'
            f'</div>\n'
        )

    refs = dados_claude.get("referencias", [])
    if noticia.get("url") and noticia.get("fonte"):
        ref_original = f"[{noticia['fonte']}]({noticia['url']})"
        if ref_original not in " ".join(refs):
            refs.insert(0, ref_original)

    refs_html = "<ul>\n"
    for ref in refs:
        if not ref or not ref.strip():
            continue
        ref_text = ref.strip().lstrip("-").strip()
        match = re.search(r"\[(.+?)\]\((.+?)\)", ref_text)
        if match:
            link_text = match.group(1)
            link_url = match.group(2)
            link_html = f'<a href="{link_url}" target="_blank" rel="noopener">{link_text}</a>'
            prefix = ref_text[:match.start()].strip().rstrip(":").strip()
            if prefix:
                refs_html += f'<li><span class="ref-label">{prefix}:</span> {link_html}</li>\n'
            else:
                refs_html += f'<li>{link_html}</li>\n'
        else:
            refs_html += f'<li>{ref_text}</li>\n'
    refs_html += "</ul>\n"

    faq_schema = [
        {
            "@type": "Question",
            "name": item.get("pergunta", ""),
            "acceptedAnswer": {
                "@type": "Answer",
                "text": item.get("resposta", "")
            }
        }
        for item in dados_claude.get("faq", [])
    ]

    schema = [
        {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": titulo,
            "description": dados_claude.get("meta_description", ""),
            "datePublished": data_iso,
            "dateModified": data_iso,
            "author": {"@type": "Organization", "name": "SAFIE", "url": "https://safie.com.br"},
            "publisher": {"@type": "Organization", "name": nome_blog, "url": url_blog},
            "url": f"{url_blog}/artigos/{slug}.html",
            "articleSection": noticia.get("tema_nome", ""),
            "inLanguage": "pt-BR",
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq_schema,
        }
    ]

    relacionados_html = (
        '<p style="color:var(--cinza);font-size:0.9rem;">Mais artigos em breve.</p>'
    )

    return {
        "slug": slug,
        "titulo": titulo,
        "meta_titulo": f"{titulo} — {nome_blog}",
        "meta_description": dados_claude.get("meta_description", ""),
        "canonical_url": f"{url_blog}/artigos/{slug}.html",
        "data_iso": data_iso,
        "data_formatada": data_fmt,
        "ano": ano,
        "tempo_leitura": estimar_tempo_leitura(corpo_html),
        "tema_nome": noticia.get("tema_nome", ""),
        "tema_slug": noticia.get("tema_slug", ""),
        "resumo_executivo": dados_claude.get("resumo_executivo", ""),
        "conteudo": corpo_html,
        "faq_html": faq_html,
        "referencias_html": refs_html,
        "relacionados_html": relacionados_html,
        "schema_json": json.dumps(schema, ensure_ascii=False, indent=2),
        "palavras_corpo": contar_palavras(corpo_html),
        "noticia_origem": noticia,
        "blog_nome": nome_blog,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main(noticia_path: Path = NOTICIA_PATH) -> dict:
    log.info("=" * 60)
    log.info("GERAR ARTIGO — início")

    noticia     = ler_json(noticia_path, {})
    config_blog = ler_json(CONFIG_BLOG, {})

    if not noticia:
        log.error(f"Nenhuma notícia encontrada em {noticia_path}")
        sys.exit(1)

    log.info(f"Notícia: {noticia.get('titulo', '(sem título)')}")
    log.info(f"Tema: {noticia.get('tema_nome', '')}")

    system_prompt = construir_system_prompt(config_blog)
    prompt        = montar_prompt(noticia, config_blog)
    resposta      = chamar_claude(prompt, system_prompt)

    log.info("[Claude] Parseando resposta...")
    dados_claude = extrair_json(resposta)

    artigo = montar_artigo_completo(dados_claude, noticia, config_blog)

    log.info(f"Artigo gerado: '{artigo['titulo']}' ({artigo['palavras_corpo']} palavras)")
    log.info(f"Slug: {artigo['slug']}")

    salvar_json(ARTIGO_PATH, artigo)
    log.info(f"Artigo salvo em {ARTIGO_PATH}")
    log.info("=" * 60)

    return artigo


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera artigo via Claude API")
    parser.add_argument("--noticia", default=str(NOTICIA_PATH), help="Caminho para o JSON da notícia")
    args = parser.parse_args()

    artigo = main(noticia_path=Path(args.noticia))
    print(f"\nArtigo gerado: {artigo['titulo']}")
    print(f"Palavras: {artigo['palavras_corpo']}")
    print(f"Slug: {artigo['slug']}")
