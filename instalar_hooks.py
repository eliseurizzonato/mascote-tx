#!/usr/bin/env python3
"""Liga o Mascote TX ao Claude Code: adiciona hooks HTTP em ~/.claude/settings.json.

Uso: instalar_hooks.py            (instala; faz backup antes)
     instalar_hooks.py --remover  (tira só os hooks do mascote)
"""
import json
import os
import shutil
import sys
import time

PORTA = int(os.environ.get("MASCOTE_PORTA", "47900"))
URL = f"http://127.0.0.1:{PORTA}/evento"
EVENTOS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Notification",
           "Stop", "SubagentStart", "SubagentStop", "SessionEnd"]
ARQ = os.path.expanduser("~/.claude/settings.json")


def eh_nosso(grupo):
    return any(h.get("url") == URL for h in grupo.get("hooks", []))


def main():
    remover = "--remover" in sys.argv
    cfg = {}
    if os.path.exists(ARQ):
        with open(ARQ, encoding="utf-8") as f:
            cfg = json.load(f)
        backup = f"{ARQ}.bak-mascote-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(ARQ, backup)
        print("backup:", backup)
    hooks = cfg.setdefault("hooks", {})
    for ev in EVENTOS:
        grupos = [g for g in hooks.get(ev, []) if not eh_nosso(g)]
        if not remover:
            grupos.append({"hooks": [{"type": "http", "url": URL, "timeout": 1}]})
        if grupos:
            hooks[ev] = grupos
        else:
            hooks.pop(ev, None)
    tmp = ARQ + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, ARQ)
    print("hooks removidos" if remover else f"hooks instalados -> {URL} ({len(EVENTOS)} eventos)")


if __name__ == "__main__":
    main()
