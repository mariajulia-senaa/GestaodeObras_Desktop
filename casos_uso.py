"""Casos de uso do sistema (Nível 3).

"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional

from dominio import (
    Engenheiro, Equipamento, Etapa, ErroDadosInsuficientes, ErroPreCondicao,
    ErroValidacao, Material, Obra, Validador,
)
from repositorio import RepositorioSQLite


class CadastrarObra:
    def __init__(self, repositorio: RepositorioSQLite):
        self.repositorio = repositorio

    def executar(self, id_obra, nome: str, engenheiro: Optional[Engenheiro] = None) -> Obra:
        codigo = Validador.inteiro(id_obra, "O Código deve ser numérico.")
        if codigo <= 0:
            raise ErroValidacao("O Código deve ser um número positivo.")
        obra = self.repositorio.cadastrar(Obra(codigo, nome))
        if engenheiro is not None:
            engenheiro.alocar_obra(obra)
            self.repositorio.salvar_alocacoes(engenheiro)
        return obra


class AdicionarEtapa:
    def __init__(self, repositorio: RepositorioSQLite):
        self.repositorio = repositorio

    def executar(self, obra: Obra, nome: str, inicio, fim, custo) -> Etapa:
        obra = _obra_cadastrada_em_andamento(self.repositorio, obra)
        etapa = obra.adicionar_etapa(nome, inicio, fim, custo)
        self.repositorio.salvar(obra)
        return etapa


class AdicionarRecurso:
    TIPOS = ("Material", "Equipamento")

    def __init__(self, repositorio: RepositorioSQLite):
        self.repositorio = repositorio

    def executar(self, obra: Obra, id_etapa: int, tipo: str, nome: str, quantidade_horas, valor) -> None:
        obra = _obra_cadastrada_em_andamento(self.repositorio, obra)
        etapa = obra.buscar_etapa(id_etapa)
        if etapa is None:
            raise ErroPreCondicao("Etapa não encontrada nesta obra")
        qtd = Validador.numero(quantidade_horas, "Quantidade/horas deve ser número")
        val = Validador.numero(valor, "Valor deve ser número")
        if tipo == "Material":
            recurso = Material(nome, qtd, val)
        elif tipo == "Equipamento":
            recurso = Equipamento(nome, qtd, val)
        else:
            raise ErroValidacao("Tipo de recurso inválido")
        etapa.adicionar_recurso(recurso)
        self.repositorio.salvar(obra)


class ConcluirObra:
    def __init__(self, repositorio: RepositorioSQLite):
        self.repositorio = repositorio

    def executar(self, obra: Obra) -> None:
        obra = _obra_cadastrada_em_andamento(self.repositorio, obra)
        obra.concluir()
        self.repositorio.salvar(obra)


def _obra_cadastrada_em_andamento(repositorio: RepositorioSQLite, obra: Obra) -> Obra:
    """Recarrega a obra do banco (fonte da verdade) e exige que esteja em andamento."""
    atual = repositorio.buscar_por_id(obra.id)
    if atual is None:
        raise ErroPreCondicao("A obra não está cadastrada no sistema")
    if not atual.esta_em_andamento():
        raise ErroPreCondicao('A obra precisa estar com o status "Em Andamento"')
    return atual


class RegistrarAvancoRealBase(ABC):
    """O fluxo é fixo; a validação da obra varia por subclasse."""

    MSG_SUCESSO = "Avanço registrado com sucesso"

    def __init__(self, repositorio: RepositorioSQLite):
        self.repositorio = repositorio

    @abstractmethod
    def listar_obras(self) -> list[Obra]: ...

    @abstractmethod
    def _exigir_obra_valida(self, obra: Obra) -> Obra: ...

    def listar_etapas(self, obra: Obra) -> list[Etapa]:
        return list(self._exigir_obra_valida(obra).etapas)

    def salvar(self, obra: Obra, id_etapa: int, data_inicio, data_fim,
               custo_real=None, percentual=None) -> str:
        obra = self._exigir_obra_valida(obra)
        etapa = obra.buscar_etapa(id_etapa)
        if etapa is None:
            raise ErroPreCondicao("Etapa não encontrada nesta obra")
        etapa.registrar_avanco(data_inicio, data_fim, custo_real, percentual)
        self.repositorio.salvar(obra)
        return self.MSG_SUCESSO


class RegistrarAvancoRealCDU02(RegistrarAvancoRealBase):
    def listar_obras(self) -> list[Obra]:
        return self.repositorio.listar_ativas()

    def _exigir_obra_valida(self, obra: Obra) -> Obra:
        return _obra_cadastrada_em_andamento(self.repositorio, obra)


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

    def __init__(self, repositorio: RepositorioSQLite):
        self.repositorio = repositorio

    def listar_obras(self) -> list[Obra]:
        obras = self.repositorio.listar_todas()
        if not obras:
            raise ErroPreCondicao("Nenhuma obra cadastrada no sistema")
        return obras

    def gerar(self, obra: Obra) -> RelatorioKPIs:
        obra = self.repositorio.buscar_por_id(obra.id)
        if obra is None:
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
    """Formata o relatório em texto."""

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


class GerenciarEngenheiros:
    MSG_LOGIN_INVALIDO = "Usuário ou senha inválidos"

    def __init__(self, repositorio: RepositorioSQLite):
        self.repositorio = repositorio

    def cadastrar(self, nome: str, senha: str) -> Engenheiro:
        return self.repositorio.cadastrar_engenheiro(Engenheiro(nome, senha))

    def entrar(self, nome: str, senha: str) -> Engenheiro:
        eng = self.repositorio.buscar_engenheiro((nome or "").strip())
        if eng is None or not eng.autenticar(senha):
            raise ErroValidacao(self.MSG_LOGIN_INVALIDO)
        return eng

    def alocar_obra(self, engenheiro: Engenheiro, obra: Obra) -> None:
        atual = self.repositorio.buscar_por_id(obra.id)
        if atual is None:
            raise ErroPreCondicao("A obra não está cadastrada no sistema")
        engenheiro.alocar_obra(atual)
        self.repositorio.salvar_alocacoes(engenheiro)

    def minhas_obras(self, engenheiro: Engenheiro) -> list[Obra]:
        recarregado = self.repositorio.buscar_engenheiro(engenheiro.nome)
        return list(recarregado.obras_alocadas) if recarregado else []