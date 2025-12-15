import anthropic
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import base64
import json
import logging
import time

logger = logging.getLogger(__name__)


class ClaudeCallLog(BaseModel):
    """Log de uma chamada individual ao Claude"""
    activity: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    prompt: Optional[str] = None  # Prompt enviado para a IA


class ItemAnalysisResult(BaseModel):
    nome_canonico: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    part_number: Optional[str] = None
    codigo_interno: Optional[str] = None
    especificacoes_tecnicas: Dict[str, Any] = {}  # Especificações técnicas extraídas
    palavras_chave: List[str] = []
    sinonimos: List[str] = []
    query_principal: str  # Query baseada nas especificações técnicas
    query_alternativas: List[str] = []
    termos_excluir: List[str] = []
    observacoes: Optional[str] = None
    nivel_confianca: float = 0.0
    total_tokens_used: int = 0  # Total de tokens usados em todas as chamadas
    call_logs: List[ClaudeCallLog] = []  # Log detalhado de cada chamada


class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.total_tokens_used = 0  # Rastrear tokens usados
        self.call_logs: List[ClaudeCallLog] = []  # Log de todas as chamadas

    def _call_with_retry(self, func, max_retries=5):
        """Chama a API com retry exponencial em caso de rate limit ou API sobrecarregada"""
        for attempt in range(max_retries):
            try:
                return func()
            except anthropic.RateLimitError as e:
                if attempt == max_retries - 1:
                    raise

                # Extrair tempo de espera do erro, ou usar backoff exponencial
                wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
                logger.warning(f"Rate limit atingido. Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
            except anthropic.APIStatusError as e:
                # Tratar erro 529 (overloaded) com retry
                if e.status_code == 529:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s, 20s, 25s
                    logger.warning(f"API sobrecarregada (529). Aguardando {wait_time}s antes de tentar novamente (tentativa {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                raise

    async def analyze_item(
        self,
        input_text: Optional[str] = None,
        image_files: Optional[List[bytes]] = None
    ) -> ItemAnalysisResult:
        """
        Analisa item em duas etapas:
        1. Análise da descrição de texto OU OCR de imagem
        2. Se specs relevantes não estiverem visíveis, busca na web
        """
        # Se só tiver texto (sem imagem), usar fluxo simplificado
        if input_text and not image_files:
            return await self._analyze_text_only(input_text)

        content = []

        if input_text:
            content.append({
                "type": "text",
                "text": f"Descrição fornecida: {input_text}"
            })

        if image_files:
            for img_data in image_files:
                img_base64 = base64.standard_b64encode(img_data).decode("utf-8")
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_base64,
                    },
                })

        # ETAPA 1: OCR e identificação básica
        ocr_prompt = """
Você é um assistente especializado em identificação de equipamentos.

## TAREFA: OCR E IDENTIFICAÇÃO BÁSICA

Analise a imagem e extraia:

1. **OCR COMPLETO**: Transcreva TODO o texto visível na imagem literalmente

2. **Tipo de produto**: (notebook, ar condicionado, impressora, etc.)

3. **Marca**: Se visível na etiqueta

4. **Modelo**: Código do modelo (ex: UL1502Y, 42AFCB12M5)

## ESPECIFICAÇÕES TÉCNICAS RELEVANTES PARA COTAÇÃO
Identifique se as seguintes specs estão VISÍVEIS na imagem:

Para NOTEBOOK:
- Processador (Intel i5, i7, Ryzen 5, Ryzen 7, etc.) - VISÍVEL?
- Memória RAM (8GB, 16GB, etc.) - VISÍVEL?
- Armazenamento (SSD 256GB, SSD 512GB, HD 1TB, etc.) - VISÍVEL?
- Tamanho da tela (14", 15.6", etc.) - VISÍVEL?

Para AR CONDICIONADO:
- Capacidade BTUs (9000, 12000, 18000, etc.) - VISÍVEL?
- Ciclo (Frio/Quente-Frio) - VISÍVEL?
- Tipo (Split, Inverter) - VISÍVEL?

Para IMPRESSORA:
- Tipo (laser, jato de tinta) - VISÍVEL?
- Recursos (wifi, duplex) - VISÍVEL?

Retorne um JSON:
{
  "ocr_completo": "todo texto extraído da imagem",
  "tipo_produto": "notebook/ar_condicionado/impressora/outro",
  "marca": "marca identificada ou null",
  "modelo": "código do modelo ou null",
  "specs_visiveis": {
    "processador": "valor ou null",
    "ram": "valor ou null",
    "armazenamento": "valor ou null",
    "tela": "valor ou null",
    "btus": "valor ou null",
    "ciclo": "valor ou null",
    "outras": {}
  },
  "tem_specs_relevantes": true/false
}

## CRITÉRIO CRÍTICO PARA tem_specs_relevantes:

⚠️ ATENÇÃO - LEIA COM CUIDADO:

Para NOTEBOOK, tem_specs_relevantes = true SOMENTE SE pelo menos UMA destas specs estiver visível:
- Processador (Intel Core i3/i5/i7, AMD Ryzen 3/5/7, etc.)
- Memória RAM (4GB, 8GB, 16GB, 32GB)
- Armazenamento (SSD ou HD com capacidade)

❌ NÃO SÃO specs relevantes para cotação de notebook:
- Voltagem de entrada (19V, 110V, 220V)
- Potência da fonte/carregador (45W, 65W, 90W)
- Corrente (2.37A, 3.42A)
- Número de série
- Modelo de placa WiFi (RTL8821CE)
- Certificações (ANATEL, FCC, CE)

Exemplo: Uma etiqueta mostrando "Input: 19V 2.37A 45W" é uma etiqueta da FONTE DE ALIMENTAÇÃO, não do notebook. Neste caso tem_specs_relevantes = false.

Para AR CONDICIONADO, tem_specs_relevantes = true SOMENTE SE:
- Capacidade em BTUs estiver visível

Para IMPRESSORA, tem_specs_relevantes = true SOMENTE SE:
- Tipo de impressão (laser/jato de tinta) estiver visível
"""

        content.insert(0, {"type": "text", "text": ocr_prompt})

        logger.info("Etapa 1: OCR e identificação básica")
        ocr_response = self._call_with_retry(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": content}]
            )
        )

        # Registrar tokens usados
        if hasattr(ocr_response, 'usage'):
            input_tokens = ocr_response.usage.input_tokens
            output_tokens = ocr_response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            # Registrar log da chamada
            self.call_logs.append(ClaudeCallLog(
                activity="OCR e identificação básica da imagem",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=ocr_prompt
            ))

            logger.info(f"OCR tokens: {total_tokens}")

        ocr_text = ocr_response.content[0].text
        ocr_data = self._parse_json(ocr_text)

        logger.info(f"OCR resultado: tipo={ocr_data.get('tipo_produto')}, marca={ocr_data.get('marca')}, modelo={ocr_data.get('modelo')}")
        logger.info(f"Tem specs relevantes: {ocr_data.get('tem_specs_relevantes')}")

        # ETAPA 2: Busca web se necessário (specs não visíveis na imagem)
        specs_from_web = {}
        if not ocr_data.get('tem_specs_relevantes', False) and ocr_data.get('marca') and ocr_data.get('modelo'):
            marca = ocr_data.get('marca')
            modelo = ocr_data.get('modelo')
            tipo = ocr_data.get('tipo_produto', 'produto')

            logger.info(f"Etapa 2: Buscando specs na web para {marca} {modelo}")
            specs_from_web = await self._search_specs_on_web(marca, modelo, tipo)
            logger.info(f"Specs encontradas na web: {specs_from_web}")

        # ETAPA 3: Gerar resultado final com todas as informações
        final_prompt = self._build_final_prompt(ocr_data, specs_from_web)

        logger.info("Etapa 3: Gerando análise final")
        final_response = self._call_with_retry(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": final_prompt}]
            )
        )

        # Registrar tokens usados
        if hasattr(final_response, 'usage'):
            input_tokens = final_response.usage.input_tokens
            output_tokens = final_response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            # Registrar log da chamada
            self.call_logs.append(ClaudeCallLog(
                activity="Análise final e geração de query de busca",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=final_prompt
            ))

            logger.info(f"Final analysis tokens: {total_tokens}")

        response_text = final_response.content[0].text
        data = self._parse_json(response_text)

        # Adicionar total de tokens e logs ao resultado
        data['total_tokens_used'] = self.total_tokens_used
        data['call_logs'] = [log.dict() for log in self.call_logs]

        return ItemAnalysisResult(**data)

    async def _search_specs_on_web(self, marca: str, modelo: str, tipo: str) -> Dict[str, Any]:
        """Busca especificações técnicas na web usando web_search do Claude"""

        search_prompt = f"""
Busque as especificações técnicas do produto: {marca} {modelo} ({tipo})

Use a ferramenta web_search para encontrar as especificações técnicas REAIS deste produto.

Após a busca, retorne um JSON com as especificações encontradas:

Para NOTEBOOK:
{{
  "processador": "ex: Intel Core i5-1235U",
  "ram": "ex: 8GB DDR4",
  "armazenamento": "ex: SSD 256GB",
  "tela": "ex: 15.6 polegadas Full HD",
  "fonte_informacao": "URL da fonte"
}}

Para AR CONDICIONADO:
{{
  "capacidade_btus": "ex: 12000",
  "ciclo": "ex: Frio",
  "tipo": "ex: Split Inverter",
  "tensao": "ex: 220V",
  "fonte_informacao": "URL da fonte"
}}

Para IMPRESSORA:
{{
  "tipo_impressao": "ex: Laser Monocromática",
  "velocidade": "ex: 40 ppm",
  "conectividade": "ex: WiFi, USB, Ethernet",
  "fonte_informacao": "URL da fonte"
}}

Retorne APENAS o JSON com as especificações encontradas.
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                tools=[{
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 3
                }],
                messages=[{"role": "user", "content": search_prompt}]
            )

            # Registrar tokens usados
            if hasattr(response, 'usage'):
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                self.total_tokens_used += total_tokens

                # Registrar log da chamada
                self.call_logs.append(ClaudeCallLog(
                    activity=f"Busca de especificações técnicas na web: {marca} {modelo}",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    prompt=search_prompt
                ))

                logger.info(f"Web search tokens: {total_tokens}")

            # Processar resposta que pode conter tool_use e text
            result_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    result_text += block.text

            if result_text:
                return self._parse_json(result_text)
            return {}

        except Exception as e:
            logger.warning(f"Erro ao buscar specs na web: {e}")
            return {}

    def _build_final_prompt(self, ocr_data: Dict, web_specs: Dict) -> str:
        """Constrói o prompt final combinando OCR + specs da web"""

        specs_info = ""
        if web_specs:
            specs_info = f"""
## ESPECIFICAÇÕES ENCONTRADAS NA WEB:
{json.dumps(web_specs, indent=2, ensure_ascii=False)}

Use estas especificações para criar a query de busca.
"""

        return f"""
# AGENTE: Gerador de Queries para Cotação de Preços

## MISSÃO
Gerar queries otimizadas para buscar **cotações de preços** no Google Shopping, com foco em:
- Encontrar **produtos equivalentes** (mesmas especificações técnicas)
- Queries **curtas e objetivas** (máximo 60 caracteres na principal)
- **Sem marcas específicas** - buscamos preço por especificação

---

## DADOS DO ITEM ANALISADO

### DADOS DO OCR (extraídos da imagem):
- Texto OCR: {ocr_data.get('ocr_completo', 'N/A')}
- Tipo de produto: {ocr_data.get('tipo_produto', 'N/A')}
- Marca: {ocr_data.get('marca', 'N/A')}
- Modelo: {ocr_data.get('modelo', 'N/A')}
- Specs visíveis na imagem: {json.dumps(ocr_data.get('specs_visiveis') or {}, ensure_ascii=False)}
{specs_info}

---

## REGRAS DE GERAÇÃO DE QUERY

### ✅ FAZER (Obrigatório):
1. **Usar especificações técnicas** como base da query (processador, RAM, BTUs, etc.)
2. **Queries curtas**: máximo 60 caracteres na principal
3. **Termos genéricos**: "notebook", "ar condicionado", "impressora" (não marcas)
4. **Specs mais importantes primeiro**: processador > RAM > armazenamento
5. **Gerar alternativas** com variações de termos

### ❌ NÃO FAZER:
1. **Nunca usar marca** na query principal (Dell, HP, Samsung, etc.)
2. **Nunca usar modelo específico** (Inspiron, Vostro, etc.)
3. **Evitar termos vagos**: "bom", "qualidade", "melhor"
4. **Não incluir preço**: "barato", "promoção"

---

## FORMATO DA QUERY

### Estrutura padrão:
`[tipo_produto] [spec1] [spec2] [spec3]`

### Exemplos por categoria:

**NOTEBOOK:**
- ✅ `notebook i5 8gb ssd 256gb`
- ✅ `notebook i7 16gb ssd 512gb 15.6`
- ❌ `notebook dell inspiron 15`

**AR CONDICIONADO:**
- ✅ `ar condicionado split 12000 btus 220v`
- ✅ `ar condicionado inverter 9000 btus`
- ❌ `ar condicionado samsung wind free`

**IMPRESSORA:**
- ✅ `impressora laser monocromatica wifi`
- ✅ `impressora multifuncional colorida duplex`
- ❌ `impressora hp laserjet pro`

**MONITOR:**
- ✅ `monitor 24 full hd ips`
- ✅ `monitor 27 4k 144hz`
- ❌ `monitor lg ultrawide`

---

## RETORNE O JSON FINAL:

{{
  "nome_canonico": "[Tipo] [Marca] [Modelo]",
  "marca": "marca do OCR",
  "modelo": "modelo do OCR",
  "part_number": null,
  "codigo_interno": null,
  "especificacoes_tecnicas": {{
    // TODAS as specs relevantes (OCR + web)
  }},
  "palavras_chave": ["spec1", "spec2", "spec3"],
  "sinonimos": ["termo_alternativo1", "termo_alternativo2"],
  "query_principal": "query curta baseada em specs (max 60 chars)",
  "query_alternativas": [
    "variacao 1 da query",
    "variacao 2 com outros termos"
  ],
  "termos_excluir": ["usado", "peças", "conserto", "defeito", "recondicionado"],
  "observacoes": "texto OCR completo para referência",
  "nivel_confianca": 0.0-1.0
}}

---

## CRITÉRIOS DE CONFIANÇA:
- **0.9-1.0**: Specs claras e completas (processador + RAM + armazenamento)
- **0.7-0.8**: Specs parciais mas identificáveis
- **0.5-0.6**: Apenas tipo e algumas características
- **< 0.5**: Informações insuficientes

Retorne APENAS o JSON válido.
"""

    async def _analyze_text_only(self, input_text: str) -> ItemAnalysisResult:
        """Analisa apenas texto (sem imagem) de forma direta"""
        logger.info("Analisando texto puro (sem imagem)")

        prompt = f'''# AGENTE: Especialista em Pesquisa de Preços para Reavaliação Patrimonial

## CONTEXTO

Você é um especialista em pesquisa de preços de mercado para **reavaliação de bens patrimoniais** de órgãos públicos brasileiros. Sua função é analisar descrições de bens móveis permanentes e gerar queries otimizadas para o **Google Shopping**, buscando o **valor justo de reposição**.

### Base normativa:
- NBC TSP 07 (Ativo Imobilizado)
- MCASP (Manual de Contabilidade Aplicada ao Setor Público)
- Lei 14.133/2021 (Licitações e Contratos)

### Princípio de busca:
> Encontrar o **valor de mercado atual** de bens equivalentes (mesmas especificações funcionais), independente da marca/fabricante original.

---

## DADO DE ENTRADA
```
Descrição do bem: "{input_text}"
```

---

## PROCESSO DE ANÁLISE

### Etapa 1: Identificação do bem
- Extrair tipo/categoria do bem
- Identificar marca e modelo (se presentes)
- Classificar natureza: eletrônico | mobiliário | equipamento | instrumento | veículo

### Etapa 2: Extração de especificações
- Separar especificações **essenciais** (definem equivalência funcional)
- Separar especificações **complementares** (refinam a busca)
- Priorizar atributos conforme categoria:

| Categoria | Especificações prioritárias |
|-----------|----------------------------|
| **Eletrônicos/TI** | processador, memória, armazenamento, tela, conectividade |
| **Mobiliário** | material, dimensões, tipo de uso, capacidade |
| **Equipamentos** | potência, capacidade, voltagem, função |
| **Instrumentos** | tipo, faixa de medição, precisão, certificação |
| **Veículos** | tipo, capacidade, motorização, ano |

### Etapa 3: Construção da query
- Estrutura: `[TIPO] + [SPECS ESSENCIAIS] + [QUALIFICADORES]`
- Limite: 4-8 termos por query
- Usar linguagem de e-commerce (não técnica)
- Abreviações padrão de mercado (gb, cm, pol, w)

---

## REGRAS OBRIGATÓRIAS

| # | Regra | Motivo |
|---|-------|--------|
| 1 | `query_principal` **NUNCA** pode ser vazia | Garantir funcionalidade da busca |
| 2 | Priorizar especificações sobre marca | Encontrar equivalentes de qualquer fabricante |
| 3 | Omitir marca na `query_principal` | Ampliar resultados para valor justo |
| 4 | Incluir marca apenas em `query_com_marca` | Referência de preço do item original |
| 5 | Usar termos comerciais | Melhor indexação no Google Shopping |
| 6 | Buscar sempre bem NOVO | Base para cálculo de valor de reposição |

---

## FORMATO DE SAÍDA

Retorne **APENAS** o JSON abaixo, sem texto adicional:
```json
{{
  "bem_patrimonial": {{
    "nome_canonico": "Descrição padronizada do bem",
    "marca": "marca identificada ou null",
    "modelo": "modelo identificado ou null",
    "categoria": "Eletrônicos | Mobiliário | Equipamentos | Instrumentos | Veículos",
    "natureza": "eletronico | mobiliario | equipamento | instrumento | veiculo"
  }},
  "especificacoes": {{
    "essenciais": {{}},
    "complementares": {{}}
  }},
  "queries": {{
    "principal": "query otimizada SEM marca (OBRIGATÓRIO - nunca vazio)",
    "alternativas": ["variação 1", "variação 2"],
    "com_marca": "query incluindo marca original para referência"
  }},
  "busca": {{
    "palavras_chave": ["termo1", "termo2", "termo3"],
    "termos_excluir": ["usado", "seminovo", "recondicionado", "peças", "conserto", "defeito", "outlet"],
    "ordenacao": "relevancia"
  }},
  "avaliacao": {{
    "confianca": 0.0,
    "completude_dados": "alta | media | baixa",
    "observacoes": "notas relevantes para a reavaliação"
  }}
}}
```

---

## EXEMPLOS

### Entrada 1:
```
"Notebook Dell Inspiron 15, processador Intel Core i5, 8GB RAM, SSD 256GB, tela 15.6 polegadas"
```

### Saída 1:
```json
{{
  "bem_patrimonial": {{
    "nome_canonico": "Notebook Intel Core i5 8GB SSD 256GB 15.6 polegadas",
    "marca": "Dell",
    "modelo": "Inspiron 15",
    "categoria": "Eletrônicos",
    "natureza": "eletronico"
  }},
  "especificacoes": {{
    "essenciais": {{
      "processador": "Intel Core i5",
      "memoria_ram": "8GB",
      "armazenamento": "SSD 256GB",
      "tela": "15.6 polegadas"
    }},
    "complementares": {{}}
  }},
  "queries": {{
    "principal": "notebook i5 8gb ssd 256gb 15.6 polegadas",
    "alternativas": [
      "notebook intel core i5 8gb ssd 256",
      "laptop i5 8gb ram ssd 256gb"
    ],
    "com_marca": "notebook dell inspiron i5 8gb ssd 256gb"
  }},
  "busca": {{
    "palavras_chave": ["notebook", "i5", "8gb", "ssd", "256gb", "15.6"],
    "termos_excluir": ["usado", "seminovo", "recondicionado", "peças", "conserto", "defeito", "outlet"],
    "ordenacao": "relevancia"
  }},
  "avaliacao": {{
    "confianca": 0.95,
    "completude_dados": "alta",
    "observacoes": "Especificações completas permitem busca precisa de equivalentes"
  }}
}}
```

---

### Entrada 2:
```
"Cadeira giratória tipo presidente, couro sintético preto, braços reguláveis, base cromada"
```

### Saída 2:
```json
{{
  "bem_patrimonial": {{
    "nome_canonico": "Cadeira Presidente Giratória Couro Sintético",
    "marca": null,
    "modelo": null,
    "categoria": "Mobiliário",
    "natureza": "mobiliario"
  }},
  "especificacoes": {{
    "essenciais": {{
      "tipo": "presidente",
      "material": "couro sintético",
      "base": "giratória"
    }},
    "complementares": {{
      "cor": "preto",
      "bracos": "reguláveis",
      "acabamento_base": "cromada"
    }}
  }},
  "queries": {{
    "principal": "cadeira presidente giratoria couro sintetico",
    "alternativas": [
      "cadeira escritorio presidente braco regulavel",
      "poltrona executiva giratoria couro"
    ],
    "com_marca": ""
  }},
  "busca": {{
    "palavras_chave": ["cadeira", "presidente", "giratoria", "couro", "sintetico", "escritorio"],
    "termos_excluir": ["usado", "seminovo", "recondicionado", "peças", "conserto", "defeito", "outlet"],
    "ordenacao": "relevancia"
  }},
  "avaliacao": {{
    "confianca": 0.85,
    "completude_dados": "media",
    "observacoes": "Sem marca identificada. Dimensões auxiliariam na precisão"
  }}
}}
```

---

### Entrada 3:
```
"Ar condicionado split 12000 BTUs inverter 220V quente/frio"
```

### Saída 3:
```json
{{
  "bem_patrimonial": {{
    "nome_canonico": "Ar-condicionado Split 12000 BTUs Inverter 220V",
    "marca": null,
    "modelo": null,
    "categoria": "Equipamentos",
    "natureza": "equipamento"
  }},
  "especificacoes": {{
    "essenciais": {{
      "tipo": "split",
      "capacidade": "12000 BTUs",
      "tecnologia": "inverter",
      "voltagem": "220V"
    }},
    "complementares": {{
      "funcao": "quente/frio"
    }}
  }},
  "queries": {{
    "principal": "ar condicionado split 12000 btus inverter 220v",
    "alternativas": [
      "split 12000 btus inverter quente frio",
      "ar condicionado 12000 btus 220v inverter"
    ],
    "com_marca": ""
  }},
  "busca": {{
    "palavras_chave": ["ar condicionado", "split", "12000", "btus", "inverter", "220v"],
    "termos_excluir": ["usado", "seminovo", "recondicionado", "peças", "conserto", "defeito", "outlet", "instalacao"],
    "ordenacao": "relevancia"
  }},
  "avaliacao": {{
    "confianca": 0.92,
    "completude_dados": "alta",
    "observacoes": "Especificações técnicas completas para equivalência"
  }}
}}
```

---

## TRATAMENTO DE DADOS INCOMPLETOS

Se a descrição for insuficiente:

1. **Extrair o máximo possível** da descrição fornecida
2. **Gerar query genérica** baseada no tipo identificado
3. **Indicar baixa confiança** no campo `confianca`
4. **Documentar limitações** em `observacoes`

Exemplo para entrada vaga como `"computador antigo"`:
```json
{{
  "queries": {{
    "principal": "computador desktop",
    "alternativas": ["pc desktop", "computador completo"]
  }},
  "avaliacao": {{
    "confianca": 0.30,
    "completude_dados": "baixa",
    "observacoes": "Descrição insuficiente. Necessário complementar com especificações técnicas (processador, memória, armazenamento)"
  }}
}}
```

---

## INSTRUÇÃO FINAL

Analise a descrição do bem patrimonial fornecida e retorne exclusivamente o JSON conforme formato especificado. A `query_principal` é OBRIGATÓRIA e nunca pode estar vazia.
'''

        response = self._call_with_retry(
            lambda: self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
        )

        # Registrar tokens
        if hasattr(response, 'usage'):
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            self.call_logs.append(ClaudeCallLog(
                activity="Análise de descrição de texto (reavaliação patrimonial)",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=prompt
            ))

            logger.info(f"Text analysis tokens: {total_tokens}")

        response_text = response.content[0].text
        raw_data = self._parse_json(response_text)

        # Transformar novo formato para formato compatível com ItemAnalysisResult
        data = self._transform_patrimonial_response(raw_data)

        # Adicionar total de tokens e logs
        data['total_tokens_used'] = self.total_tokens_used
        data['call_logs'] = [log.dict() for log in self.call_logs]

        return ItemAnalysisResult(**data)

    def _transform_patrimonial_response(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transforma resposta do novo formato patrimonial para formato ItemAnalysisResult"""
        bem = raw_data.get('bem_patrimonial', {})
        specs = raw_data.get('especificacoes', {})
        queries = raw_data.get('queries', {})
        busca = raw_data.get('busca', {})
        avaliacao = raw_data.get('avaliacao', {})

        # Combinar especificações essenciais e complementares
        especificacoes_tecnicas = {}
        especificacoes_tecnicas.update(specs.get('essenciais', {}))
        especificacoes_tecnicas.update(specs.get('complementares', {}))

        # Adicionar categoria e natureza às especificações
        if bem.get('categoria'):
            especificacoes_tecnicas['categoria'] = bem.get('categoria')
        if bem.get('natureza'):
            especificacoes_tecnicas['natureza'] = bem.get('natureza')

        return {
            'nome_canonico': bem.get('nome_canonico', ''),
            'marca': bem.get('marca'),
            'modelo': bem.get('modelo'),
            'part_number': None,
            'codigo_interno': None,
            'especificacoes_tecnicas': especificacoes_tecnicas,
            'palavras_chave': busca.get('palavras_chave', []),
            'sinonimos': [],
            'query_principal': queries.get('principal', ''),
            'query_alternativas': queries.get('alternativas', []),
            'termos_excluir': busca.get('termos_excluir', []),
            'observacoes': avaliacao.get('observacoes', ''),
            'nivel_confianca': avaliacao.get('confianca', 0.0),
            # Campos extras para referência
            'query_com_marca': queries.get('com_marca', ''),
            'completude_dados': avaliacao.get('completude_dados', ''),
        }

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Extrai e parseia JSON de uma string"""
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = text[json_start:json_end]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(f"Erro ao parsear JSON: {json_str[:200]}")
                return {}
        return {}
