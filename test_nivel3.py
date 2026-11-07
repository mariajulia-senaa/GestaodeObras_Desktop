"""Testes do Nível 3. Execute com:  python -m unittest -v test_nivel3"""
import os
import tempfile
import unittest

from app_terminal import AppTerminal
from casos_uso import (
    AdicionarEtapa, AdicionarRecurso, CadastrarObra, ConcluirObra, GerarRelatorioKPIs,
    GerenciarEngenheiros, RegistrarAvancoRealCDU02,
)
from dominio import (
    Engenheiro, Equipamento, ErroDadosInsuficientes, ErroPreCondicao, ErroValidacao,
    Material, Obra, StatusEtapa, StatusObra,
)
from repositorio import RepositorioSQLite


class TestPersistencia(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = os.path.join(self.pasta.name, "teste.db")
        self.repo = RepositorioSQLite(self.caminho)

    def tearDown(self):
        self.repo.fechar()
        self.pasta.cleanup()

    def test_dados_sobrevivem_ao_reabrir_o_banco(self):
        CadastrarObra(self.repo).executar("1", "Residencial")
        obra = self.repo.buscar_por_id(1)
        AdicionarEtapa(self.repo).executar(obra, "Fundação", "01/10/2026", "15/10/2026", "15000")
        obra = self.repo.buscar_por_id(1)
        AdicionarRecurso(self.repo).executar(obra, 1, "Material", "Cimento", "10", "35,5")
        AdicionarRecurso(self.repo).executar(obra, 1, "Equipamento", "Betoneira", "8", "50")
        self.repo.fechar()

        novo = RepositorioSQLite(self.caminho)
        try:
            obra = novo.buscar_por_id(1)
            self.assertEqual(obra.nome, "Residencial")
            etapa = obra.etapas[0]
            self.assertEqual(etapa.custo_planejado, 15000)
            self.assertEqual(len(etapa.recursos), 2)
            self.assertIsInstance(etapa.recursos[0], Material)
            self.assertIsInstance(etapa.recursos[1], Equipamento)
            self.assertAlmostEqual(etapa.custo_recursos(), 10 * 35.5 + 8 * 50)
        finally:
            novo.fechar()
            self.repo = RepositorioSQLite(self.caminho)

    def test_id_de_obra_duplicado_e_rejeitado(self):
        CadastrarObra(self.repo).executar("1", "A")
        with self.assertRaises(ErroValidacao):
            CadastrarObra(self.repo).executar("1", "B")

    def test_codigo_nao_numerico_e_rejeitado(self):
        with self.assertRaises(ErroValidacao):
            CadastrarObra(self.repo).executar("abc", "A")

    def test_ids_de_etapa_continuam_apos_recarregar(self):
        CadastrarObra(self.repo).executar("1", "A")
        add = AdicionarEtapa(self.repo)
        add.executar(self.repo.buscar_por_id(1), "E1", "01/01/2026", "02/01/2026", "10")
        add.executar(self.repo.buscar_por_id(1), "E2", "03/01/2026", "04/01/2026", "10")
        self.assertEqual([e.id for e in self.repo.buscar_por_id(1).etapas], [1, 2])


class TestAvancoEKpis(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite()
        CadastrarObra(self.repo).executar("1", "Obra")
        AdicionarEtapa(self.repo).executar(self.repo.buscar_por_id(1), "Fundação",
                                           "01/10/2026", "15/10/2026", "1000")
        self.avanco = RegistrarAvancoRealCDU02(self.repo)

    def tearDown(self):
        self.repo.fechar()

    def test_kpis_sem_avanco_levanta_dados_insuficientes(self):
        with self.assertRaises(ErroDadosInsuficientes):
            GerarRelatorioKPIs(self.repo).gerar(self.repo.buscar_por_id(1))

    def test_avanco_persiste_e_gera_kpis(self):
        obra = self.repo.buscar_por_id(1)
        self.avanco.salvar(obra, 1, "01/10/2026", "18/10/2026", "1200", "100")
        etapa = self.repo.buscar_por_id(1).etapas[0]
        self.assertEqual(etapa.status, StatusEtapa.CONCLUIDA)
        r = GerarRelatorioKPIs(self.repo).gerar(obra)
        self.assertEqual(r.desvio_financeiro, 200)
        self.assertEqual(r.desvio_fisico_dias, 3)

    def test_custo_real_vazio_usa_custo_dos_recursos(self):
        AdicionarRecurso(self.repo).executar(self.repo.buscar_por_id(1), 1, "Material", "Areia", "4", "25")
        self.avanco.salvar(self.repo.buscar_por_id(1), 1, "01/10/2026", "10/10/2026", "", "50")
        etapa = self.repo.buscar_por_id(1).etapas[0]
        self.assertEqual(etapa.custo_real, 100)
        self.assertEqual(etapa.status, StatusEtapa.EM_ANDAMENTO)

    def test_datas_invalidas_nao_sao_gravadas(self):
        obra = self.repo.buscar_por_id(1)
        with self.assertRaises(ErroValidacao):
            self.avanco.salvar(obra, 1, "20/10/2026", "10/10/2026")
        self.assertFalse(self.repo.buscar_por_id(1).etapas[0].tem_avanco_real())


class TestConclusao(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite()
        CadastrarObra(self.repo).executar("1", "Obra")
        AdicionarEtapa(self.repo).executar(self.repo.buscar_por_id(1), "E1",
                                           "01/10/2026", "02/10/2026", "10")

    def tearDown(self):
        self.repo.fechar()

    def test_nao_conclui_com_etapa_pendente(self):
        with self.assertRaises(ErroPreCondicao):
            ConcluirObra(self.repo).executar(self.repo.buscar_por_id(1))

    def test_conclui_e_bloqueia_novas_alteracoes(self):
        RegistrarAvancoRealCDU02(self.repo).salvar(
            self.repo.buscar_por_id(1), 1, "01/10/2026", "02/10/2026", "10", "100")
        ConcluirObra(self.repo).executar(self.repo.buscar_por_id(1))
        self.assertEqual(self.repo.buscar_por_id(1).status, StatusObra.CONCLUIDA)
        with self.assertRaises(ErroPreCondicao):
            AdicionarEtapa(self.repo).executar(self.repo.buscar_por_id(1), "E2",
                                               "01/11/2026", "02/11/2026", "10")


class TestLogin(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSQLite()
        self.ger = GerenciarEngenheiros(self.repo)

    def tearDown(self):
        self.repo.fechar()

    def test_senha_nao_e_guardada_em_texto_puro(self):
        self.ger.cadastrar("ana", "segredo")
        linha = self.repo._con.execute("SELECT * FROM usuario").fetchone()
        self.assertNotIn(b"segredo", bytes(linha["senha_hash"]) + bytes(linha["salt"]))

    def test_login_correto_e_incorreto(self):
        self.ger.cadastrar("ana", "segredo")
        self.assertTrue(self.ger.entrar("ana", "segredo").autenticado)
        with self.assertRaises(ErroValidacao):
            self.ger.entrar("ana", "errada")
        with self.assertRaises(ErroValidacao):
            self.ger.entrar("inexistente", "segredo")

    def test_usuario_duplicado_e_senha_curta(self):
        self.ger.cadastrar("ana", "segredo")
        with self.assertRaises(ErroValidacao):
            self.ger.cadastrar("ana", "outra123")
        with self.assertRaises(ErroValidacao):
            self.ger.cadastrar("bia", "123")

    def test_alocacao_persiste(self):
        eng = self.ger.cadastrar("ana", "segredo")
        CadastrarObra(self.repo).executar("7", "Ponte", eng)
        self.assertEqual([o.id for o in self.ger.minhas_obras(eng)], [7])
        outra = self.ger.cadastrar("bia", "segredo")
        self.assertEqual(self.ger.minhas_obras(outra), [])
        self.ger.alocar_obra(outra, self.repo.buscar_por_id(7))
        self.assertEqual([o.id for o in self.ger.minhas_obras(outra)], [7])


class TestMenuTerminal(unittest.TestCase):
    def rodar(self, repo, entradas):
        it = iter(entradas)
        saidas = []
        AppTerminal(repo, entrada=lambda _p: next(it), saida=saidas.append).executar()
        return "\n".join(saidas)

    def test_fluxo_completo_pelo_menu(self):
        repo = RepositorioSQLite()
        try:
            saida = self.rodar(repo, [
                "2", "ana", "segredo",
                "1", "ana", "segredo",
                "1", "1", "Residencial",
                "3", "1", "Fundação", "01/10/2026", "15/10/2026", "15000",
                "4", "1", "1", "1", "Cimento", "10", "35",
                "4", "1", "1", "2", "Betoneira", "8", "50",
                "2",
                "5", "1", "1", "01/10/2026", "18/10/2026", "", "100",
                "6", "1",
                "7", "1",
                "9",
                "0", "0",
            ])
            self.assertIn("Obra 'Residencial' cadastrada", saida)
            self.assertIn("Material 'Cimento' adicionado", saida)
            self.assertIn("Equipamento 'Betoneira' adicionado", saida)
            self.assertIn("Avanço registrado com sucesso", saida)
            self.assertIn("Custo Real: R$ 750,00", saida)
            self.assertIn("Custo Planejado: R$ 15.000,00", saida)
            self.assertIn("economia", saida)
            self.assertIn("Desvio Físico: +3 dia(s) - atraso", saida)
            self.assertIn("concluída com sucesso", saida)
            self.assertEqual(repo.buscar_por_id(1).status, StatusObra.CONCLUIDA)
        finally:
            repo.fechar()

    def test_erros_nao_derrubam_o_programa(self):
        repo = RepositorioSQLite()
        try:
            saida = self.rodar(repo, [
                "2", "ana", "segredo", "1", "ana", "errada",
                "1", "ana", "segredo",
                "1", "xx", "Obra",
                "6",
                "x",
                "0", "0",
            ])
            self.assertIn("Usuário ou senha inválidos", saida)
            self.assertIn("O Código deve ser numérico", saida)
            self.assertIn("Nenhuma obra cadastrada no sistema", saida)
            self.assertIn("Opção inválida", saida)
        finally:
            repo.fechar()


if __name__ == "__main__":
    unittest.main()