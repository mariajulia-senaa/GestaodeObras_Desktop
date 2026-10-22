import sys
import tkinter as tk
from tkinter import ttk, messagebox
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

# CAMADA DE DOMÍNIO E APLICAÇÃO (BACKEND)

class ErroValidacao(Exception): pass
class ErroPreCondicao(Exception): pass
class ErroDadosInsuficientes(Exception): pass

def converter_data(valor, rotulo):
    if isinstance(valor, datetime): return valor.date()
    if isinstance(valor, date): return valor
    if isinstance(valor, str):
        try: return datetime.strptime(valor.strip(), "%d/%m/%Y").date()
        except ValueError: pass
    raise ErroValidacao(f"A {rotulo} possui formato inválido (use dd/mm/aaaa)")

def converter_numero(valor, mensagem_invalido):
    if isinstance(valor, bool): raise ErroValidacao(mensagem_invalido)
    if isinstance(valor, (int, float)): return float(valor)
    if isinstance(valor, str):
        try: return float(valor.strip().replace(",", "."))
        except ValueError: pass
    raise ErroValidacao(mensagem_invalido)

def exigir_nao_negativo(valor, mensagem):
    if valor < 0: raise ErroValidacao(mensagem)
    return valor

class Recurso(ABC):
    def __init__(self, nome): self.nome = nome
    @abstractmethod
    def calcular_custo_total(self): pass

class Material(Recurso):
    def __init__(self, nome, quantidade, preco_unitario):
        super().__init__(nome)
        self.quantidade = exigir_nao_negativo(quantidade, "Quantidade inválida")
        self.preco_unitario = exigir_nao_negativo(preco_unitario, "Preço inválido")
    def calcular_custo_total(self): return self.quantidade * self.preco_unitario

class Equipamento(Recurso):
    def __init__(self, nome, horas_uso, taxa_por_hora):
        super().__init__(nome)
        self.horas_uso = exigir_nao_negativo(horas_uso, "Horas inválidas")
        self.taxa_por_hora = exigir_nao_negativo(taxa_por_hora, "Taxa inválida")
    def calcular_custo_total(self): return self.horas_uso * self.taxa_por_hora

class Etapa:
    def __init__(self, id_etapa, nome):
        self.id = id_etapa
        self.nome = nome
        self.status = "Pendente"
        self.data_inicio_real = None
        self.data_fim_real = None
        self.custo_real = 0.0
        self.percentual_conclusao = 0.0
        self.recursos = []
        self.data_inicio_planejada = None
        self.data_fim_planejada = None
        self.custo_planejado = None

    def planejar(self, data_inicio, data_fim, custo):
        inicio = converter_data(data_inicio, "data início planejada")
        fim = converter_data(data_fim, "data término planejada")
        valor = converter_numero(custo, "Custo deve ser número")
        exigir_nao_negativo(valor, "Custo não pode ser negativo")
        if fim < inicio: raise ErroValidacao("Término não pode ser antes do início")
        self.data_inicio_planejada, self.data_fim_planejada, self.custo_planejado = inicio, fim, valor

    def tem_avanco_real(self): return self.data_fim_real is not None
    def adicionar_recurso(self, recurso: Recurso): self.recursos.append(recurso)
    def custo_recursos(self): return sum(r.calcular_custo_total() for r in self.recursos)

    def registrar_avanco(self, data_inicio, data_fim, custo_real, percentual=None):
        inicio = converter_data(data_inicio, "data início real")
        fim = converter_data(data_fim, "data término real")
        custo = converter_numero(custo_real, "Custo deve ser número")
        exigir_nao_negativo(custo, "Custo não pode ser negativo")
        pct = self.percentual_conclusao
        if percentual not in (None, ""):
            pct = converter_numero(percentual, "Porcentagem deve ser número")
            if not 0 <= pct <= 100: raise ErroValidacao("Porcentagem entre 0 e 100")
        if fim < inicio: raise ErroValidacao("Término não pode ser antes do início")
        self.data_inicio_real, self.data_fim_real, self.custo_real, self.percentual_conclusao = inicio, fim, custo, pct
        self.status = "Concluída" if pct >= 100 else "Em Andamento"

class Obra:
    STATUS_EM_ANDAMENTO = "Em Andamento"
    def __init__(self, id_obra, nome_obra):
        self.id = id_obra
        self.nome = nome_obra
        self.status = Obra.STATUS_EM_ANDAMENTO
        self._etapas = []
    @property
    def etapas(self): return tuple(self._etapas)
    def adicionar_etapa(self, nome_etapa, inicio_plan=None, fim_plan=None, custo_plan=None):
        etapa = Etapa(len(self._etapas) + 1, nome_etapa)
        if any(v is not None for v in (inicio_plan, fim_plan, custo_plan)):
            etapa.planejar(inicio_plan, fim_plan, custo_plan)
        self._etapas.append(etapa)
        return etapa
    def buscar_etapa(self, id_etapa):
        return next((e for e in self._etapas if e.id == id_etapa), None)
    def esta_em_andamento(self): return self.status == Obra.STATUS_EM_ANDAMENTO

class Usuario:
    def __init__(self, nome, senha):
        self.nome = nome
        self._senha = senha
        self.autenticado = False

class Engenheiro(Usuario):
    def __init__(self, nome, senha):
        super().__init__(nome, senha)
        self.obras_alocadas = []
    def alocar_obra(self, obra: Obra):
        if obra not in self.obras_alocadas: self.obras_alocadas.append(obra)
    def obras_ativas(self): return [o for o in self.obras_alocadas if o.esta_em_andamento()]

class RepositorioObras:
    def __init__(self): self._obras = []
    def cadastrar(self, obra: Obra):
        self._obras.append(obra)
        return obra
    def listar_todas(self): return list(self._obras)
    def listar_ativas(self): return [o for o in self._obras if o.esta_em_andamento()]
    def contem(self, obra: Obra): return obra in self._obras

class RegistrarAvancoRealBase(ABC):
    MSG_SUCESSO = "Avanço registrado com sucesso"
    @abstractmethod
    def listar_obras(self): pass
    @abstractmethod
    def _exigir_obra_valida(self, obra: Obra): pass
    def listar_etapas(self, obra: Obra):
        self._exigir_obra_valida(obra)
        return list(obra.etapas)
    def salvar(self, obra: Obra, id_etapa, data_inicio, data_fim, custo_real, percentual=None):
        self._exigir_obra_valida(obra)
        etapa = obra.buscar_etapa(id_etapa)
        if etapa is None: raise ErroPreCondicao("Etapa não encontrada nesta obra")
        etapa.registrar_avanco(data_inicio, data_fim, custo_real, percentual)
        return RegistrarAvancoRealBase.MSG_SUCESSO
    @staticmethod
    def _exigir_em_andamento(obra: Obra):
        if not obra.esta_em_andamento(): raise ErroPreCondicao('A obra precisa estar com o status "Em Andamento"')

class RegistrarAvancoRealCDU02(RegistrarAvancoRealBase):
    def __init__(self, repositorio: RepositorioObras): self.repositorio = repositorio
    def listar_obras(self): return self.repositorio.listar_ativas()
    def _exigir_obra_valida(self, obra: Obra):
        if not self.repositorio.contem(obra): raise ErroPreCondicao("A obra não está cadastrada no sistema")
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
    etapas: tuple
    etapas_com_avanco: int
    etapas_totais: int

class GerarRelatorioKPIs:
    MSG_DADOS_INSUFICIENTES = "Dados insuficientes: Nenhuma etapa possui avanço real registrado"
    def __init__(self, repositorio: RepositorioObras): self.repositorio = repositorio
    def listar_obras(self):
        obras = self.repositorio.listar_todas()
        if not obras: raise ErroPreCondicao("Nenhuma obra cadastrada no sistema")
        return obras
    def gerar(self, obra: Obra) -> RelatorioKPIs:
        if not self.repositorio.contem(obra): raise ErroPreCondicao("A obra não está cadastrada no sistema")
        executadas = [e for e in obra.etapas if e.tem_avanco_real()]
        if not executadas: raise ErroDadosInsuficientes(GerarRelatorioKPIs.MSG_DADOS_INSUFICIENTES)

        detalhes = tuple(self._desvio_da_etapa(e) for e in executadas)
        planejado = sum(d.custo_planejado for d in detalhes)
        real = sum(d.custo_real for d in detalhes)
        termino_plan = max(d.data_fim_planejada for d in detalhes)
        termino_real = max(d.data_fim_real for d in detalhes)

        return RelatorioKPIs(
            nome_obra=obra.nome, status_obra=obra.status,
            custo_planejado_total=round(planejado, 2), custo_real_total=round(real, 2),
            desvio_financeiro=round(real - planejado, 2),
            data_termino_planejada=termino_plan, data_termino_real=termino_real,
            desvio_fisico_dias=(termino_real - termino_plan).days,
            etapas=detalhes, etapas_com_avanco=len(executadas), etapas_totais=len(obra.etapas)
        )
    @staticmethod
    def _desvio_da_etapa(etapa: Etapa) -> DesvioEtapa:
        if etapa.data_fim_planejada is None or etapa.custo_planejado is None:
            raise ErroPreCondicao(f'A etapa "{etapa.nome}" não possui planejamento')
        return DesvioEtapa(
            nome=etapa.nome, data_fim_planejada=etapa.data_fim_planejada, data_fim_real=etapa.data_fim_real,
            desvio_prazo_dias=(etapa.data_fim_real - etapa.data_fim_planejada).days,
            custo_planejado=etapa.custo_planejado, custo_real=etapa.custo_real,
            desvio_custo=round(etapa.custo_real - etapa.custo_planejado, 2)
        )

class ExibidorRelatorioKPIs:
    @staticmethod
    def _data(d): return d.strftime("%d/%m/%Y")
    @staticmethod
    def _moeda(valor, sinal=False):
        prefixo = ("+" if valor > 0 else "-" if valor < 0 else "") if sinal else ""
        return f"{prefixo}R$ {abs(valor):,.2f}"
    @staticmethod
    def _prazo(dias):
        if dias > 0: return f"+{dias} dia(s) - atraso"
        if dias < 0: return f"{dias} dia(s) - adiantamento"
        return "0 dia(s) - no prazo"
    @staticmethod
    def _custo(valor):
        if valor > 0: return "estouro de orçamento"
        if valor < 0: return "economia"
        return "dentro do orçamento"

# CAMADA DE APRESENTAÇÃO (TKINTER) 

class TelaCadastroObra(tk.Toplevel):
    def __init__(self, parent, repositorio):
        super().__init__(parent)
        self.repositorio = repositorio
        self.title("Gestão de Obras - Nova Obra/Etapa")
        self.geometry("500x650")
        self.configure(padx=20, pady=20)
        self.grab_set()

        # --- SECÇÃO 1: NOVA OBRA ---
        self.frame_obra = ttk.Frame(self)
        self.frame_obra.pack(fill="x")

        ttk.Label(self.frame_obra, text="Nova Obra", font=("Arial", 14, "bold")).pack(pady=(0, 15))
        ttk.Label(self.frame_obra, text="Código (ID) da Obra:").pack(anchor="w")
        self.entry_id = ttk.Entry(self.frame_obra, width=40)
        self.entry_id.pack(pady=(0, 10))

        ttk.Label(self.frame_obra, text="Nome da Obra:").pack(anchor="w")
        self.entry_nome = ttk.Entry(self.frame_obra, width=40)
        self.entry_nome.pack(pady=(0, 20))

        frame_botoes = ttk.Frame(self.frame_obra)
        frame_botoes.pack(fill="x")

        self.btn_salvar = ttk.Button(frame_botoes, text="Cadastrar Obra", command=self.salvar_informacoes)
        self.btn_salvar.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.btn_etapas = ttk.Button(frame_botoes, text="⬇ Adicionar Etapas", command=self.alternar_menu_etapas)
        self.btn_etapas.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # --- SECÇÃO 2: NOVA ETAPA ---
        self.frame_etapas = ttk.LabelFrame(self, text=" Cadastrar Nova Etapa ", padding=15)
        self.etapas_visivel = False 

        ttk.Label(self.frame_etapas, text="Selecione a Obra:").pack(anchor="w")
        self.combo_obras = ttk.Combobox(self.frame_etapas, state="readonly", width=38)
        self.combo_obras.pack(pady=(0, 10))

        ttk.Label(self.frame_etapas, text="Nome da Etapa:").pack(anchor="w")
        self.entry_nome_etapa = ttk.Entry(self.frame_etapas, width=40)
        self.entry_nome_etapa.pack(pady=(0, 10))

        ttk.Label(self.frame_etapas, text="Data Início Planejada (dd/mm/aaaa):").pack(anchor="w")
        self.entry_inicio = ttk.Entry(self.frame_etapas, width=40)
        self.entry_inicio.pack(pady=(0, 10))

        ttk.Label(self.frame_etapas, text="Data Término Planejada (dd/mm/aaaa):").pack(anchor="w")
        self.entry_fim = ttk.Entry(self.frame_etapas, width=40)
        self.entry_fim.pack(pady=(0, 10))

        ttk.Label(self.frame_etapas, text="Custo Planejado (R$):").pack(anchor="w")
        self.entry_custo = ttk.Entry(self.frame_etapas, width=40)
        self.entry_custo.pack(pady=(0, 15))

        self.btn_salvar_etapa = ttk.Button(self.frame_etapas, text="Salvar Etapa", command=self.salvar_etapa)
        self.btn_salvar_etapa.pack(fill="x")

    def alternar_menu_etapas(self):
        if self.etapas_visivel:
            self.frame_etapas.pack_forget()
            self.btn_etapas.config(text="⬇ Adicionar Etapas")
            self.etapas_visivel = False
        else:
            self.atualizar_lista_obras()
            self.frame_etapas.pack(fill="both", expand=True, pady=(20, 0))
            self.btn_etapas.config(text="⬆ Ocultar Etapas")
            self.etapas_visivel = True

    def atualizar_lista_obras(self):
        obras = self.repositorio.listar_ativas()
        if not obras:
            self.combo_obras.set("Nenhuma obra cadastrada")
            self.combo_obras['values'] = []
        else:
            self.combo_obras['values'] = [f"{o.id} - {o.nome}" for o in obras]
            self.combo_obras.current(len(obras) - 1) 

    def salvar_informacoes(self):
        id_texto = self.entry_id.get().strip()
        nome_texto = self.entry_nome.get().strip()

        if not id_texto or not nome_texto:
            messagebox.showwarning("Atenção", "Preencha todos os campos da Obra!")
            return
        try:
            id_obra = int(id_texto)
            if any(o.id == id_obra for o in self.repositorio.listar_todas()):
                messagebox.showerror("Erro", "Já existe uma obra com este Código (ID).")
                return
            self.repositorio.cadastrar(Obra(id_obra, nome_texto))
            messagebox.showinfo("Sucesso", f"Obra '{nome_texto}' cadastrada!")
            self.entry_id.delete(0, tk.END)
            self.entry_nome.delete(0, tk.END)
            if self.etapas_visivel:
                self.atualizar_lista_obras()
        except ValueError:
            messagebox.showerror("Erro de Validação", "O Código deve ser numérico.")

    def salvar_etapa(self):
        selecao = self.combo_obras.get()
        if not selecao or selecao == "Nenhuma obra cadastrada":
            messagebox.showwarning("Atenção", "Cadastre uma obra primeiro!")
            return
        nome = self.entry_nome_etapa.get().strip()
        inicio = self.entry_inicio.get().strip()
        fim = self.entry_fim.get().strip()
        custo = self.entry_custo.get().strip()
        try:
            id_obra = int(selecao.split(" - ")[0])
            obra = next(o for o in self.repositorio.listar_todas() if o.id == id_obra)
            obra.adicionar_etapa(nome, inicio, fim, custo)
            messagebox.showinfo("Sucesso", f"Etapa adicionada à obra '{obra.nome}'!")
            for campo in (self.entry_nome_etapa, self.entry_inicio, self.entry_fim, self.entry_custo):
                campo.delete(0, tk.END)
        except ErroValidacao as erro:
            messagebox.showerror("Erro de Validação", str(erro))
        except ValueError:
            messagebox.showerror("Erro", "Formato de dados inválido.")


class TelaRegistrarAvanco(tk.Toplevel):
    def __init__(self, parent, repositorio):
        super().__init__(parent)
        self.caso_uso = RegistrarAvancoRealCDU02(repositorio)
        self.title("Registrar Avanço Real")
        self.geometry("400x500")
        self.configure(padx=20, pady=20)
        self.grab_set()

        ttk.Label(self, text="Registrar Avanço", font=("Arial", 14, "bold")).pack(pady=(0, 15))

        ttk.Label(self, text="Selecione a Obra:").pack(anchor="w")
        self.combo_obras = ttk.Combobox(self, state="readonly", width=38)
        self.combo_obras.pack(pady=(0, 10))
        self.combo_obras.bind("<<ComboboxSelected>>", self.carregar_etapas)

        ttk.Label(self, text="Selecione a Etapa:").pack(anchor="w")
        self.combo_etapas = ttk.Combobox(self, state="readonly", width=38)
        self.combo_etapas.pack(pady=(0, 15))

        ttk.Label(self, text="Data Início Real (dd/mm/aaaa):").pack(anchor="w")
        self.entry_inicio = ttk.Entry(self, width=40)
        self.entry_inicio.pack(pady=(0, 10))

        ttk.Label(self, text="Data Fim Real (dd/mm/aaaa):").pack(anchor="w")
        self.entry_fim = ttk.Entry(self, width=40)
        self.entry_fim.pack(pady=(0, 10))

        ttk.Label(self, text="Custo Real (R$):").pack(anchor="w")
        self.entry_custo = ttk.Entry(self, width=40)
        self.entry_custo.pack(pady=(0, 10))

        ttk.Label(self, text="% Conclusão (Opcional):").pack(anchor="w")
        self.entry_pct = ttk.Entry(self, width=40)
        self.entry_pct.pack(pady=(0, 20))

        ttk.Button(self, text="Salvar Avanço", command=self.salvar_avanco).pack(fill="x")
        self.carregar_obras()

    def carregar_obras(self):
        obras = self.caso_uso.listar_obras()
        self.combo_obras['values'] = [f"{o.id} - {o.nome}" for o in obras]

    def carregar_etapas(self, event=None):
        if not self.combo_obras.get(): return
        id_obra = int(self.combo_obras.get().split(" - ")[0])
        obra = next(o for o in self.caso_uso.listar_obras() if o.id == id_obra)
        etapas = self.caso_uso.listar_etapas(obra)
        self.combo_etapas['values'] = [f"{e.id} - {e.nome}" for e in etapas]
        if etapas: self.combo_etapas.current(0)

    def salvar_avanco(self):
        if not self.combo_obras.get() or not self.combo_etapas.get():
            messagebox.showwarning("Atenção", "Selecione obra e etapa.")
            return
        
        id_obra = int(self.combo_obras.get().split(" - ")[0])
        obra = next(o for o in self.caso_uso.listar_obras() if o.id == id_obra)
        id_etapa = int(self.combo_etapas.get().split(" - ")[0])
        
        try:
            msg = self.caso_uso.salvar(
                obra, id_etapa, self.entry_inicio.get(), self.entry_fim.get(),
                self.entry_custo.get(), self.entry_pct.get()
            )
            messagebox.showinfo("Sucesso", msg)
            self.destroy()
        except ErroValidacao as erro:
            messagebox.showerror("Erro de Validação", str(erro))

class TelaKPIs(tk.Toplevel):
    def __init__(self, parent, repositorio):
        super().__init__(parent)
        self.caso_uso = GerarRelatorioKPIs(repositorio)
        self.title("Relatório de KPIs")
        self.geometry("600x400")
        self.configure(padx=20, pady=20)
        self.grab_set()

        ttk.Label(self, text="Gerar Relatório de KPIs", font=("Arial", 14, "bold")).pack(pady=(0, 15))

        frame_top = ttk.Frame(self)
        frame_top.pack(fill="x", pady=(0, 20))

        ttk.Label(frame_top, text="Selecione a Obra:").pack(side="left")
        self.combo_obras = ttk.Combobox(frame_top, state="readonly", width=35)
        self.combo_obras.pack(side="left", padx=10)
        
        ttk.Button(frame_top, text="Gerar Relatório", command=self.gerar).pack(side="left")

        self.text_area = tk.Text(self, wrap="word", state="disabled")
        self.text_area.pack(fill="both", expand=True)
        self.carregar_obras()

    def carregar_obras(self):
        try:
            obras = self.caso_uso.listar_obras()
            self.combo_obras['values'] = [f"{o.id} - {o.nome}" for o in obras]
            if obras: self.combo_obras.current(0)
        except ErroPreCondicao:
            self.combo_obras.set("Nenhuma obra cadastrada")

    def gerar(self):
        if not self.combo_obras.get() or self.combo_obras.get() == "Nenhuma obra cadastrada": return
        id_obra = int(self.combo_obras.get().split(" - ")[0])
        obra = next(o for o in self.caso_uso.listar_obras() if o.id == id_obra)

        self.text_area.config(state="normal")
        self.text_area.delete(1.0, tk.END)
        try:
            r = self.caso_uso.gerar(obra)
            exibidor = ExibidorRelatorioKPIs()
            relatorio = (
                f"Obra: {r.nome_obra} | Status: {r.status_obra}\n"
                f"Etapas com avanço: {r.etapas_com_avanco}/{r.etapas_totais}\n"
                f"{'-'*40}\n"
                f"Custo Planejado: {exibidor._moeda(r.custo_planejado_total)}\n"
                f"Custo Real: {exibidor._moeda(r.custo_real_total)}\n"
                f"Desvio Financeiro: {exibidor._moeda(r.desvio_financeiro, True)} ({exibidor._custo(r.desvio_financeiro)})\n"
                f"{'-'*40}\n"
                f"Término Planejado: {exibidor._data(r.data_termino_planejada)}\n"
                f"Término Real: {exibidor._data(r.data_termino_real)}\n"
                f"Desvio Físico: {exibidor._prazo(r.desvio_fisico_dias)}\n"
            )
            self.text_area.insert(tk.END, relatorio)
        except (ErroDadosInsuficientes, ErroPreCondicao) as e:
            self.text_area.insert(tk.END, f"Não foi possível gerar o relatório:\n{str(e)}")
        finally:
            self.text_area.config(state="disabled")

class MenuPrincipal(tk.Tk):
    def __init__(self, repositorio):
        super().__init__()
        self.repositorio = repositorio
        self.title("Sistema de Gestão de Obras")
        self.geometry("350x400")
        self.configure(padx=30, pady=30)
        self.eval('tk::PlaceWindow . center')

        ttk.Label(self, text="Menu Principal", font=("Arial", 16, "bold")).pack(pady=(0, 30))
        
        btn_obra = ttk.Button(self, text="1. Cadastrar Obras e Etapas", command=lambda: TelaCadastroObra(self, self.repositorio))
        btn_obra.pack(pady=10, **{'ipadx': 10, 'ipady': 5})

        btn_avanco = ttk.Button(self, text="2. Registrar Avanço Real", command=lambda: TelaRegistrarAvanco(self, self.repositorio))
        btn_avanco.pack(pady=10, **{'ipadx': 10, 'ipady': 5})

        btn_kpi = ttk.Button(self, text="3. Gerar Relatório de KPIs", command=lambda: TelaKPIs(self, self.repositorio))
        btn_kpi.pack(pady=10, **{'ipadx': 10, 'ipady': 5})

        ttk.Button(self, text="Sair do Sistema", command=self.destroy).pack(side="bottom", pady=20)

# INICIALIZAÇÃO
if __name__ == "__main__":
    repo = RepositorioObras()
    
    # Dados de exemplo pré-carregados
    obra_teste = repo.cadastrar(Obra(1, "Residencial Alphaville"))
    obra_teste.adicionar_etapa("Fundação", "01/10/2026", "15/10/2026", 15000)
    
    app = MenuPrincipal(repositorio=repo)
    app.mainloop()