# Prompts para Claude Code - REVISÃO do Sistema de Cotações SerpAPI

> **Contexto:** O sistema já existe e está funcionando. O objetivo é revisar e ajustar o código para ficar aderente à especificação documentada.  
> **Pré-requisito:** O arquivo `docs/SPEC_COTACOES_SERPAPI.md` deve estar no projeto.  
> **Abordagem:** Análise → Diagnóstico → Correções cirúrgicas

---

## 🔍 PROMPT 0 - Mapeamento do Código Existente

```
Preciso que você faça uma análise completa do código existente relacionado ao sistema de cotações via SerpAPI.

1. Navegue pelo projeto e identifique TODOS os arquivos relacionados a:
   - Integração com SerpAPI (Google Shopping, Google Immersive)
   - Processamento de cotações
   - Validação de produtos
   - Formação de blocos de preço

2. Para cada arquivo encontrado, liste:
   - Caminho completo
   - Classes/funções principais
   - Responsabilidade do arquivo

3. Mapeie o fluxo atual:
   - Onde começa o processamento?
   - Qual a sequência de chamadas?
   - Onde termina?

Apresente um resumo estruturado do que existe hoje.
```

---

## 📋 PROMPT 1 - Análise de Gaps (Código vs Especificação)

```
Agora leia o arquivo docs/SPEC_COTACOES_SERPAPI.md que contém a especificação desejada.

Compare o código existente com a especificação e crie uma tabela de gaps:

| Item da SPEC | Status no Código | Diferença/Gap | Arquivo Afetado |
|--------------|------------------|---------------|-----------------|
| ...          | ✅/⚠️/❌         | ...           | ...             |

Analise especificamente:

ETAPA 1 - GOOGLE SHOPPING:
- [ ] Extração dos 5 campos corretos (position, title, serpapi_immersive_product_api, source, extracted_price)
- [ ] Filtro de domínios bloqueados por "source"
- [ ] Filtro de preços inválidos (None, zero, não-numérico)
- [ ] Ordenação por preço CRESCENTE
- [ ] Limitação a MAX_VALID_PRODUCTS (150)
- [ ] Formação de blocos com variação máxima E quantidade mínima

ETAPA 2 - GOOGLE IMMERSIVE:
- [ ] Validação 1: Link de loja existe
- [ ] Validação 2: Domínio não bloqueado
- [ ] Validação 3: Domínio brasileiro (.br)
- [ ] Validação 4: Domínio não duplicado
- [ ] Validação 5: URL não é de listagem (padrões /busca/, /search/, ?q=, etc)
- [ ] Validação 6: Extração de preço da página
- [ ] Validação 7: Preço confere com extracted_price

CONTROLE DE FLUXO:
- [ ] Bloco falha quando válidos + restantes < mínimo necessário
- [ ] Produtos que falharam são DESCARTADOS (não entram na reformação)
- [ ] Produtos já validados NÃO são revalidados
- [ ] Reformação usa validados + pendentes apenas
- [ ] Incremento de variação quando sem blocos válidos
- [ ] Respeita limite máximo de variação

Liste os gaps em ordem de prioridade (crítico → menor).
```

---

## 🔧 PROMPT 2 - Plano de Correções

```
Com base nos gaps identificados, crie um plano de correções.

Para cada gap, defina:

1. **Descrição:** O que está errado/faltando
2. **Impacto:** Alto/Médio/Baixo
3. **Arquivo(s):** Onde mexer
4. **Tipo de mudança:** 
   - Adicionar código novo
   - Modificar lógica existente
   - Remover código incorreto
   - Reordenar operações
5. **Dependências:** Se depende de outra correção ser feita antes
6. **Estimativa:** Simples/Moderado/Complexo

Agrupe as correções em "batches" que podem ser feitos juntos sem quebrar o sistema.

IMPORTANTE: 
- Priorize manter compatibilidade com código que já funciona
- Identifique se há testes existentes que precisam ser atualizados
- Sinalize se alguma correção pode ter efeito colateral
```

---

## 🛠️ PROMPT 3 - Correção: Etapa Google Shopping

```
Implemente as correções da ETAPA 1 (Google Shopping) conforme os gaps identificados.

Referência: docs/SPEC_COTACOES_SERPAPI.md seção 3

Verifique e corrija se necessário:

1. EXTRAÇÃO DE DADOS
   - Campos extraídos: position, title, serpapi_immersive_product_api, source, extracted_price
   - Está extraindo todos? Falta algum? Tem campo extra desnecessário?

2. FILTRO DE DOMÍNIOS BLOQUEADOS  
   - Deve usar o campo "source" (não o link final)
   - Normalização de domínio (lowercase, sem www)
   - Está usando a lista correta de blocked_domains?

3. FILTRO DE PREÇOS INVÁLIDOS
   - None → remover
   - Zero → remover  
   - Não conversível para float → remover
   - A ordem está correta (filtrar ANTES de ordenar)?

4. ORDENAÇÃO
   - Deve ser CRESCENTE por extracted_price
   - Verificar se está usando o campo correto

5. LIMITAÇÃO
   - Deve limitar a MAX_VALID_PRODUCTS (150)
   - Acontece DEPOIS da ordenação?

6. FORMAÇÃO DE BLOCOS
   - Fórmula de variação: (max - min) / min
   - Blocos com menos de quotes_per_search produtos são DESCARTADOS
   - Não devem ser retornados como "blocos incompletos"

Faça as alterações necessárias, mantendo a estrutura existente quando possível.
Mostre o diff de cada arquivo alterado.
```

---

## 🛠️ PROMPT 4 - Correção: Validações do Produto

```
Implemente as correções das VALIDAÇÕES DE PRODUTO conforme gaps identificados.

Referência: docs/SPEC_COTACOES_SERPAPI.md seção 4

Verifique a ORDEM e COMPLETUDE das validações:

1. NO_STORE_LINK - API Immersive não retornou link válido
   - Está verificando corretamente?
   - O que acontece se a API falhar?

2. BLOCKED_DOMAIN - Loja na lista de bloqueio
   - Está extraindo domínio do store_link (não do source original)?
   - Normalização consistente?

3. FOREIGN_DOMAIN - Loja não brasileira
   - Aceita .br E .com.br?
   - E outros TLDs brasileiros (org.br, gov.br)?

4. DUPLICATE_DOMAIN - Já existe cotação desta loja
   - Está mantendo registro dos domínios já validados?
   - Compara domínio normalizado?

5. LISTING_URL - URL é página de busca
   Padrões que DEVEM ser rejeitados:
   - /busca/
   - /search/
   - ?q=
   - /categoria/
   - /colecao/
   - buscape.com.br (domínio inteiro)
   - zoom.com.br (domínio inteiro)
   Todos estão implementados?

6. EXTRACTION_ERROR - Não conseguiu extrair preço
   - Como está tratando falhas de scraping?

7. PRICE_MISMATCH - Preço divergente
   - Qual tolerância está usando?
   - SPEC sugere 5%

Corrija o que estiver diferente. Mostre antes/depois de cada mudança.
```

---

## 🛠️ PROMPT 5 - Correção: Lógica de Blocos e Falhas

```
Implemente as correções da LÓGICA DE CONTROLE DE BLOCOS.

Referência: docs/SPEC_COTACOES_SERPAPI.md seções 4.3 e 5

Esta é a parte mais crítica. Verifique:

1. FALHA ANTECIPADA DE BLOCO
   Quando um produto falha, o sistema deve verificar:
   - válidos_até_agora + produtos_restantes >= quotes_per_search?
   - Se NÃO: bloco deve FALHAR IMEDIATAMENTE (não continuar validando)
   
   O código atual faz isso? Se não, implementar.

2. PRODUTOS JÁ VALIDADOS
   - Produtos com validation_status == VALID não devem chamar API novamente
   - Devem ser contados como válidos automaticamente
   - Verificar se há flag/status sendo mantido corretamente

3. PRODUTOS QUE FALHARAM
   - Devem ser DESCARTADOS permanentemente
   - NÃO devem entrar na reformação de blocos
   - Verificar se estão sendo filtrados corretamente

4. REFORMAÇÃO DE BLOCOS
   Quando bloco falha:
   a. Pool = validados + pendentes (SEM os falhos)
   b. Reordenar por preço
   c. Reformar blocos com MESMA variação atual
   d. Continuar processamento
   
   O código faz exatamente isso?

5. INCREMENTO DE VARIAÇÃO
   Só acontece quando:
   - Não é possível formar NENHUM bloco válido
   - Incremento: variação_atual + variation_increment (ex: 25% + 20% = 30%)
   - Limite: max_variation_limit (ex: 50%)
   - Ao incrementar, NÃO revalida produtos (só reforma blocos)

Corrija cada item que estiver diferente da especificação.
```

---

## 🛠️ PROMPT 6 - Correção: Loop Principal / Orquestrador

```
Revise a função/método principal que orquestra todo o fluxo de cotações.

Referência: docs/SPEC_COTACOES_SERPAPI.md seção 7

O fluxo CORRETO é:

1. Receber JSON do Google Shopping
2. Processar (extrair, filtrar, ordenar, limitar)
3. variação_atual = config.max_price_variation
4. validated_domains = set()

5. LOOP PRINCIPAL:
   5.1. Separar produtos: VALID | PENDING | FAILED
   5.2. Pool = VALID + PENDING (descartar FAILED)
   5.3. Ordenar pool por preço
   5.4. Formar blocos com variação_atual
   
   5.5. SE sem blocos válidos:
        - variação_atual += increment
        - SE variação_atual > limite: FALHA FINAL
        - CONTINUAR loop (não sair)
   
   5.6. PARA cada bloco:
        - Processar bloco
        - SE bloco VÁLIDO: RETORNAR SUCESSO
        - SE bloco FALHOU: próximo bloco
   
   5.7. SE todos blocos falharam:
        - Voltar ao 5.1 (reformar com novos status)

6. Retornar resultado

Compare com o código atual e ajuste o que divergir.
Atenção especial para:
- Ordem das operações
- Condições de saída do loop
- Tratamento de estados
```

---

## 🧪 PROMPT 7 - Verificação e Testes

```
Após as correções, verifique a integridade do sistema:

1. VERIFICAÇÃO DE SINTAXE
   - Rode o linter/type checker nos arquivos alterados
   - Corrija erros se houver

2. TESTES EXISTENTES
   - Rode os testes existentes
   - Algum quebrou com as mudanças?
   - Se sim, o teste estava errado ou a correção está errada?

3. TESTES FALTANTES
   Verifique se existem testes para estes cenários críticos:
   
   - [ ] Bloco falha por impossibilidade matemática (válidos + restantes < mínimo)
   - [ ] Produtos validados não são revalidados
   - [ ] Produtos falhos são descartados na reformação
   - [ ] Incremento de variação funciona corretamente
   - [ ] Limite de variação é respeitado
   - [ ] Todos os 7 motivos de falha de produto
   
   Se faltarem testes, crie-os.

4. TESTE MANUAL SUGERIDO
   Descreva um cenário de teste manual que o André pode executar para validar o fluxo completo.
```

---

## 📝 PROMPT 8 - Documentação e Finalização

```
Finalize as alterações:

1. CHANGELOG
   Crie um resumo das alterações feitas:
   - O que foi modificado
   - Por que foi modificado
   - Arquivos afetados

2. COMENTÁRIOS NO CÓDIGO
   Adicione comentários explicativos onde a lógica é crítica:
   - Condição de falha antecipada de bloco
   - Lógica de reformação
   - Incremento de variação

3. DOCSTRINGS
   Atualize docstrings de funções alteradas para refletir o comportamento correto

4. TODOs/FIXMEs
   - Remova TODOs que foram resolvidos
   - Liste qualquer pendência que ficou para depois

5. RESUMO FINAL
   Apresente:
   - Total de arquivos alterados
   - Principais mudanças de comportamento
   - Riscos ou pontos de atenção
   - Sugestões de melhorias futuras (se houver)
```

---

## ⚡ PROMPT ÚNICO (Alternativa Rápida)

Se preferir um único prompt mais direto:

```
Leia docs/SPEC_COTACOES_SERPAPI.md e revise todo o código do sistema de cotações SerpAPI.

TAREFA: Identificar e corrigir divergências entre o código atual e a especificação.

FOCO PRINCIPAL nas regras de negócio:

1. ETAPA SHOPPING: filtros por source e preço, ordenação crescente, limite 150, formação de blocos (variação ≤ X%, mínimo N produtos, descartar blocos pequenos)

2. VALIDAÇÕES: 7 validações na ordem (link, bloqueado, brasileiro, duplicado, listagem, extração, preço) - todas devem passar

3. CONTROLE DE BLOCOS:
   - Falha antecipada quando válidos + restantes < mínimo
   - Produtos VALID não revalidam
   - Produtos FAILED são descartados
   - Reformação usa apenas VALID + PENDING

4. VARIAÇÃO: incrementa só quando sem blocos, respeita limite máximo, não revalida ao incrementar

Para cada divergência encontrada:
1. Mostre o código atual (trecho relevante)
2. Explique o problema
3. Mostre a correção
4. Aplique a mudança

Comece analisando os arquivos e listando o que precisa mudar.
```

---

## 💡 Dicas de Uso

- **Sempre comece pelo PROMPT 0** para o Claude Code entender a estrutura existente
- **Se uma correção for grande demais**, peça para dividir em partes menores
- **Se algo quebrar**, cole o erro e peça para reverter/corrigir
- **Valide cada batch** antes de prosseguir para o próximo
- **Mantenha backup** do código antes de iniciar (branch git)
