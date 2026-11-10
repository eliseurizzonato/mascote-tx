#!/usr/bin/env python3
"""Mascote TX: personagem de Natal personalizável que anda pela tela e reage ao Claude Code.

- Anda em cima da barra de tarefas nos monitores, sobe nas paredes laterais, dá tchau,
  toma chocolate quente, solta presentes e faz nevar.
- Personagem, nome, chapéu, uniforme (com a logo TX), cores e tamanho mudam em
  "Personalizar…" (clique direito) e ficam salvos em ~/.config/mascote-tx/config.json.
- Personagens próprios: arquivos .json em personagens/ (veja personagens/coruja.json).
- Turma: "Adicionar personagem" cria outros mascotes (salvos em turma/), que lutam entre si
  com socos, rajadas e explosões até um nocaute.
- Recebe os hooks do Claude Code em http://127.0.0.1:47900/evento; falas em /falar;
  configuração em /config (GET lê, POST altera).
"""
import datetime
import glob
import json
import math
import os
import random
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
gi.require_foreign("cairo")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

PORTA = int(os.environ.get("MASCOTE_PORTA", "47900"))
DIR = os.path.dirname(os.path.abspath(__file__))
CONF_DIR = os.path.expanduser("~/.config/mascote-tx")
CONFIG = os.environ.get("MASCOTE_CONFIG") or os.path.join(CONF_DIR, "config.json")
TURMA_DIR = os.path.join(os.path.dirname(CONFIG), "turma")  # um .json por personagem extra
TURMA = []  # mascotes na tela; o primeiro é o principal (recebe os eventos do Claude Code)
FPS = 30
GRAV = 1.1
TIPO = {"dock": Gdk.WindowTypeHint.DOCK, "utility": Gdk.WindowTypeHint.UTILITY,
        "notification": Gdk.WindowTypeHint.NOTIFICATION}.get(
            os.environ.get("MASCOTE_TIPO", "dock"), Gdk.WindowTypeHint.DOCK)

# Grade do personagem: corpo nas colunas 3..16 (centro entre 9 e 10), cabeça nas linhas 1..7,
# tronco/uniforme 8..14, pernas 15..16. Olhando para a esquerda, a coluna c vira 19 - c.
CX, PES, ESPELHO = 10, 17, 19

BRANCO = (0.98, 0.98, 0.98)
OLHO = (0.12, 0.10, 0.10)
VERMELHO = (0.82, 0.12, 0.15)
VERMELHO_E = (0.62, 0.08, 0.10)
VERDE = (0.13, 0.55, 0.25)
OURO = (0.98, 0.80, 0.20)
MARROM = (0.45, 0.27, 0.15)
ROSA = (0.96, 0.55, 0.55)
GELO = (0.80, 0.92, 1.00)
CIANO = (0.45, 0.95, 1.00)
VISOR = (0.08, 0.12, 0.14)
CHIFRE = (0.42, 0.27, 0.16)
BICO = (1.00, 0.62, 0.15)
BIGODE = (0.92, 0.92, 0.92)
TEAL_TX = (0.02, 0.23, 0.25)
LARANJA_TX = (1.00, 0.35, 0.12)
COR = {"r": VERMELHO, "w": BRANCO, "g": VERDE, "y": OURO, "b": MARROM, "c": GELO}

ITENS = {
    "presente": ["..g..g..", "...gg...", "rrrggrrr", "rrrggrrr",
                 "gggggggg", "rrrggrrr", "rrrggrrr", "rrrggrrr"],
    "bengala": ["..rwr...", ".w...w..", ".r...r..", ".....w..",
                ".....r..", ".....w..", ".....r..", ".....w.."],
    "estrela": ["...y....", "...y....", "yyyyyyy.", ".yyyyy..",
                "..yyy...", ".yy.yy..", "y.....y.", "........"],
    "biscoito": ["..bbb...", ".bwbwb..", "..bbb...", "bbbbbbb.",
                 ".bbwbb..", "..bbb...", ".bb.bb..", "bb...bb."],
    "floco": ["...c....", ".c.c.c..", "..ccc...", "ccccccc.",
              "..ccc...", ".c.c.c..", "...c....", "........"],
}
SOLTAVEIS = ["presente", "presente", "bengala", "estrela", "biscoito"]

# Logos em pixels: "o" é a seta (cor da seta), o resto é letra (cor da logo). Não espelham.
_LETRAS = {"t": [".t.", "ttt", ".t.", ".t.", ".tt"], "i": ["t", ".", "t", "t", "t"],
           "f": [".tt", ".t.", "ttt", ".t.", ".t."], "l": ["t", "t", "t", "t", "t"],
           "u": ["...", "...", "t.t", "t.t", "ttt"], "x": ["...", "...", "o.t", ".o.", "o.t"]}
LOGOS = {
    "tx": [".t........", "ttt.o..x.x", ".t...o..x.", ".t..o..x.x", "..tt......"],
    "setas": ["oo..oo..", ".oo..oo.", "..oo..oo", ".oo..oo.", "oo..oo.."],
    "tiflux": [".".join(_LETRAS[letra][r] for letra in "tiflux") for r in range(5)],
}
LOGO_ESTILOS = {"tx": "t›x", "setas": "» setas", "tiflux": "tiflux"}
SETA_PODER = ["oo..oo..", ".oo..oo.", "..oo..oo", ".oo..oo.", "oo..oo.."]

PODERES = {"rajada": "Rajada TX »", "explosao": "Explosão de presentes", "teleporte": "Teletransporte",
           "superpulo": "Super pulo", "aura": "Aura TX", "nevasca": "Nevasca"}
FALAS_PODER = {"rajada": "Rajada TX! »»", "explosao": "Chuva de presentes! 🎁", "teleporte": "Puf! ✨",
               "superpulo": "Super puloooo! 🚀", "aura": "Poder TX ativado! ⚡", "nevasca": "Nevasca! ❄️"}

MODELOS = {  # id: [rótulo, cor padrão do corpo, desenho próprio (personagens/*.json) ou None]
    "boneco": ["Boneco TX", "#ECEFF1", None],
    "tix": ["Tix, o robô", "#5B8A94", None],
    "rena": ["Rena", "#8B5A3C", None],
    "gato": ["Gatinho", "#E8A24A", None],
    "pinguim": ["Pinguim", "#24262B", None],
    "neve": ["Boneco de neve", "#F2F6FA", None],
    "bolota": ["Bolota", "#E9879A", None],
    "bloco": ["Bloquinho", "#D9774F", None],
}
CHAPEUS = {"gorro": "Gorro de Natal", "bone": "Boné TX", "chifres": "Chifres de rena", "nenhum": "Nenhum"}
UNIFORMES = {"camiseta": "Camiseta", "jaqueta": "Jaqueta", "nenhum": "Sem uniforme"}
PADRAO = {"nome": "Tix", "modelo": "boneco", "chapeu": "gorro", "uniforme": "camiseta", "logo": True,
          "logo_estilo": "tx", "logo_auto": True, "cor_logo": "#FFFFFF", "cor_seta": "#FF5A1F",
          "cor_corpo": None, "cor_uniforme": "#063A40", "cor_detalhe": "#FF5A1F",
          "tamanho": 4, "velocidade": 1.0, "paredes": True, "falas": True, "lutas": True}
NOMES_TURMA = ["Gigi", "Biscoito", "Faísca", "Pipoca", "Rudi", "Jingle", "Turbo", "Bolinha", "Nevasca", "Cometa"]
CORES_TURMA = [("#063A40", "#FF5A1F"), ("#1F3A93", "#FFC107"), ("#7B1E3A", "#FFFFFF"),
               ("#2E7D32", "#E53935"), ("#4A148C", "#00BCD4"), ("#263238", "#FF5A1F")]
FALAS_DESAFIO = ["Vem! 😤", "Pode vir! 💪", "Vai apanhar! 🥊", "Aceito! ⚔️"]
FALAS_DOR = ["Ai! 😣", "Ui!", "Essa doeu! 😖", "Ouch!"]
FALAS_DESVIO = ["Errou! 😜", "Desviei! 💨", "Nem doeu 😎"]
FALAS_KO = ["Fui… 😵", "Nocaute! 💫", "Peço arrego… 🏳️"]
HEX = re.compile(r"#[0-9a-fA-F]{6}")

FALAS_TOOL = [
    (("Bash",), "Rodando um comando… 🛷"),
    (("Edit", "Write", "MultiEdit", "NotebookEdit"), "Embrulhando o código… 🎁"),
    (("Read",), "Lendo a cartinha… 📜"),
    (("Grep", "Glob", "LS"), "Procurando presente escondido… 🔎"),
    (("WebFetch", "WebSearch"), "Perguntando pras renas… 🦌"),
    (("Agent", "Task"), "Chamando um elfo ajudante… 🧝"),
]
FALAS_CHOCOLATE = ["Pausa pro chocolate quente ☕", "Chocolate quente? ☕",
                   "Esse café tá com gosto de Natal ☕"]
FALAS_PAREDE = ["Escalando! 🧗", "Vista bonita daqui de cima 👀", "Parkour natalino!"]


# ---------- utilidades ----------
def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def hexa(c):
    return "#%02X%02X%02X" % tuple(round(v * 255) for v in c[:3])


def escurecer(c, f=0.80):
    return tuple(v * f for v in c)


def luminancia(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def distancia(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def dias_pro_natal():
    hoje = datetime.date.today()
    natal = datetime.date(hoje.year, 12, 25)
    if natal < hoje:
        natal = datetime.date(hoje.year + 1, 12, 25)
    return (natal - hoje).days


def frase_aleatoria(nome):
    d = dias_pro_natal()
    natal = "É NATAL!!! 🎄🎁" if d == 0 else f"Faltam {d} dias pro Natal! 🎄"
    return random.choice([
        "Ho ho ho! 🎅", natal, "Cadê meu presente? 🎁", "Bora codar antes da ceia!",
        "Commit antes do amigo secreto 😄", f"{nome} de plantão na oficina 🔧",
        "Já bebeu água hoje? 💧", "Me chama se precisar do Claude! ✨",
    ])


def fala_tool(nome):
    for nomes, fala in FALAS_TOOL:
        if nome in nomes:
            return fala
    if nome.startswith("mcp__"):
        return f"Usando {nome.split('__')[-1]}… ✨"
    return f"Usando {nome}… ✨"


def ultima_resposta(caminho):
    """Último texto do assistente no transcript (quando o hook não manda)."""
    if not caminho or not os.path.isfile(caminho):
        return ""
    try:
        with open(caminho, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 300_000))
            linhas = f.read().decode("utf-8", "ignore").splitlines()
        for linha in reversed(linhas):
            try:
                o = json.loads(linha)
            except ValueError:
                continue
            if o.get("type") != "assistant":
                continue
            cont = (o.get("message") or {}).get("content")
            if isinstance(cont, str) and cont.strip():
                return cont
            partes = [c.get("text", "") for c in cont or []
                      if isinstance(c, dict) and c.get("type") == "text"]
            if any(p.strip() for p in partes):
                return " ".join(partes)
    except OSError:
        pass
    return ""


def resumo(texto, limite=110):
    texto = re.sub(r"[`*#>_\[\]|]", "", texto or "")
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto[:limite] + ("…" if len(texto) > limite else "")


# ---------- configuração e personagens próprios ----------
def carregar_personagens():
    arquivos = sorted(glob.glob(os.path.join(DIR, "personagens", "*.json"))
                      + glob.glob(os.path.join(CONF_DIR, "personagens", "*.json")))
    for arq in arquivos:
        try:
            with open(arq, encoding="utf-8") as f:
                p = json.load(f)
            desenho = [str(linha)[:18].ljust(18, ".") for linha in p["desenho"]][-12:]
            cores = {k: rgb(v) for k, v in (p.get("cores") or {}).items() if len(k) == 1}
            ident = "p:" + os.path.splitext(os.path.basename(arq))[0]
            cor = p.get("cor", "#AAAAAA")
            rgb(cor)
            MODELOS[ident] = [str(p.get("nome", ident)), cor,
                              {"desenho": desenho, "cores": cores, "olhos": bool(p.get("olhos", True))}]
        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"personagem inválido em {arq}: {e}", file=sys.stderr)


def validar(cfg):
    if cfg.get("modelo") not in MODELOS:
        cfg["modelo"] = PADRAO["modelo"]
    if cfg.get("chapeu") not in CHAPEUS:
        cfg["chapeu"] = PADRAO["chapeu"]
    if cfg.get("uniforme") not in UNIFORMES:
        cfg["uniforme"] = PADRAO["uniforme"]
    if cfg.get("logo_estilo") not in LOGOS:
        cfg["logo_estilo"] = PADRAO["logo_estilo"]
    for k in ("cor_uniforme", "cor_detalhe", "cor_logo", "cor_seta"):
        if not HEX.fullmatch(str(cfg.get(k))):
            cfg[k] = PADRAO[k]
    if cfg.get("cor_corpo") is not None and not HEX.fullmatch(str(cfg["cor_corpo"])):
        cfg["cor_corpo"] = None
    for k, lo, hi in (("tamanho", 2, 12), ("velocidade", 0.3, 3.0)):
        try:
            cfg[k] = min(max(float(cfg.get(k)), lo), hi)
        except (TypeError, ValueError):
            cfg[k] = PADRAO[k]
    cfg["tamanho"] = int(cfg["tamanho"])
    cfg["nome"] = str(cfg.get("nome") or PADRAO["nome"]).strip()[:30] or PADRAO["nome"]
    for k in ("logo", "logo_auto", "paredes", "falas", "lutas"):
        cfg[k] = bool(cfg.get(k))
    return cfg


def carregar_config(caminho=CONFIG):
    cfg = dict(PADRAO)
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        cfg.update({k: v for k, v in dados.items() if k in PADRAO})
    except (OSError, ValueError, AttributeError):
        pass
    return validar(cfg)


def salvar_config(cfg, caminho=CONFIG):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, caminho)


def achar(nome):
    return next((m for m in TURMA if nome and m.cfg["nome"].lower() == str(nome).lower()), None)


def adicionar_mascote(modelo=None, nome=None):
    """Cria um personagem extra com visual sorteado e põe na tela."""
    usados = {m.cfg["nome"] for m in TURMA}
    livres = [n for n in NOMES_TURMA if n not in usados] or NOMES_TURMA
    uni, det = random.choice(CORES_TURMA)
    cfg = dict(PADRAO, nome=nome or random.choice(livres), chapeu=random.choice(list(CHAPEUS)),
               modelo=modelo if modelo in MODELOS else random.choice(list(MODELOS)),
               cor_uniforme=uni, cor_detalhe=det, tamanho=TURMA[0].cfg["tamanho"] if TURMA else PADRAO["tamanho"])
    caminho = os.path.join(TURMA_DIR, f"{time.strftime('%Y%m%d%H%M%S')}-{random.randint(0, 999):03d}.json")
    salvar_config(validar(cfg), caminho)
    TURMA.append(Mascote(caminho))
    return TURMA[-1]


# ---------- desenho do personagem ----------
def cores_logo(cfg, fundo):
    """(cor das letras, cor da seta) da logo; no automático, contrasta com o fundo."""
    if not cfg["logo_auto"]:
        return rgb(cfg["cor_logo"]), rgb(cfg["cor_seta"])
    letra = BRANCO if luminancia(fundo) < 0.45 else TEAL_TX
    seta = LARANJA_TX if distancia(fundo, LARANJA_TX) > 0.35 else letra
    return letra, seta


def montar_pixels(cfg, s, t, el, andando=False, no_ar=False, preso=False):
    """Lista de (coluna, linha, cor, alfa, desvio, tamanho).

    desvio != None: não espelha (logo), só desloca; tamanho < 1 desenha pixels menores.
    """
    px = []
    dy = [0]

    def pt(c, r, cor, a=1.0):
        px.append((c, r + dy[0], cor, a, None, 1))

    def ret(c0, c1, r0, r1, cor, a=1.0):
        for c in range(c0, c1 + 1):
            for r in range(r0, r1 + 1):
                pt(c, r, cor, a)

    def logo(r0, fundo, escala):
        grade = LOGOS[cfg["logo_estilo"]]
        letra, seta = cores_logo(cfg, fundo)
        c0 = CX - len(grade[0]) * escala / 2  # centralizada: espelhar não muda a posição
        for r, linha in enumerate(grade):
            for c, ch in enumerate(linha):
                if ch != ".":
                    px.append((c0 + c * escala, r0 + r * escala, seta if ch == "o" else letra, 1.0, 0, escala))

    def caneca(c0, r0):
        dyc = -2 if (el % 3.0) > 2.2 else 0  # gole
        ret(c0, c0 + 2, r0 + dyc, r0 + dyc, MARROM)
        ret(c0, c0 + 2, r0 + 1 + dyc, r0 + 3 + dyc, VERMELHO)
        pt(c0 + 1, r0 + 2 + dyc, BRANCO)
        ret(c0 + 3, c0 + 3, r0 + 1 + dyc, r0 + 2 + dyc, VERMELHO)
        k = (t // 8) % 2
        pt(c0 + k, r0 - 2 + dyc, BRANCO, 0.7)
        pt(c0 + 1 - k, r0 - 3 + dyc, BRANCO, 0.5)
        pt(c0 + 2, r0 - 2 + dyc - k, BRANCO, 0.6)

    modelo = cfg["modelo"]
    _, cor_padrao, proprio = MODELOS[modelo]
    corpo = rgb(cfg["cor_corpo"] or cor_padrao)
    corpo_e = escurecer(corpo)
    uni, det = rgb(cfg["cor_uniforme"]), rgb(cfg["cor_detalhe"])
    tem_uni = cfg["uniforme"] != "nenhum"
    fase = (t // (3 if s == "work" else 5)) % 2
    cima = (s == "drop" and el < 1.2) or s in ("party", "power", "dor") or preso
    acena = (t // (4 if s == "alert" else 7)) % 2
    escala_logo = 0.5 if cfg["logo_estilo"] == "tiflux" else 1.0

    if modelo == "boneco":
        # Boneco TX: cabeça em pirâmide, corpo branco com a logo, braços em lâmina e pé em ponta.
        branco, sombra = corpo, escurecer(corpo, 0.84)
        escuro, borda = uni, det
        claro = tuple(min(1.0, v * 1.5 + 0.18) for v in uni)
        ret(8, 11, 14, 14, escuro)
        pt(11, 14, borda)
        ret(9, 10, 15, 16, escuro)
        pt(10, 15, borda)
        ret(5, 14, 4, 9, branco)
        ret(6, 13, 10, 11, branco)
        ret(7, 12, 12, 12, branco)
        ret(8, 11, 13, 13, branco)
        ret(14, 14, 4, 9, sombra)
        for c, r in ((13, 10), (13, 11), (12, 12), (11, 13)):
            pt(c, r, sombra)
        ret(9, 10, 3, 3, escuro)
        if cfg["logo"]:
            logo(5.5 if escala_logo == 1.0 else 6.0, branco, 0.5)
        cabeca = {-8: (13, 14), -7: (11, 14), -6: (9, 15), -5: (7, 15), -4: (5, 16), -3: (3, 16),
                  -2: (4, 16), -1: (6, 15), 0: (8, 14), 1: (10, 13), 2: (11, 12)}
        for r, (a, b) in cabeca.items():
            ret(a, b, r, r, escuro)
            if r < 1:
                ret((a + b) // 2 + 1, b - 1, r, r, claro)
            pt(b, r, borda if r <= 0 else escuro)
            if r >= -2:
                pt(a, r, borda)
        pt(13, -8, BRANCO)
        cores = {"w": branco, "b": borda, "e": escuro}
        baixo = [(4, 5, "e"), (3, 6, "b"), (4, 6, "e"), (2, 7, "w"), (3, 7, "b"), (4, 7, "e"), (2, 8, "w"),
                 (3, 8, "b"), (4, 8, "e"), (2, 9, "w"), (3, 9, "b"), (4, 9, "e"), (2, 10, "w"), (3, 10, "b"),
                 (2, 11, "w"), (3, 11, "b"), (2, 12, "w")]
        alto = [(4, 4, "e"), (4, 3, "e"), (3, 3, "b"), (4, 2, "e"), (3, 2, "b"), (2, 2, "w"), (3, 1, "b"),
                (2, 1, "w"), (3, 0, "b"), (2, 0, "w"), (2, -1, "w")]

        def braco(lado, pontos, torto=False):
            for c, r, k in pontos:
                if torto and r <= 1:
                    c -= 1
                pt(c if lado < 0 else ESPELHO - c, r, cores[k])

        if cima:
            braco(-1, alto)
            braco(1, alto)
        else:
            braco(-1, baixo)
            if s in ("wave", "alert"):
                braco(1, alto, torto=bool(acena))
            elif s == "cocoa":
                ret(15, 18, 8, 8, branco)
                ret(15, 18, 9, 9, escuro)
                caneca(19, 7)
            elif s == "soco":
                ret(15, 20, 8, 8, branco)
                ret(15, 20, 9, 9, escuro)
                ret(21, 21, 8, 9, borda)
            else:
                braco(1, baixo)
        dy_chapeu, olhos = -8, (6, 9, -2, BRANCO, False)
    else:
        perna = BICO if modelo == "pinguim" else corpo_e
        for i, c in enumerate((5, 7, 12, 14)):
            curta = no_ar or preso or (andando and i % 2 == fase)
            ret(c, c, 15, 15 if curta else 16, perna)

        if proprio:
            n = len(proprio["desenho"])
            mapa = {"C": corpo, "c": corpo_e, "U": uni, "D": det, "B": BRANCO, "E": OLHO}
            for i, linha in enumerate(proprio["desenho"]):
                for j, ch in enumerate(linha):
                    cor = mapa.get(ch) or proprio["cores"].get(ch)
                    if ch != "." and cor:
                        pt(1 + j, 7 - (n - 1) + i, cor)
        elif modelo in ("bolota", "neve"):
            ret(3, 16, 3, 7, corpo)
            ret(4, 15, 2, 2, corpo)
            ret(5, 14, 1, 1, corpo)
        elif modelo == "tix":
            ret(3, 16, 2, 7, corpo)
            ret(4, 15, 1, 1, corpo)
        else:
            ret(3, 16, 1, 7, corpo)

        if modelo == "tix":
            ret(5, 14, 3, 5, VISOR)
            if cfg["chapeu"] == "nenhum":
                ret(9, 10, -1, 0, corpo_e)
                ret(9, 10, -2, -2, LARANJA_TX)
        elif modelo == "rena":
            pt(2, 3, corpo_e)
            pt(17, 3, corpo_e)
            ret(9, 10, 6, 6, VERMELHO)
        elif modelo == "gato":
            ret(3, 5, 0, 0, corpo)
            ret(14, 16, 0, 0, corpo)
            pt(3, -1, corpo)
            pt(16, -1, corpo)
            pt(4, 0, ROSA)
            pt(15, 0, ROSA)
            ret(9, 10, 6, 6, ROSA)
            ret(1, 2, 6, 6, BIGODE)
            ret(17, 18, 6, 6, BIGODE)
        elif modelo == "pinguim":
            ret(5, 14, 2, 7, BRANCO)
            ret(9, 10, 6, 6, BICO)
        elif modelo == "neve":
            ret(11, 13, 6, 6, BICO)
        elif modelo == "bolota":
            pt(5, 6, ROSA, 0.8)
            pt(14, 6, ROSA, 0.8)

        ret(3, 16, 8, 14, uni if tem_uni else corpo)
        ret(3, 16, 14, 14, escurecer(uni) if tem_uni else corpo_e)
        if not tem_uni:
            if modelo == "pinguim":
                ret(6, 13, 8, 13, BRANCO)
            elif modelo == "neve":
                for r in (9, 11, 13):
                    pt(9, r, OLHO)
        else:
            if cfg["uniforme"] == "camiseta":
                ret(8, 11, 8, 8, corpo)
                ret(9, 10, 9, 9, corpo)
            else:
                ret(7, 8, 8, 9, det)
                ret(11, 12, 8, 9, det)
                ret(9, 10, 8, 8, corpo)
                ret(3, 16, 14, 14, det)
            if cfg["logo"]:
                logo(10 if escala_logo == 1.0 else 11, uni, escala_logo)

        manga = uni if tem_uni else corpo
        mao = corpo
        if cima:
            pt(2, 8, manga)
            ret(1, 1, 6, 7, mao)
            pt(17, 8, manga)
            ret(18, 18, 6, 7, mao)
        else:
            ret(2, 2, 9, 10, manga)
            ret(1, 1, 9, 10, mao)
            if s in ("wave", "alert"):
                ret(17, 17, 8, 9, manga)
                if acena:
                    ret(18, 18, 6, 7, mao)
                else:
                    pt(18, 7, mao)
                    pt(19, 6, mao)
            elif s == "cocoa":
                pt(17, 10, manga)
                pt(18, 10, mao)
                caneca(19, 9)
            elif s == "soco":
                ret(17, 18, 9, 9, manga)
                ret(19, 20, 8, 9, mao)
            else:
                ret(17, 17, 9, 10, manga)
                ret(18, 18, 9, 10, mao)
        olho = CIANO if modelo == "tix" else OLHO
        dy_chapeu = 0
        olhos = None if (proprio and not proprio["olhos"]) else (6, 13, 5, olho, modelo != "tix")

    # chapéu e presente, deslocados para cima no Boneco TX
    dy[0] = dy_chapeu
    if modelo == "rena" or cfg["chapeu"] == "chifres":
        for c0, lado in ((5, -1), (14, 1)):
            ret(c0, c0, -3, 0, CHIFRE)
            pt(c0 + lado, -2, CHIFRE)
            pt(c0 + 2 * lado, -2, CHIFRE)
            pt(c0 - lado, -4, CHIFRE)
            pt(c0 + lado, -4, CHIFRE)
    if cfg["chapeu"] == "gorro":
        bal = (t // 6) % 2 if andando else 0
        ret(4, 15, 0, 0, VERMELHO)
        ret(5, 14, -1, -1, VERMELHO)
        ret(7, 12, -2, -2, VERMELHO)
        ret(6, 9, -3, -3, VERMELHO)
        ret(4, 5, -4, -4, VERMELHO)
        for c, r in ((15, 0), (14, -1), (12, -2)):
            pt(c, r, VERMELHO_E)
        ret(2, 3, -5 + bal, -4 + bal, BRANCO)
        ret(3, 16, 1, 1, BRANCO)
    elif cfg["chapeu"] == "bone":
        ret(5, 14, -1, -1, uni)
        ret(4, 15, 0, 1, uni)
        ret(15, 18, 1, 1, det)
        for c, r in ((10, -1), (11, 0), (10, 1)):
            pt(c, r, cores_logo(cfg, uni)[1])
    if s == "drop" and el < 1.2:
        ret(6, 13, -10, -6, VERMELHO)
        ret(9, 10, -10, -6, VERDE)
        ret(6, 13, -8, -8, VERDE)
        pt(8, -11, VERDE)
        pt(11, -11, VERDE)
    dy[0] = 0

    if olhos is None:
        return px
    e1, e2, base, olho, bochecha = olhos
    ex = 1 if andando and modelo != "boneco" else 0
    e1, e2 = e1 + ex, e2 + ex
    if s == "sleep":
        ret(e1 - 1, e1, base, base, olho)
        ret(e2, e2 + 1, base, base, olho)
    elif s in ("party", "wave", "power") or (s == "drop" and el >= 1.2):
        for e in (e1, e2):
            pt(e - 1, base, olho)
            pt(e, base - 1, olho)
            pt(e + 1, base, olho)
        if bochecha:
            pt(e1 - 2, base + 1, ROSA, 0.9)
            pt(e2 + 2, base + 1, ROSA, 0.9)
    elif s in ("dor", "ko"):
        for e in (e1, e2):
            pt(e - 1, base - 1, olho)
            pt(e + 1, base - 1, olho)
            pt(e, base, olho)
            pt(e - 1, base + 1, olho)
            pt(e + 1, base + 1, olho)
    elif s in ("luta", "soco"):
        ret(e1, e1, base - 1, base, olho)
        ret(e2, e2, base - 1, base, olho)
        pt(e1 - 1, base - 3, olho)
        pt(e1, base - 2, olho)
        pt(e2 + 1, base - 3, olho)
        pt(e2, base - 2, olho)
    elif s == "alert" or preso:
        ret(e1, e1, base - 2, base, olho)
        ret(e2, e2, base - 2, base, olho)
        ret(9 + ex, 10 + ex, base + 2, base + 2, olho)
    elif t % 100 < 4:
        ret(e1, e1, base, base, olho)
        ret(e2, e2, base, base, olho)
    else:
        ret(e1, e1, base - 1, base, olho)
        ret(e2, e2, base - 1, base, olho)
    return px


def desenhar_sprite(cr, pixels, px, espelho):
    """Desenha com os pés do personagem na origem atual do contexto."""
    for c, r, cor, a, desvio, tam in pixels:
        if espelho:
            c = c + desvio if desvio is not None else ESPELHO - c
        cr.set_source_rgba(*cor, a)
        cr.rectangle((c - CX) * px, (r - PES) * px, px * tam, px * tam)
        cr.fill()


def preparar_janela(w):
    w.set_decorated(False)
    w.set_app_paintable(True)
    w.set_keep_above(True)
    w.set_skip_taskbar_hint(True)
    w.set_skip_pager_hint(True)
    w.set_accept_focus(False)
    w.set_focus_on_map(False)
    w.set_type_hint(TIPO)
    w.stick()
    visual = w.get_screen().get_rgba_visual()
    if visual:
        w.set_visual(visual)


def limpar(cr):
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgba(0, 0, 0, 0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_OVER)


class Item(Gtk.Window):
    """Presente/floco que cai, quica e some depois de um tempo."""

    def __init__(self, app, nome, x, y, vx=0.0, vy=0.0, neve=False):
        super().__init__()
        preparar_janela(self)
        self.app, self.grade, self.neve = app, ITENS[nome], neve
        self.ipx = app.ipx
        self.lado = 8 * self.ipx
        self.set_size_request(self.lado, self.lado)
        self.resize(self.lado, self.lado)
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.pousou = None
        self.vida = 7 if neve else 30
        self.fase = random.random() * 6
        self.connect("draw", self.on_draw)
        self.move(int(x - self.lado / 2), int(y - self.lado))
        self.show_all()
        self.get_window().input_shape_combine_region(cairo.Region(), 0, 0)

    def passo(self, agora):
        if self.pousou is None:
            chao = self.app.chao(self.x, self.y)
            if self.neve:
                self.fase += 0.08
                self.y += self.vy
                self.x += math.sin(self.fase) * 0.8
            else:
                self.vy += 0.45
                self.x += self.vx
                self.y += self.vy
                self.vx *= 0.98
            if self.y >= chao:
                self.y = chao
                if not self.neve and self.vy > 4:
                    self.vy, self.vx = -self.vy * 0.35, self.vx * 0.5
                else:
                    self.pousou = agora
            self.move(int(self.x - self.lado / 2), int(self.y - self.lado))
        else:
            resta = self.vida - (agora - self.pousou)
            if resta <= 0:
                self.destroy()
                return False
            if resta < 2:
                self.set_opacity(resta / 2)
        return True

    def on_draw(self, _w, cr):
        limpar(cr)
        for r, linha in enumerate(self.grade):
            for c, ch in enumerate(linha):
                if ch != ".":
                    cr.set_source_rgb(*COR[ch])
                    cr.rectangle(c * self.ipx, r * self.ipx, self.ipx, self.ipx)
                    cr.fill()
        return True


class Efeito(Gtk.Window):
    """Partículas de um poder (setas voando, explosão, brilho) numa janela transparente."""

    def __init__(self, app, x0, y0, larg, alt, particulas, dur):
        super().__init__()
        preparar_janela(self)
        self.parts, self.dur, self.ini = particulas, dur, time.time()
        self.set_size_request(larg, alt)
        self.resize(larg, alt)
        self.connect("draw", self.on_draw)
        self.move(int(x0), int(y0))
        self.show_all()
        self.get_window().input_shape_combine_region(cairo.Region(), 0, 0)

    def passo(self, agora):
        if agora - self.ini > self.dur:
            self.destroy()
            return False
        for p in self.parts:
            if agora - self.ini >= p.get("atraso", 0):
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["vy"] += p.get("g", 0)
        self.queue_draw()
        return True

    def on_draw(self, _w, cr):
        limpar(cr)
        idade = time.time() - self.ini
        alfa = max(0.0, 1 - (idade / self.dur) ** 2)
        for p in self.parts:
            if idade < p.get("atraso", 0):
                continue
            cr.set_source_rgba(*p["cor"], alfa)
            tam = p["tam"]
            if p.get("forma") == "seta":
                for r, linha in enumerate(SETA_PODER):
                    for c, ch in enumerate(linha):
                        if ch != ".":
                            cc = c if p["vx"] >= 0 else len(linha) - 1 - c
                            cr.rectangle(p["x"] + cc * tam, p["y"] + r * tam, tam, tam)
                cr.fill()
            else:
                cr.rectangle(p["x"], p["y"], tam, tam)
                cr.fill()
        return True


class Mascote(Gtk.Window):
    ANGULO = {"chao": 0.0, "esq": math.pi / 2, "dir": -math.pi / 2}

    def __init__(self, caminho=CONFIG):
        super().__init__()
        preparar_janela(self)
        self.caminho = caminho
        self.cfg = carregar_config(caminho)
        self.itens, self.t = [], 0
        self.S, self.win_pos, self.regiao_chave = 0, None, None
        self.px = self.cfg["tamanho"]
        self.carregar_monitores()
        disp = Gdk.Display.get_default()
        disp.connect("monitor-added", lambda *_: self.carregar_monitores())
        disp.connect("monitor-removed", lambda *_: self.carregar_monitores())

        _, wa = self.principal
        self.x = wa.x + wa.width * (0.5 if caminho == CONFIG else random.uniform(0.15, 0.85))
        self.y = self.chao(self.x)
        self.vy, self.dir, self.surf = 0.0, 1, "chao"
        self.balao, self.balao_ate, self.balao_ini = "", 0.0, 0.0
        self.ultimo_tool = 0.0
        self.arrastando = self.arr_moveu = False
        self.salvar_id = None
        self.janela_cfg = None
        self.aura_ate = self.trilha_ate = 0.0
        self.oculto, self.duplo = False, False
        self.poder_nome, self.poder_feito = "", True
        self.oponente, self.hp, self.kb = None, 100, 0.0
        self.luta_prox = self.luta_fim = self.luta_cd = self.dor_ate = self.barra_ate = 0.0

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                        | Gdk.EventMask.POINTER_MOTION_MASK)
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        self.connect("motion-notify-event", self.on_motion)
        self.menu = self.criar_menu()
        self.aplicar_config(salvar=False)
        self.reposicionar()
        self.show_all()
        self.set_state("wave", 3)
        self.dizer(f"Ho ho ho! {self.cfg['nome']} chegou 🎅", 4)
        GLib.timeout_add(1000 // FPS, self.tick)

    # ---------- configuração ----------
    def aplicar_config(self, salvar=True):
        validar(self.cfg)
        self.px = self.cfg["tamanho"]
        self.ipx = max(3, self.px - 1)
        self.meia = 10 * self.px
        S = int(2 * max(36 * self.px + 130, 26 * self.px + 260))
        if S != self.S:
            self.S = S
            self.set_size_request(S, S)
            self.resize(S, S)
            self.win_pos = None
        self.regiao_chave = None
        self.carregar_monitores()
        self.set_title(self.cfg["nome"])
        self.item_nome.set_label(f"🎄 {self.cfg['nome']}")
        self.sincronizando = True
        self.item_falas.set_active(self.cfg["falas"])
        self.item_lutas.set_active(self.cfg["lutas"])
        self.sincronizando = False
        if salvar:
            if self.salvar_id:
                GLib.source_remove(self.salvar_id)
            self.salvar_id = GLib.timeout_add(400, self._salvar)

    def _salvar(self):
        self.salvar_id = None
        salvar_config(self.cfg, self.caminho)
        return False

    def mudar(self, **valores):
        self.cfg.update(valores)
        self.aplicar_config()

    # ---------- monitores e chão ----------
    def carregar_monitores(self):
        disp = Gdk.Display.get_default()
        self.mons, self.principal = [], None
        for i in range(disp.get_n_monitors()):
            m = disp.get_monitor(i)
            par = (m.get_geometry(), m.get_workarea())
            self.mons.append(par)
            if m.is_primary():
                self.principal = par
        self.principal = self.principal or self.mons[0]
        self.borda_esq = min(g.x for g, _ in self.mons)
        self.borda_dir = max(g.x + g.width for g, _ in self.mons)
        self.lim_esq = self.borda_esq + 10 * self.px
        self.lim_dir = self.borda_dir - 10 * self.px

    def monitor(self, x, y=None):
        cands = [(g, wa) for g, wa in self.mons if g.x <= x < g.x + g.width]
        if not cands:
            return min(self.mons, key=lambda p: min(abs(p[0].x - x), abs(p[0].x + p[0].width - x)))
        if y is not None and len(cands) > 1:
            for g, wa in cands:
                if g.y <= y <= g.y + g.height:
                    return g, wa
        return cands[0]

    def chao(self, x, y=None):
        _, wa = self.monitor(x, y)
        return wa.y + wa.height

    def no_chao(self):
        return self.surf == "chao" and self.vy == 0 and abs(self.y - self.chao(self.x, self.y)) < 1

    def cabeca(self, fracao=1.0):
        """Ponto acima da cabeça (fracao=0.5: meio do corpo), em coordenadas da tela."""
        a = self.ANGULO[self.surf]
        d = (26 if self.cfg["modelo"] == "boneco" else 19) * self.px * fracao
        return self.x + d * math.sin(a), self.y - d * math.cos(a)

    def cor_poder(self):
        fundo = rgb(self.cfg["cor_corpo"] or MODELOS[self.cfg["modelo"]][1]) \
            if self.cfg["modelo"] == "boneco" else rgb(self.cfg["cor_uniforme"])
        return cores_logo(self.cfg, fundo)[1]

    def olhando_direita(self):
        if self.surf == "chao":
            return self.dir > 0
        return self.surf == "esq"

    def espelho(self):
        return self.dir > 0 if self.surf == "esq" else self.dir < 0

    # ---------- estados ----------
    def set_state(self, nome, dur):
        self.state, self.state_ini = nome, time.time()
        self.state_ate = self.state_ini + dur
        self.soltou = nome != "drop"
        if nome == "party" and self.no_chao():
            self.vy = -9

    def proximo_estado(self):
        agora = time.time()
        if self.surf == "chao" and self.cfg["lutas"] and agora > self.luta_cd and random.random() < 0.05:
            rivais = [m for m in TURMA if m is not self and m.cfg["lutas"] and m.luta_cd < agora and m.pode_lutar()]
            if rivais and self.desafiar(random.choice(rivais)):
                return
        if self.surf != "chao":
            opcoes = [("descer", 45), ("subir", 15), ("idle", 20), ("wave", 10), ("cocoa", 5), ("sleep", 5)]
        else:
            hora = datetime.datetime.now().hour
            noite = hora >= 20 or hora < 7
            opcoes = [("walk", 45), ("idle", 18), ("wave", 6), ("cocoa", 8), ("drop", 6),
                      ("sleep", 14 if noite else 3), ("poder", 2)]
        nome = random.choices([o for o, _ in opcoes], [p for _, p in opcoes])[0]
        if nome == "poder":
            self.poder(random.choice(["rajada", "aura", "explosao", "superpulo"]))
            return
        if nome in ("descer", "subir"):
            self.dir = 1 if nome == "subir" else -1
            self.set_state("walk", 30 if nome == "descer" else random.uniform(2, 5))
            return
        dur = {"walk": random.uniform(3, 10), "idle": random.uniform(2, 5), "wave": 2.5,
               "cocoa": 7, "drop": 2.2, "sleep": random.uniform(8, 15)}[nome]
        if nome == "walk" and random.random() < 0.5:
            self.dir *= -1
        self.set_state(nome, dur)
        if nome == "cocoa" and random.random() < 0.6:
            self.dizer(random.choice(FALAS_CHOCOLATE), 4)
        elif nome in ("idle", "wave") and random.random() < 0.25:
            self.dizer(frase_aleatoria(self.cfg["nome"]), 4)

    def dizer(self, texto, segundos=5, forcar=False):
        if not self.cfg["falas"] and not forcar:
            return
        self.balao, self.balao_ini = texto, time.time()
        self.balao_ate = self.balao_ini + segundos

    def soltar(self, nome):
        if len(self.itens) > 40:
            self.itens.pop(0).destroy()
        hx, hy = self.cabeca()
        if self.surf == "chao":
            vx = (1 if self.dir > 0 else -1) * random.uniform(0.5, 2.0)
        else:
            vx = (1 if self.surf == "esq" else -1) * random.uniform(1.0, 2.5)
        self.itens.append(Item(self, nome, hx, hy, vx=vx, vy=-3))

    def nevar(self):
        g, _ = self.monitor(self.x, self.y)
        for _ in range(20):
            self.itens.append(Item(self, "floco", random.uniform(g.x + 20, g.x + g.width - 20),
                                   g.y - random.uniform(0, 300), vy=random.uniform(0.8, 1.8), neve=True))
        self.dizer("Tá nevando! ❄️", 3, forcar=True)

    def clique(self):
        self.set_state("wave", 2.5)
        self.dizer(frase_aleatoria(self.cfg["nome"]), 4, forcar=True)
        self.soltar(random.choice(SOLTAVEIS))

    # ---------- poderes ----------
    def poder(self, nome=None):
        if nome not in PODERES:
            nome = random.choice(list(PODERES))
        if nome == "superpulo" and self.surf != "chao":
            nome = "rajada"
        self.poder_nome, self.poder_feito = nome, False
        self.set_state("power", 1.3)
        self.dizer(FALAS_PODER[nome], 2.5, forcar=True)

    def explosao(self, x, y, n=60, g=0.25, dur=1.6, cores=None):
        cores = cores or [self.cor_poder(), rgb(self.cfg["cor_detalhe"]), VERMELHO, VERDE, OURO, BRANCO]
        meio = 260
        parts = []
        for _ in range(n):
            ang, vel = random.uniform(0, 2 * math.pi), random.uniform(2.5, 9)
            parts.append({"x": meio, "y": meio, "vx": math.cos(ang) * vel, "vy": math.sin(ang) * vel - 1.5,
                          "g": g, "cor": random.choice(cores), "tam": random.choice((self.ipx, self.ipx + 2))})
        self.itens.append(Efeito(self, x - meio, y - meio, 2 * meio, 2 * meio, parts, dur))

    def executar_poder(self, nome):
        hx, hy = self.cabeca(0.5)
        cor = self.cor_poder()
        if nome == "rajada":
            direita = self.olhando_direita()
            larg, tam = 1200, max(3, self.px)
            parts = [{"x": (-8 * tam - i * 70) if direita else (larg + i * 70), "y": 10, "vx": 22 if direita else -22,
                      "vy": 0, "cor": cor if i % 2 == 0 else rgb(self.cfg["cor_detalhe"]), "tam": tam}
                     for i in range(6)]
            for p in parts:
                p["forma"] = "seta"
            x0 = hx if direita else hx - larg
            self.itens.append(Efeito(self, x0, hy - 2.5 * tam - 10, larg, 5 * tam + 20, parts, 1.6))
        elif nome == "explosao":
            self.explosao(hx, hy)
            for _ in range(3):
                self.soltar(random.choice(SOLTAVEIS))
        elif nome == "teleporte":
            self.explosao(hx, hy, n=45, g=0, dur=0.8, cores=[cor, BRANCO, GELO])
            self.oculto = True
            GLib.timeout_add(600, self.reaparecer)
        elif nome == "superpulo":
            g, _ = self.monitor(self.x, self.y)
            altura = max(80, min(450, self.y - g.y - 30 * self.px))
            self.vy = -math.sqrt(2 * GRAV * altura)
            self.trilha_ate = time.time() + 1.4
        elif nome == "aura":
            self.aura_ate = time.time() + 5
        elif nome == "nevasca":
            self.nevar()
            self.nevar()

    def reaparecer(self):
        g, wa = random.choice(self.mons)
        self.surf, self.vy = "chao", 0.0
        self.x = random.uniform(g.x + self.meia, g.x + g.width - self.meia)
        self.y = wa.y + wa.height - 120
        self.oculto = False
        hx, hy = self.cabeca(0.5)
        self.explosao(hx, hy, n=45, g=0, dur=0.8, cores=[self.cor_poder(), BRANCO, GELO])
        return False

    # ---------- luta ----------
    def pode_lutar(self):
        return self.oponente is None and not self.arrastando and not self.oculto and self.state != "ko"

    def desafiar(self, outro):
        if outro is self or not self.pode_lutar() or not outro.pode_lutar():
            return False
        agora = time.time()
        for m, o in ((self, outro), (outro, self)):
            if m.surf != "chao":
                m.descer_parede()
            m.oponente, m.hp, m.kb = o, 100, 0.0
            m.luta_prox, m.luta_fim = agora + random.uniform(1.0, 2.0), agora + 45
            m.set_state("luta", 60)
        self.dizer(f"{outro.cfg['nome']}, bora lutar! 🥊", 2.5, forcar=True)
        outro.dizer(random.choice(FALAS_DESAFIO), 2.5, forcar=True)
        return True

    def lutar(self, agora):
        """Um passo da luta: chega perto, soca, solta rajada ou explosão."""
        o = self.oponente
        if o not in TURMA or o.oponente is not self:
            self.encerrar_luta()
            return
        if agora > self.luta_fim:
            for m in (self, o):
                m.encerrar_luta()
                m.set_state("wave", 2.5)
            self.dizer("Empate! 🤝", 3, forcar=True)
            return
        if self.state in ("soco", "power", "dor") and agora < self.state_ate:
            return
        dx = o.x - self.x
        self.dir = 1 if dx >= 0 else -1
        perto = abs(dx) < 9 * (self.px + o.px) + 12
        mesma_altura = abs(o.y - self.y) < 120
        if agora >= self.luta_prox and mesma_altura:
            self.luta_prox = agora + random.uniform(0.9, 2.0)
            sorteio = random.random()
            if perto and sorteio < 0.6:
                self.set_state("soco", 0.35)
                self.mover_luta(self.dir * 2 * self.px)
                GLib.timeout_add(120, lambda: self.acertar(o, random.randint(8, 14), perto=True) and False)
            elif perto and sorteio > 0.88:
                self.poder_nome, self.poder_feito = "explosao", False
                self.set_state("power", 1.0)
                self.dizer("Explosão de presentes! 🎁", 1.5, forcar=True)
                GLib.timeout_add(500, lambda: self.acertar(o, random.randint(18, 26), perto=True) and False)
            elif abs(dx) > 6 * self.px and (perto or sorteio < 0.3):
                self.poder_nome, self.poder_feito = "rajada", False
                self.set_state("power", 0.9)
                if random.random() < 0.4:
                    self.dizer(FALAS_PODER["rajada"], 1.5, forcar=True)
                voo = int(400 + abs(dx) / 22 * 1000 / FPS)
                GLib.timeout_add(voo, lambda: self.acertar(o, random.randint(10, 18)) and False)
            else:
                self.luta_prox = agora + 0.5
            if self.state != "walk":
                return
        if perto:
            if self.state != "luta":
                self.set_state("luta", 60)
        else:
            if self.state != "walk":
                self.set_state("walk", 60)
            self.mover(self.dir * 2.6 * self.cfg["velocidade"])

    def mover_luta(self, d):
        """Empurrão ou investida no chão, sem subir parede nem atravessar degrau."""
        nx = min(max(self.x + d, self.lim_esq), self.lim_dir)
        if self.chao(nx, self.y) >= self.y - 3:
            self.x = nx

    def acertar(self, o, dano, perto=False):
        if self.oponente is not o or (perto and abs(o.x - self.x) > 9 * (self.px + o.px) + 40):
            return
        hx, hy = o.cabeca(0.5)
        self.explosao(hx - self.dir * 6 * o.px, hy, n=14, g=0.1, dur=0.5, cores=[BRANCO, OURO, self.cor_poder()])
        o.levar(self, dano)

    def levar(self, de, dano):
        if self.oponente is not de:
            return
        if random.random() < 0.12:
            if self.no_chao():
                self.vy = -6
            self.dizer(random.choice(FALAS_DESVIO), 1.5, forcar=True)
            return
        self.hp = max(0, self.hp - dano)
        self.kb = (1 if self.x >= de.x else -1) * (4 + dano * 0.4)
        self.dor_ate = time.time() + 0.25
        if self.no_chao():
            self.vy = -4
        if self.hp <= 0:
            self.encerrar_luta()
            de.encerrar_luta()
            self.kb *= 1.8
            self.set_state("ko", 5)
            self.dizer(random.choice(FALAS_KO), 3, forcar=True)
            de.vencer(self)
            return
        self.set_state("dor", 0.35)
        if random.random() < 0.3:
            self.dizer(random.choice(FALAS_DOR), 1.2, forcar=True)

    def vencer(self, perdedor):
        self.set_state("party", 3.5)
        self.dizer(f"Venci! 🏆 {perdedor.cfg['nome']} vai precisar de chocolate quente ☕", 4, forcar=True)
        hx, hy = self.cabeca()
        self.explosao(hx, hy, n=40, g=0.2, dur=1.4)
        self.soltar("estrela")

    def encerrar_luta(self):
        self.oponente = None
        self.luta_cd = time.time() + 90
        self.barra_ate = time.time() + 4
        if self.state in ("luta", "walk", "soco", "dor"):
            self.set_state("idle", 1.5)

    def remover(self):
        if self is TURMA[0]:
            return
        if self.oponente:
            self.oponente.encerrar_luta()
        TURMA.remove(self)
        try:
            os.remove(self.caminho)
        except OSError:
            pass
        for w in [self.janela_cfg, *self.itens]:
            if w:
                w.destroy()
        self.destroy()

    # ---------- movimento ----------
    def subir_parede(self, lado):
        g, wa = self.monitor(self.x, self.y)
        self.parede = (g, wa)
        self.surf, self.vy, self.dir = lado, 0.0, 1
        self.x = g.x if lado == "esq" else g.x + g.width
        self.y = wa.y + wa.height - self.meia
        self.set_state("walk", random.uniform(3, 8))
        if random.random() < 0.4:
            self.dizer(random.choice(FALAS_PAREDE), 3)

    def escalar(self):
        """Vai até a parede lateral mais próxima e sobe."""
        if self.surf != "chao":
            return
        lado = "esq" if self.x - self.borda_esq < self.borda_dir - self.x else "dir"
        self.x = self.lim_esq if lado == "esq" else self.lim_dir - 1
        self.y, self.vy = self.chao(self.x), 0.0
        self.subir_parede(lado)

    def descer_parede(self):
        _, wa = self.parede
        lado = self.surf
        self.surf, self.vy = "chao", 0.0
        self.x = self.x + self.meia if lado == "esq" else self.x - self.meia
        self.y = wa.y + wa.height
        self.dir = 1 if lado == "esq" else -1
        self.set_state("walk", random.uniform(3, 8))

    def mover(self, d):
        if self.surf != "chao":
            g, wa = self.parede
            self.y -= d
            topo = max(g.y, wa.y) + self.meia
            if self.y <= topo:
                self.y, self.dir = topo, -1
            elif self.y >= wa.y + wa.height - self.meia + 1:
                self.descer_parede()
            return
        nx = self.x + d
        if not self.lim_esq <= nx <= self.lim_dir:
            if self.cfg["paredes"] and self.no_chao() and random.random() < 0.7:
                self.subir_parede("esq" if nx < self.lim_esq else "dir")
            else:
                self.dir *= -1
            return
        alvo = self.chao(nx, self.y)
        if alvo < self.y - 3:  # degrau para cima (monitor mais alto): pula
            if self.no_chao():
                self.vy = -math.sqrt(2 * GRAV * (self.y - alvo + 14))
            if self.y > alvo:
                return
        self.x = nx

    def fisica(self):
        if self.surf != "chao":
            return
        chao = self.chao(self.x, self.y)
        if self.y < chao or self.vy < 0:
            self.vy += GRAV
            self.y += self.vy
            if self.y >= chao and self.vy > 0:
                self.y, self.vy = chao, 0.0
        else:
            self.y, self.vy = chao, 0.0

    def tick(self):
        if self not in TURMA:  # saiu da turma
            return False
        self.t += 1
        agora = time.time()
        if not self.arrastando:
            if self.oponente:
                self.lutar(agora)
            elif agora >= self.state_ate:
                self.proximo_estado()
            s, vel = self.state, self.cfg["velocidade"]
            if self.kb and self.surf == "chao":
                self.mover_luta(self.kb)
                self.kb = 0.0 if abs(self.kb) < 0.3 else self.kb * 0.8
            if self.oponente:
                pass
            elif s == "walk":
                self.mover(self.dir * 1.6 * vel)
            elif s == "work":
                if random.random() < 0.006:
                    self.dir *= -1
                self.mover(self.dir * 3.2 * vel)
            elif s == "alert" and self.no_chao() and self.t % 22 == 0:
                self.vy = -7
            elif s == "party" and self.no_chao() and self.t % 16 == 0 and agora - self.state_ini < 2.5:
                self.vy = -8
            if s == "drop" and not self.soltou and agora - self.state_ini > 1.2:
                self.soltou = True
                self.soltar(random.choice(SOLTAVEIS))
            if s == "power" and not self.poder_feito and agora - self.state_ini > 0.4:
                self.poder_feito = True
                self.executar_poder(self.poder_nome)
            if agora < self.trilha_ate and self.t % 3 == 0 and not self.no_chao():
                hx, hy = self.cabeca(0.5)
                self.explosao(hx, hy, n=6, g=0, dur=0.5)
            self.fisica()
        self.itens = [i for i in self.itens if i.passo(agora)]
        self.reposicionar()
        self.queue_draw()
        return True

    def reposicionar(self):
        self.win_x = int(round(self.x - self.S / 2))
        self.win_y = int(round(self.y - self.S / 2))
        if self.win_pos != (self.win_x, self.win_y):
            self.win_pos = (self.win_x, self.win_y)
            self.move(self.win_x, self.win_y)
        chave = (self.surf, self.px, self.S)
        janela = self.get_window()
        if janela and chave != self.regiao_chave:
            self.regiao_chave = chave
            a = self.ANGULO[self.surf]
            cs, sn = math.cos(a), math.sin(a)
            topo = -9 if self.cfg["modelo"] == "boneco" else -1
            cantos = [((c - CX) * self.px, (r - PES) * self.px) for c in (1, 19) for r in (topo, 17)]
            xs = [self.S / 2 + x * cs - y * sn for x, y in cantos]
            ys = [self.S / 2 + x * sn + y * cs for x, y in cantos]
            ret = cairo.RectangleInt(int(min(xs)), int(min(ys)),
                                     int(max(xs) - min(xs)), int(max(ys) - min(ys)))
            janela.input_shape_combine_region(cairo.Region(ret), 0, 0)

    # ---------- mouse e menu ----------
    def on_press(self, _w, ev):
        if ev.button == 1 and ev.type == Gdk.EventType._2BUTTON_PRESS:
            self.duplo = True
            self.poder()
        elif ev.button == 1:
            self.arrastando, self.arr_moveu = True, False
            self.arr_ini = (ev.x_root, ev.y_root)
        elif ev.button == 3:
            self.montar_menu_luta()
            self.menu.popup_at_pointer(ev)
        return True

    def on_motion(self, _w, ev):
        if not self.arrastando:
            return False
        if abs(ev.x_root - self.arr_ini[0]) + abs(ev.y_root - self.arr_ini[1]) > 6:
            self.arr_moveu = True
        if self.arr_moveu:
            self.surf, self.vy = "chao", 0.0
            self.x = min(max(ev.x_root, self.lim_esq), self.lim_dir)
            self.y = ev.y_root + 9 * self.px
        return True

    def on_release(self, _w, ev):
        if ev.button != 1 or not self.arrastando:
            return False
        self.arrastando = False
        if self.duplo:
            self.duplo = False
        elif self.arr_moveu:
            self.vy = 0.1
            self.set_state("idle", 1.5)
            self.dizer("Uiii! 😵", 2, forcar=True)
        else:
            self.clique()
        return True

    def criar_menu(self):
        menu = Gtk.Menu()
        self.item_nome = Gtk.MenuItem(label="")
        self.item_nome.set_sensitive(False)
        menu.append(self.item_nome)
        menu.append(Gtk.SeparatorMenuItem())
        acoes = [("Personalizar…", self.abrir_personalizar),
                 ("Falar algo", lambda: self.dizer(frase_aleatoria(self.cfg["nome"]), 4, True)),
                 ("Soltar presente", lambda: self.soltar("presente")),
                 ("Fazer nevar ❄", self.nevar),
                 ("Dar tchau", lambda: self.set_state("wave", 3)),
                 ("Escalar parede", self.escalar),
                 ("Maior", lambda: self.mudar(tamanho=self.cfg["tamanho"] + 1)),
                 ("Menor", lambda: self.mudar(tamanho=self.cfg["tamanho"] - 1))]
        for rotulo, fn in acoes:
            it = Gtk.MenuItem(label=rotulo)
            it.connect("activate", lambda _i, f=fn: f())
            menu.append(it)
        poderes = Gtk.Menu()
        for ident, rotulo in [("", "Aleatório (duplo clique)")] + list(PODERES.items()):
            it = Gtk.MenuItem(label=rotulo)
            it.connect("activate", lambda _i, p=ident: self.poder(p or None))
            poderes.append(it)
        it = Gtk.MenuItem(label="Soltar poder ⚡")
        it.set_submenu(poderes)
        menu.append(it)
        menu.append(Gtk.SeparatorMenuItem())
        it = Gtk.MenuItem(label="Adicionar personagem ➕")
        it.connect("activate", lambda _i: adicionar_mascote())
        menu.append(it)
        self.item_lutar = Gtk.MenuItem(label="Lutar com 🥊")
        menu.append(self.item_lutar)
        self.item_remover = Gtk.MenuItem(label="Tirar da turma")
        self.item_remover.connect("activate", lambda _i: GLib.idle_add(lambda: self.remover() and False))
        menu.append(self.item_remover)
        self.sincronizando = False
        self.item_falas = Gtk.CheckMenuItem(label="Falas aleatórias")
        self.item_falas.connect("toggled", lambda i: self.sincronizando or self.mudar(falas=i.get_active()))
        menu.append(self.item_falas)
        self.item_lutas = Gtk.CheckMenuItem(label="Lutas automáticas")
        self.item_lutas.connect("toggled", lambda i: self.sincronizando or self.mudar(lutas=i.get_active()))
        menu.append(self.item_lutas)
        menu.append(Gtk.SeparatorMenuItem())
        sair = Gtk.MenuItem(label="Sair (todos)")
        sair.connect("activate", lambda _i: Gtk.main_quit())
        menu.append(sair)
        menu.show_all()
        return menu

    def montar_menu_luta(self):
        sub = Gtk.Menu()
        rivais = [m for m in TURMA if m is not self]
        for m in rivais:
            it = Gtk.MenuItem(label=m.cfg["nome"])
            it.connect("activate", lambda _i, o=m: self.desafiar(o))
            sub.append(it)
        if not rivais:
            it = Gtk.MenuItem(label="Adicione outro personagem antes")
            it.set_sensitive(False)
            sub.append(it)
        sub.show_all()
        self.item_lutar.set_submenu(sub)
        self.item_lutar.set_sensitive(self.pode_lutar())
        self.item_remover.set_visible(self is not TURMA[0])

    def abrir_personalizar(self):
        if self.janela_cfg is None:
            self.janela_cfg = Personalizar(self)
        self.janela_cfg.show_all()
        self.janela_cfg.present()

    # ---------- Claude Code ----------
    def on_http(self, caminho, dados):
        if caminho == "/falar":
            texto = str(dados.get("texto", ""))[:200]
            if texto:
                self.dizer(texto, float(dados.get("segundos", 6)), forcar=True)
            if dados.get("item") in ITENS:
                self.soltar(dados["item"])
            if dados.get("acao") in ("wave", "cocoa", "party", "sleep", "alert", "drop", "walk"):
                self.set_state(dados["acao"], float(dados.get("duracao", 4)))
            if dados.get("acao") == "nevar":
                self.nevar()
            if dados.get("acao") == "escalar":
                self.escalar()
            if dados.get("acao") == "poder":
                self.poder(dados.get("poder"))
        elif caminho == "/config":
            self.mudar(**{k: v for k, v in dados.items() if k in PADRAO})
            if self.janela_cfg:
                self.janela_cfg.recarregar()
        else:
            self.on_evento(dados)
        return False

    def on_evento(self, d):
        ev = d.get("hook_event_name", "")
        agora = time.time()
        nome = self.cfg["nome"]
        if ev == "SessionStart":
            self.set_state("wave", 3)
            self.dizer(f"Ho ho ho! {nome} na área 🎄", 4)
        elif ev == "UserPromptSubmit":
            self.set_state("work", 8)
            self.dizer(random.choice(["Pedido anotado! Indo pra oficina 🎅", "Recebi sua cartinha! ✉️",
                                      "Bora trabalhar, elfos! 🔨"]), 3.5)
        elif ev == "PreToolUse":
            if self.state != "alert":
                self.set_state("work", 8)
            if agora - self.ultimo_tool > 3:
                self.ultimo_tool = agora
                self.dizer(fala_tool(d.get("tool_name", "")), 3)
        elif ev == "PostToolUse":
            if self.state == "alert":  # permissão concedida
                self.set_state("work", 6)
                self.balao_ate = 0
        elif ev == "Notification":
            tipo, msg = d.get("notification_type", ""), d.get("message", "")
            if "permission" in tipo or "permission" in msg.lower():
                self.set_state("alert", 25)
                self.dizer("🔔 Ei! O Claude precisa da sua permissão!", 25, forcar=True)
            elif tipo == "idle_prompt" or "waiting" in msg.lower():
                self.set_state("wave", 3)
                self.dizer("Tô te esperando… ☕", 5, forcar=True)
            else:
                self.dizer(resumo(msg) or "Psiu! O Claude chamou 🔔", 6, forcar=True)
        elif ev == "Stop":
            texto = resumo(d.get("last_assistant_message") or ultima_resposta(d.get("transcript_path")))
            self.set_state("party", 3.5)
            self.dizer("Pronto! 🎁 " + texto if texto else "Pronto! Terminei 🎁", 7, forcar=True)
            self.soltar("presente")
            if random.random() < 0.35:
                GLib.timeout_add(1800, lambda: self.poder(random.choice(["explosao", "rajada", "aura"])) and False)
        elif ev == "SubagentStart":
            self.dizer("Um elfo entrou na oficina 🧝", 3)
        elif ev == "SubagentStop":
            self.soltar(random.choice(["estrela", "biscoito"]))
        elif ev == "SessionEnd":
            self.set_state("wave", 3)
            self.dizer("Tchau! Feliz Natal 🎄", 4)

    # ---------- desenho ----------
    def on_draw(self, _w, cr):
        limpar(cr)
        el = time.time() - self.state_ini
        no_ar = self.surf == "chao" and not self.no_chao() and not self.arrastando
        andando = self.state in ("walk", "work") and not no_ar and not self.arrastando
        agora = time.time()
        carregando = self.state == "power" and el < 0.5
        if agora < self.aura_ate or carregando:
            self.desenhar_aura(cr, min(1.0, el / 0.4) if carregando else 1.0)
        if not self.oculto:
            pixels = montar_pixels(self.cfg, self.state, self.t, el, andando, no_ar, self.arrastando)
            cr.push_group()
            cr.translate(self.S / 2, self.S / 2)
            cr.rotate(self.ANGULO[self.surf])
            if self.state == "ko":  # cai de costas
                k = min(1.0, el / 0.3)
                cr.translate(0, -9 * self.px * k)
                cr.rotate((-1 if self.dir > 0 else 1) * math.pi / 2 * k)
            desenhar_sprite(cr, pixels, self.px, self.espelho())
            if agora < self.dor_ate:
                cr.set_operator(cairo.OPERATOR_ATOP)
                cr.set_source_rgba(1, 0.15, 0.15, 0.6)
                cr.paint()
            cr.pop_group_to_source()
            cr.paint()
        hx, hy = self.cabeca()
        if self.state == "ko":
            self.desenhar_estrelas(cr, self.x - self.win_x - self.dir * 16 * self.px, self.y - self.win_y - 9 * self.px)
        elif self.oponente or agora < self.barra_ate:
            self.desenhar_vida(cr, hx - self.win_x, hy - self.win_y)
        if self.state == "sleep":
            self.desenhar_zzz(cr, hx - self.win_x, hy - self.win_y)
        agora = time.time()
        if agora < self.balao_ate and self.balao:
            alfa = min(1.0, (agora - self.balao_ini) / 0.2, (self.balao_ate - agora) / 0.3)
            cr.push_group()
            self.desenhar_balao(cr, hx, hy)
            cr.pop_group_to_source()
            cr.paint_with_alpha(max(0.0, alfa))
        return True

    def desenhar_aura(self, cr, forca):
        cx, cy = self.cabeca(0.5)
        cx, cy = cx - self.win_x, cy - self.win_y
        cor = self.cor_poder()
        raio = (13 + 1.5 * math.sin(self.t * 0.3)) * self.px * forca
        cr.set_source_rgba(*cor, 0.12)
        cr.arc(cx, cy, raio, 0, 2 * math.pi)
        cr.fill()
        cr.set_line_width(max(2, self.px * 0.8))
        for k, a in ((1.0, 0.75), (0.8, 0.4)):
            cr.set_source_rgba(*cor, a)
            cr.arc(cx, cy, raio * k, 0, 2 * math.pi)
            cr.stroke()
        for i in range(6):  # faíscas girando
            ang = self.t * 0.12 + i * math.pi / 3
            cr.set_source_rgba(*(BRANCO if i % 2 else cor), 0.9)
            cr.rectangle(cx + math.cos(ang) * raio - self.px / 2, cy + math.sin(ang) * raio - self.px / 2,
                         self.px, self.px)
            cr.fill()

    def desenhar_vida(self, cr, x, y):
        larg, alt = 40 + 3 * self.px, 7
        x0, y0 = x - larg / 2, y - alt - 2
        cr.set_source_rgba(0.1, 0.1, 0.12, 0.85)
        cr.rectangle(x0 - 2, y0 - 2, larg + 4, alt + 4)
        cr.fill()
        f = self.hp / 100
        cr.set_source_rgb(*(VERDE if f > 0.5 else OURO if f > 0.25 else VERMELHO))
        cr.rectangle(x0, y0, larg * f, alt)
        cr.fill()

    def desenhar_estrelas(self, cr, x, y):
        for i in range(4):
            ang = self.t * 0.15 + i * math.pi / 2
            cr.set_source_rgb(*(OURO if i % 2 else BRANCO))
            cr.rectangle(x + math.cos(ang) * 6 * self.px - self.px / 2, y + math.sin(ang) * 2 * self.px - self.px / 2,
                         self.px, self.px)
            cr.fill()

    def desenhar_zzz(self, cr, x, y):
        k = (self.t // 12) % 3
        lay = PangoCairo.create_layout(cr)
        lay.set_font_description(Pango.FontDescription("Sans Bold 11"))
        lay.set_text("z Z z"[: 1 + 2 * k], -1)
        cr.set_source_rgba(0.55, 0.75, 1.0, 0.95)
        cr.move_to(x + 2 * self.px, y - 16 - 4 * k)
        PangoCairo.show_layout(cr, lay)

    def desenhar_balao(self, cr, hx, hy):
        lay = PangoCairo.create_layout(cr)
        lay.set_font_description(Pango.FontDescription("Sans Bold 10"))
        lay.set_width(220 * Pango.SCALE)
        lay.set_wrap(Pango.WrapMode.WORD_CHAR)
        lay.set_height(-4)
        lay.set_ellipsize(Pango.EllipsizeMode.END)
        lay.set_text(self.balao, -1)
        tw, th = lay.get_pixel_size()
        bw, bh = tw + 20, th + 14
        g, _ = self.monitor(self.x, self.y)
        gx = min(max(hx - bw / 2, g.x + 4), g.x + g.width - bw - 4)
        gy = hy - bh - 10
        embaixo = gy < g.y + 4
        if embaixo:
            gy = hy + 10 + 19 * self.px * (self.surf == "chao")
        bx, by = gx - self.win_x, gy - self.win_y
        ponta = min(max(hx - self.win_x, bx + 14), bx + bw - 14)
        r = 9
        cr.new_path()
        cr.arc(bx + r, by + r, r, math.pi, 1.5 * math.pi)
        if embaixo:
            cr.line_to(ponta - 7, by)
            cr.line_to(ponta, by - 9)
            cr.line_to(ponta + 7, by)
        cr.arc(bx + bw - r, by + r, r, 1.5 * math.pi, 2 * math.pi)
        cr.arc(bx + bw - r, by + bh - r, r, 0, 0.5 * math.pi)
        if not embaixo:
            cr.line_to(ponta + 7, by + bh)
            cr.line_to(ponta, by + bh + 9)
            cr.line_to(ponta - 7, by + bh)
        cr.arc(bx + r, by + bh - r, r, 0.5 * math.pi, math.pi)
        cr.close_path()
        cr.set_source_rgb(1, 1, 1)
        cr.fill_preserve()
        cr.set_line_width(2.5)
        cr.set_source_rgb(*rgb(self.cfg["cor_detalhe"]))
        cr.stroke()
        cr.set_source_rgb(0.15, 0.10, 0.10)
        cr.move_to(bx + 10, by + 7)
        PangoCairo.show_layout(cr, lay)


class Personalizar(Gtk.Window):
    """Janela para escolher nome, personagem, chapéu, uniforme, cores e tamanho."""

    PREVIEW = ["walk", "wave", "cocoa", "idle", "drop", "party", "power"]

    def __init__(self, app):
        super().__init__(title="Personalizar mascote")
        self.app, self.t = app, 0
        self.set_border_width(16)
        self.set_keep_above(True)
        self.set_resizable(False)
        self.connect("delete-event", lambda *_: self.hide() or True)

        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        self.add(caixa)
        self.preview = Gtk.DrawingArea()
        self.preview.set_size_request(220, 260)
        self.preview.connect("draw", self.on_preview)
        caixa.pack_start(self.preview, False, False, 0)

        grade = Gtk.Grid(column_spacing=12, row_spacing=8)
        caixa.pack_start(grade, True, True, 0)
        self.linha = 0

        def add(rotulo, w):
            grade.attach(Gtk.Label(label=rotulo, xalign=0), 0, self.linha, 1, 1)
            w.set_hexpand(True)
            grade.attach(w, 1, self.linha, 1, 1)
            self.linha += 1
            return w

        def combo(opcoes, chave):
            c = Gtk.ComboBoxText()
            for ident, rotulo in opcoes.items():
                c.append(ident, rotulo)
            c.connect("changed", lambda w: self.ocupado or self.mudar_combo(chave, w.get_active_id()))
            return c

        def chave_liga(chave):
            s = Gtk.Switch(halign=Gtk.Align.START)
            s.set_hexpand(False)
            s.connect("notify::active", lambda w, _p: self.ocupado or self.app.mudar(**{chave: w.get_active()}))
            return s

        def cor(chave):
            b = Gtk.ColorButton()
            b.connect("color-set", lambda w: self.mudar_cor(chave, w))
            return b

        self.ocupado = True
        self.w_nome = add("Nome", Gtk.Entry())
        self.w_nome.connect("changed", lambda e: self.ocupado or self.app.mudar(nome=e.get_text()))
        self.w_modelo = add("Personagem", combo({k: v[0] for k, v in MODELOS.items()}, "modelo"))
        self.w_chapeu = add("Chapéu", combo(CHAPEUS, "chapeu"))
        self.w_uniforme = add("Uniforme", combo(UNIFORMES, "uniforme"))
        grade.attach(Gtk.Label(label="Logo TX no uniforme", xalign=0), 0, self.linha, 1, 1)
        self.w_logo = chave_liga("logo")
        grade.attach(self.w_logo, 1, self.linha, 1, 1)
        self.linha += 1
        self.w_logo_estilo = add("Estilo da logo", combo(LOGO_ESTILOS, "logo_estilo"))
        grade.attach(Gtk.Label(label="Cores automáticas da logo", xalign=0), 0, self.linha, 1, 1)
        self.w_logo_auto = chave_liga("logo_auto")
        grade.attach(self.w_logo_auto, 1, self.linha, 1, 1)
        self.linha += 1
        self.w_cor_logo = add("Cor da logo", cor("cor_logo"))
        self.w_cor_seta = add("Cor da seta / poder", cor("cor_seta"))
        self.w_cor_corpo = add("Cor do corpo", cor("cor_corpo"))
        self.w_cor_uniforme = add("Cor do uniforme", cor("cor_uniforme"))
        self.w_cor_detalhe = add("Cor de detalhe", cor("cor_detalhe"))
        self.w_tamanho = add("Tamanho", Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 2, 12, 1))
        self.w_tamanho.connect("value-changed",
                               lambda w: self.ocupado or self.app.mudar(tamanho=int(w.get_value())))
        self.w_vel = add("Velocidade", Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.3, 3.0, 0.1))
        self.w_vel.connect("value-changed",
                           lambda w: self.ocupado or self.app.mudar(velocidade=round(w.get_value(), 1)))
        for rotulo, chave in (("Andar nas paredes", "paredes"), ("Falas aleatórias", "falas"),
                              ("Lutar com a turma", "lutas")):
            grade.attach(Gtk.Label(label=rotulo, xalign=0), 0, self.linha, 1, 1)
            s = chave_liga(chave)
            setattr(self, "w_" + chave, s)
            grade.attach(s, 1, self.linha, 1, 1)
            self.linha += 1
        dica = Gtk.Label(xalign=0)
        dica.set_markup("<small>Personagens próprios: coloque um .json em\n"
                        "~/.config/mascote-tx/personagens/ e reabra o mascote.</small>")
        grade.attach(dica, 0, self.linha, 2, 1)
        self.linha += 1
        botoes = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        poder = Gtk.Button(label="⚡ Soltar poder")
        poder.connect("clicked", lambda _b: self.app.poder())
        botoes.pack_start(poder, False, False, 0)
        restaurar = Gtk.Button(label="Restaurar padrão")
        restaurar.connect("clicked", lambda _b: self.restaurar())
        fechar = Gtk.Button(label="Fechar")
        fechar.connect("clicked", lambda _b: self.hide())
        botoes.pack_start(restaurar, False, False, 0)
        botoes.pack_start(fechar, False, False, 0)
        grade.attach(botoes, 0, self.linha, 2, 1)
        self.recarregar()
        GLib.timeout_add(100, self.animar)

    def recarregar(self):
        cfg = self.app.cfg
        self.ocupado = True
        self.w_nome.set_text(cfg["nome"])
        self.w_modelo.set_active_id(cfg["modelo"])
        self.w_chapeu.set_active_id(cfg["chapeu"])
        self.w_uniforme.set_active_id(cfg["uniforme"])
        self.w_logo.set_active(cfg["logo"])
        self.w_logo_estilo.set_active_id(cfg["logo_estilo"])
        self.w_logo_auto.set_active(cfg["logo_auto"])
        for chave, w in (("cor_corpo", self.w_cor_corpo), ("cor_uniforme", self.w_cor_uniforme),
                         ("cor_detalhe", self.w_cor_detalhe), ("cor_logo", self.w_cor_logo),
                         ("cor_seta", self.w_cor_seta)):
            rgba = Gdk.RGBA()
            rgba.parse(cfg[chave] or MODELOS[cfg["modelo"]][1])
            w.set_rgba(rgba)
        self.w_tamanho.set_value(cfg["tamanho"])
        self.w_vel.set_value(cfg["velocidade"])
        self.w_paredes.set_active(cfg["paredes"])
        self.w_falas.set_active(cfg["falas"])
        self.w_lutas.set_active(cfg["lutas"])
        self.set_title(f"Personalizar {cfg['nome']}")
        self.ocupado = False

    def mudar_combo(self, chave, valor):
        extra = {"cor_corpo": None} if chave == "modelo" else {}
        self.app.mudar(**{chave: valor}, **extra)
        if chave == "modelo":
            self.recarregar()

    def mudar_cor(self, chave, botao):
        rgba = botao.get_rgba()
        extra = {"logo_auto": False} if chave in ("cor_logo", "cor_seta") else {}
        self.app.mudar(**{chave: hexa((rgba.red, rgba.green, rgba.blue))}, **extra)
        if extra:
            self.recarregar()

    def restaurar(self):
        self.app.cfg = dict(PADRAO, nome=self.app.cfg["nome"]) if self.app is not TURMA[0] else dict(PADRAO)
        self.app.aplicar_config()
        self.recarregar()

    def animar(self):
        if self.get_visible():
            self.t += 1
            self.preview.queue_draw()
            self.set_title(f"Personalizar {self.app.cfg['nome']}")
        return True

    def on_preview(self, w, cr):
        larg, alt = w.get_allocated_width(), w.get_allocated_height()
        cr.set_source_rgb(0.13, 0.14, 0.16)
        cr.rectangle(0, 0, larg, alt)
        cr.fill()
        s = self.PREVIEW[(self.t // 30) % len(self.PREVIEW)]
        el = (self.t % 30) / 10
        px = 6
        cr.save()
        cr.translate(larg / 2, alt - 40)
        desenhar_sprite(cr, montar_pixels(self.app.cfg, s, self.t * 3, el, andando=s == "walk"), px, False)
        cr.restore()
        lay = PangoCairo.create_layout(cr)
        lay.set_font_description(Pango.FontDescription("Sans Bold 12"))
        lay.set_text(self.app.cfg["nome"], -1)
        tw, _ = lay.get_pixel_size()
        cr.set_source_rgb(0.95, 0.95, 0.95)
        cr.move_to((larg - tw) / 2, alt - 30)
        PangoCairo.show_layout(cr, lay)
        return True


ULTIMO = {}


def rotear(caminho, dados):
    """Roda no laço do GTK: distribui as chamadas HTTP entre os mascotes."""
    if not TURMA:
        return False
    alvo = achar(dados.get("mascote")) or TURMA[0]
    if caminho == "/adicionar":
        adicionar_mascote(dados.get("modelo"), dados.get("nome"))
    elif caminho == "/lutar":
        a = achar(dados.get("a")) or TURMA[0]
        rivais = [m for m in TURMA if m is not a]
        b = achar(dados.get("b")) or (random.choice(rivais) if rivais else None)
        if b:
            a.desafiar(b)
    elif caminho == "/remover":
        alvo.remover()
    elif caminho in ("/falar", "/config"):
        alvo.on_http(caminho, dados)
    else:
        TURMA[0].on_evento(dados)
        if dados.get("hook_event_name") == "Stop":
            for m in TURMA[1:]:
                if not m.oponente:
                    m.set_state("party", 3)
    return False


def estado(m):
    return {"mascote": m.cfg["nome"], "x": round(m.x), "y": round(m.y), "superficie": m.surf,
            "estado": m.state, "vida": m.hp, "oponente": m.oponente.cfg["nome"] if m.oponente else None}


def iniciar_servidor():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                dados = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except ValueError:
                dados = {}
            if not isinstance(dados, dict):
                dados = {}
            caminho = self.path.split("?")[0]
            ULTIMO["evento"] = dados.get("hook_event_name") or caminho
            ULTIMO["quando"] = time.strftime("%H:%M:%S")
            GLib.idle_add(rotear, caminho, dados)
            self._responder(b"{}")

        def do_GET(self):
            turma = list(TURMA)
            if not turma:
                corpo = {"ok": False}
            elif self.path.split("?")[0] == "/config":
                corpo = turma[0].cfg
            else:
                corpo = {"ok": True, **estado(turma[0]), "ultimo": ULTIMO, "turma": [estado(m) for m in turma]}
            self._responder(json.dumps(corpo, ensure_ascii=False).encode())

        def _responder(self, corpo):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *_):
            pass

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORTA), Handler)
    except OSError:
        print(f"O mascote já está rodando (porta {PORTA} ocupada).")
        sys.exit(0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def main():
    carregar_personagens()
    iniciar_servidor()
    TURMA.append(Mascote())
    for arq in sorted(glob.glob(os.path.join(TURMA_DIR, "*.json"))):
        TURMA.append(Mascote(arq))
    if "--personalizar" in sys.argv:
        TURMA[0].abrir_personalizar()
    Gtk.main()


if __name__ == "__main__":
    main()
