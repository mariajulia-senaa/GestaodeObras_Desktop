from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

COR = {
    "fundo": "#f3f5f9",
    "card": "#ffffff",
    "lateral": "#1b2540",
    "lateral_hover": "#2a3760",
    "lateral_ativa": "#34447a",
    "destaque": "#f59e0b",
    "destaque_hover": "#d98a06",
    "texto": "#1f2937",
    "suave": "#6b7280",
    "borda": "#dfe4ee",
    "ok": "#15803d",
    "ok_fundo": "#dcfce7",
    "perigo": "#b91c1c",
    "perigo_hover": "#991b1b",
    "selecao": "#fde7b0",
    "info": "#2563eb",
}

FAMILIAS_PREFERIDAS = ("Segoe UI", "Helvetica Neue", "Inter", "Noto Sans", "DejaVu Sans")
FAMILIA = "TkDefaultFont"


def fonte(tamanho: int = 10, peso: str = "normal") -> tuple:
    return (FAMILIA, tamanho, peso)


def _escolher_familia(raiz: tk.Misc) -> str:
    disponiveis = set(tkfont.families(raiz))
    for nome in FAMILIAS_PREFERIDAS:
        if nome in disponiveis:
            return nome
    return tkfont.nametofont("TkDefaultFont").actual("family")


def _botao(estilo: ttk.Style, nome: str, fundo: str, texto: str, hover: str, **extra) -> None:
    estilo.configure(
        nome, background=fundo, foreground=texto, relief="flat", borderwidth=0,
        padding=(16, 9), font=fonte(10, "bold"), focuscolor=fundo,
        lightcolor=fundo, darkcolor=fundo, bordercolor=fundo, **extra,
    )
    estilo.map(
        nome,
        background=[("pressed", hover), ("active", hover)],
        foreground=[("pressed", texto), ("active", texto)],
        bordercolor=[("pressed", hover), ("active", hover)],
        lightcolor=[("pressed", hover), ("active", hover)],
        darkcolor=[("pressed", hover), ("active", hover)],
    )


def aplicar_tema(raiz: tk.Misc) -> None:
    global FAMILIA
    FAMILIA = _escolher_familia(raiz)
    raiz.configure(bg=COR["fundo"])
    raiz.option_add("*TCombobox*Listbox.font", fonte(10))
    raiz.option_add("*TCombobox*Listbox.background", COR["card"])
    raiz.option_add("*TCombobox*Listbox.foreground", COR["texto"])
    raiz.option_add("*TCombobox*Listbox.selectBackground", COR["destaque"])
    raiz.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    e = ttk.Style(raiz)
    e.theme_use("clam")
    e.configure(".", background=COR["fundo"], foreground=COR["texto"], font=fonte(10),
                bordercolor=COR["borda"])

    e.configure("TFrame", background=COR["fundo"])
    e.configure("Card.TFrame", background=COR["card"], relief="solid", borderwidth=1,
                bordercolor=COR["borda"])
    e.configure("Lateral.TFrame", background=COR["lateral"])
    e.configure("Notificacao.TFrame", background=COR["ok_fundo"])

    e.configure("TLabel", background=COR["fundo"], foreground=COR["texto"])
    e.configure("Card.TLabel", background=COR["card"])
    e.configure("Titulo.TLabel", font=fonte(20, "bold"))
    e.configure("Secao.TLabel", font=fonte(14, "bold"))
    e.configure("Subtitulo.TLabel", foreground=COR["suave"])
    e.configure("Erro.TLabel", foreground=COR["perigo"])
    e.configure("Ok.TLabel", foreground=COR["ok"])
    e.configure("Vazio.TLabel", foreground=COR["suave"], font=fonte(11))
    e.configure("Lateral.TLabel", background=COR["lateral"], foreground="#ffffff")
    e.configure("LateralTitulo.TLabel", background=COR["lateral"], foreground="#ffffff",
                font=fonte(20, "bold"))
    e.configure("LateralSuave.TLabel", background=COR["lateral"], foreground="#94a3b8")
    e.configure("Notificacao.TLabel", background=COR["ok_fundo"], foreground=COR["ok"],
                font=fonte(10, "bold"), padding=(32, 10))
    e.configure("CardTitulo.TLabel", background=COR["card"], foreground=COR["suave"],
                font=fonte(9, "bold"))
    e.configure("CardValor.TLabel", background=COR["card"], font=fonte(18, "bold"))
    e.configure("Ok.CardValor.TLabel", foreground=COR["ok"])
    e.configure("Perigo.CardValor.TLabel", foreground=COR["perigo"])
    e.configure("CardNota.TLabel", background=COR["card"], foreground=COR["suave"],
                font=fonte(9))

    _botao(e, "Primario.TButton", COR["destaque"], "#ffffff", COR["destaque_hover"])
    _botao(e, "Perigo.TButton", COR["perigo"], "#ffffff", COR["perigo_hover"])
    _botao(e, "Secundario.TButton", COR["card"], COR["texto"], "#eef1f7")
    e.configure("Secundario.TButton", borderwidth=1, bordercolor=COR["borda"])
    e.map("Secundario.TButton", bordercolor=[("active", COR["borda"])])
    _botao(e, "Menu.TButton", COR["lateral"], "#cbd5e1", COR["lateral_hover"],
           anchor="w")
    e.configure("Menu.TButton", padding=(22, 13), font=fonte(10))
    e.map("Menu.TButton", foreground=[("active", "#ffffff")])
    _botao(e, "MenuAtivo.TButton", COR["lateral_ativa"], "#ffffff", COR["lateral_ativa"],
           anchor="w")
    e.configure("MenuAtivo.TButton", padding=(22, 13))
    _botao(e, "Link.TButton", COR["fundo"], COR["info"], COR["fundo"])
    e.configure("Link.TButton", padding=(0, 4), font=fonte(10))
    e.map("Link.TButton", foreground=[("active", COR["destaque_hover"])])

    campo = dict(fieldbackground=COR["card"], padding=7, bordercolor=COR["borda"],
                 lightcolor=COR["borda"], darkcolor=COR["borda"], relief="flat")
    destaque = [("focus", COR["destaque"])]
    e.configure("TEntry", **campo)
    e.map("TEntry", bordercolor=destaque, lightcolor=destaque, darkcolor=destaque)
    e.configure("TCombobox", background=COR["card"], arrowcolor=COR["suave"], **campo)
    e.map("TCombobox", fieldbackground=[("readonly", COR["card"])],
          selectbackground=[("readonly", COR["card"])],
          selectforeground=[("readonly", COR["texto"])],
          bordercolor=destaque, lightcolor=destaque, darkcolor=destaque)

    e.configure("Treeview", background=COR["card"], fieldbackground=COR["card"],
                foreground=COR["texto"], rowheight=32, borderwidth=0, font=fonte(10))
    e.map("Treeview", background=[("selected", COR["selecao"])],
          foreground=[("selected", COR["texto"])])
    e.configure("Treeview.Heading", background=COR["lateral"], foreground="#ffffff",
                font=fonte(10, "bold"), relief="flat", padding=(8, 8))
    e.map("Treeview.Heading", background=[("active", COR["lateral_hover"])])
    e.configure("Vertical.TScrollbar", background=COR["borda"], troughcolor=COR["card"],
                bordercolor=COR["card"], arrowcolor=COR["suave"])
