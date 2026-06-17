#!/bin/zsh
# rodar_diario.sh — Orquestrador do pipeline diário
# Executado às 7h30 via launchd
# Fluxo: buscar_noticia → gerar_artigo → publicar

set -e

PASTA="$HOME/CLAUDE/Blogs-SAFIE/Blog-ecommerce"
LOG="$PASTA/logs/pipeline_$(date +%Y-%m-%d).log"

# ── Gate de dia da semana — Direção 1 (3x/semana) ──
DIA_HOJE=$(date +%u)  # 1=seg … 7=dom
DIAS_VALIDOS=$(python3 -c "
import json
mapa = {'seg':1,'ter':2,'qua':3,'qui':4,'sex':5,'sab':6,'dom':7}
cfg = json.load(open('$PASTA/config/blog.json'))
print(','.join(str(mapa[d]) for d in cfg.get('dias_publicacao', []) if d in mapa))
")
if ! echo ",$DIAS_VALIDOS," | grep -q ",$DIA_HOJE,"; then
  mkdir -p "$PASTA/logs"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Hoje (weekday $DIA_HOJE) nao e dia de publicacao [$DIAS_VALIDOS]. Encerrando." >> "$PASTA/logs/skip_$(date +%Y-%m-%d).log"
  exit 0
fi

echo "=======================================" >> "$LOG"
echo "PIPELINE INICIADO: $(date)" >> "$LOG"
echo "=======================================" >> "$LOG"

cd "$PASTA"

source "$HOME/.zshrc" 2>/dev/null || true
source "$PASTA/.env" 2>/dev/null || true

echo "[1/4] Buscando notícia..." >> "$LOG"
set +e
python3 scripts/buscar_noticia.py >> "$LOG" 2>&1
EXIT_BUSCA=$?
set -e
case $EXIT_BUSCA in
  0)  echo "[$(date '+%H:%M:%S')] Notícia encontrada, prosseguindo." >> "$LOG" ;;
  75)
      echo "[$(date '+%H:%M:%S')] Sem notícia fresca hoje. Registrando tentativa e encerrando." >> "$LOG"
      HOJE=$(date +%Y-%m-%d); HORA=$(date +%H)
      case "$HORA" in
        06|07|08) JANELA="manha" ;;
        12|13|14) JANELA="tarde" ;;
        17|18|19) JANELA="noite" ;;
        *) JANELA="outra" ;;
      esac
      JANELA="$JANELA" HOJE="$HOJE" PASTA="$PASTA" RESULTADO="sem_noticia" python3 -c "
import json, os
from pathlib import Path
from datetime import datetime
marcador = Path(os.environ['PASTA']) / 'dados' / f\"tentativas_{os.environ['HOJE']}.json\"
marcador.parent.mkdir(parents=True, exist_ok=True)
d = json.loads(marcador.read_text()) if marcador.exists() else {'data': os.environ['HOJE'], 'tentativas': []}
d['tentativas'].append({'janela': os.environ['JANELA'], 'hora': datetime.now().strftime('%H:%M'), 'resultado': os.environ['RESULTADO']})
marcador.write_text(json.dumps(d, ensure_ascii=False, indent=2))
hoje = datetime.now()
for f in marcador.parent.glob('tentativas_*.json'):
    try:
        if (hoje - datetime.strptime(f.stem.replace('tentativas_',''), '%Y-%m-%d')).days > 7:
            f.unlink()
    except Exception:
        pass
"
      exit 75 ;;
  *)  echo "[$(date '+%H:%M:%S')] ERRO em buscar_noticia.py (exit $EXIT_BUSCA). Abortando." >> "$LOG"; exit $EXIT_BUSCA ;;
esac

echo "[2/4] Gerando artigo..." >> "$LOG"
python3 scripts/gerar_artigo.py >> "$LOG" 2>&1

echo "[3/4] Otimizando SEO/GEO..." >> "$LOG"
python3 scripts/otimizar_seo.py >> "$LOG" 2>&1

echo "[4/4] Publicando..." >> "$LOG"
python3 scripts/publicar.py >> "$LOG" 2>&1

# Marcador consolidado (Opção A) — registra sucesso
HOJE=$(date +%Y-%m-%d); HORA=$(date +%H)
case "$HORA" in
  06|07|08) JANELA="manha" ;;
  12|13|14) JANELA="tarde" ;;
  17|18|19) JANELA="noite" ;;
  *) JANELA="outra" ;;
esac
JANELA="$JANELA" HOJE="$HOJE" PASTA="$PASTA" python3 -c "
import json, os
from pathlib import Path
from datetime import datetime
marcador = Path(os.environ['PASTA']) / 'dados' / f\"tentativas_{os.environ['HOJE']}.json\"
marcador.parent.mkdir(parents=True, exist_ok=True)
d = json.loads(marcador.read_text()) if marcador.exists() else {'data': os.environ['HOJE'], 'tentativas': []}
d['tentativas'].append({'janela': os.environ['JANELA'], 'hora': datetime.now().strftime('%H:%M'), 'resultado': 'ok'})
marcador.write_text(json.dumps(d, ensure_ascii=False, indent=2))
" >> "$LOG" 2>&1

echo "PIPELINE CONCLUÍDO: $(date)" >> "$LOG"
echo "=======================================" >> "$LOG"
