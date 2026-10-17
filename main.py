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

class RepositorioObras:
    def __init__(self): self._obras = []
    def cadastrar(self, obra: Obra):
        self._obras.append(obra)
        return obra
    def listar_todas(self): return list(self._obras)
    def listar_ativas(self): return [o for o in self._obras if o.esta_em_andamento()]
    def contem(self, obra: Obra): return obra in self._obras


# CAMADA DE APRESENTAÇÃO (TKINTER)

class TelaCadastroObra(tk.Tk):
    def __init__(self, repositorio):
        super().__init__()
        self.repositorio = repositorio
        
        self.title("Gestão de Obras")
        # Tamanho maior para acomodar a secção de etapas quando for revelada
        self.geometry("500x650")
        self.configure(padx=20, pady=20)

        # --- SECÇÃO 1: NOVA OBRA ---
        self.frame_obra = ttk.Frame(self)
        self.frame_obra.pack(fill="x")

        titulo = ttk.Label(self.frame_obra, text="Nova Obra", font=("Arial", 14, "bold"))
        titulo.pack(pady=(0, 15))

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

        # Botão que mostra/oculta o formulário de etapas abaixo
        self.btn_etapas = ttk.Button(frame_botoes, text="⬇ Adicionar Etapas", command=self.alternar_menu_etapas)
        self.btn_etapas.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # --- SECÇÃO 2: NOVA ETAPA (Menu abaixo, inicialmente oculto) ---
        # Usamos um LabelFrame para dar um contorno visual à área de etapas
        self.frame_etapas = ttk.LabelFrame(self, text=" Cadastrar Nova Etapa ", padding=15)
        self.etapas_visivel = False # Controlo de estado

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
        """Lógica para mostrar (revelar) ou ocultar a secção de etapas"""
        if self.etapas_visivel:
            self.frame_etapas.pack_forget() # Esconde a secção
            self.btn_etapas.config(text="⬇ Adicionar Etapas")
            self.etapas_visivel = False
        else:
            self.atualizar_lista_obras()
            self.frame_etapas.pack(fill="both", expand=True, pady=(20, 0)) # Mostra a secção
            self.btn_etapas.config(text="⬆ Ocultar Etapas")
            self.etapas_visivel = True

    def atualizar_lista_obras(self):
        """Atualiza a caixa de seleção com as obras disponíveis"""
        obras = self.repositorio.listar_ativas()
        if not obras:
            self.combo_obras.set("Nenhuma obra cadastrada")
            self.combo_obras['values'] = []
        else:
            self.combo_obras['values'] = [f"{o.id} - {o.nome}" for o in obras]
            # Seleciona automaticamente a obra mais recente que foi inserida
            self.combo_obras.current(len(obras) - 1) 

    def salvar_informacoes(self):
        id_texto = self.entry_id.get().strip()
        nome_texto = self.entry_nome.get().strip()

        if not id_texto or not nome_texto:
            messagebox.showwarning("Atenção", "Por favor, preencha todos os campos da Obra!")
            return

        try:
            id_obra = int(id_texto)
            
            if any(o.id == id_obra for o in self.repositorio.listar_todas()):
                messagebox.showerror("Erro", "Já existe uma obra com este Código (ID).")
                return

            nova_obra = Obra(id_obra, nome_texto)
            self.repositorio.cadastrar(nova_obra)
            
            messagebox.showinfo("Sucesso", f"Obra '{nome_texto}' cadastrada com sucesso!")
            
            self.entry_id.delete(0, tk.END)
            self.entry_nome.delete(0, tk.END)
            self.entry_id.focus()

            # Se o menu de etapas já estiver revelado em baixo, atualiza a lista dinamicamente
            if self.etapas_visivel:
                self.atualizar_lista_obras()

        except ValueError:
            messagebox.showerror("Erro de Validação", "O Código (ID) deve ser um número inteiro.")

    def salvar_etapa(self):
        selecao = self.combo_obras.get()
        if not selecao or selecao == "Nenhuma obra cadastrada":
            messagebox.showwarning("Atenção", "Cadastre uma obra primeiro!")
            return

        nome = self.entry_nome_etapa.get().strip()
        inicio = self.entry_inicio.get().strip()
        fim = self.entry_fim.get().strip()
        custo = self.entry_custo.get().strip()

        if not all([nome, inicio, fim, custo]):
            messagebox.showwarning("Atenção", "Preencha todos os campos da etapa!")
            return

        try:
            id_obra = int(selecao.split(" - ")[0])
            obra = next(o for o in self.repositorio.listar_todas() if o.id == id_obra)

            # Grava a etapa utilizando a regra de negócio do Backend
            obra.adicionar_etapa(nome, inicio, fim, custo)
            
            messagebox.showinfo("Sucesso", f"Etapa '{nome}' adicionada à obra '{obra.nome}'!")
            
            # Limpa apenas os campos da Etapa para permitir nova inserção
            self.entry_nome_etapa.delete(0, tk.END)
            self.entry_inicio.delete(0, tk.END)
            self.entry_fim.delete(0, tk.END)
            self.entry_custo.delete(0, tk.END)

        except ErroValidacao as erro:
            messagebox.showerror("Erro de Validação", str(erro))
        except ValueError:
            messagebox.showerror("Erro", "Verifique o formato dos dados preenchidos.")

# INICIALIZAÇÃO
if __name__ == "__main__":
    repo = RepositorioObras()
    
    # Adicionando uma obra de exemplo apenas para testar a caixa de seleção
    repo.cadastrar(Obra(1, "Residencial Alphaville"))
    
    app = TelaCadastroObra(repositorio=repo)
    app.mainloop()