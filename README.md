# Sistema de Gestão de Obras (Desktop)

Aplicação desktop em Python para **planejar e acompanhar obras de construção civil**, comparando o que foi planejado com o que foi realmente executado em cada etapa. O sistema calcula indicadores de prazo e de custo (KPIs) para mostrar se a obra está atrasada, adiantada, dentro ou fora do orçamento.

Projeto desenvolvido na disciplina de Programação Orientada a Objetos, como parte da macro tarefa **Desk App** (Níveis I a IV).

---

## O problema que o sistema resolve

Em uma obra, cada etapa (fundação, alvenaria, acabamento...) é planejada com datas e custo previstos. Durante a execução, esses valores mudam. Acompanhar isso em planilhas soltas é trabalhoso e propenso a erro.

Este sistema centraliza o processo:

1. **Planejar:** cadastrar a obra e suas etapas, com datas e custo planejados.
2. **Executar:** registrar o avanço real de cada etapa (datas, custo e percentual de conclusão).
3. **Analisar:** gerar um relatório de KPIs com os desvios de prazo e de custo, por etapa e no total da obra.

---

## Funcionalidades

| Funcionalidade | Descrição |
|---|---|
| Cadastrar obras | Cria uma obra com código (ID) único e nome. Toda obra nasce com status "Em Andamento". |
| Cadastrar etapas | Adiciona etapas a uma obra, com data de início e término planejadas e custo planejado. |
| Registrar avanço real | Informa data de início e fim reais, custo real (opcional) e percentual de conclusão (opcional). Só é permitido em obras em andamento. |
| Gerar relatório de KPIs | Mostra custo planejado x real, desvio financeiro, término planejado x real e desvio físico em dias, no total e por etapa. |

### Regras de negócio principais

- O código (ID) da obra não pode se repetir.
- A data de término não pode ser anterior à data de início.
- Datas devem estar no formato `dd/mm/aaaa`.
- Custos e quantidades não podem ser negativos; o percentual de conclusão fica entre 0 e 100.
- Se o custo real não for informado, o sistema usa a soma do custo dos recursos (materiais e equipamentos) da etapa.
- Uma etapa com 100% de conclusão passa para "Concluída"; abaixo disso fica "Em Andamento".
- Uma obra só pode ser concluída quando todas as suas etapas estiverem concluídas.
- O relatório de KPIs exige ao menos uma etapa com avanço real registrado e que essa etapa tenha planejamento.

### Como os KPIs são interpretados

- **Desvio financeiro** = custo real − custo planejado. Positivo indica estouro de orçamento; negativo, economia.
- **Desvio físico** = data de término real − data de término planejada, em dias. Positivo indica atraso; negativo, adiantamento.

---

## Modelagem orientada a objetos

O projeto aplica os conceitos vistos em sala de aula:

| Conceito | Onde aparece |
|---|---|
| **Herança** | `Material` e `Equipamento` herdam de `Recurso`; `Engenheiro` herda de `Usuario`; `RegistrarAvancoRealCDU02` herda de `RegistrarAvancoRealBase`. |
| **Polimorfismo** | `calcular_custo_total()` é abstrato em `Recurso` e implementado de forma diferente em cada subclasse (quantidade x preço para material; horas x taxa para equipamento). |
| **Composição** | Uma `Obra` é composta por `Etapa`s, e uma `Etapa` é composta por `Recurso`s. Sem a obra, as etapas não existem. |
| **Associação** | `Engenheiro` está associado às `Obra`s alocadas a ele; `RepositorioObras` guarda as obras cadastradas. |
| **Dependência** | Os casos de uso (`GerarRelatorioKPIs`, `RegistrarAvancoRealCDU02`) dependem do `RepositorioObras`; `ExibidorRelatorioKPIs` depende de `RelatorioKPIs`. |

Também há um **Template Method** em `RegistrarAvancoRealBase`: o fluxo de registrar o avanço é fixo e a validação da obra varia por subclasse.

---

## Arquitetura

O código é dividido em camadas, para que a regra de negócio não dependa da tela nem da forma de guardar os dados:

1. **Exceções e validadores:** `ErroValidacao`, `ErroPreCondicao`, `ErroDadosInsuficientes` e a classe `Validador`.
2. **Domínio:** `Obra`, `Etapa`, `Recurso` (`Material`, `Equipamento`), `Usuario` (`Engenheiro`) e os enums de status.
3. **Repositório:** `RepositorioObras`, responsável por guardar e consultar as obras.
4. **Casos de uso:** registrar avanço real e gerar relatório de KPIs.
5. **Apresentação:** menu principal e telas em Tkinter.

---

## Tecnologias

- Python 3.10 ou superior
- Tkinter (biblioteca gráfica que já vem com o Python)

Não há dependências externas para instalar.

---

## Como executar

```bash
git clone https://github.com/mariajulia-senaa/GestaodeObras_Desktop.git
cd GestaodeObras_Desktop
python main.py
```

No Linux, caso o Tkinter não esteja instalado:

```bash
sudo apt install python3-tk
```

Ao abrir, o sistema já carrega uma obra de exemplo ("Residencial Alphaville", com a etapa "Fundação") para facilitar os testes.

---

## Status do projeto

| Nível | Entrega | Situação |
|---|---|---|
| Nível 1 | Modelagem completa com UML e vídeo de apresentação | Concluído |
| Nível 2 | Menu totalmente funcional, ainda sem banco de dados (dados em memória) | Concluído |
| Nível 3 | Funcionamento completo no terminal, com banco de dados | Em desenvolvimento |
| Nível 4 | Interface gráfica com janelas, botões e estilos personalizados | Planejado |

### Limitações atuais

- Os dados ficam apenas em memória e são perdidos ao fechar o programa.
- Materiais e equipamentos existem no modelo, mas ainda não podem ser cadastrados pelo menu.
- Login de engenheiros e alocação de obras existem no modelo, mas ainda não estão ligados às telas.

### Próximos passos (Nível 3)

- Persistir obras, etapas e recursos em banco de dados SQLite.
- Criar o menu de terminal com todas as funcionalidades.
- Ligar ao menu o cadastro de recursos, a conclusão de obras e o login de engenheiros.

---

## Autora

Maria Júlia Sena