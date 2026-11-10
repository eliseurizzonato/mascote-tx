#!/usr/bin/env bash
# Instala o Mascote TX para o seu usuário (sem sudo).
#   ./instalar.sh             instala, inicia com o computador e abre o mascote
#   ./instalar.sh --remover   desinstala (mantém suas configurações em ~/.config/mascote-tx)
set -euo pipefail
ORIGEM="$(cd "$(dirname "$0")" && pwd)"
DESTINO="${XDG_DATA_HOME:-$HOME/.local/share}/mascote-tx"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/mascote-tx.desktop"
MENU="${XDG_DATA_HOME:-$HOME/.local/share}/applications/mascote-tx.desktop"

if [ "${1:-}" = "--remover" ]; then
  [ -x "$DESTINO/mascote.sh" ] && "$DESTINO/mascote.sh" parar || true
  if [ -f "$HOME/.claude/settings.json" ] && [ -f "$DESTINO/instalar_hooks.py" ]; then
    python3 "$DESTINO/instalar_hooks.py" --remover
  fi
  rm -rf "$DESTINO" "$AUTOSTART" "$MENU"
  echo "Mascote TX removido. Suas configurações continuam em ~/.config/mascote-tx."
  exit 0
fi

if ! python3 -c 'import gi, cairo; gi.require_version("Gtk", "3.0"); gi.require_foreign("cairo"); from gi.repository import Gtk' 2>/dev/null; then
  echo "Faltam bibliotecas do Python/GTK. No Ubuntu, Mint ou Debian, rode:"
  echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0"
  echo "No Fedora: sudo dnf install python3-gobject gtk3"
  echo "Depois rode ./instalar.sh de novo."
  exit 1
fi
command -v curl >/dev/null || { echo "Instale o curl (sudo apt install curl) e rode de novo."; exit 1; }
[ "${XDG_SESSION_TYPE:-x11}" = "wayland" ] &&
  echo "Aviso: sua sessão é Wayland. O mascote roda via XWayland; se ele não aparecer em cima da barra, entre numa sessão X11 (Xorg)."

mkdir -p "$DESTINO" "$(dirname "$AUTOSTART")" "$(dirname "$MENU")"
[ "$ORIGEM" = "$(cd "$DESTINO" && pwd)" ] || cp -r "$ORIGEM/mascote.py" "$ORIGEM/mascote.sh" "$ORIGEM/instalar_hooks.py" "$ORIGEM/instalar.sh" \
  "$ORIGEM/personagens" "$ORIGEM/README.md" "$DESTINO/"
chmod +x "$DESTINO/mascote.sh" "$DESTINO/instalar.sh"

for arq in "$AUTOSTART" "$MENU"; do
  cat >"$arq" <<DESK
[Desktop Entry]
Type=Application
Name=Mascote TX
Comment=Mascote de Natal que anda pela tela e reage ao Claude Code
Exec=$DESTINO/mascote.sh iniciar
Icon=face-smile
Categories=Utility;
X-GNOME-Autostart-enabled=true
DESK
done

if [ -d "$HOME/.claude" ]; then
  resp="${MASCOTE_HOOKS:-}"
  if [ -z "$resp" ] && [ -t 0 ]; then
    read -r -p "Ligar o mascote ao seu Claude Code (ele reage ao que o Claude faz)? [S/n] " resp
  fi
  case "${resp:-s}" in
    [nN]*) echo "Ok, sem ligação com o Claude Code (dá para ligar depois: python3 $DESTINO/instalar_hooks.py)";;
    *) python3 "$DESTINO/instalar_hooks.py";;
  esac
fi

"$DESTINO/mascote.sh" iniciar
echo
echo "Pronto! O Mascote TX abre sozinho quando você liga o computador e está no menu de aplicativos."
echo "Clique direito nele para personalizar, adicionar personagens e lutar."
echo "Comandos: $DESTINO/mascote.sh iniciar|parar|personalizar|adicionar|lutar ..."
