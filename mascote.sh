#!/usr/bin/env bash
# mascote.sh iniciar | parar | reiniciar | status | personalizar | falar "texto" [item] | nevar | poder [nome]
#            | config chave valor | jogar | adicionar [modelo] [nome] | lutar [nome] [nome] | remover nome
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
PORTA="${MASCOTE_PORTA:-47900}"
URL="http://127.0.0.1:$PORTA"
LOG="${XDG_RUNTIME_DIR:-/tmp}/mascote-tx-$PORTA.log"
PID="${XDG_RUNTIME_DIR:-/tmp}/mascote-tx-$PORTA.pid"

case "${1:-iniciar}" in
  iniciar|personalizar)
    if curl -sf "$URL/" >/dev/null; then
      [ "$1" = personalizar ] && { "$0" parar; sleep 1; } || { echo "já está rodando"; exit 0; }
    fi
    extra=""; [ "${1:-}" = personalizar ] && extra="--personalizar"
    GDK_BACKEND=x11 DISPLAY="${DISPLAY:-:0}" nohup python3 "$DIR/mascote.py" $extra >"$LOG" 2>&1 &
    echo $! >"$PID"
    echo "mascote iniciado (log: $LOG)";;
  parar) if [ -f "$PID" ] && kill "$(cat "$PID")" 2>/dev/null; then echo "parado"; else echo "não estava rodando"; fi; rm -f "$PID";;
  reiniciar) "$0" parar || true; sleep 1; "$0" iniciar;;
  status) curl -s "$URL/" || echo "parado"; echo;;
  falar)
    python3 -c 'import json,sys; print(json.dumps({"texto": sys.argv[1], "item": sys.argv[2] if len(sys.argv) > 2 else None}))' "${2:-Ho ho ho!}" ${3:-} |
      curl -s -X POST "$URL/falar" -H 'Content-Type: application/json' -d @- >/dev/null;;
  poder) curl -s -X POST "$URL/falar" -d "{\"acao\":\"poder\",\"poder\":\"${2:-}\"}" >/dev/null;;
  jogar) curl -s -X POST "$URL/jogar" -d '{}' >/dev/null;;
  adicionar) curl -s -X POST "$URL/adicionar" -d "{\"modelo\":\"${2:-}\",\"nome\":\"${3:-}\"}" >/dev/null;;
  lutar) curl -s -X POST "$URL/lutar" -d "{\"a\":\"${2:-}\",\"b\":\"${3:-}\"}" >/dev/null;;
  remover) curl -s -X POST "$URL/remover" -d "{\"mascote\":\"${2:?nome do personagem}\"}" >/dev/null;;
  nevar) curl -s -X POST "$URL/falar" -d '{"acao":"nevar"}' >/dev/null;;
  config)
    python3 -c 'import json,sys; v=sys.argv[2]
try: v=json.loads(v)
except ValueError: pass
print(json.dumps({sys.argv[1]: v}))' "$2" "$3" | curl -s -X POST "$URL/config" -d @- >/dev/null;;
  *) echo "uso: $0 iniciar|parar|reiniciar|status|personalizar|falar \"texto\" [item]|nevar|poder [rajada|explosao|teleporte|superpulo|aura|nevasca]|config chave valor|jogar|adicionar [modelo] [nome]|lutar [nome] [nome]|remover nome"; exit 1;;
esac
