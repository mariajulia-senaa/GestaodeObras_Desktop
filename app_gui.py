"""Sistema de Gestão de Obras - interface gráfica (Nível 4).

Uso:
    python app_gui.py                 # usa o banco gestao_obras.db
    python app_gui.py --db outro.db   # usa outro arquivo de banco
"""
from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

import tema
from casos_uso import (
    AdicionarEtapa, AdicionarRecurso, CadastrarObra, ConcluirObra, GerarRelatorioKPIs,
    GerenciarEngenheiros, RegistrarAvancoRealCDU02,
)
from casos_uso import ExibidorRelatorioKPIs as Fmt
from dominio import (
    Engenheiro, ErroDadosInsuficientes, ErroPreCondicao, ErroValidacao, Etapa, Material, Obra,
)
from repositorio import RepositorioSQLite
from tema import COR, fonte

ERROS_ESPERADOS = (ErroValidacao, ErroPreCondicao, ErroDadosInsuficientes)

COLUNAS_OBRAS = [
    ("id", "Código", 80, "center"),
    ("nome", "Nome da obra", 320, "w"),
    ("status", "Status", 130, "center"),
    ("etapas", "Etapas", 80, "center"),
    ("progresso", "Progresso", 220, "w"),
]


def texto_data(valor) -> str:
    return Fmt.data(valor) if valor else "-"


def texto_moeda(valor, sinal: bool = False) -> str:
    return "-" if valor is None else Fmt.moeda(valor, sinal)


def texto_numero(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")


def rotulo(item) -> str:
    return f"{item.id} - {item.nome}"


def id_do_rotulo(texto: str) -> Optional[int]:
    try:
        return int(texto.split(" - ")[0])
    except (ValueError, IndexError):
        return None


def progresso_obra(obra: Obra) -> Optional[float]:
    if not obra.etapas:
        return None
    return sum(e.percentual_conclusao for e in obra.etapas) / len(obra.etapas)


def texto_progresso(obra: Obra) -> str:
    pct = progresso_obra(obra)
    if pct is None:
        return "sem etapas"
    cheios = round(pct / 10)
    return f"{'█' * cheios}{'░' * (10 - cheios)}  {pct:.0f}%"


def nota_prazo(dias: int) -> str:
    return "atraso" if dias > 0 else "adiantamento" if dias < 0 else "no prazo"


def mostrar_erro(pai, titulo: str, mensagem: str) -> None:
    messagebox.showerror(titulo, mensagem, parent=pai)


def confirmar(pai, mensagem: str) -> bool:
    return messagebox.askyesno("Confirmar", mensagem, parent=pai)


def tentar(pai, acao: Callable[[], None]) -> bool:
    try:
        acao()
    except ErroPreCondicao as e:
        mostrar_erro(pai, "Não foi possível concluir", str(e))
        return False
    except ErroDadosInsuficientes as e:
        mostrar_erro(pai, "Dados insuficientes", str(e))
        return False
    except ErroValidacao as e:
        mostrar_erro(pai, "Dados inválidos", str(e))
        return False
    return True


def centralizar(janela: tk.Misc, largura: int, altura: int) -> None:
    janela.update_idletasks()
    x = max((janela.winfo_screenwidth() - largura) // 2, 0)
    y = max((janela.winfo_screenheight() - altura) // 3, 0)
    janela.geometry(f"{largura}x{altura}+{x}+{y}")


def criar_tabela(pai, colunas, altura: int = 8):
    quadro = ttk.Frame(pai, style="Card.TFrame")
    arvore = ttk.Treeview(quadro, columns=[c[0] for c in colunas], show="headings",
                          height=altura, selectmode="browse")
    for chave, titulo, largura, ancora in colunas:
        arvore.heading(chave, text=titulo, anchor=ancora)
        arvore.column(chave, width=largura, anchor=ancora)
    rolagem = ttk.Scrollbar(quadro, orient="vertical", command=arvore.yview)
    arvore.configure(yscrollcommand=rolagem.set)
    arvore.pack(side="left", fill="both", expand=True)
    rolagem.pack(side="right", fill="y")
    arvore.tag_configure("concluida", foreground=COR["ok"])
    arvore.tag_configure("atraso", foreground=COR["perigo"])
    return quadro, arvore


def preencher(arvore: ttk.Treeview, linhas) -> None:
    arvore.delete(*arvore.get_children())
    for iid, valores, tags in linhas:
        arvore.insert("", "end", iid=str(iid), values=valores, tags=tuple(tags))


def linhas_obras(obras: list[Obra]):
    return [
        (o.id, (o.id, o.nome, o.status.value, len(o.etapas), texto_progresso(o)),
         ("concluida",) if not o.esta_em_andamento() else ())
        for o in obras
    ]


class Logo(tk.Canvas):
    def __init__(self, pai, tamanho: int = 44, fundo: str = COR["lateral"]):
        super().__init__(pai, width=tamanho, height=tamanho, bg=fundo, highlightthickness=0)
        t = tamanho
        self.create_rectangle(0, 0, t, t, fill=COR["destaque"], outline="")
        base = t * 0.82
        for i, altura in enumerate((0.34, 0.58, 0.46)):
            x0 = t * (0.16 + i * 0.27)
            self.create_rectangle(x0, base - t * altura, x0 + t * 0.19, base,
                                  fill="#ffffff", outline="")


class Cartao(ttk.Frame):
    def __init__(self, pai, titulo: str):
        super().__init__(pai, style="Card.TFrame", padding=(18, 14))
        ttk.Label(self, text=titulo.upper(), style="CardTitulo.TLabel").pack(anchor="w")
        self.valor = ttk.Label(self, text="-", style="CardValor.TLabel")
        self.valor.pack(anchor="w", pady=(6, 0))
        self.nota = ttk.Label(self, text=" ", style="CardNota.TLabel")
        self.nota.pack(anchor="w")

    def definir(self, texto: str, tom: str = "", nota: str = " ") -> None:
        estilo = {"ok": "Ok.CardValor.TLabel", "perigo": "Perigo.CardValor.TLabel"}.get(
            tom, "CardValor.TLabel")
        self.valor.configure(text=texto, style=estilo)
        self.nota.configure(text=nota or " ")


class Dialogo(tk.Toplevel):
    def __init__(self, app: "Aplicacao", titulo: str, subtitulo: str,
                 ao_concluir: Optional[Callable[[], None]] = None):
        super().__init__(app)
        self.app = app
        self.ao_concluir = ao_concluir
        self.title(titulo)
        self.configure(bg=COR["fundo"])
        self.resizable(False, False)
        self.transient(app)
        corpo = ttk.Frame(self, padding=(30, 26))
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=titulo, style="Secao.TLabel").pack(anchor="w")
        ttk.Label(corpo, text=subtitulo, style="Subtitulo.TLabel", wraplength=380).pack(
            anchor="w", pady=(2, 0))
        self.formulario = ttk.Frame(corpo)
        self.formulario.pack(fill="x", pady=(8, 0))
        self._corpo = corpo
        self._entradas: list[ttk.Entry] = []

    def campo(self, texto: str, dica: str = "", valor: str = "") -> ttk.Entry:
        etiqueta = ttk.Label(self.formulario, text=texto)
        etiqueta.pack(anchor="w", pady=(12, 4))
        entrada = ttk.Entry(self.formulario, width=44)
        entrada.pack(fill="x")
        entrada.rotulo = etiqueta
        if valor:
            entrada.insert(0, valor)
        if dica:
            ttk.Label(self.formulario, text=dica, style="Subtitulo.TLabel",
                      wraplength=380).pack(anchor="w", pady=(3, 0))
        self._entradas.append(entrada)
        return entrada

    def lista(self, texto: str, valores: list[str]) -> ttk.Combobox:
        ttk.Label(self.formulario, text=texto).pack(anchor="w", pady=(12, 4))
        combo = ttk.Combobox(self.formulario, state="readonly", values=valores, width=42)
        combo.pack(fill="x")
        return combo

    def finalizar(self, texto_confirmar: str) -> None:
        rodape = ttk.Frame(self._corpo)
        rodape.pack(fill="x", pady=(24, 0))
        self.botao_confirmar = ttk.Button(rodape, text=texto_confirmar,
                                          style="Primario.TButton", command=self.confirmar)
        self.botao_confirmar.pack(side="right")
        ttk.Button(rodape, text="Cancelar", style="Secundario.TButton",
                   command=self.destroy).pack(side="right", padx=(0, 10))
        self.bind("<Return>", self.confirmar)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar(self, max(self.winfo_reqwidth(), 460), self.winfo_reqheight())
        if self._entradas:
            self._entradas[0].focus_set()
        self._capturar()

    def _capturar(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            self.after(50, self._capturar)

    def confirmar(self, _evento=None) -> None:
        resultado: list[str] = []
        if not tentar(self, lambda: resultado.append(self.salvar())):
            return
        self.destroy()
        if resultado and resultado[0]:
            self.app.notificar(resultado[0])
        if self.ao_concluir:
            self.ao_concluir()

    def salvar(self) -> str:
        raise NotImplementedError


class DialogoNovaObra(Dialogo):
    def __init__(self, app, ao_concluir=None):
        super().__init__(app, "Nova obra", "A obra nasce em andamento e fica alocada a você.",
                         ao_concluir)
        self.entrada_codigo = self.campo("Código (ID) da obra", "Número inteiro positivo, único.")
        self.entrada_nome = self.campo("Nome da obra")
        self.finalizar("Cadastrar obra")

    def salvar(self) -> str:
        obra = self.app.cadastrar_obra.executar(
            self.entrada_codigo.get(), self.entrada_nome.get(), self.app.usuario)
        return f"Obra '{obra.nome}' cadastrada e alocada a você."


class DialogoEtapa(Dialogo):
    def __init__(self, app, obra: Obra, ao_concluir=None):
        super().__init__(app, "Nova etapa", f"Planejamento da etapa na obra '{obra.nome}'.",
                         ao_concluir)
        self.obra = obra
        self.entrada_nome = self.campo("Nome da etapa")
        self.entrada_inicio = self.campo("Início planejado", "Formato dd/mm/aaaa")
        self.entrada_fim = self.campo("Término planejado", "Formato dd/mm/aaaa")
        self.entrada_custo = self.campo("Custo planejado (R$)")
        self.finalizar("Salvar etapa")

    def salvar(self) -> str:
        etapa = self.app.adicionar_etapa.executar(
            self.obra, self.entrada_nome.get(), self.entrada_inicio.get(),
            self.entrada_fim.get(), self.entrada_custo.get())
        return f"Etapa '{etapa.nome}' adicionada à obra '{self.obra.nome}'."


class DialogoRecurso(Dialogo):
    ROTULOS = {
        "Material": ("Quantidade", "Preço unitário (R$)"),
        "Equipamento": ("Horas de uso", "Taxa por hora (R$)"),
    }

    def __init__(self, app, obra: Obra, etapa: Etapa, ao_concluir=None):
        super().__init__(app, "Material ou equipamento",
                         f"Recurso da etapa '{etapa.nome}' (obra '{obra.nome}').", ao_concluir)
        self.obra, self.etapa = obra, etapa
        self.combo_tipo = self.lista("Tipo de recurso", list(self.ROTULOS))
        self.combo_tipo.set("Material")
        self.combo_tipo.bind("<<ComboboxSelected>>", self._trocar_tipo)
        self.entrada_nome = self.campo("Nome do recurso")
        self.entrada_quantidade = self.campo("Quantidade")
        self.entrada_valor = self.campo("Preço unitário (R$)")
        self.finalizar("Adicionar recurso")

    def _trocar_tipo(self, _evento=None) -> None:
        quantidade, valor = self.ROTULOS[self.combo_tipo.get()]
        self.entrada_quantidade.rotulo.configure(text=quantidade)
        self.entrada_valor.rotulo.configure(text=valor)

    def salvar(self) -> str:
        tipo = self.combo_tipo.get()
        self.app.adicionar_recurso.executar(
            self.obra, self.etapa.id, tipo, self.entrada_nome.get(),
            self.entrada_quantidade.get(), self.entrada_valor.get())
        return f"{tipo} '{self.entrada_nome.get().strip()}' adicionado à etapa '{self.etapa.nome}'."


class DialogoAvanco(Dialogo):
    def __init__(self, app, obra: Obra, etapa: Etapa, ao_concluir=None):
        super().__init__(app, "Registrar avanço real",
                         f"Etapa '{etapa.nome}' da obra '{obra.nome}'.", ao_concluir)
        self.obra, self.etapa = obra, etapa
        self.entrada_inicio = self.campo("Início real", "Formato dd/mm/aaaa")
        self.entrada_fim = self.campo("Término real", "Formato dd/mm/aaaa")
        self.entrada_custo = self.campo(
            "Custo real (R$)",
            f"Em branco, usa o custo dos recursos: {texto_moeda(etapa.custo_recursos())}")
        self.entrada_percentual = self.campo(
            "Conclusão (%)", "100 conclui a etapa.", valor="100")
        self.finalizar("Salvar avanço")

    def salvar(self) -> str:
        return self.app.avanco.salvar(
            self.obra, self.etapa.id, self.entrada_inicio.get(), self.entrada_fim.get(),
            self.entrada_custo.get(), self.entrada_percentual.get())


class Pagina(ttk.Frame):
    def __init__(self, pai, app: "Aplicacao", titulo: str, subtitulo: str):
        super().__init__(pai, padding=(32, 26, 32, 16))
        self.app = app
        ttk.Label(self, text=titulo, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self, text=subtitulo, style="Subtitulo.TLabel").pack(anchor="w", pady=(2, 0))

    def atualizar(self) -> None:
        pass

    def seletor_obra(self, comando: Callable[[], None]) -> ttk.Combobox:
        linha = ttk.Frame(self)
        linha.pack(fill="x", pady=(18, 0))
        ttk.Label(linha, text="Obra", font=fonte(10, "bold")).pack(side="left", padx=(0, 12))
        combo = ttk.Combobox(linha, state="readonly", width=46)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda _e: comando())
        self.barra_seletor = linha
        return combo

    def recarregar_seletor(self, combo: ttk.Combobox) -> None:
        obras = self.app.repo.listar_todas()
        atual = id_do_rotulo(combo.get())
        combo["values"] = [f"{o.id} - {o.nome}  [{o.status.value}]" for o in obras]
        ids = [o.id for o in obras]
        if atual in ids:
            combo.current(ids.index(atual))
        elif obras:
            combo.current(len(obras) - 1)
        else:
            combo.set("")

    def obra_do_seletor(self, combo: ttk.Combobox) -> Obra:
        id_obra = id_do_rotulo(combo.get())
        obra = self.app.repo.buscar_por_id(id_obra) if id_obra is not None else None
        if obra is None:
            raise ErroPreCondicao("Selecione uma obra.")
        return obra


class PaginaPainel(Pagina):
    def __init__(self, pai, app):
        super().__init__(pai, app, "Painel de obras", "Visão geral de todas as obras cadastradas.")
        cartoes = ttk.Frame(self)
        cartoes.pack(fill="x", pady=(18, 0))
        self.cartao_total = Cartao(cartoes, "Obras cadastradas")
        self.cartao_andamento = Cartao(cartoes, "Em andamento")
        self.cartao_concluidas = Cartao(cartoes, "Concluídas")
        for i, cartao in enumerate((self.cartao_total, self.cartao_andamento,
                                    self.cartao_concluidas)):
            cartao.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 14, 0))
            cartoes.columnconfigure(i, weight=1, uniform="cartao")

        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(18, 10))
        ttk.Button(barra, text="+  Nova obra", style="Primario.TButton",
                   command=self.nova_obra).pack(side="left")
        ttk.Button(barra, text="Concluir obra", style="Secundario.TButton",
                   command=self.concluir).pack(side="left", padx=(10, 0))
        ttk.Button(barra, text="Alocar-me à obra", style="Secundario.TButton",
                   command=self.alocar).pack(side="left", padx=(10, 0))
        ttk.Button(barra, text="Atualizar", style="Secundario.TButton",
                   command=self.atualizar).pack(side="right")

        quadro, self.tabela = criar_tabela(self, COLUNAS_OBRAS, 9)
        quadro.pack(fill="both", expand=True)

    def atualizar(self) -> None:
        obras = self.app.repo.listar_todas()
        concluidas = sum(1 for o in obras if not o.esta_em_andamento())
        self.cartao_total.definir(str(len(obras)), nota="no sistema")
        self.cartao_andamento.definir(str(len(obras) - concluidas), nota="em execução")
        self.cartao_concluidas.definir(str(concluidas), "ok" if concluidas else "",
                                       "finalizadas")
        preencher(self.tabela, linhas_obras(obras))

    def obra_selecionada(self) -> Obra:
        selecao = self.tabela.selection()
        obra = self.app.repo.buscar_por_id(int(selecao[0])) if selecao else None
        if obra is None:
            raise ErroPreCondicao("Selecione uma obra na tabela.")
        return obra

    def nova_obra(self) -> None:
        DialogoNovaObra(self.app, self.app.atualizar_paginas)

    def concluir(self) -> None:
        def acao():
            obra = self.obra_selecionada()
            if not confirmar(self, f"Concluir a obra '{obra.nome}'?"):
                return
            self.app.concluir_obra.executar(obra)
            self.app.notificar(f"Obra '{obra.nome}' concluída com sucesso.")
            self.app.atualizar_paginas()
        tentar(self, acao)

    def alocar(self) -> None:
        def acao():
            obra = self.obra_selecionada()
            self.app.engenheiros.alocar_obra(self.app.usuario, obra)
            self.app.notificar(f"Você foi alocado(a) à obra '{obra.nome}'.")
            self.app.atualizar_paginas()
        tentar(self, acao)


class PaginaEtapas(Pagina):
    COLUNAS_ETAPAS = [
        ("id", "Nº", 50, "center"),
        ("nome", "Etapa", 190, "w"),
        ("status", "Status", 110, "center"),
        ("pct", "%", 60, "center"),
        ("periodo", "Período planejado", 190, "center"),
        ("planejado", "Custo planejado", 120, "e"),
        ("real", "Custo real", 120, "e"),
    ]
    COLUNAS_RECURSOS = [
        ("tipo", "Tipo", 120, "w"),
        ("nome", "Recurso", 260, "w"),
        ("quantidade", "Quantidade / horas", 150, "center"),
        ("valor", "Valor unitário", 130, "e"),
        ("total", "Custo total", 130, "e"),
    ]

    def __init__(self, pai, app):
        super().__init__(pai, app, "Etapas e recursos",
                         "Planejamento, materiais, equipamentos e avanço real de cada etapa.")
        self.combo_obra = self.seletor_obra(self.carregar)
        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(14, 10))
        ttk.Button(barra, text="+  Nova etapa", style="Primario.TButton",
                   command=self.nova_etapa).pack(side="left")
        ttk.Button(barra, text="+  Material / equipamento", style="Secundario.TButton",
                   command=self.novo_recurso).pack(side="left", padx=(10, 0))
        ttk.Button(barra, text="Registrar avanço real", style="Secundario.TButton",
                   command=self.registrar_avanco).pack(side="left", padx=(10, 0))

        quadro, self.tabela_etapas = criar_tabela(self, self.COLUNAS_ETAPAS, 5)
        quadro.pack(fill="x")
        self.tabela_etapas.bind("<<TreeviewSelect>>", lambda _e: self.carregar_recursos())
        ttk.Label(self, text="Recursos da etapa selecionada", style="Secao.TLabel").pack(
            anchor="w", pady=(16, 8))
        quadro, self.tabela_recursos = criar_tabela(self, self.COLUNAS_RECURSOS, 4)
        quadro.pack(fill="both", expand=True)

    def atualizar(self) -> None:
        self.recarregar_seletor(self.combo_obra)
        self.carregar()

    def obra_atual(self) -> Obra:
        return self.obra_do_seletor(self.combo_obra)

    def etapa_selecionada(self, obra: Obra) -> Etapa:
        selecao = self.tabela_etapas.selection()
        etapa = obra.buscar_etapa(int(selecao[0])) if selecao else None
        if etapa is None:
            raise ErroPreCondicao("Selecione uma etapa na tabela.")
        return etapa

    def carregar(self) -> None:
        selecao = self.tabela_etapas.selection()
        try:
            obra = self.obra_atual()
        except ErroPreCondicao:
            preencher(self.tabela_etapas, [])
            preencher(self.tabela_recursos, [])
            return
        linhas = []
        for e in obra.etapas:
            periodo = "sem planejamento"
            if e.tem_planejamento():
                periodo = f"{texto_data(e.data_inicio_planejada)} a {texto_data(e.data_fim_planejada)}"
            real = texto_moeda(e.custo_real) if e.tem_avanco_real() else "-"
            linhas.append((e.id, (e.id, e.nome, e.status.value, f"{e.percentual_conclusao:.0f}%",
                                  periodo, texto_moeda(e.custo_planejado), real),
                           ("concluida",) if e.percentual_conclusao >= 100 else ()))
        preencher(self.tabela_etapas, linhas)
        if selecao and self.tabela_etapas.exists(selecao[0]):
            self.tabela_etapas.selection_set(selecao[0])
        self.carregar_recursos()

    def carregar_recursos(self) -> None:
        try:
            etapa = self.etapa_selecionada(self.obra_atual())
        except ErroPreCondicao:
            preencher(self.tabela_recursos, [])
            return
        linhas = []
        for i, r in enumerate(etapa.recursos):
            if isinstance(r, Material):
                quantidade, unitario = texto_numero(r.quantidade), r.preco_unitario
            else:
                quantidade, unitario = f"{texto_numero(r.horas_uso)} h", r.taxa_por_hora
            linhas.append((i, (type(r).__name__, r.nome, quantidade, texto_moeda(unitario),
                               texto_moeda(r.calcular_custo_total())), ()))
        preencher(self.tabela_recursos, linhas)

    def nova_etapa(self) -> None:
        def acao():
            DialogoEtapa(self.app, self.obra_atual(), self.app.atualizar_paginas)
        tentar(self, acao)

    def novo_recurso(self) -> None:
        def acao():
            obra = self.obra_atual()
            DialogoRecurso(self.app, obra, self.etapa_selecionada(obra),
                           self.app.atualizar_paginas)
        tentar(self, acao)

    def registrar_avanco(self) -> None:
        def acao():
            obra = self.obra_atual()
            DialogoAvanco(self.app, obra, self.etapa_selecionada(obra),
                          self.app.atualizar_paginas)
        tentar(self, acao)


class PaginaKPIs(Pagina):
    COLUNAS = [
        ("etapa", "Etapa", 160, "w"),
        ("prazo", "Desvio de prazo", 130, "center"),
        ("custo", "Desvio de custo", 140, "e"),
    ]

    def __init__(self, pai, app):
        super().__init__(pai, app, "Relatório de KPIs",
                         "Compara o planejado com o realizado, no prazo e no custo.")
        self.combo_obra = self.seletor_obra(self.gerar)
        ttk.Button(self.barra_seletor, text="Gerar relatório", style="Primario.TButton",
                   command=self.gerar).pack(side="left", padx=(12, 0))
        self.aviso = ttk.Label(self, text="", style="Vazio.TLabel")
        self.aviso.pack(anchor="w", pady=(10, 0))

        cartoes = ttk.Frame(self)
        cartoes.pack(fill="x", pady=(8, 0))
        self.cartoes = {nome: Cartao(cartoes, nome) for nome in (
            "Custo planejado", "Custo real", "Desvio financeiro",
            "Término planejado", "Término real", "Desvio físico")}
        for i, cartao in enumerate(self.cartoes.values()):
            cartao.grid(row=i // 3, column=i % 3, sticky="ew",
                        padx=(0 if i % 3 == 0 else 14, 0), pady=(0 if i < 3 else 12, 0))
        for coluna in range(3):
            cartoes.columnconfigure(coluna, weight=1, uniform="cartao")

        baixo = ttk.Frame(self)
        baixo.pack(fill="both", expand=True, pady=(16, 0))
        baixo.rowconfigure(0, weight=1)
        for coluna in (0, 1):
            baixo.columnconfigure(coluna, weight=1, uniform="metade")
        quadro, self.tabela = criar_tabela(baixo, self.COLUNAS, 5)
        quadro.grid(row=0, column=0, sticky="nsew")
        moldura = ttk.Frame(baixo, style="Card.TFrame", padding=8)
        moldura.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        self.grafico = tk.Canvas(moldura, bg=COR["card"], highlightthickness=0, height=180)
        self.grafico.pack(fill="both", expand=True)
        self.grafico.bind("<Configure>", lambda _e: self.desenhar_grafico())
        self.detalhes: tuple = ()

    def atualizar(self) -> None:
        self.recarregar_seletor(self.combo_obra)
        if self.combo_obra.get():
            self.gerar()
        else:
            self.limpar("Nenhuma obra cadastrada no sistema.")

    def limpar(self, mensagem: str) -> None:
        for cartao in self.cartoes.values():
            cartao.definir("-")
        preencher(self.tabela, [])
        self.detalhes = ()
        self.desenhar_grafico()
        self.aviso.configure(text=mensagem)

    def gerar(self) -> None:
        def acao():
            obra = self.obra_do_seletor(self.combo_obra)
            try:
                relatorio = self.app.relatorio.gerar(obra)
            except ErroDadosInsuficientes as e:
                self.limpar(str(e))
                return
            self.exibir(relatorio)
        tentar(self, acao)

    def exibir(self, r) -> None:
        self.aviso.configure(text="")
        c = self.cartoes
        c["Custo planejado"].definir(texto_moeda(r.custo_planejado_total))
        c["Custo real"].definir(texto_moeda(r.custo_real_total))
        c["Desvio financeiro"].definir(
            texto_moeda(r.desvio_financeiro, True),
            "perigo" if r.desvio_financeiro > 0 else "ok", Fmt.custo(r.desvio_financeiro))
        c["Término planejado"].definir(texto_data(r.data_termino_planejada))
        c["Término real"].definir(texto_data(r.data_termino_real))
        c["Desvio físico"].definir(
            f"{r.desvio_fisico_dias:+d} dia(s)",
            "perigo" if r.desvio_fisico_dias > 0 else "ok", nota_prazo(r.desvio_fisico_dias))
        preencher(self.tabela, [
            (i, (d.nome, f"{d.desvio_prazo_dias:+d} dia(s)", texto_moeda(d.desvio_custo, True)),
             ("atraso",) if d.desvio_prazo_dias > 0 else ())
            for i, d in enumerate(r.etapas)
        ])
        self.detalhes = r.etapas
        self.desenhar_grafico()

    @staticmethod
    def _abreviar(valor: float) -> str:
        return f"R$ {valor / 1000:.0f} mil" if valor >= 1000 else f"R$ {valor:.0f}"

    def desenhar_grafico(self) -> None:
        tela = self.grafico
        tela.delete("all")
        largura, altura = tela.winfo_width(), tela.winfo_height()
        if not self.detalhes or largura < 120 or altura < 80:
            return
        esquerda, direita, topo, base = 62, 14, 44, 34
        maximo = max(max(d.custo_planejado, d.custo_real) for d in self.detalhes) or 1
        area_h, area_l = altura - topo - base, largura - esquerda - direita
        tela.create_text(10, 10, text="Custo planejado x real por etapa", anchor="w",
                         font=fonte(9, "bold"), fill=COR["texto"])
        for fracao in (0, 0.5, 1):
            y = altura - base - area_h * fracao
            tela.create_line(esquerda, y, largura - direita, y, fill=COR["borda"])
            tela.create_text(esquerda - 6, y, text=self._abreviar(maximo * fracao),
                             anchor="e", font=fonte(8), fill=COR["suave"])
        grupo = area_l / len(self.detalhes)
        larg_barra = min(30, grupo / 3)
        for i, d in enumerate(self.detalhes):
            centro = esquerda + grupo * (i + 0.5)
            for deslocamento, valor, cor in (
                (-larg_barra / 2 - 1, d.custo_planejado, "#94a3b8"),
                (larg_barra / 2 + 1, d.custo_real,
                 COR["perigo"] if d.custo_real > d.custo_planejado else COR["destaque"]),
            ):
                x = centro + deslocamento
                tela.create_rectangle(x - larg_barra / 2, altura - base - area_h * valor / maximo,
                                      x + larg_barra / 2, altura - base, fill=cor, outline="")
            nome = d.nome if len(d.nome) <= 12 else d.nome[:11] + "…"
            tela.create_text(centro, altura - base + 12, text=nome, font=fonte(8),
                             fill=COR["texto"])
        for x, cor, texto in ((10, "#94a3b8", "Planejado"), (92, COR["destaque"], "Real"),
                              (140, COR["perigo"], "Real acima do planejado")):
            tela.create_rectangle(x, 25, x + 10, 35, fill=cor, outline="")
            tela.create_text(x + 14, 30, text=texto, anchor="w", font=fonte(8), fill=COR["suave"])


class PaginaMinhasObras(Pagina):
    def __init__(self, pai, app):
        super().__init__(pai, app, "Minhas obras", "Obras alocadas ao engenheiro logado.")
        quadro, self.tabela = criar_tabela(self, COLUNAS_OBRAS, 12)
        quadro.pack(fill="both", expand=True, pady=(18, 0))
        self.aviso = ttk.Label(self, text="", style="Vazio.TLabel")
        self.aviso.pack(anchor="w", pady=(10, 0))

    def atualizar(self) -> None:
        obras = self.app.engenheiros.minhas_obras(self.app.usuario) if self.app.usuario else []
        preencher(self.tabela, linhas_obras(obras))
        self.aviso.configure(text="" if obras else "Você ainda não está alocado(a) a nenhuma obra.")


class TelaLogin(ttk.Frame):
    def __init__(self, pai, app: "Aplicacao"):
        super().__init__(pai)
        self.app = app
        self.modo_cadastro = False
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        banner = ttk.Frame(self, style="Lateral.TFrame", padding=(40, 48), width=380)
        banner.grid(row=0, column=0, sticky="ns")
        banner.grid_propagate(False)
        Logo(banner, 56).pack(anchor="w")
        ttk.Label(banner, text="Gestão de Obras", style="LateralTitulo.TLabel").pack(
            anchor="w", pady=(20, 4))
        ttk.Label(banner, text="Planejado x realizado, etapa por etapa.",
                  style="LateralSuave.TLabel", wraplength=300).pack(anchor="w")
        for item in ("Cadastre obras, etapas e recursos", "Registre o avanço real da execução",
                     "Veja desvios de prazo e custo em segundos"):
            ttk.Label(banner, text=f"•  {item}", style="Lateral.TLabel", wraplength=300).pack(
                anchor="w", pady=(18, 0))

        lado = ttk.Frame(self, padding=(70, 0))
        lado.grid(row=0, column=1, sticky="nsew")
        lado.rowconfigure(0, weight=1)
        lado.rowconfigure(2, weight=1)
        lado.columnconfigure(0, weight=1)
        form = ttk.Frame(lado)
        form.grid(row=1, column=0, sticky="ew")
        self.titulo = ttk.Label(form, text="", style="Titulo.TLabel")
        self.titulo.pack(anchor="w")
        self.subtitulo = ttk.Label(form, text="", style="Subtitulo.TLabel")
        self.subtitulo.pack(anchor="w", pady=(2, 18))
        ttk.Label(form, text="Usuário").pack(anchor="w", pady=(0, 4))
        self.entrada_usuario = ttk.Entry(form, width=36)
        self.entrada_usuario.pack(fill="x")
        ttk.Label(form, text="Senha").pack(anchor="w", pady=(14, 4))
        self.entrada_senha = ttk.Entry(form, width=36, show="•")
        self.entrada_senha.pack(fill="x")
        self.mensagem = ttk.Label(form, text=" ", style="Erro.TLabel", wraplength=360)
        self.mensagem.pack(anchor="w", pady=(10, 6))
        self.botao_principal = ttk.Button(form, style="Primario.TButton", command=self.enviar)
        self.botao_principal.pack(fill="x", ipady=3)
        self.botao_alternar = ttk.Button(form, style="Link.TButton", command=self.alternar)
        self.botao_alternar.pack(anchor="w", pady=(14, 0))
        self.entrada_usuario.bind("<Return>", lambda _e: self.entrada_senha.focus_set())
        self.entrada_senha.bind("<Return>", lambda _e: self.enviar())
        self.aplicar_modo()
        self.entrada_usuario.focus_set()

    def aplicar_modo(self) -> None:
        if self.modo_cadastro:
            self.titulo.configure(text="Criar conta")
            self.subtitulo.configure(text="Cadastre-se como engenheiro(a). Senha com 4+ caracteres.")
            self.botao_principal.configure(text="Criar conta")
            self.botao_alternar.configure(text="Já tenho conta. Entrar")
        else:
            self.titulo.configure(text="Entrar")
            self.subtitulo.configure(text="Acesse com sua conta de engenheiro(a).")
            self.botao_principal.configure(text="Entrar")
            self.botao_alternar.configure(text="Não tem conta? Criar conta")

    def alternar(self) -> None:
        self.modo_cadastro = not self.modo_cadastro
        self.aplicar_modo()
        self.exibir_mensagem("")

    def exibir_mensagem(self, texto: str, ok: bool = False) -> None:
        self.mensagem.configure(text=texto or " ", style="Ok.TLabel" if ok else "Erro.TLabel")

    def enviar(self) -> None:
        usuario, senha = self.entrada_usuario.get(), self.entrada_senha.get()
        try:
            if self.modo_cadastro:
                self.app.engenheiros.cadastrar(usuario, senha)
                self.modo_cadastro = False
                self.aplicar_modo()
                self.entrada_senha.delete(0, tk.END)
                self.exibir_mensagem("Conta criada! Agora é só entrar.", ok=True)
                self.entrada_senha.focus_set()
                return
            engenheiro = self.app.engenheiros.entrar(usuario, senha)
        except ERROS_ESPERADOS as e:
            self.exibir_mensagem(str(e))
            return
        self.app.iniciar_sessao(engenheiro)


class TelaPrincipal(ttk.Frame):
    PAGINAS = (
        ("painel", "Painel de obras", PaginaPainel),
        ("etapas", "Etapas e recursos", PaginaEtapas),
        ("kpis", "Relatório de KPIs", PaginaKPIs),
        ("minhas", "Minhas obras", PaginaMinhasObras),
    )

    def __init__(self, pai, app: "Aplicacao"):
        super().__init__(pai)
        self.app = app
        self._aviso_pendente = None

        lateral = ttk.Frame(self, style="Lateral.TFrame", width=250)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        topo = ttk.Frame(lateral, style="Lateral.TFrame", padding=(22, 26, 22, 8))
        topo.pack(fill="x")
        Logo(topo, 40).pack(side="left")
        textos = ttk.Frame(topo, style="Lateral.TFrame")
        textos.pack(side="left", padx=(12, 0))
        ttk.Label(textos, text="Gestão de Obras", style="Lateral.TLabel",
                  font=fonte(12, "bold")).pack(anchor="w")
        ttk.Label(textos, text=f"Eng. {app.usuario.nome}", style="LateralSuave.TLabel").pack(
            anchor="w")
        ttk.Frame(lateral, style="Lateral.TFrame", height=24).pack()

        self.botoes: dict[str, ttk.Button] = {}
        for chave, texto, _classe in self.PAGINAS:
            botao = ttk.Button(lateral, text=texto, style="Menu.TButton",
                               command=lambda c=chave: self.ir(c))
            botao.pack(fill="x")
            self.botoes[chave] = botao
        ttk.Button(lateral, text="Sair da conta", style="Menu.TButton",
                   command=app.sair).pack(side="bottom", fill="x", pady=(0, 18))

        direita = ttk.Frame(self)
        direita.pack(side="left", fill="both", expand=True)
        self.faixa = ttk.Frame(direita, style="Notificacao.TFrame")
        self.texto_faixa = ttk.Label(self.faixa, text="", style="Notificacao.TLabel")
        self.texto_faixa.pack(anchor="w")
        container = ttk.Frame(direita)
        container.pack(fill="both", expand=True)
        self.container = container
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        self.paginas: dict[str, Pagina] = {}
        for chave, _texto, classe in self.PAGINAS:
            pagina = classe(container, app)
            pagina.grid(row=0, column=0, sticky="nsew")
            self.paginas[chave] = pagina
        self.atual = "painel"
        self.ir("painel")

    def ir(self, chave: str) -> None:
        self.atual = chave
        for k, botao in self.botoes.items():
            botao.configure(style="MenuAtivo.TButton" if k == chave else "Menu.TButton")
        self.paginas[chave].tkraise()
        self.paginas[chave].atualizar()

    def atualizar(self) -> None:
        self.paginas[self.atual].atualizar()

    def notificar(self, mensagem: str) -> None:
        if self._aviso_pendente is not None:
            self.after_cancel(self._aviso_pendente)
        self.texto_faixa.configure(text=mensagem)
        self.faixa.pack(fill="x", before=self.container)
        self._aviso_pendente = self.after(4500, self.ocultar_aviso)

    def ocultar_aviso(self) -> None:
        self._aviso_pendente = None
        self.faixa.pack_forget()


class Aplicacao(tk.Tk):
    def __init__(self, repositorio: RepositorioSQLite):
        super().__init__()
        self.repo = repositorio
        self.engenheiros = GerenciarEngenheiros(repositorio)
        self.cadastrar_obra = CadastrarObra(repositorio)
        self.adicionar_etapa = AdicionarEtapa(repositorio)
        self.adicionar_recurso = AdicionarRecurso(repositorio)
        self.avanco = RegistrarAvancoRealCDU02(repositorio)
        self.concluir_obra = ConcluirObra(repositorio)
        self.relatorio = GerarRelatorioKPIs(repositorio)
        self.usuario: Optional[Engenheiro] = None
        self.tela: Optional[ttk.Frame] = None
        self.title("Sistema de Gestão de Obras")
        tema.aplicar_tema(self)
        self.mostrar_login()

    def _trocar(self, tela: ttk.Frame, largura: int, altura: int, minimo: tuple[int, int]) -> None:
        if self.tela is not None:
            self.tela.destroy()
        self.tela = tela
        tela.pack(fill="both", expand=True)
        self.minsize(*minimo)
        centralizar(self, largura, altura)

    def mostrar_login(self) -> None:
        self._trocar(TelaLogin(self, self), 920, 560, (820, 520))

    def iniciar_sessao(self, engenheiro: Engenheiro) -> None:
        self.usuario = engenheiro
        self._trocar(TelaPrincipal(self, self), 1200, 720, (1040, 640))

    def sair(self) -> None:
        if self.usuario is not None:
            self.usuario.sair()
        self.usuario = None
        self.mostrar_login()

    def atualizar_paginas(self) -> None:
        if isinstance(self.tela, TelaPrincipal):
            self.tela.atualizar()

    def notificar(self, mensagem: str) -> None:
        if isinstance(self.tela, TelaPrincipal):
            self.tela.notificar(mensagem)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sistema de Gestão de Obras (interface gráfica)")
    parser.add_argument("--db", default="gestao_obras.db", help="arquivo SQLite (padrão: gestao_obras.db)")
    args = parser.parse_args()
    repo = RepositorioSQLite(args.db)
    try:
        Aplicacao(repo).mainloop()
    finally:
        repo.fechar()


if __name__ == "__main__":
    main()
