"""Testes da interface gráfica (Nível 4). Execute com:  python -m unittest -v test_nivel4

Precisam de ambiente gráfico; sem ele os testes são ignorados.
"""
import unittest

try:
    import tkinter as tk
    import app_gui
    from repositorio import RepositorioSQLite
    from dominio import StatusObra

    _raiz = tk.Tk()
    _raiz.destroy()
    GUI_DISPONIVEL = True
except Exception:
    GUI_DISPONIVEL = False


def preencher(entrada, texto):
    entrada.delete(0, "end")
    entrada.insert(0, texto)


@unittest.skipUnless(GUI_DISPONIVEL, "ambiente gráfico indisponível")
class TestInterface(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite()
        self.app = app_gui.Aplicacao(self.repo)
        self.erros = []
        self.confirmacoes = []
        self.resposta_confirmar = True
        self._erro_original = app_gui.mostrar_erro
        self._confirmar_original = app_gui.confirmar
        app_gui.mostrar_erro = lambda pai, titulo, msg: self.erros.append(msg)
        app_gui.confirmar = self._confirmar_falso

    def tearDown(self):
        app_gui.mostrar_erro = self._erro_original
        app_gui.confirmar = self._confirmar_original
        self.app.destroy()
        self.repo.fechar()

    def _confirmar_falso(self, pai, mensagem):
        self.confirmacoes.append(mensagem)
        return self.resposta_confirmar

    def criar_conta_e_entrar(self, nome="maria", senha="1234"):
        login = self.app.tela
        login.alternar()
        preencher(login.entrada_usuario, nome)
        preencher(login.entrada_senha, senha)
        login.enviar()
        preencher(login.entrada_senha, senha)
        login.enviar()
        self.assertIsInstance(self.app.tela, app_gui.TelaPrincipal)

    def enviar_dialogo(self, dialogo, **campos):
        for nome, valor in campos.items():
            preencher(getattr(dialogo, nome), valor)
        dialogo.confirmar()
        self.app.update()

    def cadastrar_obra(self, codigo="1", nome="Residencial"):
        self.enviar_dialogo(app_gui.DialogoNovaObra(self.app, self.app.atualizar_paginas),
                            entrada_codigo=codigo, entrada_nome=nome)

    def cadastrar_etapa(self, obra_id=1, nome="Fundação", inicio="01/10/2026",
                        fim="15/10/2026", custo="15000"):
        obra = self.repo.buscar_por_id(obra_id)
        self.enviar_dialogo(app_gui.DialogoEtapa(self.app, obra, self.app.atualizar_paginas),
                            entrada_nome=nome, entrada_inicio=inicio, entrada_fim=fim,
                            entrada_custo=custo)

    def test_login_invalido_mostra_mensagem_na_tela(self):
        login = self.app.tela
        preencher(login.entrada_usuario, "ninguem")
        preencher(login.entrada_senha, "1234")
        login.enviar()
        self.assertIsInstance(self.app.tela, app_gui.TelaLogin)
        self.assertIn("Usuário ou senha inválidos", login.mensagem.cget("text"))

    def test_criar_conta_com_senha_curta_e_rejeitada(self):
        login = self.app.tela
        login.alternar()
        preencher(login.entrada_usuario, "maria")
        preencher(login.entrada_senha, "12")
        login.enviar()
        self.assertIn("ao menos 4 caracteres", login.mensagem.cget("text"))
        self.assertIsNone(self.repo.buscar_engenheiro("maria"))

    def test_criar_conta_entrar_e_sair(self):
        self.criar_conta_e_entrar()
        self.assertEqual(self.app.usuario.nome, "maria")
        self.app.sair()
        self.assertIsInstance(self.app.tela, app_gui.TelaLogin)
        self.assertIsNone(self.app.usuario)

    def test_cadastrar_obra_atualiza_painel_e_banco(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        painel = self.app.tela.paginas["painel"]
        self.assertEqual(painel.tabela.get_children(), ("1",))
        self.assertEqual(painel.cartao_total.valor.cget("text"), "1")
        self.assertEqual(self.repo.buscar_por_id(1).nome, "Residencial")
        self.assertEqual(self.erros, [])

    def test_codigo_duplicado_mostra_erro_e_mantem_dialogo_aberto(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        dialogo = app_gui.DialogoNovaObra(self.app)
        self.enviar_dialogo(dialogo, entrada_codigo="1", entrada_nome="Outra")
        self.assertEqual(self.erros, ["Já existe uma obra com este Código (ID)."])
        self.assertTrue(dialogo.winfo_exists())
        dialogo.destroy()

    def test_etapa_com_datas_invertidas_e_rejeitada(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.cadastrar_etapa(inicio="20/10/2026", fim="10/10/2026")
        self.assertIn("Término não pode ser antes do início", self.erros[0])
        self.assertEqual(self.repo.buscar_por_id(1).etapas, ())

    def test_recurso_troca_rotulos_e_calcula_custo(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.cadastrar_etapa()
        obra = self.repo.buscar_por_id(1)
        dialogo = app_gui.DialogoRecurso(self.app, obra, obra.etapas[0],
                                         self.app.atualizar_paginas)
        dialogo.combo_tipo.set("Equipamento")
        dialogo._trocar_tipo()
        self.assertEqual(dialogo.entrada_quantidade.rotulo.cget("text"), "Horas de uso")
        self.enviar_dialogo(dialogo, entrada_nome="Betoneira", entrada_quantidade="20",
                            entrada_valor="50")
        etapa = self.repo.buscar_por_id(1).etapas[0]
        self.assertEqual(etapa.custo_recursos(), 1000)

        pagina = self.app.tela.paginas["etapas"]
        self.app.tela.ir("etapas")
        pagina.tabela_etapas.selection_set("1")
        pagina.carregar_recursos()
        linha = pagina.tabela_recursos.item(pagina.tabela_recursos.get_children()[0], "values")
        self.assertEqual(linha[0], "Equipamento")
        self.assertEqual(linha[2], "20 h")
        self.assertEqual(linha[4], "R$ 1.000,00")

    def test_avanco_sem_selecionar_etapa_avisa(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.cadastrar_etapa()
        self.app.tela.ir("etapas")
        self.app.tela.paginas["etapas"].registrar_avanco()
        self.assertEqual(self.erros, ["Selecione uma etapa na tabela."])

    def test_fluxo_completo_ate_relatorio_e_conclusao(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.cadastrar_etapa(nome="Fundação", inicio="01/10/2026", fim="15/10/2026", custo="15000")
        self.cadastrar_etapa(nome="Alvenaria", inicio="16/10/2026", fim="30/10/2026", custo="20000")
        obra = self.repo.buscar_por_id(1)

        self.enviar_dialogo(app_gui.DialogoRecurso(self.app, obra, obra.etapas[0]),
                            entrada_nome="Cimento", entrada_quantidade="100", entrada_valor="35")
        self.enviar_dialogo(app_gui.DialogoAvanco(self.app, obra, obra.etapas[0]),
                            entrada_inicio="01/10/2026", entrada_fim="18/10/2026",
                            entrada_custo="", entrada_percentual="100")
        self.enviar_dialogo(app_gui.DialogoAvanco(self.app, obra, obra.etapas[1]),
                            entrada_inicio="16/10/2026", entrada_fim="05/11/2026",
                            entrada_custo="21000", entrada_percentual="100")
        self.assertEqual(self.erros, [])

        self.app.tela.ir("kpis")
        cartoes = self.app.tela.paginas["kpis"].cartoes
        self.assertEqual(cartoes["Custo planejado"].valor.cget("text"), "R$ 35.000,00")
        self.assertEqual(cartoes["Custo real"].valor.cget("text"), "R$ 24.500,00")
        self.assertEqual(cartoes["Desvio financeiro"].valor.cget("text"), "-R$ 10.500,00")
        self.assertEqual(cartoes["Desvio financeiro"].nota.cget("text"), "economia")
        self.assertEqual(cartoes["Desvio físico"].valor.cget("text"), "+6 dia(s)")
        self.assertEqual(cartoes["Desvio físico"].nota.cget("text"), "atraso")
        self.assertEqual(len(self.app.tela.paginas["kpis"].tabela.get_children()), 2)

        self.app.tela.ir("painel")
        painel = self.app.tela.paginas["painel"]
        painel.tabela.selection_set("1")
        painel.concluir()
        self.assertEqual(len(self.confirmacoes), 1)
        self.assertEqual(self.repo.buscar_por_id(1).status, StatusObra.CONCLUIDA)
        self.assertEqual(painel.cartao_concluidas.valor.cget("text"), "1")

    def test_concluir_cancelado_nao_altera_obra(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.cadastrar_etapa()
        obra = self.repo.buscar_por_id(1)
        self.enviar_dialogo(app_gui.DialogoAvanco(self.app, obra, obra.etapas[0]),
                            entrada_inicio="01/10/2026", entrada_fim="02/10/2026",
                            entrada_custo="10", entrada_percentual="100")
        painel = self.app.tela.paginas["painel"]
        painel.tabela.selection_set("1")
        self.resposta_confirmar = False
        painel.concluir()
        self.assertEqual(self.repo.buscar_por_id(1).status, StatusObra.EM_ANDAMENTO)

    def test_concluir_com_etapa_pendente_mostra_erro(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.cadastrar_etapa()
        painel = self.app.tela.paginas["painel"]
        painel.tabela.selection_set("1")
        painel.concluir()
        self.assertEqual(self.erros, ["Todas as etapas precisam estar concluídas"])

    def test_relatorio_sem_avanco_mostra_aviso_na_tela(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.cadastrar_etapa()
        self.app.tela.ir("kpis")
        pagina = self.app.tela.paginas["kpis"]
        self.assertIn("Dados insuficientes", pagina.aviso.cget("text"))
        self.assertEqual(self.erros, [])

    def test_alocacao_e_minhas_obras(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra()
        self.app.sair()
        self.criar_conta_e_entrar("joao", "abcd")
        self.app.tela.ir("minhas")
        minhas = self.app.tela.paginas["minhas"]
        self.assertEqual(minhas.tabela.get_children(), ())
        self.app.tela.ir("painel")
        painel = self.app.tela.paginas["painel"]
        painel.tabela.selection_set("1")
        painel.alocar()
        self.app.tela.ir("minhas")
        self.assertEqual(minhas.tabela.get_children(), ("1",))

    def test_dados_persistem_entre_sessoes(self):
        self.criar_conta_e_entrar()
        self.cadastrar_obra(nome="Persistente")
        self.app.sair()
        login = self.app.tela
        preencher(login.entrada_usuario, "maria")
        preencher(login.entrada_senha, "1234")
        login.enviar()
        painel = self.app.tela.paginas["painel"]
        valores = painel.tabela.item("1", "values")
        self.assertEqual(valores[1], "Persistente")


if __name__ == "__main__":
    unittest.main()
