#!/bin/zsh
# verificar_e_rodar.sh — Watchdog (Direção 1: 3x/semana, sem evergreen, 3 tentativas/dia)
#
# Roda a cada 30 min via launchd. Só dispara o pipeline se:
#   1. Hoje é dia de publicação (config/blog.json -> dias_publicacao)
#   2. Ainda não publicou de fato hoje (artigos/indice.json)
#   3. Tentativas do dia < 3 (marcador dados/tentativas_<DATA>.json)
#   4. Está dentro de uma das janelas (manha/tarde/noite) ainda não tentada
#   5. Tem conexão com a internet
# O registro da tentativa é feito pelo rodar_diario.sh (fonte única — Opção A).

cd "$(dirname "$0")/.." || exit 1
PASTA="$(pwd)"

# 1. Gate de dia da semana
DIA_HOJE=$(date +%u)
DIAS_VALIDOS=$(python3 -c "
import json
mapa = {'seg':1,'ter':2,'qua':3,'qui':4,'sex':5,'sab':6,'dom':7}
cfg = json.load(open('$PASTA/config/blog.json'))
print(','.join(str(mapa[d]) for d in cfg.get('dias_publicacao', []) if d in mapa))
")
if ! echo ",$DIAS_VALIDOS," | grep -q ",$DIA_HOJE,"; then
  exit 0
fi

# 2. Já publicou de fato hoje?
HOJE=$(date +%Y-%m-%d)
if [ -f artigos/indice.json ] && grep -q "$HOJE" artigos/indice.json; then
  exit 0
fi

# 3. Quantas tentativas hoje?
MARCADOR="dados/tentativas_${HOJE}.json"
TENTATIVAS=$(python3 -c "
import json
try:
    d = json.load(open('$MARCADOR'))
    print(len(d.get('tentativas', [])))
except FileNotFoundError:
    print(0)
")
if [ "$TENTATIVAS" -ge 3 ]; then
  exit 0
fi

# 4. Janela atual
HORA=$(date +%H)
case "$HORA" in
  06|07|08) JANELA="manha" ;;
  12|13|14) JANELA="tarde" ;;
  17|18|19) JANELA="noite" ;;
  *) exit 0 ;;
esac

# 5. Janela já tentada hoje?
JA_TENTOU=$(python3 -c "
import json
try:
    d = json.load(open('$MARCADOR'))
    print('sim' if any(t.get('janela') == '$JANELA' for t in d.get('tentativas', [])) else 'nao')
except FileNotFoundError:
    print('nao')
")
if [ "$JA_TENTOU" = "sim" ]; then
  exit 0
fi

# 6. Internet disponível?
if ! curl -s --max-time 5 https://8.8.8.8 > /dev/null 2>&1; then
  exit 0
fi

# 7. Dispara o pipeline (rodar_diario.sh registra a tentativa no marcador)
./rodar_diario.sh
