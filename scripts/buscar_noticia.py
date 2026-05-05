"""
buscar_noticia.py — Fase 3 do pipeline diário

Fluxo:
  1. Para cada tema em config/temas.json, busca notícias via Apify Google News Scraper
  2. Filtra resultados das últimas 48h
  3. Seleciona a notícia mais relevante (sem repetir histórico dos últimos 15 dias)
  4. Se Apify falhar (limite esgotado ou erro) → fallback para RSS
  5. Se RSS também falhar → retorna tema evergreen de config/temas.json
  6. Registra consumo em dados/consumo_apify.json

Uso:
  python3 scripts/buscar_noticia.py
  python3 scripts/buscar_noticia.py --forcar-rss   (pula Apify, usa só RSS)
  python3 scripts/buscar_noticia.py --tema tributacao-ecommerce  (busca 1 tema)
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

import requests
import feedparser
from dotenv import load_dotenv
from apify_client import ApifyClient

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent
CONFIG_BLOG    = BASE / "config" / "blog.json"
CONFIG_TEMAS   = BASE / "config" / "temas.json"
CONFIG_FONTES  = BASE / "config" / "fontes.json"
HISTORICO      = BASE / "dados" / "historico_noticias.json"
CONSUMO_APIFY  = BASE / "dados" / "consumo_apify.json"
LOG_DIR        = BASE / "logs"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR.mkdir(exist_ok=True)
hoje = datetime.now().strftime("%Y-%m-%d")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"busca_{hoje}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── Carregar .env ─────────────────────────────────────────────────────────────
load_dotenv(BASE / ".env")
load_dotenv(Path.home() / ".zshrc", override=False)

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")

# Termos jurídicos e regulatórios genéricos (comuns a todos os blogs SAFIE)
PALAVRAS_JURIDICAS_BASE = [
    "receita federal", "regulação", "lei", "instrução normativa",
    "resolução", "normativo", "tributação", "imposto", "compliance",
    "banco central", "decreto", "portaria", "medida provisória",
]


# ── Helpers de arquivo ────────────────────────────────────────────────────────

def ler_json(caminho: Path, padrao):
    if caminho.exists():
        try:
            return json.loads(caminho.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Erro ao ler {caminho}: {e}")
    return padrao


def salvar_json(caminho: Path, dados):
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Controle de consumo Apify ─────────────────────────────────────────────────

def registrar_consumo(query: str, resultados: int, creditos: int = 0, erro: str = ""):
    dados = ler_json(CONSUMO_APIFY, {"registros": []})
    dados["registros"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "resultados": resultados,
        "creditos_consumidos": creditos,
        "erro": erro,
    })
    salvar_json(CONSUMO_APIFY, dados)


def resumo_consumo():
    dados = ler_json(CONSUMO_APIFY, {"registros": []})
    registros = dados.get("registros", [])
    total = sum(r.get("creditos_consumidos", 0) for r in registros)
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    hoje_count = sum(1 for r in registros if r.get("timestamp", "").startswith(hoje_str))
    log.info(f"Consumo Apify — chamadas hoje: {hoje_count} | créditos acumulados: {total}")


# ── Histórico de notícias ─────────────────────────────────────────────────────

def ja_publicado(url: str, tema_slug: str,
                 dias_url: int = 15, dias_tema: int = 3) -> bool:
    """
    Retorna True se URL ou tema_slug já foi publicado dentro
    de sua respectiva janela de tempo.
    - dias_url: janela em dias para bloquear mesma URL (default 15)
    - dias_tema: janela em dias para espaçar mesmo tema (default 3)
    Entradas com url_fonte ou tema_slug vazios são ignoradas.
    Entradas com data_publicacao inválida são ignoradas.
    """
    dados = ler_json(HISTORICO, {"noticias": []})
    agora = datetime.now(timezone.utc)
    limite_url = agora - timedelta(days=dias_url)
    limite_tema = agora - timedelta(days=dias_tema)

    for item in dados.get("noticias", []):
        item_url = item.get("url_fonte", "")
        item_tema = item.get("tema_slug", "")
        data_str = item.get("data_publicacao", "")

        try:
            data_pub = datetime.fromisoformat(data_str)
        except (ValueError, TypeError):
            continue

        if url and item_url == url and data_pub >= limite_url:
            return True

        if tema_slug and item_tema == tema_slug and data_pub >= limite_tema:
            return True

    return False


def registrar_noticia_publicada(noticia: dict):
    dados = ler_json(HISTORICO, {"noticias": []})
    dados["noticias"].append({
        "data_publicacao": datetime.now(timezone.utc).isoformat(),
        "titulo_noticia": noticia.get("titulo", ""),
        "url_fonte": noticia.get("url", ""),
        "tema_slug": noticia.get("tema_slug", ""),
    })
    dados["noticias"] = dados["noticias"][-90:]
    salvar_json(HISTORICO, dados)


# ── Apify — Google News Scraper ───────────────────────────────────────────────

def buscar_apify(query: str, apify_ator: str, max_resultados: int = 8) -> List[Dict]:
    if not APIFY_TOKEN or not apify_ator:
        if not APIFY_TOKEN:
            log.info("[Apify] APIFY_TOKEN não configurado. Usando RSS.")
        else:
            log.info("[Apify] apify_ator não configurado em config/blog.json. Usando RSS.")
        return []

    log.info(f"[Apify] Buscando: '{query}' via {apify_ator}")
    try:
        client = ApifyClient(APIFY_TOKEN)
        run_input = {
            "queries": query,
            "maxItemsPerQuery": max_resultados,
            "language": "pt-BR",
            "country": "BR",
            "timeRange": "1d",
        }

        run = client.actor(apify_ator).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

        log.info(f"[Apify] {len(items)} resultado(s) para '{query}'")
        registrar_consumo(query, len(items))
        return items

    except Exception as e:
        msg = str(e)
        if "402" in msg or "payment" in msg.lower() or "credit" in msg.lower():
            log.warning("[Apify] Limite de créditos atingido. Ativando fallback RSS.")
            registrar_consumo(query, 0, 0, erro="limite_atingido")
        elif "401" in msg or "unauthorized" in msg.lower():
            log.warning("[Apify] Token inválido ou expirado.")
            registrar_consumo(query, 0, 0, erro="token_invalido")
        else:
            msg_segura = msg.replace(APIFY_TOKEN, "***") if APIFY_TOKEN else msg
            log.error(f"[Apify] Erro: {msg_segura}")
            registrar_consumo(query, 0, 0, erro=msg_segura)
        return []


def normalizar_apify(item: Dict, tema: Dict) -> Dict:
    return {
        "titulo": item.get("title", ""),
        "url": item.get("url", item.get("link", "")),
        "fonte": item.get("publisher", {}).get("title", "") if isinstance(item.get("publisher"), dict) else item.get("publisher", ""),
        "data": item.get("publishedAt", item.get("date", "")),
        "resumo": item.get("snippet", item.get("description", "")),
        "tema_slug": tema["slug"],
        "tema_nome": tema["nome"],
        "origem": "apify",
    }


# ── RSS fallback ──────────────────────────────────────────────────────────────

def buscar_rss(tema: Dict, fontes: List[Dict]) -> List[Dict]:
    # Usa frases exatas para evitar falsos positivos de palavras genéricas.
    # Cada keyword é buscada como substring literal no texto (title + summary).
    keywords = [kw.lower() for kw in tema.get("palavras_chave", [])]

    limite = datetime.now(timezone.utc) - timedelta(hours=48)
    resultados = []

    for fonte in fontes:
        log.info(f"[RSS] Lendo {fonte['nome']}...")
        try:
            feed = feedparser.parse(fonte["url"])
            for entry in feed.entries:
                texto = (
                    (entry.get("title") or "") + " " +
                    (entry.get("summary") or "")
                ).lower()

                if not any(kw in texto for kw in keywords):
                    continue

                data_entry = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    import time
                    ts = time.mktime(entry.published_parsed)
                    data_entry = datetime.fromtimestamp(ts, tz=timezone.utc)

                if data_entry and data_entry < limite:
                    continue

                resultados.append({
                    "titulo": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "fonte": fonte["nome"],
                    "data": data_entry.isoformat() if data_entry else "",
                    "resumo": entry.get("summary", "")[:300],
                    "tema_slug": tema["slug"],
                    "tema_nome": tema["nome"],
                    "origem": "rss",
                })

        except Exception as e:
            log.warning(f"[RSS] Erro em {fonte['nome']}: {e}")

    log.info(f"[RSS] {len(resultados)} resultado(s) para tema '{tema['nome']}'")
    return resultados


# ── Pontuação de relevância ───────────────────────────────────────────────────

def pontuar_noticia(noticia: dict, fontes_autoridade: Dict[str, int], palavras_juridicas: List[str]) -> float:
    texto = (noticia.get("titulo", "") + " " + noticia.get("resumo", "")).lower()
    pontos = 0.0

    for dominio, score in fontes_autoridade.items():
        if dominio in noticia.get("url", "").lower() or dominio in noticia.get("fonte", "").lower():
            pontos += score
            break

    for palavra in palavras_juridicas:
        if palavra in texto:
            pontos += 2

    data_str = noticia.get("data", "")
    if data_str:
        try:
            data = datetime.fromisoformat(data_str)
            if data.tzinfo is None:
                data = data.replace(tzinfo=timezone.utc)
            horas_atras = (datetime.now(timezone.utc) - data).total_seconds() / 3600
            if horas_atras < 6:
                pontos += 8
            elif horas_atras < 24:
                pontos += 4
        except Exception:
            pass

    if not noticia.get("resumo"):
        pontos -= 3

    return pontos


# ── Seleção da notícia mais relevante ────────────────────────────────────────

def selecionar_melhor(candidatos: List[Dict], fontes_autoridade: Dict, palavras_juridicas: List[str]) -> Optional[Dict]:
    validos = [
        c for c in candidatos
        if c.get("url") and not ja_publicado(c["url"], c.get("tema_slug", ""))
    ]

    if not validos:
        return None

    validos.sort(key=lambda n: pontuar_noticia(n, fontes_autoridade, palavras_juridicas), reverse=True)
    escolhida = validos[0]
    log.info(f"Notícia selecionada: [{escolhida['tema_nome']}] {escolhida['titulo']}")
    return escolhida


# ── Evergreen fallback ────────────────────────────────────────────────────────

def escolher_evergreen(temas_slugs_usados: List[str], temas_evergreen: List[Dict]) -> Dict:
    for tema in temas_evergreen:
        if tema["tema_slug"] not in temas_slugs_usados:
            return tema
    return temas_evergreen[0] if temas_evergreen else {
        "tipo": "evergreen",
        "tema_slug": "geral",
        "tema_nome": "Análise jurídica",
        "titulo": "Conformidade jurídica para empresas digitais no Brasil",
        "resumo": "Guia prático sobre obrigações legais e regulatórias para empresas que operam no ambiente digital.",
        "url": "",
        "fonte": "evergreen",
        "data": "",
        "origem": "evergreen",
    }


# ── Orquestrador principal ────────────────────────────────────────────────────

def main(forcar_rss: bool = False, apenas_tema: str = "") -> Dict:
    log.info("=" * 60)
    log.info("BUSCAR NOTÍCIA — início")
    resumo_consumo()

    config_blog   = ler_json(CONFIG_BLOG, {})
    config_temas  = ler_json(CONFIG_TEMAS, {"temas": [], "temas_evergreen": [], "palavras_juridicas_extras": []})
    config_fontes = ler_json(CONFIG_FONTES, {"rss_feeds": [], "fontes_autoridade": {}})

    temas = config_temas.get("temas", [])
    fontes_rss = config_fontes.get("rss_feeds", [])
    fontes_autoridade = config_fontes.get("fontes_autoridade", {})
    temas_evergreen = config_temas.get("temas_evergreen", [])

    # Combina termos jurídicos base com os específicos do nicho
    palavras_juridicas_extras = config_temas.get("palavras_juridicas_extras", [])
    palavras_juridicas = PALAVRAS_JURIDICAS_BASE + palavras_juridicas_extras

    apify_ator = config_blog.get("apify_ator", "")

    if apenas_tema:
        temas = [t for t in temas if t["slug"] == apenas_tema]
        if not temas:
            log.error(f"Tema '{apenas_tema}' não encontrado em config/temas.json")
            sys.exit(1)

    todos_candidatos = []
    apify_falhou = forcar_rss

    # ── Etapa 1: Apify ──
    if not apify_falhou:
        for tema in temas:
            for query in tema["palavras_chave"][:2]:
                items = buscar_apify(query, apify_ator, max_resultados=5)
                if items is None or (not items and not APIFY_TOKEN):
                    apify_falhou = True
                    break
                for item in items:
                    todos_candidatos.append(normalizar_apify(item, tema))
            if apify_falhou:
                break

    # ── Etapa 2: RSS fallback ──
    if apify_falhou or not todos_candidatos:
        log.info("Ativando fallback RSS...")
        for tema in temas:
            resultados_rss = buscar_rss(tema, fontes_rss)
            todos_candidatos.extend(resultados_rss)

    # ── Etapa 3: Seleção ──
    noticia = selecionar_melhor(todos_candidatos, fontes_autoridade, palavras_juridicas)

    # ── Etapa 4: Evergreen ──
    if not noticia:
        log.warning("Nenhuma notícia nova encontrada. Usando tema evergreen.")
        slugs_usados = [t["slug"] for t in temas]
        noticia = escolher_evergreen(slugs_usados, temas_evergreen)

    log.info("=" * 60)
    log.info(f"RESULTADO FINAL:")
    log.info(f"  Tema:   {noticia.get('tema_nome')}")
    log.info(f"  Título: {noticia.get('titulo')}")
    log.info(f"  Fonte:  {noticia.get('fonte')} ({noticia.get('origem')})")
    log.info(f"  URL:    {noticia.get('url') or '(sem URL — evergreen)'}")
    log.info("=" * 60)

    resultado_path = BASE / "dados" / "noticia_selecionada.json"
    salvar_json(resultado_path, noticia)
    log.info(f"Resultado salvo em {resultado_path}")

    if noticia.get("url"):
        try:
            registrar_noticia_publicada(noticia)
        except Exception as e:
            log.warning(f"[aviso] falha ao registrar histórico: {e}")

    print(json.dumps(noticia, ensure_ascii=False, indent=2))

    return noticia


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Busca notícia para o artigo diário")
    parser.add_argument("--forcar-rss", action="store_true", help="Pular Apify e usar só RSS")
    parser.add_argument("--tema", default="", help="Slug do tema específico")
    args = parser.parse_args()

    main(forcar_rss=args.forcar_rss, apenas_tema=args.tema)
