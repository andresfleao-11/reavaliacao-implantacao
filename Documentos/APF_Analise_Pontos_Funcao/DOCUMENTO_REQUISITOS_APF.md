# DOCUMENTO DE REQUISITOS E CONTAGEM DE PONTOS DE FUNÇÃO

## Sistema de Cotação Automatizada de Preços para Reavaliação Patrimonial

**Versão:** 1.0
**Data:** 12/12/2025
**Metodologia:** IFPUG/NESMA (Análise de Pontos de Função)

---

## 1. SUMÁRIO EXECUTIVO

### 1.1 Visão Geral do Sistema

O **Sistema de Cotação Automatizada de Preços** é uma aplicação web desenvolvida para automatizar o processo de pesquisa e cotação de preços de mercado para fins de reavaliação patrimonial de órgãos públicos brasileiros.

O sistema utiliza tecnologias de Inteligência Artificial (Claude/Anthropic) e Web Scraping (SerpAPI + Playwright) para:
- Analisar descrições técnicas ou imagens de produtos
- Pesquisar automaticamente preços no mercado (Google Shopping)
- Extrair preços de páginas web de forma automatizada
- Gerar relatórios padronizados em PDF com evidências

### 1.2 Objetivo de Negócio

Automatizar e padronizar o processo de cotação de preços para reavaliação patrimonial, reduzindo:
- Tempo de pesquisa manual
- Erros humanos na coleta de preços
- Subjetividade na seleção de fontes
- Custo operacional do processo

### 1.3 Público-Alvo

- **Usuários Finais:** Analistas de patrimônio, técnicos de contabilidade
- **Gestores:** Coordenadores de projetos de implantação
- **Administradores:** Gestores de TI responsáveis pela configuração do sistema

---

## 2. ESCOPO FUNCIONAL

### 2.1 Módulos do Sistema

| Módulo | Descrição |
|--------|-----------|
| **Cotação de Preços** | Núcleo do sistema - criação e processamento de cotações automatizadas |
| **Gestão de Clientes** | Cadastro de órgãos públicos contratantes |
| **Gestão de Projetos** | Gerenciamento de projetos de implantação vinculados a clientes |
| **Catálogo de Materiais** | Gestão de tipos de materiais/produtos e suas características |
| **Gestão de Itens** | Controle de itens individuais do patrimônio |
| **Configurações** | Parâmetros do sistema, integrações e fatores de reavaliação |
| **Gestão Financeira** | Controle de custos de APIs e transações |
| **Gestão de Usuários** | Autenticação e controle de acesso |

---

## 3. REQUISITOS FUNCIONAIS DETALHADOS

### 3.1 RF001 - Criar Cotação de Preços

**Descrição:** O usuário deve poder criar uma nova solicitação de cotação de preços informando descrição textual do produto e/ou fazendo upload de imagens do produto.

**Regras de Negócio:**
- RN001: Obrigatório informar descrição textual OU pelo menos uma imagem
- RN002: Imagens aceitas nos formatos PNG, JPG, JPEG
- RN003: A cotação inicia automaticamente após criação
- RN004: O sistema deve vincular a cotação a um projeto (opcional)

**Campos de Entrada:**
| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| inputText | Texto | Condicional | Descrição técnica do produto |
| images | Arquivo[] | Condicional | Imagens do produto |
| codigo | Texto | Não | Código do item |
| local | Texto | Não | Local da pesquisa |
| pesquisador | Texto | Não | Nome do pesquisador |
| project_id | Inteiro | Não | ID do projeto vinculado |

**Fluxo Principal:**
1. Usuário acessa tela de nova cotação
2. Usuário informa dados do produto
3. Sistema valida dados obrigatórios
4. Sistema cria registro da cotação com status PROCESSING
5. Sistema salva imagens no storage
6. Sistema enfileira tarefa de processamento assíncrono
7. Sistema retorna ID da cotação criada

---

### 3.2 RF002 - Processar Cotação Automatizada

**Descrição:** O sistema deve processar a cotação de forma automatizada, utilizando IA para análise e web scraping para coleta de preços.

**Etapas do Processamento:**

| Etapa | Progresso | Descrição |
|-------|-----------|-----------|
| analyzing_image | 0-20% | Análise de imagens/texto via Claude AI |
| generating_query | 20-30% | Geração de query de busca otimizada |
| searching_prices | 30-50% | Pesquisa no Google Shopping via SerpAPI |
| extracting_prices | 50-90% | Extração de preços das páginas encontradas |
| processing_results | 90-95% | Cálculo de estatísticas e detecção de outliers |
| generating_pdf | 95-100% | Geração do relatório PDF |

**Regras de Negócio:**
- RN005: Utilizar modelo Claude para análise de especificações
- RN006: Gerar query de busca em português para Google Shopping Brasil
- RN007: Limitar número de fontes conforme parâmetro configurado
- RN008: Detectar outliers com base na tolerância configurada
- RN009: Calcular valor médio apenas de fontes não-outlier

---

### 3.3 RF003 - Consultar Cotação

**Descrição:** O usuário deve poder consultar o status e resultado de uma cotação.

**Campos de Saída:**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | Inteiro | Identificador único |
| status | Enum | PROCESSING, DONE, ERROR, CANCELLED |
| created_at | DateTime | Data de criação |
| input_text | Texto | Descrição informada |
| search_query_final | Texto | Query utilizada na busca |
| valor_medio | Decimal | Preço médio calculado |
| valor_minimo | Decimal | Menor preço encontrado |
| valor_maximo | Decimal | Maior preço encontrado |
| sources | Lista | Fontes de preços encontradas |
| current_step | Texto | Etapa atual do processamento |
| progress_percentage | Inteiro | Percentual de progresso |

---

### 3.4 RF004 - Listar Cotações (Histórico)

**Descrição:** O usuário deve poder visualizar o histórico de cotações com filtros e paginação.

**Filtros Disponíveis:**
- Período (data inicial/final)
- Status (PROCESSING, DONE, ERROR, CANCELLED)
- Projeto
- Cliente

**Campos de Listagem:**
- ID, Status, Data, Código do Item, Nome do Item, Valor Médio, Projeto, Cliente

---

### 3.5 RF005 - Cancelar Cotação

**Descrição:** O usuário deve poder cancelar uma cotação em andamento.

**Regras de Negócio:**
- RN010: Somente cotações com status PROCESSING podem ser canceladas
- RN011: Atualizar status para CANCELLED e registrar mensagem

---

### 3.6 RF006 - Recotar Item

**Descrição:** O usuário deve poder criar nova cotação baseada em uma cotação anterior com erro ou cancelada.

**Regras de Negócio:**
- RN012: Somente cotações com status ERROR ou CANCELLED podem ser recotadas
- RN013: Copiar dados da cotação original (texto, imagens, código, local, pesquisador)
- RN014: Criar nova cotação com status PROCESSING

---

### 3.7 RF007 - Gerar/Download PDF

**Descrição:** O usuário deve poder gerar e baixar relatório PDF da cotação.

**Conteúdo do PDF:**
- Identificação do item cotado
- Especificações técnicas identificadas
- Query de busca utilizada
- Lista de fontes com preços
- Screenshots das páginas
- Estatísticas (média, mínimo, máximo)
- Data e responsável pela pesquisa

---

### 3.8 RF008 - CRUD de Clientes

**Descrição:** Manutenção do cadastro de clientes (órgãos públicos).

**Campos:**
| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| nome | Texto(300) | Sim |
| nome_curto | Texto(100) | Não |
| cnpj | Texto(20) | Não (único) |
| tipo_orgao | Texto(100) | Não |
| esfera | Texto(50) | Não |
| endereco | Texto | Não |
| cidade | Texto(100) | Não |
| uf | Texto(2) | Não |
| cep | Texto(10) | Não |
| telefone | Texto(20) | Não |
| email | Texto(200) | Não |
| responsavel | Texto(200) | Não |
| ativo | Boolean | Sim (default: true) |

**Operações:** Incluir, Alterar, Consultar, Listar, Excluir (lógica)

---

### 3.9 RF009 - CRUD de Projetos

**Descrição:** Manutenção do cadastro de projetos de implantação.

**Campos:**
| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| client_id | FK | Sim |
| nome | Texto(300) | Sim |
| codigo | Texto(50) | Não (único) |
| descricao | Texto | Não |
| numero_contrato | Texto(100) | Não |
| numero_processo | Texto(100) | Não |
| modalidade_licitacao | Texto(100) | Não |
| data_inicio | DateTime | Não |
| data_previsao_fim | DateTime | Não |
| data_fim | DateTime | Não |
| valor_contrato | Decimal(15,2) | Não |
| status | Enum | Sim |
| responsavel_tecnico | Texto(200) | Não |
| responsavel_cliente | Texto(200) | Não |

**Status Possíveis:** PLANEJAMENTO, EM_ANDAMENTO, CONCLUIDO, CANCELADO, SUSPENSO

**Operações:** Incluir, Alterar, Consultar, Listar, Excluir

---

### 3.10 RF010 - CRUD de Materiais

**Descrição:** Manutenção do catálogo de tipos de materiais/produtos.

**Campos do Material:**
| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| nome | Texto(300) | Sim |
| descricao | Texto | Não |
| codigo | Texto(9) | Não |
| categoria | Texto(100) | Não |
| subcategoria | Texto(100) | Não |
| tipo | Texto(100) | Não |
| marca | Texto(100) | Não |
| fabricante | Texto(200) | Não |
| unidade | Texto(20) | Não (default: UN) |
| client_id | FK | Não |
| ativo | Boolean | Sim (default: true) |

**Sub-funcionalidade:** Gerenciar características do material (nome, tipo_dado, opções)

**Operações:** Incluir, Alterar, Consultar, Listar, Excluir, Importar CSV/XLSX

---

### 3.11 RF011 - CRUD de Itens

**Descrição:** Manutenção de itens individuais do patrimônio.

**Campos do Item:**
| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| material_id | FK | Sim |
| client_id | FK | Não |
| codigo | Texto(100) | Não |
| patrimonio | Texto(50) | Não (único) |
| project_id | FK | Não |
| status | Texto(50) | Sim (default: DISPONIVEL) |
| localizacao | Texto(200) | Não |
| observacoes | Texto | Não |

**Status Possíveis:** DISPONIVEL, EM_USO, MANUTENCAO, BAIXADO, TRANSFERIDO

**Sub-funcionalidades:**
- Gerenciar características do item (valores específicos)
- Gerar itens em lote a partir de material base
- Importar itens via CSV/XLSX

**Operações:** Incluir, Alterar, Consultar, Listar, Excluir, Geração em Lote

---

### 3.12 RF012 - Configurar Parâmetros do Sistema

**Descrição:** Configuração dos parâmetros globais do sistema.

**Parâmetros:**
| Parâmetro | Tipo | Default |
|-----------|------|---------|
| numero_cotacoes_por_pesquisa | Inteiro | 3 |
| max_cotacoes_armazenadas_por_item | Inteiro | 10 |
| tolerancia_outlier_percent | Decimal | 25.0 |
| tolerancia_variacao_vs_banco_percent | Decimal | 30.0 |
| pesquisador_padrao | Texto | "Sistema" |
| local_padrao | Texto | "Online" |
| serpapi_location | Texto | "São Paulo,SP,Brazil" |

---

### 3.13 RF013 - Gerenciar Banco de Preços

**Descrição:** Manutenção da base de preços de referência.

**Campos:**
| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| codigo | Texto(100) | Sim (único) |
| material | Texto(500) | Sim |
| caracteristicas | Texto | Não |
| vl_mercado | Decimal(12,2) | Não |
| update_mode | Enum | Não |

**Modos de Atualização:** MARKET, IPCA, MANUAL, SKIP

**Operações:** Incluir, Alterar, Consultar, Listar, Excluir

---

### 3.14 RF014 - Configurar Fatores de Reavaliação

**Descrição:** Configuração dos fatores para cálculo de reavaliação patrimonial.

**Mapas Configuráveis:**
- **EC (Estado de Conservação):** BOM, REGULAR, RUIM → valores percentuais
- **PU (Período de Utilização):** faixas de anos → valores percentuais
- **VUF (Vida Útil Futura):** faixas de anos → valores percentuais
- **Pesos:** EC, PU, VUF → pesos para cálculo ponderado

---

### 3.15 RF015 - Gerenciar Integrações

**Descrição:** Configuração das integrações com APIs externas.

**Integrações:**
| Provedor | Configurações |
|----------|---------------|
| Anthropic | API Key, Modelo |
| SerpAPI | API Key, Location, Language |

**Funcionalidades:**
- Salvar/Alterar chave de API (criptografada)
- Testar conexão com API
- Visualizar chave mascarada

---

### 3.16 RF016 - Gerenciar Configurações de Projeto

**Descrição:** Cada projeto pode ter sua própria versão de configurações.

**Funcionalidades:**
- Criar nova versão de configuração
- Herdar configurações da versão anterior
- Definir parâmetros específicos do projeto
- Banco de preços específico do projeto
- Fatores de reavaliação específicos

---

### 3.17 RF017 - CRUD de Usuários

**Descrição:** Manutenção do cadastro de usuários do sistema.

**Campos:**
| Campo | Tipo | Obrigatório |
|-------|------|-------------|
| email | Texto(255) | Sim (único) |
| nome | Texto(255) | Sim |
| password | Texto | Sim |
| role | Enum | Sim (default: USER) |
| ativo | Boolean | Sim (default: true) |

**Papéis:** ADMIN, USER

**Operações:** Incluir, Alterar, Consultar, Listar, Desativar

---

### 3.18 RF018 - Autenticação

**Descrição:** Login e controle de sessão do usuário.

**Funcionalidades:**
- Login com email e senha
- Validação de credenciais
- Geração de token de sessão
- Logout

---

### 3.19 RF019 - Gestão Financeira

**Descrição:** Controle de custos das APIs utilizadas.

**Funcionalidades:**
- Registrar transações financeiras por cotação
- Configurar custos por API (por token/chamada)
- Gerar relatórios de custos por período
- Dashboard com resumo financeiro

**Campos da Transação:**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| api_name | Texto | anthropic ou serpapi |
| quote_id | FK | Cotação relacionada |
| quantity | Inteiro | Tokens ou chamadas |
| unit_cost_brl | Decimal | Custo unitário |
| total_cost_brl | Decimal | Custo total |

---

### 3.20 RF020 - Sugestão de Materiais

**Descrição:** Sugerir materiais existentes baseado em especificações técnicas.

**Algoritmo de Similaridade:**
- Match de marca (30%)
- Match de categoria/tipo (25%)
- Match de características (45%)

---

## 4. REQUISITOS NÃO FUNCIONAIS

### 4.1 Desempenho
- RNF001: O sistema deve processar uma cotação completa em até 5 minutos
- RNF002: A interface deve responder em até 3 segundos
- RNF003: O sistema deve suportar até 50 cotações simultâneas

### 4.2 Segurança
- RNF004: Senhas devem ser armazenadas com hash bcrypt
- RNF005: Chaves de API devem ser criptografadas no banco
- RNF006: Autenticação obrigatória para todas as funcionalidades

### 4.3 Disponibilidade
- RNF007: O sistema deve estar disponível 99% do tempo
- RNF008: Backup diário do banco de dados

### 4.4 Usabilidade
- RNF009: Interface responsiva para desktop
- RNF010: Feedback visual de progresso em operações longas

### 4.5 Integrações
- RNF011: Integração com Anthropic Claude API
- RNF012: Integração com SerpAPI (Google Shopping)
- RNF013: Web Scraping via Playwright

---

## 5. MODELO DE DADOS

### 5.1 Diagrama Entidade-Relacionamento (Resumido)

```
┌─────────────┐       ┌─────────────┐       ┌─────────────────┐
│   Client    │1─────n│   Project   │1─────n│  QuoteRequest   │
└─────────────┘       └──────┬──────┘       └────────┬────────┘
                             │1                      │1
                             │                       │
                             │n                      │n
                      ┌──────┴──────────┐     ┌──────┴───────┐
                      │ProjectConfigVer │     │ QuoteSource  │
                      └─────────────────┘     └──────────────┘

┌─────────────┐       ┌─────────────┐       ┌─────────────────┐
│  Material   │1─────n│    Item     │1─────n│ItemCharacteristic│
└──────┬──────┘       └─────────────┘       └─────────────────┘
       │1
       │n
┌──────┴──────────────┐
│MaterialCharacteristic│
└─────────────────────┘

┌─────────────┐       ┌──────────────────┐
│    User     │       │FinancialTransact │
└─────────────┘       └──────────────────┘

┌─────────────┐       ┌─────────────┐       ┌─────────────────┐
│  BankPrice  │       │  Setting    │       │IntegrationSetting│
└─────────────┘       └─────────────┘       └─────────────────┘
```

### 5.2 Entidades Principais

| Entidade | Descrição | Campos Principais |
|----------|-----------|-------------------|
| Client | Órgão público contratante | nome, cnpj, tipo_orgao, endereco |
| Project | Projeto de implantação | nome, codigo, contrato, status |
| QuoteRequest | Solicitação de cotação | input_text, status, valores |
| QuoteSource | Fonte de preço encontrada | url, price_value, is_outlier |
| Material | Tipo de material | nome, codigo, categoria |
| MaterialCharacteristic | Característica do material | nome, tipo_dado, opcoes |
| Item | Item individual | codigo, patrimonio, status |
| ItemCharacteristic | Valor de característica | tipo_id, valor |
| User | Usuário do sistema | email, nome, role |
| ProjectConfigVersion | Versão de config do projeto | parametros, banco_precos |
| FinancialTransaction | Transação financeira | api_name, total_cost |
| BankPrice | Banco de preços global | codigo, material, vl_mercado |
| Setting | Configurações do sistema | key, value_json |
| IntegrationSetting | Config de integração | provider, api_key |
| File | Arquivo (imagem/PDF) | type, storage_path |

---

## 6. CONTAGEM DE PONTOS DE FUNÇÃO

### 6.1 Metodologia

A contagem segue o padrão **IFPUG CPM 4.3.1** (International Function Point Users Group - Counting Practices Manual).

**Tipos de Função:**

| Tipo | Sigla | Descrição |
|------|-------|-----------|
| Arquivo Lógico Interno | ALI | Dados mantidos pelo sistema |
| Arquivo de Interface Externa | AIE | Dados referenciados de sistemas externos |
| Entrada Externa | EE | Processo que mantém ALI |
| Saída Externa | SE | Processo que gera dados para fora |
| Consulta Externa | CE | Processo de consulta sem cálculo |

**Complexidade e Pontos:**

| Tipo | Baixa | Média | Alta |
|------|-------|-------|------|
| ALI | 7 | 10 | 15 |
| AIE | 5 | 7 | 10 |
| EE | 3 | 4 | 6 |
| SE | 4 | 5 | 7 |
| CE | 3 | 4 | 6 |

### 6.2 Arquivos Lógicos Internos (ALI)

| # | ALI | DER | RLR | Complexidade | PF |
|---|-----|-----|-----|--------------|-----|
| 1 | Client | 14 | 1 | Baixa | 7 |
| 2 | Project | 16 | 2 | Média | 10 |
| 3 | QuoteRequest | 18 | 4 | Alta | 15 |
| 4 | QuoteSource | 11 | 2 | Baixa | 7 |
| 5 | Material | 12 | 2 | Média | 10 |
| 6 | MaterialCharacteristic | 6 | 1 | Baixa | 7 |
| 7 | CharacteristicType | 8 | 1 | Baixa | 7 |
| 8 | Item | 11 | 2 | Média | 10 |
| 9 | ItemCharacteristic | 5 | 2 | Baixa | 7 |
| 10 | User | 7 | 1 | Baixa | 7 |
| 11 | ProjectConfigVersion | 22 | 3 | Alta | 15 |
| 12 | ProjectBankPrice | 7 | 1 | Baixa | 7 |
| 13 | FinancialTransaction | 12 | 2 | Média | 10 |
| 14 | ApiCostConfig | 11 | 1 | Baixa | 7 |
| 15 | BankPrice | 6 | 1 | Baixa | 7 |
| 16 | RevaluationParam | 5 | 1 | Baixa | 7 |
| 17 | Setting | 3 | 1 | Baixa | 7 |
| 18 | IntegrationSetting | 4 | 1 | Baixa | 7 |
| 19 | File | 6 | 1 | Baixa | 7 |
| 20 | GeneratedDocument | 4 | 2 | Baixa | 7 |
| | **SUBTOTAL ALI** | | | | **169** |

**Legenda:** DER = Dados Elementares Referenciados, RLR = Registros Lógicos Referenciados

### 6.3 Arquivos de Interface Externa (AIE)

| # | AIE | DER | RLR | Complexidade | PF |
|---|-----|-----|-----|--------------|-----|
| 1 | API Anthropic (Claude) | 8 | 1 | Média | 7 |
| 2 | API SerpAPI | 6 | 1 | Baixa | 5 |
| 3 | Páginas Web (Scraping) | 10 | 1 | Média | 7 |
| | **SUBTOTAL AIE** | | | | **19** |

### 6.4 Entradas Externas (EE)

| # | EE | ALI Ref | DER | Complexidade | PF |
|---|-----|---------|-----|--------------|-----|
| 1 | Incluir Cliente | 1 | 14 | Média | 4 |
| 2 | Alterar Cliente | 1 | 14 | Média | 4 |
| 3 | Excluir Cliente | 1 | 2 | Baixa | 3 |
| 4 | Incluir Projeto | 2 | 16 | Média | 4 |
| 5 | Alterar Projeto | 2 | 16 | Média | 4 |
| 6 | Excluir Projeto | 1 | 2 | Baixa | 3 |
| 7 | Criar Cotação | 3 | 12 | Alta | 6 |
| 8 | Cancelar Cotação | 1 | 3 | Baixa | 3 |
| 9 | Recotar Item | 3 | 10 | Alta | 6 |
| 10 | Incluir Material | 2 | 12 | Média | 4 |
| 11 | Alterar Material | 2 | 12 | Média | 4 |
| 12 | Excluir Material | 2 | 2 | Baixa | 3 |
| 13 | Incluir Característica Material | 2 | 6 | Baixa | 3 |
| 14 | Alterar Característica Material | 2 | 6 | Baixa | 3 |
| 15 | Excluir Característica Material | 1 | 2 | Baixa | 3 |
| 16 | Incluir Item | 3 | 11 | Média | 4 |
| 17 | Alterar Item | 3 | 11 | Média | 4 |
| 18 | Excluir Item | 2 | 2 | Baixa | 3 |
| 19 | Gerar Itens em Lote | 4 | 15 | Alta | 6 |
| 20 | Importar Materiais CSV/XLSX | 4 | 12 | Alta | 6 |
| 21 | Incluir Usuário | 1 | 5 | Baixa | 3 |
| 22 | Alterar Usuário | 1 | 5 | Baixa | 3 |
| 23 | Desativar Usuário | 1 | 2 | Baixa | 3 |
| 24 | Realizar Login | 1 | 3 | Baixa | 3 |
| 25 | Atualizar Parâmetros Sistema | 1 | 8 | Baixa | 3 |
| 26 | Incluir Banco Preços | 1 | 6 | Baixa | 3 |
| 27 | Alterar Banco Preços | 1 | 6 | Baixa | 3 |
| 28 | Excluir Banco Preços | 1 | 2 | Baixa | 3 |
| 29 | Atualizar Fatores Reavaliação | 1 | 5 | Baixa | 3 |
| 30 | Configurar Integração | 1 | 4 | Baixa | 3 |
| 31 | Criar Versão Config Projeto | 2 | 22 | Alta | 6 |
| 32 | Incluir Config Custo API | 1 | 11 | Média | 4 |
| 33 | Alterar Config Custo API | 1 | 11 | Média | 4 |
| 34 | Registrar Transação Financeira | 2 | 12 | Média | 4 |
| | **SUBTOTAL EE** | | | | **131** |

### 6.5 Saídas Externas (SE)

| # | SE | ALI/AIE Ref | DER | Complexidade | PF |
|---|-----|-------------|-----|--------------|-----|
| 1 | Processar Cotação (IA + Scraping) | 4 | 25 | Alta | 7 |
| 2 | Gerar PDF Cotação | 3 | 20 | Alta | 7 |
| 3 | Calcular Estatísticas Cotação | 2 | 8 | Média | 5 |
| 4 | Detectar Outliers | 2 | 6 | Média | 5 |
| 5 | Sugerir Materiais | 2 | 15 | Alta | 7 |
| 6 | Relatório Financeiro | 3 | 12 | Alta | 7 |
| 7 | Dashboard Financeiro | 2 | 8 | Média | 5 |
| 8 | Testar Integração API | 2 | 4 | Baixa | 4 |
| | **SUBTOTAL SE** | | | | **47** |

### 6.6 Consultas Externas (CE)

| # | CE | ALI/AIE Ref | DER | Complexidade | PF |
|---|-----|-------------|-----|--------------|-----|
| 1 | Consultar Cliente | 1 | 14 | Média | 4 |
| 2 | Listar Clientes | 1 | 10 | Baixa | 3 |
| 3 | Consultar Projeto | 2 | 16 | Média | 4 |
| 4 | Listar Projetos | 2 | 10 | Média | 4 |
| 5 | Consultar Cotação | 4 | 25 | Alta | 6 |
| 6 | Listar Cotações | 3 | 12 | Média | 4 |
| 7 | Download Screenshot | 1 | 4 | Baixa | 3 |
| 8 | Consultar Material | 2 | 12 | Média | 4 |
| 9 | Listar Materiais | 2 | 10 | Média | 4 |
| 10 | Listar Características Material | 2 | 6 | Baixa | 3 |
| 11 | Consultar Item | 3 | 11 | Média | 4 |
| 12 | Listar Itens | 3 | 10 | Média | 4 |
| 13 | Listar Opções Status Item | 1 | 3 | Baixa | 3 |
| 14 | Consultar Usuário | 1 | 5 | Baixa | 3 |
| 15 | Listar Usuários | 1 | 5 | Baixa | 3 |
| 16 | Consultar Parâmetros Sistema | 1 | 8 | Baixa | 3 |
| 17 | Listar Banco Preços | 1 | 6 | Baixa | 3 |
| 18 | Consultar Fatores Reavaliação | 1 | 5 | Baixa | 3 |
| 19 | Consultar Integração | 1 | 4 | Baixa | 3 |
| 20 | Listar Localizações SerpAPI | 1 | 3 | Baixa | 3 |
| 21 | Listar Modelos Anthropic | 1 | 3 | Baixa | 3 |
| 22 | Consultar Config Projeto | 2 | 22 | Alta | 6 |
| 23 | Listar Transações Financeiras | 2 | 12 | Média | 4 |
| 24 | Listar Configs Custo API | 1 | 11 | Média | 4 |
| 25 | Obter Configs Ativas API | 1 | 6 | Baixa | 3 |
| 26 | Listar Opções Materiais | 1 | 3 | Baixa | 3 |
| 27 | Listar Tipos Características | 1 | 3 | Baixa | 3 |
| | **SUBTOTAL CE** | | | | **97** |

---

## 7. RESUMO DA CONTAGEM

### 7.1 Totais por Tipo de Função

| Tipo de Função | Quantidade | Pontos |
|----------------|------------|--------|
| Arquivos Lógicos Internos (ALI) | 20 | 169 |
| Arquivos de Interface Externa (AIE) | 3 | 19 |
| Entradas Externas (EE) | 34 | 131 |
| Saídas Externas (SE) | 8 | 47 |
| Consultas Externas (CE) | 27 | 97 |
| **TOTAL PONTOS DE FUNÇÃO BRUTOS** | **92** | **463** |

### 7.2 Fator de Ajuste (VAF)

Características Gerais do Sistema (GSC):

| # | Característica | Valor (0-5) | Justificativa |
|---|----------------|-------------|---------------|
| 1 | Comunicação de Dados | 4 | API REST, integrações externas |
| 2 | Processamento Distribuído | 3 | Celery workers, Redis |
| 3 | Desempenho | 3 | Processamento assíncrono, timeout |
| 4 | Configuração Pesadamente Utilizada | 2 | Docker, variáveis de ambiente |
| 5 | Volume de Transações | 3 | Múltiplas cotações simultâneas |
| 6 | Entrada de Dados Online | 4 | Interface web React/Next.js |
| 7 | Eficiência do Usuário Final | 4 | Interface moderna, feedback visual |
| 8 | Atualização Online | 4 | CRUD completo via web |
| 9 | Processamento Complexo | 5 | IA, web scraping, cálculos |
| 10 | Reusabilidade | 3 | Componentes React, serviços Python |
| 11 | Facilidade de Instalação | 3 | Docker Compose |
| 12 | Facilidade Operacional | 3 | Logs, monitoramento |
| 13 | Múltiplos Locais | 2 | Containerizado |
| 14 | Facilidade de Mudanças | 3 | Migrations, versionamento |
| **TOTAL DI (Degree of Influence)** | | **46** |

**Cálculo do VAF:**
```
VAF = (DI × 0.01) + 0.65
VAF = (46 × 0.01) + 0.65
VAF = 0.46 + 0.65
VAF = 1.11
```

### 7.3 Pontos de Função Ajustados

```
PF Ajustados = PF Brutos × VAF
PF Ajustados = 463 × 1.11
PF Ajustados = 513,93 ≈ 514 PF
```

---

## 8. ANÁLISE DE COMPLEXIDADE

### 8.1 Distribuição por Complexidade

| Complexidade | EE | SE | CE | Total Transações |
|--------------|----|----|-----|------------------|
| Baixa | 19 | 1 | 17 | 37 (54%) |
| Média | 11 | 4 | 9 | 24 (35%) |
| Alta | 4 | 3 | 1 | 8 (12%) |
| **Total** | **34** | **8** | **27** | **69** |

### 8.2 Funcionalidades de Maior Complexidade

| Funcionalidade | Tipo | Complexidade | Justificativa |
|----------------|------|--------------|---------------|
| Processar Cotação | SE | Alta | IA + múltiplas APIs + scraping |
| Gerar PDF Cotação | SE | Alta | Composição de dados + imagens |
| Criar Cotação | EE | Alta | Upload + validação + enfileiramento |
| Importar Materiais | EE | Alta | Parse CSV/XLSX + criação múltipla |
| Gerar Itens Lote | EE | Alta | Criação múltipla + hash unicidade |

---

## 9. ESTIMATIVAS DE ESFORÇO

### 9.1 Produtividade de Referência

| Perfil de Projeto | Horas/PF |
|-------------------|----------|
| Sistema Novo - Equipe Experiente | 8-12 |
| Sistema Novo - Equipe Média | 12-16 |
| Sistema Novo - Equipe Inexperiente | 16-20 |
| Manutenção - Equipe Experiente | 4-8 |

### 9.2 Estimativa de Esforço para o Projeto

Considerando **514 PF** e equipe com experiência média:

| Cenário | Horas/PF | Esforço Total |
|---------|----------|---------------|
| Otimista | 10 | 5.140 horas |
| Realista | 14 | 7.196 horas |
| Pessimista | 18 | 9.252 horas |

**Conversão para Homem-Mês (HM):**
Considerando 176 horas/mês:

| Cenário | Esforço (horas) | Homem-Mês |
|---------|-----------------|-----------|
| Otimista | 5.140 | 29,2 HM |
| Realista | 7.196 | 40,9 HM |
| Pessimista | 9.252 | 52,6 HM |

---

## 10. MATRIZ DE RASTREABILIDADE

### 10.1 Requisitos × Funções

| Requisito | EE | SE | CE |
|-----------|----|----|-----|
| RF001 - Criar Cotação | X | | |
| RF002 - Processar Cotação | | X | |
| RF003 - Consultar Cotação | | | X |
| RF004 - Listar Cotações | | | X |
| RF005 - Cancelar Cotação | X | | |
| RF006 - Recotar Item | X | | |
| RF007 - Gerar PDF | | X | |
| RF008 - CRUD Clientes | X | | X |
| RF009 - CRUD Projetos | X | | X |
| RF010 - CRUD Materiais | X | | X |
| RF011 - CRUD Itens | X | | X |
| RF012 - Config Parâmetros | X | | X |
| RF013 - Banco Preços | X | | X |
| RF014 - Fatores Reavaliação | X | | X |
| RF015 - Integrações | X | X | X |
| RF016 - Config Projeto | X | | X |
| RF017 - CRUD Usuários | X | | X |
| RF018 - Autenticação | X | | |
| RF019 - Gestão Financeira | X | X | X |
| RF020 - Sugestão Materiais | | X | |

---

## 11. TECNOLOGIAS UTILIZADAS

### 11.1 Stack Backend

| Tecnologia | Versão | Função |
|------------|--------|--------|
| Python | 3.11+ | Linguagem principal |
| FastAPI | 0.109.0 | Framework web |
| SQLAlchemy | 2.0.25 | ORM |
| PostgreSQL | 15 | Banco de dados |
| Celery | 5.3.6 | Processamento assíncrono |
| Redis | 7 | Message broker |
| Playwright | 1.41.0 | Web scraping |
| Anthropic SDK | 0.18.1 | Integração Claude AI |

### 11.2 Stack Frontend

| Tecnologia | Versão | Função |
|------------|--------|--------|
| Next.js | 14.1.0 | Framework React |
| React | 18.2.0 | UI Library |
| TypeScript | 5.3.3 | Linguagem |
| Tailwind CSS | 3.4.1 | Estilização |
| Axios | 1.6.7 | Cliente HTTP |
| SWR | 2.2.5 | Data fetching |

### 11.3 Infraestrutura

| Componente | Tecnologia |
|------------|------------|
| Containerização | Docker + Docker Compose |
| CI/CD | - |
| Monitoramento | - |

---

## 12. GLOSSÁRIO

| Termo | Definição |
|-------|-----------|
| **ALI** | Arquivo Lógico Interno - grupo de dados logicamente relacionados mantidos dentro da fronteira da aplicação |
| **AIE** | Arquivo de Interface Externa - grupo de dados referenciados pela aplicação mas mantidos fora de sua fronteira |
| **APF** | Análise de Pontos de Função |
| **CE** | Consulta Externa - processo elementar que envia dados para fora da fronteira |
| **DER** | Dados Elementares Referenciados - campo único reconhecido pelo usuário |
| **EE** | Entrada Externa - processo elementar que processa dados vindos de fora da fronteira |
| **IFPUG** | International Function Point Users Group |
| **PF** | Ponto de Função - unidade de medida de tamanho funcional de software |
| **RLR** | Registro Lógico Referenciado - subgrupo de dados reconhecido pelo usuário |
| **SE** | Saída Externa - processo elementar que envia dados para fora da fronteira com processamento lógico |
| **VAF** | Value Adjustment Factor - fator de ajuste de valor |

---

## 13. REFERÊNCIAS

1. IFPUG - Counting Practices Manual (CPM) 4.3.1
2. NESMA - Netherlands Software Metrics Association
3. ISBSG - International Software Benchmarking Standards Group
4. IEEE 14143 - Software Measurement - Functional Size Measurement

---

## 14. HISTÓRICO DE REVISÕES

| Versão | Data | Autor | Descrição |
|--------|------|-------|-----------|
| 1.0 | 12/12/2025 | Claude | Versão inicial do documento |

---

**Documento gerado automaticamente por análise do código-fonte do projeto.**

---

## ANEXO A - RESUMO EXECUTIVO PARA GESTORES

### Tamanho do Projeto
- **Pontos de Função Brutos:** 463 PF
- **Pontos de Função Ajustados:** 514 PF
- **Classificação:** Projeto de Médio Porte

### Esforço Estimado
- **Cenário Realista:** ~7.200 horas ou 41 Homem-Mês

### Principais Características
- Sistema web completo (frontend + backend + integrações)
- 20 Arquivos Lógicos Internos (entidades de dados)
- 3 Integrações externas (Claude AI, SerpAPI, Web Scraping)
- 69 Funções de Transação (CRUD + processos de negócio)

### Complexidade
- 54% das transações são de baixa complexidade
- 35% de média complexidade
- 12% de alta complexidade (núcleo do negócio: IA e scraping)

### Pontos de Atenção
1. Dependência de APIs externas (Anthropic, SerpAPI)
2. Processamento assíncrono (Celery/Redis)
3. Web scraping sujeito a mudanças em sites terceiros
4. Criptografia de credenciais sensíveis

