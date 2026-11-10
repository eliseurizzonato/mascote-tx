#!/usr/bin/env bash
# Gera dist/mascote-tx.tar.gz para compartilhar (sem prints, configurações nem cache).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/mascote-tx" "$DIR/dist"
cp -r "$DIR/mascote.py" "$DIR/mascote.sh" "$DIR/instalar.sh" "$DIR/instalar_hooks.py" \
  "$DIR/personagens" "$DIR/README.md" "$TMP/mascote-tx/"
tar -czf "$DIR/dist/mascote-tx.tar.gz" -C "$TMP" mascote-tx
echo "$DIR/dist/mascote-tx.tar.gz"
