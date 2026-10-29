from __future__ import annotations

import tkinter as tk
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from tkinter import messagebox, ttk
from typing import Optional


# 1. EXCEÇÕES E VALIDADORES

class ErroValidacao(Exception):
    """Dado informado pelo usuário é inválido."""


class ErroPreCondicao(Exception):
    """Uma pré-condição do caso de uso não foi atendida."""


class ErroDadosInsuficientes(Exception):
    """Não há dados suficientes para gerar o resultado."""


class Validador:
    """Funções de conversão/validação reutilizadas pelo domínio."""

    FORMATO_DATA = "%d/%m/%Y"

    @staticmethod
    def data(valor, rotulo: str) -> date:
        if isinstance(valor, datetime):
            return valor.date()
        if isinstance(valor, date):
            return valor
        if isinstance(valor, str):
            try:
                return datetime.strptime(valor.strip(), Validador.FORMATO_DATA).date()
            except ValueError:
                pass
        raise ErroValidacao(f"A {rotulo} possui formato inválido (use dd/mm/aaaa)")

    @staticmethod
    def numero(valor, mensagem: str) -> float:
        if isinstance(valor, bool):
            raise ErroValidacao(mensagem)
        if isinstance(valor, (int, float)):
            return float(valor)
        if isinstance(valor, str):
            try:
                return float(valor.strip().replace(",", "."))
            except ValueError:
                pass
        raise ErroValidacao(mensagem)

    @staticmethod
    def nao_negativo(valor: float, mensagem: str) -> float:
        if valor < 0:
            raise ErroValidacao(mensagem)
        return valor

    @staticmethod
    def texto_obrigatorio(valor, mensagem: str) -> str:
        texto = (valor or "").strip() if isinstance(valor, str) else ""
        if not texto:
            raise ErroValidacao(mensagem)
        return texto

    @staticmethod
    def periodo(inicio: date, fim: date) -> None:
        if fim < inicio:
            raise ErroValidacao("Término não pode ser antes do início")


# 2. DOMÍNIO

class StatusObra(str, Enum):
    EM_ANDAMENTO = "Em Andamento"
    CONCLUIDA = "Concluída"


class StatusEtapa(str, Enum):
    PENDENTE = "Pendente"
    EM_ANDAMENTO = "Em Andamento"
    CONCLUIDA = "Concluída"


# ---------- Recursos (polimorfismo) ----------

class Recurso(ABC):
    def __init__(self, nome: str):
        self.nome = Validador.texto_obrigatorio(nome, "Nome do recurso é obrigatório")

    @abstractmethod
    def calcular_custo_total(self) -> float: ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.nome!r}, R$ {self.calcular_custo_total():.2f})"


class Material(Recurso):
    def __init__(self, nome: str, quantidade: float, preco_unitario: float):
        super().__init__(nome)
        self.quantidade = Validador.nao_negativo(quantidade, "Quantidade inválida")
        self.preco_unitario = Validador.nao_negativo(preco_unitario, "Preço inválido")

    def calcular_custo_total(self) -> float:
        return self.quantidade * self.preco_unitario


class Equipamento(Recurso):
    def __init__(self, nome: str, horas_uso: float, taxa_por_hora: float):
        super().__init__(nome)
        self.horas_uso = Validador.nao_negativo(horas_uso, "Horas inválidas")
        self.taxa_por_hora = Validador.nao_negativo(taxa_por_hora, "Taxa inválida")

    def calcular_custo_total(self) -> float:
        return self.horas_uso * self.taxa_por_hora


# ---------- Etapa ----------

class Etapa:
    def __init__(self, id_etapa: int, nome: str):
        self.id = id_etapa
        self.nome = Validador.texto_obrigatorio(nome, "Nome da etapa é obrigatório")
        self.status = StatusEtapa.PENDENTE
        self.percentual_conclusao = 0.0
        self._recursos: list[Recurso] = []

        # Planejado
        self.data_inicio_planejada: Optional[date] = None
        self.data_fim_planejada: Optional[date] = None
        self.custo_planejado: Optional[float] = None

        # Real
        self.data_inicio_real: Optional[date] = None
        self.data_fim_real: Optional[date] = None
        self.custo_real = 0.0

    # --- consultas ---
    @property
    def recursos(self) -> tuple[Recurso, ...]:
        return tuple(self._recursos)

    def tem_planejamento(self) -> bool:
        return self.data_fim_planejada is not None and self.custo_planejado is not None

    def tem_avanco_real(self) -> bool:
        return self.data_fim_real is not None

    def custo_recursos(self) -> float:
        return sum(r.calcular_custo_total() for r in self._recursos)

    # --- comandos ---
    def adicionar_recurso(self, recurso: Recurso) -> None:
        self._recursos.append(recurso)

    def planejar(self, data_inicio, data_fim, custo) -> None:
        inicio = Validador.data(data_inicio, "data início planejada")
        fim = Validador.data(data_fim, "data término planejada")
        valor = Validador.numero(custo, "Custo deve ser número")
        Validador.nao_negativo(valor, "Custo não pode ser negativo")
        Validador.periodo(inicio, fim)
        self.data_inicio_planejada, self.data_fim_planejada, self.custo_planejado = inicio, fim, valor

    def registrar_avanco(self, data_inicio, data_fim, custo_real=None, percentual=None) -> None:
        """Registra o avanço real. Se `custo_real` for vazio, usa o custo dos recursos."""
        inicio = Validador.data(data_inicio, "data início real")
        fim = Validador.data(data_fim, "data término real")
        Validador.periodo(inicio, fim)

        if custo_real in (None, ""):
            custo = self.custo_recursos()
        else:
            custo = Validador.numero(custo_real, "Custo deve ser número")
        Validador.nao_negativo(custo, "Custo não pode ser negativo")

        pct = self.percentual_conclusao
        if percentual not in (None, ""):
            pct = Validador.numero(percentual, "Porcentagem deve ser número")
            if not 0 <= pct <= 100:
                raise ErroValidacao("Porcentagem entre 0 e 100")

        self.data_inicio_real, self.data_fim_real = inicio, fim
        self.custo_real, self.percentual_conclusao = custo, pct
        self.status = StatusEtapa.CONCLUIDA if pct >= 100 else StatusEtapa.EM_ANDAMENTO

    def __repr__(self) -> str:
        return f"Etapa({self.id}, {self.nome!r}, {self.status.value})"


# ---------- Obra ----------

class Obra:
    def __init__(self, id_obra: int, nome_obra: str):
        self.id = id_obra
        self.nome = Validador.texto_obrigatorio(nome_obra, "Nome da obra é obrigatório")
        self.status = StatusObra.EM_ANDAMENTO
        self._etapas: list[Etapa] = []

    @property
    def etapas(self) -> tuple[Etapa, ...]:
        return tuple(self._etapas)

    def adicionar_etapa(self, nome_etapa: str, inicio_plan=None, fim_plan=None, custo_plan=None) -> Etapa:
        etapa = Etapa(len(self._etapas) + 1, nome_etapa)
        if any(v not in (None, "") for v in (inicio_plan, fim_plan, custo_plan)):
            etapa.planejar(inicio_plan, fim_plan, custo_plan)
        self._etapas.append(etapa)
        return etapa

    def buscar_etapa(self, id_etapa: int) -> Optional[Etapa]:
        return next((e for e in self._etapas if e.id == id_etapa), None)

    def esta_em_andamento(self) -> bool:
        return self.status == StatusObra.EM_ANDAMENTO

    def concluir(self) -> None:
        if any(e.status != StatusEtapa.CONCLUIDA for e in self._etapas) or not self._etapas:
            raise ErroPreCondicao("Todas as etapas precisam estar concluídas")
        self.status = StatusObra.CONCLUIDA

    def __repr__(self) -> str:
        return f"Obra({self.id}, {self.nome!r}, {self.status.value})"


# ---------- Usuários ----------

class Usuario:
    def __init__(self, nome: str, senha: str):
        self.nome = nome
        self._senha = senha
        self.autenticado = False

    def autenticar(self, senha: str) -> bool:
        self.autenticado = senha == self._senha
        return self.autenticado

    def sair(self) -> None:
        self.autenticado = False


class Engenheiro(Usuario):
    def __init__(self, nome: str, senha: str):
        super().__init__(nome, senha)
        self._obras_alocadas: list[Obra] = []

    @property
    def obras_alocadas(self) -> tuple[Obra, ...]:
        return tuple(self._obras_alocadas)

    def alocar_obra(self, obra: Obra) -> None:
        if obra not in self._obras_alocadas:
            self._obras_alocadas.append(obra)

    def obras_ativas(self) -> list[Obra]:
        return [o for o in self._obras_alocadas if o.esta_em_andamento()]


# 3. REPOSITÓRIO

class RepositorioObras:
    def __init__(self):
        self._obras: dict[int, Obra] = {}

    def cadastrar(self, obra: Obra) -> Obra:
        if obra.id in self._obras:
            raise ErroValidacao("Já existe uma obra com este Código (ID).")
        self._obras[obra.id] = obra
        return obra

    def buscar_por_id(self, id_obra: int) -> Optional[Obra]:
        return self._obras.get(id_obra)

    def listar_todas(self) -> list[Obra]:
        return list(self._obras.values())

    def listar_ativas(self) -> list[Obra]:
        return [o for o in self._obras.values() if o.esta_em_andamento()]

    def contem(self, obra: Obra) -> bool:
        return self._obras.get(obra.id) is obra

# 4. CASOS DE USO

class RegistrarAvancoRealBase(ABC):
    """Template Method: o fluxo é fixo, a validação da obra varia por subclasse."""

    MSG_SUCESSO = "Avanço registrado com sucesso"

    @abstractmethod
    def listar_obras(self) -> list[Obra]: ...

    @abstractmethod
    def _exigir_obra_valida(self, obra: Obra) -> None: ...

    def listar_etapas(self, obra: Obra) -> list[Etapa]:
        self._exigir_obra_valida(obra)
        return list(obra.etapas)

    def salvar(self, obra: Obra, id_etapa: int, data_inicio, data_fim,
               custo_real=None, percentual=None) -> str:
        self._exigir_obra_valida(obra)
        etapa = obra.buscar_etapa(id_etapa)
        if etapa is None:
            raise ErroPreCondicao("Etapa não encontrada nesta obra")
        etapa.registrar_avanco(data_inicio, data_fim, custo_real, percentual)
        return self.MSG_SUCESSO

    @staticmethod
    def _exigir_em_andamento(obra: Obra) -> None:
        if not obra.esta_em_andamento():
            raise ErroPreCondicao('A obra precisa estar com o status "Em Andamento"')


class RegistrarAvancoRealCDU02(RegistrarAvancoRealBase):
    def __init__(self, repositorio: RepositorioObras):
        self.repositorio = repositorio

    def listar_obras(self) -> list[Obra]:
        return self.repositorio.listar_ativas()

    def _exigir_obra_valida(self, obra: Obra) -> None:
        if not self.repositorio.contem(obra):
            raise ErroPreCondicao("A obra não está cadastrada no sistema")
        self._exigir_em_andamento(obra)


@dataclass(frozen=True)
class DesvioEtapa:
    nome: str
    data_fim_planejada: date
    data_fim_real: date
    desvio_prazo_dias: int
    custo_planejado: float
    custo_real: float
    desvio_custo: float


@dataclass(frozen=True)
class RelatorioKPIs:
    nome_obra: str
    status_obra: str
    custo_planejado_total: float
    custo_real_total: float
    desvio_financeiro: float
    data_termino_planejada: date
    data_termino_real: date
    desvio_fisico_dias: int
    etapas: tuple[DesvioEtapa, ...]
    etapas_com_avanco: int
    etapas_totais: int


class GerarRelatorioKPIs:
    MSG_DADOS_INSUFICIENTES = "Dados insuficientes: Nenhuma etapa possui avanço real registrado"

    def __init__(self, repositorio: RepositorioObras):
        self.repositorio = repositorio

    def listar_obras(self) -> list[Obra]:
        obras = self.repositorio.listar_todas()
        if not obras:
            raise ErroPreCondicao("Nenhuma obra cadastrada no sistema")
        return obras

    def gerar(self, obra: Obra) -> RelatorioKPIs:
        if not self.repositorio.contem(obra):
            raise ErroPreCondicao("A obra não está cadastrada no sistema")

        executadas = [e for e in obra.etapas if e.tem_avanco_real()]
        if not executadas:
            raise ErroDadosInsuficientes(self.MSG_DADOS_INSUFICIENTES)

        detalhes = tuple(self._desvio_da_etapa(e) for e in executadas)
        planejado = sum(d.custo_planejado for d in detalhes)
        real = sum(d.custo_real for d in detalhes)
        termino_plan = max(d.data_fim_planejada for d in detalhes)
        termino_real = max(d.data_fim_real for d in detalhes)

        return RelatorioKPIs(
            nome_obra=obra.nome,
            status_obra=obra.status.value,
            custo_planejado_total=round(planejado, 2),
            custo_real_total=round(real, 2),
            desvio_financeiro=round(real - planejado, 2),
            data_termino_planejada=termino_plan,
            data_termino_real=termino_real,
            desvio_fisico_dias=(termino_real - termino_plan).days,
            etapas=detalhes,
            etapas_com_avanco=len(executadas),
            etapas_totais=len(obra.etapas),
        )

    @staticmethod
    def _desvio_da_etapa(etapa: Etapa) -> DesvioEtapa:
        if not etapa.tem_planejamento():
            raise ErroPreCondicao(f'A etapa "{etapa.nome}" não possui planejamento')
        return DesvioEtapa(
            nome=etapa.nome,
            data_fim_planejada=etapa.data_fim_planejada,
            data_fim_real=etapa.data_fim_real,
            desvio_prazo_dias=(etapa.data_fim_real - etapa.data_fim_planejada).days,
            custo_planejado=etapa.custo_planejado,
            custo_real=etapa.custo_real,
            desvio_custo=round(etapa.custo_real - etapa.custo_planejado, 2),
        )


class ExibidorRelatorioKPIs:
    """Formata o relatório em texto (a tela só exibe o resultado)."""

    @staticmethod
    def data(d: date) -> str:
        return d.strftime("%d/%m/%Y")

    @staticmethod
    def moeda(valor: float, sinal: bool = False) -> str:
        prefixo = ("+" if valor > 0 else "-" if valor < 0 else "") if sinal else ""
        texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{prefixo}R$ {texto}"

    @staticmethod
    def prazo(dias: int) -> str:
        if dias > 0:
            return f"+{dias} dia(s) - atraso"
        if dias < 0:
            return f"{dias} dia(s) - adiantamento"
        return "0 dia(s) - no prazo"

    @staticmethod
    def custo(valor: float) -> str:
        if valor > 0:
            return "estouro de orçamento"
        if valor < 0:
            return "economia"
        return "dentro do orçamento"

    @classmethod
    def formatar(cls, r: RelatorioKPIs) -> str:
        linha = "-" * 40
        partes = [
            f"Obra: {r.nome_obra} | Status: {r.status_obra}",
            f"Etapas com avanço: {r.etapas_com_avanco}/{r.etapas_totais}",
            linha,
            f"Custo Planejado: {cls.moeda(r.custo_planejado_total)}",
            f"Custo Real: {cls.moeda(r.custo_real_total)}",
            f"Desvio Financeiro: {cls.moeda(r.desvio_financeiro, True)} ({cls.custo(r.desvio_financeiro)})",
            linha,
            f"Término Planejado: {cls.data(r.data_termino_planejada)}",
            f"Término Real: {cls.data(r.data_termino_real)}",
            f"Desvio Físico: {cls.prazo(r.desvio_fisico_dias)}",
            linha,
            "Por etapa:",
        ]
        for e in r.etapas:
            partes.append(
                f"  • {e.nome}: prazo {cls.prazo(e.desvio_prazo_dias)}; "
                f"custo {cls.moeda(e.desvio_custo, True)} ({cls.custo(e.desvio_custo)})"
            )
        return "\n".join(partes) + "\n"


# 5. APRESENTAÇÃO (TKINTER)

def _rotulo(item) -> str:
    return f"{item.id} - {item.nome}"


def _id_do_rotulo(texto: str) -> Optional[int]:
    try:
        return int(texto.split(" - ")[0])
    except (ValueError, IndexError):
        return None


class TelaBase(tk.Toplevel):
    """Utilitários comuns às telas."""

    def __init__(self, parent, titulo: str, geometria: str):
        super().__init__(parent)
        self.title(titulo)
        self.geometry(geometria)
        self.configure(padx=20, pady=20)
        self.grab_set()

    def campo(self, container, texto: str, pady_final=10) -> ttk.Entry:
        ttk.Label(container, text=texto).pack(anchor="w")
        entry = ttk.Entry(container, width=40)
        entry.pack(pady=(0, pady_final))
        return entry

    def combo(self, container, texto: str, pady_final=10) -> ttk.Combobox:
        ttk.Label(container, text=texto).pack(anchor="w")
        combo = ttk.Combobox(container, state="readonly", width=38)
        combo.pack(pady=(0, pady_final))
        return combo

    def erro(self, titulo: str, mensagem: str) -> None:
        messagebox.showerror(titulo, mensagem, parent=self)


class TelaCadastroObra(TelaBase):
    def __init__(self, parent, repositorio: RepositorioObras):
        super().__init__(parent, "Gestão de Obras - Nova Obra/Etapa", "500x650")
        self.repositorio = repositorio
        self.etapas_visivel = False

        # Seção 1: nova obra
        frame_obra = ttk.Frame(self)
        frame_obra.pack(fill="x")
        ttk.Label(frame_obra, text="Nova Obra", font=("Arial", 14, "bold")).pack(pady=(0, 15))
        self.entry_id = self.campo(frame_obra, "Código (ID) da Obra:")
        self.entry_nome = self.campo(frame_obra, "Nome da Obra:", 20)

        botoes = ttk.Frame(frame_obra)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Cadastrar Obra", command=self.salvar_obra).pack(
            side="left", expand=True, fill="x", padx=(0, 5))
        self.btn_etapas = ttk.Button(botoes, text="⬇ Adicionar Etapas", command=self.alternar_menu_etapas)
        self.btn_etapas.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Seção 2: nova etapa
        self.frame_etapas = ttk.LabelFrame(self, text=" Cadastrar Nova Etapa ", padding=15)
        self.combo_obras = self.combo(self.frame_etapas, "Selecione a Obra:")
        self.entry_nome_etapa = self.campo(self.frame_etapas, "Nome da Etapa:")
        self.entry_inicio = self.campo(self.frame_etapas, "Data Início Planejada (dd/mm/aaaa):")
        self.entry_fim = self.campo(self.frame_etapas, "Data Término Planejada (dd/mm/aaaa):")
        self.entry_custo = self.campo(self.frame_etapas, "Custo Planejado (R$):", 15)
        ttk.Button(self.frame_etapas, text="Salvar Etapa", command=self.salvar_etapa).pack(fill="x")

    def alternar_menu_etapas(self):
        if self.etapas_visivel:
            self.frame_etapas.pack_forget()
            self.btn_etapas.config(text="⬇ Adicionar Etapas")
        else:
            self.atualizar_lista_obras()
            self.frame_etapas.pack(fill="both", expand=True, pady=(20, 0))
            self.btn_etapas.config(text="⬆ Ocultar Etapas")
        self.etapas_visivel = not self.etapas_visivel

    def atualizar_lista_obras(self):
        obras = self.repositorio.listar_ativas()
        self.combo_obras["values"] = [_rotulo(o) for o in obras]
        if obras:
            self.combo_obras.current(len(obras) - 1)
        else:
            self.combo_obras.set("")

    def salvar_obra(self):
        try:
            id_obra = int(self.entry_id.get().strip())
        except ValueError:
            return self.erro("Erro de Validação", "O Código deve ser numérico.")
        try:
            obra = self.repositorio.cadastrar(Obra(id_obra, self.entry_nome.get()))
        except ErroValidacao as e:
            return self.erro("Erro de Validação", str(e))

        messagebox.showinfo("Sucesso", f"Obra '{obra.nome}' cadastrada!", parent=self)
        self.entry_id.delete(0, tk.END)
        self.entry_nome.delete(0, tk.END)
        if self.etapas_visivel:
            self.atualizar_lista_obras()

    def salvar_etapa(self):
        id_obra = _id_do_rotulo(self.combo_obras.get())
        obra = self.repositorio.buscar_por_id(id_obra) if id_obra is not None else None
        if obra is None:
            return messagebox.showwarning("Atenção", "Cadastre/selecione uma obra primeiro!", parent=self)
        try:
            obra.adicionar_etapa(
                self.entry_nome_etapa.get(), self.entry_inicio.get(),
                self.entry_fim.get(), self.entry_custo.get(),
            )
        except ErroValidacao as e:
            return self.erro("Erro de Validação", str(e))

        messagebox.showinfo("Sucesso", f"Etapa adicionada à obra '{obra.nome}'!", parent=self)
        for campo in (self.entry_nome_etapa, self.entry_inicio, self.entry_fim, self.entry_custo):
            campo.delete(0, tk.END)


class TelaRegistrarAvanco(TelaBase):
    def __init__(self, parent, repositorio: RepositorioObras):
        super().__init__(parent, "Registrar Avanço Real", "400x520")
        self.caso_uso = RegistrarAvancoRealCDU02(repositorio)
        self.repositorio = repositorio

        ttk.Label(self, text="Registrar Avanço", font=("Arial", 14, "bold")).pack(pady=(0, 15))
        self.combo_obras = self.combo(self, "Selecione a Obra:")
        self.combo_obras.bind("<<ComboboxSelected>>", self.carregar_etapas)
        self.combo_etapas = self.combo(self, "Selecione a Etapa:", 15)
        self.entry_inicio = self.campo(self, "Data Início Real (dd/mm/aaaa):")
        self.entry_fim = self.campo(self, "Data Fim Real (dd/mm/aaaa):")
        self.entry_custo = self.campo(self, "Custo Real (R$) (vazio = custo dos recursos):")
        self.entry_pct = self.campo(self, "% Conclusão (Opcional):", 20)
        ttk.Button(self, text="Salvar Avanço", command=self.salvar_avanco).pack(fill="x")

        self.combo_obras["values"] = [_rotulo(o) for o in self.caso_uso.listar_obras()]

    def _obra_selecionada(self) -> Optional[Obra]:
        id_obra = _id_do_rotulo(self.combo_obras.get())
        return self.repositorio.buscar_por_id(id_obra) if id_obra is not None else None

    def carregar_etapas(self, _evento=None):
        obra = self._obra_selecionada()
        if obra is None:
            return
        try:
            etapas = self.caso_uso.listar_etapas(obra)
        except ErroPreCondicao as e:
            return self.erro("Pré-condição", str(e))
        self.combo_etapas["values"] = [_rotulo(e) for e in etapas]
        if etapas:
            self.combo_etapas.current(0)

    def salvar_avanco(self):
        obra = self._obra_selecionada()
        id_etapa = _id_do_rotulo(self.combo_etapas.get())
        if obra is None or id_etapa is None:
            return messagebox.showwarning("Atenção", "Selecione obra e etapa.", parent=self)
        try:
            msg = self.caso_uso.salvar(
                obra, id_etapa, self.entry_inicio.get(), self.entry_fim.get(),
                self.entry_custo.get(), self.entry_pct.get(),
            )
        except ErroValidacao as e:
            return self.erro("Erro de Validação", str(e))
        except ErroPreCondicao as e:
            return self.erro("Pré-condição", str(e))
        messagebox.showinfo("Sucesso", msg, parent=self)
        self.destroy()


class TelaKPIs(TelaBase):
    SEM_OBRAS = "Nenhuma obra cadastrada"

    def __init__(self, parent, repositorio: RepositorioObras):
        super().__init__(parent, "Relatório de KPIs", "620x420")
        self.caso_uso = GerarRelatorioKPIs(repositorio)
        self.repositorio = repositorio

        ttk.Label(self, text="Gerar Relatório de KPIs", font=("Arial", 14, "bold")).pack(pady=(0, 15))
        topo = ttk.Frame(self)
        topo.pack(fill="x", pady=(0, 20))
        ttk.Label(topo, text="Selecione a Obra:").pack(side="left")
        self.combo_obras = ttk.Combobox(topo, state="readonly", width=35)
        self.combo_obras.pack(side="left", padx=10)
        ttk.Button(topo, text="Gerar Relatório", command=self.gerar).pack(side="left")

        self.text_area = tk.Text(self, wrap="word", state="disabled")
        self.text_area.pack(fill="both", expand=True)
        self.carregar_obras()

    def carregar_obras(self):
        try:
            obras = self.caso_uso.listar_obras()
        except ErroPreCondicao:
            self.combo_obras.set(self.SEM_OBRAS)
            return
        self.combo_obras["values"] = [_rotulo(o) for o in obras]
        self.combo_obras.current(0)

    def _exibir(self, texto: str):
        self.text_area.config(state="normal")
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, texto)
        self.text_area.config(state="disabled")

    def gerar(self):
        id_obra = _id_do_rotulo(self.combo_obras.get())
        obra = self.repositorio.buscar_por_id(id_obra) if id_obra is not None else None
        if obra is None:
            return
        try:
            relatorio = self.caso_uso.gerar(obra)
            self._exibir(ExibidorRelatorioKPIs.formatar(relatorio))
        except (ErroDadosInsuficientes, ErroPreCondicao) as e:
            self._exibir(f"Não foi possível gerar o relatório:\n{e}")


class MenuPrincipal(tk.Tk):
    def __init__(self, repositorio: RepositorioObras):
        super().__init__()
        self.repositorio = repositorio
        self.title("Sistema de Gestão de Obras")
        self.geometry("350x400")
        self.configure(padx=30, pady=30)
        self.eval("tk::PlaceWindow . center")

        ttk.Label(self, text="Menu Principal", font=("Arial", 16, "bold")).pack(pady=(0, 30))
        opcoes = (
            ("1. Cadastrar Obras e Etapas", TelaCadastroObra),
            ("2. Registrar Avanço Real", TelaRegistrarAvanco),
            ("3. Gerar Relatório de KPIs", TelaKPIs),
        )
        for texto, tela in opcoes:
            ttk.Button(self, text=texto, command=lambda t=tela: t(self, self.repositorio)).pack(
                pady=10, ipadx=10, ipady=5)
        ttk.Button(self, text="Sair do Sistema", command=self.destroy).pack(side="bottom", pady=20)

# INICIALIZAÇÃO

def criar_dados_exemplo(repo: RepositorioObras) -> None:
    obra = repo.cadastrar(Obra(1, "Residencial Alphaville"))
    obra.adicionar_etapa("Fundação", "01/10/2026", "15/10/2026", 15000)


if __name__ == "__main__":
    repo = RepositorioObras()
    criar_dados_exemplo(repo)
    MenuPrincipal(repositorio=repo).mainloop()