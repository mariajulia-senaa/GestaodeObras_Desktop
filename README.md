# Sistema de Gestão de Obras (Desktop)

Aplicação em Python para **planejar e acompanhar obras de construção civil**, comparando o que foi planejado com o que foi realmente executado em cada etapa. O sistema calcula indicadores de prazo e de custo (KPIs) para mostrar se a obra está atrasada, adiantada, dentro ou fora do orçamento.

Projeto desenvolvido na disciplina de Programação Orientada a Objetos, como parte da macro tarefa **Desk App** (Níveis I a IV).

---

## O problema que o sistema resolve

Em uma obra, cada etapa (fundação, alvenaria, acabamento...) é planejada com datas e custo previstos. Durante a execução, esses valores mudam. Acompanhar isso em planilhas soltas é trabalhoso e propenso a erro.

Este sistema centraliza o processo:

1. **Planejar:** cadastrar a obra e suas etapas, com datas e custo planejados.
2. **Executar:** registrar o avanço real de cada etapa (datas, custo e percentual de conclusão).
3. **Analisar:** gerar um relatório de KPIs com os desvios de prazo e de custo, por etapa e no total da obra.

---

## Status do projeto

| Nível | Entrega | Situação | Como rodar |
|---|---|---|---|
| Nível 1 | Modelagem completa com UML e vídeo de apresentação | Concluído | - |
| Nível 2 | Menu totalmente funcional em Tkinter, dados em memória | Concluído | `python main.py` |
| **Nível 3** | **Funcionamento completo no terminal, com banco de dados** | **Concluído** | `python app_terminal.py` |
| Nível 4 | Interface gráfica com janelas, botões e estilos personalizados | Planejado | - |

---

## Nível 3: terminal + banco de dados SQLite

Todos os dados (usuários, obras, etapas, recursos e alocações) ficam em um arquivo SQLite. Ao fechar e abrir o programa de novo, tudo continua lá.

### Como executar

Requisitos: Python 3.10 ou superior. Não há nada para instalar: o `sqlite3` já vem com o Python.

```bash
git clone https://github.com/mariajulia-senaa/GestaodeObras_Desktop.git
cd GestaodeObras_Desktop
python app_terminal.py
```

O banco é criado automaticamente no arquivo `gestao_obras.db`. Para usar outro arquivo:

```bash
python app_terminal.py --db meu_banco.db
```

### Primeiro uso

1. Escolha **2 - Criar conta de engenheiro** (nome e senha com ao menos 4 caracteres).
2. Escolha **1 - Entrar** com a conta criada.
3. Use o menu principal.

### Funcionalidades do menu

| Opção | O que faz |
|---|---|
| 1. Cadastrar obra | Cria uma obra com código (ID) único e nome. A obra é alocada automaticamente ao engenheiro logado. |
| 2. Listar obras | Mostra todas as obras com etapas, status, percentual, valores planejados e reais e recursos. |
| 3. Cadastrar etapa | Adiciona uma etapa a uma obra em andamento, com datas e custo planejados. |
| 4. Adicionar material/equipamento | Inclui um `Material` (quantidade x preço) ou `Equipamento` (horas x taxa) em uma etapa. |
| 5. Registrar avanço real | Informa datas reais, custo real (opcional) e percentual de conclusão (opcional). |
| 6. Gerar relatório de KPIs | Mostra custo planejado x real, desvio financeiro, término planejado x real e desvio físico em dias. |
| 7. Concluir obra | Marca a obra como concluída, desde que todas as etapas estejam concluídas. |
| 8. Alocar-me a uma obra | Associa o engenheiro logado a uma obra já existente. |
| 9. Minhas obras | Lista as obras alocadas ao engenheiro logado. |

### Regras de negócio

- O código (ID) da obra deve ser numérico, positivo e não pode se repetir.
- Datas devem estar no formato `dd/mm/aaaa`, e o término não pode ser anterior ao início.
- Custos, quantidades e horas não podem ser negativos; o percentual de conclusão fica entre 0 e 100.
- Se o custo real não for informado, o sistema usa a soma do custo dos recursos (materiais e equipamentos) da etapa.
- Uma etapa com 100% de conclusão passa para "Concluída"; abaixo disso fica "Em Andamento". Para concluir a obra, informe 100% em todas as etapas.
- Etapas, recursos e avanços só podem ser alterados em obras "Em Andamento".
- O relatório de KPIs exige ao menos uma etapa com avanço real, e essa etapa precisa ter planejamento.
- Nomes de usuário não se repetem. As senhas **não são guardadas em texto puro**: o banco guarda só um salt e o hash PBKDF2-SHA256.

### Como os KPIs são interpretados

- **Desvio financeiro** = custo real − custo planejado. Positivo indica estouro de orçamento; negativo, economia.
- **Desvio físico** = data de término real − data de término planejada, em dias. Positivo indica atraso; negativo, adiantamento.

### Modelo do banco de dados

```
usuario (nome PK, salt, senha_hash)
   │
   └── alocacao (usuario_nome FK, obra_id FK)  PK composta
                                  │
obra (id PK, nome, status) ───────┘
   │
   └── etapa (obra_id FK, id)  PK composta, ON DELETE CASCADE
          │   nome, status, percentual,
          │   inicio/fim/custo planejados, inicio/fim/custo reais
          │
          └── recurso (id PK, obra_id, etapa_id FK)  ON DELETE CASCADE
                  tipo ('MATERIAL' | 'EQUIPAMENTO'), nome,
                  quantidade_horas, valor_unitario
```

Os recursos ficam em **uma única tabela** com a coluna `tipo`, que indica qual subclasse (`Material` ou `Equipamento`) deve ser recriada ao ler o banco. Cada gravação de obra é feita em uma única transação: ou grava tudo, ou nada.

---

## Modelagem orientada a objetos

| Conceito | Onde aparece |
|---|---|
| **Herança** | `Material` e `Equipamento` herdam de `Recurso`; `Engenheiro` herda de `Usuario`; `RegistrarAvancoRealCDU02` herda de `RegistrarAvancoRealBase`. |
| **Polimorfismo** | `calcular_custo_total()` é abstrato em `Recurso` e implementado de forma diferente em cada subclasse (quantidade x preço para material; horas x taxa para equipamento). |
| **Composição** | Uma `Obra` é composta por `Etapa`s, e uma `Etapa` é composta por `Recurso`s. Sem a obra, as etapas não existem (e no banco, `ON DELETE CASCADE`). |
| **Associação** | `Engenheiro` está associado às `Obra`s alocadas a ele (tabela `alocacao`). |
| **Dependência** | Os casos de uso dependem do `RepositorioSQLite`; `ExibidorRelatorioKPIs` depende de `RelatorioKPIs`; `AppTerminal` depende dos casos de uso. |

Também há um **Template Method** em `RegistrarAvancoRealBase`: o fluxo de registrar o avanço é fixo e a validação da obra varia por subclasse.

---

## Arquitetura e arquivos

O código é dividido em camadas. A regra de negócio não conhece nem o banco nem a tela, o que permite trocar a apresentação no Nível 4 sem mexer no resto.

| Arquivo | Camada | Conteúdo |
|---|---|---|
| `dominio.py` | Domínio | Exceções, `Validador`, `Obra`, `Etapa`, `Recurso` (`Material`, `Equipamento`), `Usuario` (`Engenheiro`) |
| `repositorio.py` | Persistência | `RepositorioSQLite`: criação das tabelas, gravação e leitura das obras e dos usuários |
| `casos_uso.py` | Aplicação | Cadastros, registrar avanço, concluir obra, relatório de KPIs, login e alocação |
| `app_terminal.py` | Apresentação | Menu de terminal (login e menu principal) |
| `test_nivel3.py` | Testes | 16 testes automatizados |
| `main.py` | Apresentação (Nível 2) | Versão Tkinter com dados em memória, mantida como estava |

### Testes

```bash
python -m unittest -v test_nivel3
```

Os testes usam bancos temporários e cobrem persistência entre execuções, regras de negócio, login, alocação e o fluxo completo pelo menu.

---

## Limitações conhecidas

- O `main.py` (Nível 2) ainda usa dados em memória e tem seu próprio código de domínio. Ele será substituído pela interface gráfica do Nível 4, que reaproveitará `dominio.py`, `repositorio.py` e `casos_uso.py`.
- Todos os engenheiros enxergam todas as obras; a alocação serve para a opção "Minhas obras".

---

## Autora

Maria Júlia Sena
