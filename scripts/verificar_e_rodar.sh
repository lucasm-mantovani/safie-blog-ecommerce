#!/bin/zsh
# verificar_e_rodar.sh — Watchdog do pipeline diário
#
# Roda a cada 30 minutos (via launchd).
# Só executa o pipeline se:
#   1. Ainda não gerou artigo hoje
#   2. Tem conexão com a internet

PASTA="$HOME/CLAUDE/Blogs-SAFIE/Blog-ecommerce"
INDICE="$PASTA/artigos/indice.json"
LOG="$PASTA/logs/watchdog_$(date +%Y-%m-%d).log"
HOJE=$(date +%Y-%m-%d)

echo "[$(date '+%H:%M:%S')] Watchdog verificando..." >> "$LOG"

# ── 1. Verificar se já gerou artigo hoje ──────────────────────────
if [ -f "$INDICE" ]; then
  if grep -q "\"$HOJE" "$INDICE" 2>/dev/null; then
    echo "[$(date '+%H:%M:%S')] Artigo de hoje já publicado. Nada a fazer." >> "$LOG"
    exit 0
  fi
fi

# ── 2. Verificar conexão com a internet ───────────────────────────
if ! curl -s --max-time 5 https://8.8.8.8 > /dev/null 2>&1; then
  echo "[$(date '+%H:%M:%S')] Sem internet. Tentará novamente em 30 minutos." >> "$LOG"
  exit 0
fi

# ── 3. Tudo certo — rodar o pipeline ─────────────────────────────
echo "[$(date '+%H:%M:%S')] Artigo pendente + internet disponível. Iniciando pipeline..." >> "$LOG"
/bin/zsh "$PASTA/rodar_diario.sh"
echo "[$(date '+%H:%M:%S')] Pipeline concluído." >> "$LOG"
