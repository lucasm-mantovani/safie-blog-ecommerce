#!/bin/zsh
# rodar_diario.sh — Orquestrador do pipeline diário
# Executado às 7h30 via launchd
# Fluxo: buscar_noticia → gerar_artigo → publicar

set -e

PASTA="$HOME/CLAUDE/Blog-Ecommerce"
LOG="$PASTA/logs/pipeline_$(date +%Y-%m-%d).log"

echo "=======================================" >> "$LOG"
echo "PIPELINE INICIADO: $(date)" >> "$LOG"
echo "=======================================" >> "$LOG"

cd "$PASTA"

source "$HOME/.zshrc" 2>/dev/null || true
source "$PASTA/.env" 2>/dev/null || true

echo "[1/3] Buscando notícia..." >> "$LOG"
python3 scripts/buscar_noticia.py >> "$LOG" 2>&1

echo "[2/3] Gerando artigo..." >> "$LOG"
python3 scripts/gerar_artigo.py >> "$LOG" 2>&1

echo "[3/3] Publicando..." >> "$LOG"
python3 scripts/publicar.py >> "$LOG" 2>&1

echo "PIPELINE CONCLUÍDO: $(date)" >> "$LOG"
echo "=======================================" >> "$LOG"
