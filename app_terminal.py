"""Sistema de Gestão de Obras - versão de terminal com banco de dados (Nível 3).

Uso:
    python app_terminal.py                 # usa o banco gestao_obras.db
    python app_terminal.py --db outro.db   # usa outro arquivo de banco
"""
from __future__ import annotations

import argparse
from typing import Callable, Optional

from casos_uso import (
    AdicionarEtapa, AdicionarRecurso, CadastrarObra, ConcluirObra, ExibidorRelatorioKPIs,
    GerarRelatorioKPIs, GerenciarEngenheiros, RegistrarAvancoRealCDU02,
)
from dominio import (
    Engenheiro, ErroDadosInsuficientes, ErroPreCondicao, ErroValidacao, Obra, Validador,
)
from repositorio import RepositorioSQLite

ERROS_ESPERADOS = (ErroValidacao, ErroPreCondicao, ErroDadosInsuficientes)
LARGURA = 56


class SaidaDoSistema(Exception):
    """Levantada para encerrar o programa (opção Sair ou fim da entrada)."""


class AppTerminal:
    def __init__(self, repositorio: RepositorioSQLite,
                 entrada: Callable[[str], str] = input,
                 saida: Callable[[str], None] = print):
        self.repo = repositorio
        self._entrada = entrada
        self._saida = saida
        self.engenheiros = GerenciarEngenheiros(repositorio)
        self.cadastrar_obra = CadastrarObra(repositorio)
        self.adicionar_etapa = AdicionarEtapa(repositorio)
        self.adicionar_recurso = AdicionarRecurso(repositorio)
        self.registrar_avanco = RegistrarAvancoRealCDU02(repositorio)
        self.concluir_obra = ConcluirObra(repositorio)
        self.relatorio = GerarRelatorioKPIs(repositorio)
        self.usuario: Optional[Engenheiro] = None

    # ---------- entrada e saída ----------

    def _ler(self, prompt: str) -> str:
        try:
            return self._entrada(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            raise SaidaDoSistema() from None

    def _say(self, texto: str = "") -> None:
        self._saida(texto)

    def _titulo(self, texto: str) -> None:
        self._say()
        self._say("=" * LARGURA)
        self._say(texto.center(LARGURA))
        self._say("=" * LARGURA)

    def _menu(self, titulo: str, opcoes: list[tuple[str, str]]) -> str:
        self._titulo(titulo)
        for chave, texto in opcoes:
            self._say(f"  {chave}. {texto}")
        return self._ler("\nEscolha uma opção: ")

    # ---------- fluxo principal ----------

    def executar(self) -> None:
        try:
            while True:
                if self.usuario is None:
                    self._tela_login()
                else:
                    self._tela_principal()
        except SaidaDoSistema:
            self._say("\nAté logo!")

    def _tela_login(self) -> None:
        op = self._menu("GESTÃO DE OBRAS - ACESSO", [
            ("1", "Entrar"), ("2", "Criar conta de engenheiro"), ("0", "Sair do sistema"),
        ])
        if op == "0":
            raise SaidaDoSistema()
        if op == "1":
            self._guardado(self._entrar)
        elif op == "2":
            self._guardado(self._criar_conta)
        else:
            self._say("Opção inválida.")

    def _tela_principal(self) -> None:
        op = self._menu(f"MENU PRINCIPAL - Eng. {self.usuario.nome}", [
            ("1", "Cadastrar obra"),
            ("2", "Listar obras"),
            ("3", "Cadastrar etapa em uma obra"),
            ("4", "Adicionar material/equipamento a uma etapa"),
            ("5", "Registrar avanço real"),
            ("6", "Gerar relatório de KPIs"),
            ("7", "Concluir obra"),
            ("8", "Alocar-me a uma obra existente"),
            ("9", "Minhas obras"),
            ("0", "Sair da conta"),
        ])
        acoes = {
            "1": self._cadastrar_obra, "2": self._listar_obras, "3": self._cadastrar_etapa,
            "4": self._adicionar_recurso, "5": self._registrar_avanco, "6": self._gerar_relatorio,
            "7": self._concluir_obra, "8": self._alocar_obra, "9": self._minhas_obras,
        }
        if op == "0":
            self.usuario.sair()
            self.usuario = None
            self._say("Sessão encerrada.")
        elif op in acoes:
            self._guardado(acoes[op])
        else:
            self._say("Opção inválida.")

    def _guardado(self, acao: Callable[[], None]) -> None:
        """Executa uma ação mostrando os erros de negócio sem derrubar o programa."""
        try:
            acao()
        except ErroPreCondicao as e:
            self._say(f"\n[Pré-condição] {e}")
        except ErroDadosInsuficientes as e:
            self._say(f"\n[Sem dados] {e}")
        except ErroValidacao as e:
            self._say(f"\n[Erro de validação] {e}")

    # ---------- seleção ----------

    def _escolher_obra(self, obras: list[Obra], vazio: str) -> Obra:
        if not obras:
            raise ErroPreCondicao(vazio)
        self._say("\nObras disponíveis:")
        for o in obras:
            self._say(f"  {o.id} - {o.nome} [{o.status.value}]")
        id_obra = Validador.inteiro(self._ler("Código da obra: "), "O Código deve ser numérico.")
        escolhida = next((o for o in obras if o.id == id_obra), None)
        if escolhida is None:
            raise ErroPreCondicao("Obra não encontrada na lista")
        return escolhida

    def _escolher_etapa(self, obra: Obra):
        if not obra.etapas:
            raise ErroPreCondicao("Esta obra ainda não possui etapas")
        self._say(f"\nEtapas da obra '{obra.nome}':")
        for e in obra.etapas:
            self._say(f"  {e.id} - {e.nome} [{e.status.value}]")
        id_etapa = Validador.inteiro(self._ler("Número da etapa: "), "O número da etapa deve ser numérico.")
        if obra.buscar_etapa(id_etapa) is None:
            raise ErroPreCondicao("Etapa não encontrada nesta obra")
        return id_etapa

    # ---------- ações ----------

    def _criar_conta(self) -> None:
        nome = self._ler("Nome de usuário: ")
        senha = self._ler("Senha (mín. 4 caracteres): ")
        self.engenheiros.cadastrar(nome, senha)
        self._say(f"\nConta '{nome}' criada! Agora faça login.")

    def _entrar(self) -> None:
        nome = self._ler("Nome de usuário: ")
        senha = self._ler("Senha: ")
        self.usuario = self.engenheiros.entrar(nome, senha)
        self._say(f"\nBem-vindo(a), {self.usuario.nome}!")

    def _cadastrar_obra(self) -> None:
        id_obra = self._ler("Código (ID) da obra: ")
        nome = self._ler("Nome da obra: ")
        obra = self.cadastrar_obra.executar(id_obra, nome, self.usuario)
        self._say(f"\nObra '{obra.nome}' cadastrada e alocada a você!")

    def _listar_obras(self) -> None:
        obras = self.repo.listar_todas()
        if not obras:
            raise ErroPreCondicao("Nenhuma obra cadastrada no sistema")
        for o in obras:
            self._imprimir_obra(o)

    def _imprimir_obra(self, obra: Obra) -> None:
        self._say(f"\nObra {obra.id} - {obra.nome} [{obra.status.value}]")
        if not obra.etapas:
            self._say("   (sem etapas)")
        for e in obra.etapas:
            plan = "sem planejamento"
            if e.tem_planejamento():
                plan = (f"plan.: {ExibidorRelatorioKPIs.data(e.data_inicio_planejada)} a "
                        f"{ExibidorRelatorioKPIs.data(e.data_fim_planejada)}, "
                        f"{ExibidorRelatorioKPIs.moeda(e.custo_planejado)}")
            self._say(f"   Etapa {e.id} - {e.nome} [{e.status.value}, {e.percentual_conclusao:.0f}%] {plan}")
            if e.tem_avanco_real():
                self._say(f"      real: {ExibidorRelatorioKPIs.data(e.data_inicio_real)} a "
                          f"{ExibidorRelatorioKPIs.data(e.data_fim_real)}, "
                          f"{ExibidorRelatorioKPIs.moeda(e.custo_real)}")
            for r in e.recursos:
                self._say(f"      - {type(r).__name__}: {r.nome} "
                          f"({ExibidorRelatorioKPIs.moeda(r.calcular_custo_total())})")

    def _cadastrar_etapa(self) -> None:
        obra = self._escolher_obra(self.repo.listar_ativas(), "Nenhuma obra em andamento cadastrada")
        nome = self._ler("Nome da etapa: ")
        inicio = self._ler("Data início planejada (dd/mm/aaaa): ")
        fim = self._ler("Data término planejada (dd/mm/aaaa): ")
        custo = self._ler("Custo planejado (R$): ")
        etapa = self.adicionar_etapa.executar(obra, nome, inicio, fim, custo)
        self._say(f"\nEtapa '{etapa.nome}' adicionada à obra '{obra.nome}'!")

    def _adicionar_recurso(self) -> None:
        obra = self._escolher_obra(self.repo.listar_ativas(), "Nenhuma obra em andamento cadastrada")
        id_etapa = self._escolher_etapa(obra)
        tipo = self._ler("Tipo (1 = Material, 2 = Equipamento): ")
        if tipo not in ("1", "2"):
            raise ErroValidacao("Tipo de recurso inválido")
        nome = self._ler("Nome do recurso: ")
        if tipo == "1":
            nome_tipo = "Material"
            qtd = self._ler("Quantidade: ")
            valor = self._ler("Preço unitário (R$): ")
        else:
            nome_tipo = "Equipamento"
            qtd = self._ler("Horas de uso: ")
            valor = self._ler("Taxa por hora (R$): ")
        self.adicionar_recurso.executar(obra, id_etapa, nome_tipo, nome, qtd, valor)
        self._say(f"\n{nome_tipo} '{nome}' adicionado à etapa!")

    def _registrar_avanco(self) -> None:
        obra = self._escolher_obra(self.registrar_avanco.listar_obras(),
                                   "Nenhuma obra em andamento cadastrada")
        etapas = self.registrar_avanco.listar_etapas(obra)
        if not etapas:
            raise ErroPreCondicao("Esta obra ainda não possui etapas")
        id_etapa = self._escolher_etapa(obra)
        inicio = self._ler("Data início real (dd/mm/aaaa): ")
        fim = self._ler("Data fim real (dd/mm/aaaa): ")
        custo = self._ler("Custo real (R$) [vazio = custo dos recursos]: ")
        pct = self._ler("% de conclusão [100 conclui a etapa]: ")
        self._say(f"\n{self.registrar_avanco.salvar(obra, id_etapa, inicio, fim, custo, pct)}")

    def _gerar_relatorio(self) -> None:
        obra = self._escolher_obra(self.relatorio.listar_obras(), "Nenhuma obra cadastrada no sistema")
        self._titulo("RELATÓRIO DE KPIs")
        self._say(ExibidorRelatorioKPIs.formatar(self.relatorio.gerar(obra)))

    def _concluir_obra(self) -> None:
        obra = self._escolher_obra(self.repo.listar_ativas(), "Nenhuma obra em andamento cadastrada")
        self.concluir_obra.executar(obra)
        self._say(f"\nObra '{obra.nome}' concluída com sucesso!")

    def _alocar_obra(self) -> None:
        obra = self._escolher_obra(self.repo.listar_todas(), "Nenhuma obra cadastrada no sistema")
        self.engenheiros.alocar_obra(self.usuario, obra)
        self._say(f"\nVocê foi alocado(a) à obra '{obra.nome}'.")

    def _minhas_obras(self) -> None:
        obras = self.engenheiros.minhas_obras(self.usuario)
        if not obras:
            raise ErroPreCondicao("Você ainda não está alocado(a) a nenhuma obra")
        for o in obras:
            self._imprimir_obra(o)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sistema de Gestão de Obras (terminal + banco de dados)")
    parser.add_argument("--db", default="gestao_obras.db", help="arquivo SQLite (padrão: gestao_obras.db)")
    args = parser.parse_args()

    repo = RepositorioSQLite(args.db)
    try:
        AppTerminal(repo).executar()
    finally:
        repo.fechar()


if __name__ == "__main__":
    main()
