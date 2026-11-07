"""Camada de domínio do Sistema de Gestão de Obras (Nível 3).

"""
from __future__ import annotations

import hashlib
import hmac
import os
from abc import ABC, abstractmethod
from datetime import date, datetime
from enum import Enum
from typing import Optional


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
    def inteiro(valor, mensagem: str) -> int:
        if isinstance(valor, bool):
            raise ErroValidacao(mensagem)
        if isinstance(valor, int):
            return valor
        if isinstance(valor, str):
            try:
                return int(valor.strip())
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
        texto = valor.strip() if isinstance(valor, str) else ""
        if not texto:
            raise ErroValidacao(mensagem)
        return texto

    @staticmethod
    def periodo(inicio: date, fim: date) -> None:
        if fim < inicio:
            raise ErroValidacao("Término não pode ser antes do início")


class StatusObra(str, Enum):
    EM_ANDAMENTO = "Em Andamento"
    CONCLUIDA = "Concluída"


class StatusEtapa(str, Enum):
    PENDENTE = "Pendente"
    EM_ANDAMENTO = "Em Andamento"
    CONCLUIDA = "Concluída"


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


class Etapa:
    def __init__(self, id_etapa: int, nome: str):
        self.id = id_etapa
        self.nome = Validador.texto_obrigatorio(nome, "Nome da etapa é obrigatório")
        self.status = StatusEtapa.PENDENTE
        self.percentual_conclusao = 0.0
        self._recursos: list[Recurso] = []

        self.data_inicio_planejada: Optional[date] = None
        self.data_fim_planejada: Optional[date] = None
        self.custo_planejado: Optional[float] = None

        self.data_inicio_real: Optional[date] = None
        self.data_fim_real: Optional[date] = None
        self.custo_real = 0.0

    @property
    def recursos(self) -> tuple[Recurso, ...]:
        return tuple(self._recursos)

    def tem_planejamento(self) -> bool:
        return self.data_fim_planejada is not None and self.custo_planejado is not None

    def tem_avanco_real(self) -> bool:
        return self.data_fim_real is not None

    def custo_recursos(self) -> float:
        return sum(r.calcular_custo_total() for r in self._recursos)

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


class Obra:
    def __init__(self, id_obra: int, nome_obra: str, status: StatusObra = StatusObra.EM_ANDAMENTO):
        self.id = id_obra
        self.nome = Validador.texto_obrigatorio(nome_obra, "Nome da obra é obrigatório")
        self.status = status
        self._etapas: list[Etapa] = []

    @property
    def etapas(self) -> tuple[Etapa, ...]:
        return tuple(self._etapas)

    def adicionar_etapa(self, nome_etapa: str, inicio_plan=None, fim_plan=None, custo_plan=None) -> Etapa:
        proximo_id = max((e.id for e in self._etapas), default=0) + 1
        etapa = Etapa(proximo_id, nome_etapa)
        if any(v not in (None, "") for v in (inicio_plan, fim_plan, custo_plan)):
            etapa.planejar(inicio_plan, fim_plan, custo_plan)
        self._etapas.append(etapa)
        return etapa

    def restaurar_etapa(self, etapa: Etapa) -> None:
        """Usado pelo repositório para remontar a obra a partir do banco."""
        self._etapas.append(etapa)

    def buscar_etapa(self, id_etapa: int) -> Optional[Etapa]:
        return next((e for e in self._etapas if e.id == id_etapa), None)

    def esta_em_andamento(self) -> bool:
        return self.status == StatusObra.EM_ANDAMENTO

    def concluir(self) -> None:
        if not self._etapas or any(e.status != StatusEtapa.CONCLUIDA for e in self._etapas):
            raise ErroPreCondicao("Todas as etapas precisam estar concluídas")
        self.status = StatusObra.CONCLUIDA

    def __repr__(self) -> str:
        return f"Obra({self.id}, {self.nome!r}, {self.status.value})"


class Usuario:
    """Usuário do sistema. A senha nunca é guardada em texto puro: só salt + hash."""

    ITERACOES = 100_000
    TAMANHO_MINIMO_SENHA = 4

    def __init__(self, nome: str, senha: Optional[str] = None, *,
                 salt: Optional[bytes] = None, senha_hash: Optional[bytes] = None):
        self.nome = Validador.texto_obrigatorio(nome, "Nome do usuário é obrigatório")
        if senha_hash is not None and salt is not None:
            self._salt, self._hash = salt, senha_hash
        else:
            senha = Validador.texto_obrigatorio(senha, "Senha é obrigatória")
            if len(senha) < self.TAMANHO_MINIMO_SENHA:
                raise ErroValidacao(f"A senha deve ter ao menos {self.TAMANHO_MINIMO_SENHA} caracteres")
            self._salt = os.urandom(16)
            self._hash = self._gerar_hash(senha, self._salt)
        self.autenticado = False

    @classmethod
    def _gerar_hash(cls, senha: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, cls.ITERACOES)

    @property
    def salt(self) -> bytes:
        return self._salt

    @property
    def senha_hash(self) -> bytes:
        return self._hash

    def autenticar(self, senha: str) -> bool:
        self.autenticado = hmac.compare_digest(self._gerar_hash(senha or "", self._salt), self._hash)
        return self.autenticado

    def sair(self) -> None:
        self.autenticado = False


class Engenheiro(Usuario):
    def __init__(self, nome: str, senha: Optional[str] = None, **kwargs):
        super().__init__(nome, senha, **kwargs)
        self._obras_alocadas: list[Obra] = []

    @property
    def obras_alocadas(self) -> tuple[Obra, ...]:
        return tuple(self._obras_alocadas)

    def alocar_obra(self, obra: Obra) -> None:
        if all(o.id != obra.id for o in self._obras_alocadas):
            self._obras_alocadas.append(obra)

    def obras_ativas(self) -> list[Obra]:
        return [o for o in self._obras_alocadas if o.esta_em_andamento()]