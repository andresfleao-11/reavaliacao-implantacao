import openai
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import base64
import json
import logging
import time

logger = logging.getLogger(__name__)


class OpenAICallLog(BaseModel):
    """Log de uma chamada individual ao OpenAI"""
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
    especificacoes_tecnicas: Dict[str, Any] = {}
    palavras_chave: List[str] = []
    sinonimos: List[str] = []
    query_principal: str
    query_alternativas: List[str] = []
    termos_excluir: List[str] = []
    observacoes: Optional[str] = None
    nivel_confianca: float = 0.0
    total_tokens_used: int = 0
    call_logs: List[OpenAICallLog] = []


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.total_tokens_used = 0
        self.call_logs: List[OpenAICallLog] = []

    def _call_with_retry(self, func, max_retries=5):
        """Chama a API com retry exponencial em caso de rate limit ou API sobrecarregada"""
        for attempt in range(max_retries):
            try:
                return func()
            except openai.RateLimitError as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
                logger.warning(f"Rate limit atingido. Aguardando {wait_time}s antes de tentar novamente...")
                time.sleep(wait_time)
            except openai.APIStatusError as e:
                # Tratar erro 529 (overloaded) ou 503 (service unavailable) com retry
                if e.status_code in [529, 503, 502]:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 5 * (attempt + 1)  # 5s, 10s, 15s, 20s, 25s
                    logger.warning(f"API sobrecarregada ({e.status_code}). Aguardando {wait_time}s antes de tentar novamente (tentativa {attempt + 1}/{max_retries})...")
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
        Analisa item em duas etapas (igual ao Claude):
        1. OCR e identificação básica da imagem
        2. Geração de query otimizada para busca
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
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_base64}",
                        "detail": "high"
                    }
                })

        # ETAPA 1: OCR e identificação básica
        ocr_prompt = """# AGENTE: Especialista em OCR para Reavaliação Patrimonial

## CONTEXTO

Você analisa imagens de etiquetas de bens patrimoniais para extrair dados que permitam **pesquisa de preço de reposição** em órgãos públicos brasileiros.

**Base normativa:** NBC TSP 07 | MCASP | Lei 14.133/2021

---

## TAREFA

Analise a imagem e extraia:

### 1. OCR COMPLETO
Transcreva **TODO** o texto visível, literalmente.

### 2. IDENTIFICADORES

| Campo | Descrição | Prioridade |
|-------|-----------|------------|
| **Part Number** | P/N - identifica configuração exata do produto | **CRÍTICA** |
| **Número de série** | S/N, Serial, Service Tag - identificador único | Alta |
| **Marca** | Fabricante | Alta |
| **Modelo** | Código do modelo (usar versão mais completa) | Alta |
| **Tipo** | notebook, ar_condicionado, impressora, monitor, etc. | Alta |

> ⚠️ **MODELO DUPLICADO**: Etiquetas frequentemente mostram o modelo em versão curta e completa. **Sempre usar a string mais longa.**
> Exemplo: "Inspiron 15" e "Inspiron 15 3501-M50P" → usar **"Inspiron 15 3501-M50P"**

### 3. ESPECIFICAÇÕES VISÍVEIS

Extraia **APENAS** o que estiver **VISÍVEL na imagem**:

| Tipo | Specs relevantes |
|------|------------------|
| **Notebook** | Processador (i3/i5/i7, Ryzen), RAM (8GB, 16GB), Armazenamento (SSD/HD), Tela |
| **Ar-condicionado** | BTUs, Ciclo (Frio/Quente-Frio), Tecnologia (Inverter), Voltagem |
| **Impressora** | Tecnologia (Laser/Jato), Funções (Multi/Wifi/Duplex), Velocidade (ppm) |
| **Monitor** | Tamanho, Resolução, Tipo painel |

### 4. IGNORAR (dados de fonte/certificações)
- Input: 19V, 100-240V~, corrente (2.37A)
- Potência fonte: 45W, 65W, 90W
- Certificações: ANATEL, FCC, CE

---

## FORMATO DE SAÍDA

```json
{
  "ocr_completo": "transcrição literal",
  "identificadores": {
    "part_number": "P/N ou null",
    "numero_serie": "S/N ou null",
    "marca": "marca ou null",
    "modelo": "versão mais completa do modelo ou null",
    "tipo_produto": "notebook | ar_condicionado | impressora | monitor | outro"
  },
  "specs_visiveis": {
    "processador": null,
    "ram": null,
    "armazenamento": null,
    "tela": null,
    "btus": null,
    "ciclo": null,
    "voltagem": null,
    "outras": {}
  },
  "tem_specs_relevantes": true | false,
  "pode_consultar_fabricante": true | false,
  "observacoes": "notas relevantes"
}
```

### Critérios:
- `tem_specs_relevantes` = true: Notebook (processador/RAM/armazenamento) | Ar-cond (BTUs) | Impressora (tecnologia)
- `pode_consultar_fabricante` = true: P/N ou S/N identificado **E** marca identificada

---

## EXEMPLOS

### Etiqueta com modelo duplicado
**OCR:** "Dell Inc. | Inspiron 15 | Model: Inspiron 15 3501-M50P | P/N: i3501-5081BLK | S/N: 7XK9M33"

```json
{
  "ocr_completo": "Dell Inc. Inspiron 15 Model: Inspiron 15 3501-M50P P/N: i3501-5081BLK S/N: 7XK9M33",
  "identificadores": {
    "part_number": "i3501-5081BLK",
    "numero_serie": "7XK9M33",
    "marca": "Dell",
    "modelo": "Inspiron 15 3501-M50P",
    "tipo_produto": "notebook"
  },
  "specs_visiveis": {
    "processador": null, "ram": null, "armazenamento": null, "tela": null,
    "btus": null, "ciclo": null, "voltagem": null, "outras": {}
  },
  "tem_specs_relevantes": false,
  "pode_consultar_fabricante": true,
  "observacoes": "Modelo aparece 2x na etiqueta. Selecionada versão completa (3501-M50P). P/N permite consulta direta de specs."
}
```

### Ar-condicionado
**OCR:** "LG | S4-Q12JA3AD | 12000 BTU/h | Inverter | 220V | S/N: 203TAZZ0K789"

```json
{
  "ocr_completo": "LG S4-Q12JA3AD 12000 BTU/h Inverter 220V S/N: 203TAZZ0K789",
  "identificadores": {
    "part_number": null,
    "numero_serie": "203TAZZ0K789",
    "marca": "LG",
    "modelo": "S4-Q12JA3AD",
    "tipo_produto": "ar_condicionado"
  },
  "specs_visiveis": {
    "processador": null, "ram": null, "armazenamento": null, "tela": null,
    "btus": "12000", "ciclo": null, "voltagem": "220V",
    "outras": { "tecnologia": "Inverter" }
  },
  "tem_specs_relevantes": true,
  "pode_consultar_fabricante": true,
  "observacoes": "Specs completas para cotação disponíveis na etiqueta."
}
```

### Etiqueta de FONTE (não usar)
**OCR:** "AC Adapter | Input: 100-240V~ | Output: 19V 2.37A 45W | Model: ADP-45BW"

```json
{
  "ocr_completo": "AC Adapter Input: 100-240V~ Output: 19V 2.37A 45W Model: ADP-45BW",
  "identificadores": {
    "part_number": null,
    "numero_serie": null,
    "marca": null,
    "modelo": "ADP-45BW",
    "tipo_produto": "fonte_alimentacao"
  },
  "specs_visiveis": {
    "processador": null, "ram": null, "armazenamento": null, "tela": null,
    "btus": null, "ciclo": null, "voltagem": null,
    "outras": { "potencia_saida": "45W" }
  },
  "tem_specs_relevantes": false,
  "pode_consultar_fabricante": false,
  "observacoes": "ATENÇÃO: Etiqueta da FONTE, não do equipamento. Não usar para cotação."
}
```

---

## INSTRUÇÃO FINAL

1. Extraia todo texto visível
2. Se modelo aparecer duplicado, **usar a string mais longa/completa**
3. Priorize **Part Number** (identifica configuração exata)
4. Classifique corretamente: equipamento vs. fonte/acessório
5. Retorne **APENAS o JSON**
"""

        content.insert(0, {"type": "text", "text": ocr_prompt})

        logger.info(f"Etapa 1: OCR e identificação básica com {self.model}")
        ocr_response = self._call_with_retry(
            lambda: self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=1500,
                messages=[{"role": "user", "content": content}]
            )
        )

        # Registrar tokens usados
        if hasattr(ocr_response, 'usage'):
            input_tokens = ocr_response.usage.prompt_tokens
            output_tokens = ocr_response.usage.completion_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            self.call_logs.append(OpenAICallLog(
                activity=f"OCR e identificação básica da imagem",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=ocr_prompt
            ))

            logger.info(f"OCR tokens: {total_tokens}")

        ocr_text = ocr_response.choices[0].message.content
        ocr_data = self._parse_json(ocr_text)

        # Extrair identificadores (novo formato com objeto aninhado)
        identificadores = ocr_data.get('identificadores', {})
        tipo_produto = identificadores.get('tipo_produto') or ocr_data.get('tipo_produto')
        marca = identificadores.get('marca') or ocr_data.get('marca')
        modelo = identificadores.get('modelo') or ocr_data.get('modelo')
        numero_serie = identificadores.get('numero_serie')
        part_number = identificadores.get('part_number')

        # Normalizar para formato plano (compatibilidade)
        ocr_data['tipo_produto'] = tipo_produto
        ocr_data['marca'] = marca
        ocr_data['modelo'] = modelo
        ocr_data['numero_serie'] = numero_serie
        ocr_data['part_number'] = part_number

        logger.info(f"OCR resultado: tipo={tipo_produto}, marca={marca}, modelo={modelo}, S/N={numero_serie}")
        logger.info(f"Tem specs relevantes: {ocr_data.get('tem_specs_relevantes')}, Pode consultar fabricante: {ocr_data.get('pode_consultar_fabricante')}")

        # ETAPA 2: Gerar resultado final com query otimizada
        final_prompt = self._build_final_prompt(ocr_data)

        logger.info(f"Etapa 2: Gerando análise final com {self.model}")
        final_response = self._call_with_retry(
            lambda: self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=2000,
                messages=[{"role": "user", "content": final_prompt}]
            )
        )

        # Registrar tokens usados
        if hasattr(final_response, 'usage'):
            input_tokens = final_response.usage.prompt_tokens
            output_tokens = final_response.usage.completion_tokens
            total_tokens = input_tokens + output_tokens
            self.total_tokens_used += total_tokens

            self.call_logs.append(OpenAICallLog(
                activity=f"Análise final e geração de query de busca",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=final_prompt
            ))

            logger.info(f"Final analysis tokens: {total_tokens}")

        response_text = final_response.choices[0].message.content
        data = self._parse_json(response_text)

        # Adicionar total de tokens e logs ao resultado
        data['total_tokens_used'] = self.total_tokens_used
        data['call_logs'] = [log.dict() for log in self.call_logs]

        return ItemAnalysisResult(**data)

    def _build_final_prompt(self, ocr_data: Dict) -> str:
        """Constrói o prompt final para geração de query (igual ao Claude)"""

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
- Número de série: {ocr_data.get('numero_serie', 'N/A')}
- Part Number: {ocr_data.get('part_number', 'N/A')}
- Specs visíveis na imagem: {json.dumps(ocr_data.get('specs_visiveis') or {}, ensure_ascii=False)}
- Tem specs relevantes: {ocr_data.get('tem_specs_relevantes', False)}
- Pode consultar fabricante: {ocr_data.get('pode_consultar_fabricante', False)}

---

## REGRAS DE GERAÇÃO DE QUERY

### ✅ FAZER (Obrigatório):
1. **Usar especificações técnicas** como base da query (processador, RAM, BTUs, etc.)
2. **Queries curtas**: máximo 60 caracteres na principal
3. **Termos genéricos**: "notebook", "ar condicionado", "impressora" (não marcas)
4. **Specs mais importantes primeiro**: processador > RAM > armazenamento
5. **Gerar alternativas** com variações de termos

### ❌ NÃO FAZER:
1. **Nunca usar marca** na query principal (Dell, HP, Samsung, etc.) - EXCETO quando não há specs
2. **Nunca usar modelo específico** (Inspiron, Vostro, etc.) - EXCETO quando não há specs
3. **Evitar termos vagos**: "bom", "qualidade", "melhor"
4. **Não incluir preço**: "barato", "promoção"
5. **NUNCA incluir voltagem, corrente ou potência de fonte** (19V, 2.37A, 45W)
6. **NUNCA incluir chip WiFi** (RTL8821CE)
7. **NUNCA incluir certificações** (ANATEL, FCC, CE)

### 🔴 REGRA ESPECIAL - SEM SPECS RELEVANTES:
Se tem_specs_relevantes = false (não encontrou processador/RAM/SSD na imagem):
- Use APENAS: "notebook [marca] [modelo]" ou "[tipo_produto] [marca] [modelo]"
- Exemplo: "notebook ASUS M1502Y"

---

## FORMATO DA QUERY

### Estrutura padrão:
`[tipo_produto] [spec1] [spec2] [spec3]`

### Exemplos por categoria:

**NOTEBOOK (com specs):**
- ✅ `notebook i5 8gb ssd 256gb`
- ✅ `notebook i7 16gb ssd 512gb 15.6`
- ✅ `notebook ryzen 7 8gb ssd 512gb`
- ❌ `notebook dell inspiron 15`
- ❌ `notebook 19V 2.37A 45W` (NUNCA!)
- ❌ `notebook RTL8821CE` (NUNCA!)

**NOTEBOOK (sem specs - usar marca/modelo):**
- ✅ `notebook ASUS M1502Y`
- ✅ `notebook Lenovo IdeaPad 3`
- ❌ `notebook ASUS M1502Y 19V 2.37A 45W` (NUNCA!)

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
    // APENAS specs RELEVANTES (processador, RAM, SSD, BTUs)
    // NUNCA incluir: voltagem, corrente, potência, WiFi chip, certificações
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
        logger.info(f"Analisando texto puro com {self.model}")

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
            lambda: self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
        )

        # Registrar tokens
        if hasattr(response, 'usage'):
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            self.total_tokens_used += total_tokens

            self.call_logs.append(OpenAICallLog(
                activity="Análise de descrição de texto (reavaliação patrimonial)",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                prompt=prompt
            ))

            logger.info(f"OpenAI text analysis tokens: {total_tokens}")

        response_text = response.choices[0].message.content
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
