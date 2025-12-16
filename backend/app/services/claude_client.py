import anthropic
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import base64
import json
import logging
import time
from app.services.prompts import PROMPT_ANALISE_PATRIMONIAL

logger = logging.getLogger(__name__)


class ClaudeCallLog(BaseModel):
    """Log de uma chamada individual ao Claude"""
    activity: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    prompt: Optional[str] = None  # Prompt enviado para a IA


class FipeApiParams(BaseModel):
    """Parâmetros para consulta na API FIPE"""
    vehicle_type: Optional[str] = None  # cars | motorcycles | trucks
    codigo_fipe: Optional[str] = None
    busca_marca: Optional[Dict[str, Any]] = None
    busca_modelo: Optional[Dict[str, Any]] = None
    year_id_estimado: Optional[str] = None
    fluxo_recomendado: Optional[str] = None  # por_hierarquia | por_codigo_fipe
    endpoints: Optional[Dict[str, str]] = None


class ItemAnalysisResult(BaseModel):
    # Tipo de processamento: FIPE para veículos, GOOGLE_SHOPPING para demais
    tipo_processamento: str = "GOOGLE_SHOPPING"  # FIPE | GOOGLE_SHOPPING

    # Dados do bem
    nome_canonico: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    categoria: Optional[str] = None  # Veículos, Eletrônicos, Mobiliário, etc.
    natureza: Optional[str] = None  # veiculo_carro, veiculo_moto, veiculo_caminhao, eletronico, etc.

    # Campos legados (mantidos para compatibilidade)
    part_number: Optional[str] = None
    codigo_interno: Optional[str] = None
    especificacoes_tecnicas: Dict[str, Any] = {}  # Especificações técnicas extraídas
    palavras_chave: List[str] = []
    sinonimos: List[str] = []
    query_principal: str = ""  # Query baseada nas especificações técnicas
    query_alternativas: List[str] = []
    termos_excluir: List[str] = []
    observacoes: Optional[str] = None
    nivel_confianca: float = 0.0

    # Campos para API FIPE (veículos)
    fipe_api: Optional[FipeApiParams] = None
    fallback_google_shopping: Optional[Dict[str, Any]] = None
    dados_faltantes: List[str] = []
    especificacoes: Dict[str, Any] = {}  # Especificações no formato {essenciais: {}, complementares: {}}

    # Metadados
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

        # Extrair identificadores (novo formato com objeto identificadores)
        identificadores = ocr_data.get('identificadores', {})
        tipo_produto = identificadores.get('tipo_produto') or ocr_data.get('tipo_produto')
        marca = identificadores.get('marca') or ocr_data.get('marca')
        modelo = identificadores.get('modelo') or ocr_data.get('modelo')
        numero_serie = identificadores.get('numero_serie')
        part_number = identificadores.get('part_number')

        # Normalizar ocr_data para manter compatibilidade
        ocr_data['tipo_produto'] = tipo_produto
        ocr_data['marca'] = marca
        ocr_data['modelo'] = modelo
        ocr_data['numero_serie'] = numero_serie
        ocr_data['part_number'] = part_number

        logger.info(f"OCR resultado: tipo={tipo_produto}, marca={marca}, modelo={modelo}, S/N={numero_serie}")
        logger.info(f"Tem specs relevantes: {ocr_data.get('tem_specs_relevantes')}, Pode consultar fabricante: {ocr_data.get('pode_consultar_fabricante')}")

        # ETAPA 2: Busca web se necessário (specs não visíveis na imagem)
        specs_from_web = {}
        if not ocr_data.get('tem_specs_relevantes', False) and marca and modelo:
            tipo = tipo_produto or 'produto'

            logger.info(f"Etapa 2: Buscando specs na web para {marca} {modelo} (S/N: {numero_serie}, P/N: {part_number})")
            specs_from_web = await self._search_specs_on_web(marca, modelo, tipo, numero_serie, part_number)
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

    async def _search_specs_on_web(self, marca: str, modelo: str, tipo: str, numero_serie: Optional[str] = None, part_number: Optional[str] = None) -> Dict[str, Any]:
        """Busca especificações técnicas na web usando web_search do Claude"""

        search_prompt = f"""# AGENTE: Especialista em Pesquisa de Especificações Técnicas para Reavaliação Patrimonial

## CONTEXTO

Você pesquisa especificações técnicas de bens patrimoniais para subsidiar **cotação de preços de reposição** em órgãos públicos brasileiros.

**Base normativa:** NBC TSP 07 | MCASP | Lei 14.133/2021

---

## DADOS DE ENTRADA

```
Marca: {marca}
Modelo: {modelo}
Tipo: {tipo}
Part Number: {part_number or 'null'}  // pode ser null
Número de Série: {numero_serie or 'null'}  // pode ser null
```

---

## ESTRATÉGIA DE BUSCA (usar `web_search`)

| Prioridade | Estratégia | Query |
|------------|------------|-------|
| **1ª** | Marca + Modelo | `"{marca}" "{modelo}" ficha técnica especificações` |
| **2ª** | Part Number + Marca | `"{marca}" "{part_number}" especificações` |
| **3ª** | S/N + Marca (suporte) | `"{marca}" suporte "{numero_serie}"` |
| **4ª** | Modelo genérico | `"{modelo}" specs datasheet` |

> **Marca + Modelo** é a busca mais direta e comum.
> **Part Number** refina para configuração exata quando o modelo tem variantes.
> **Número de série** permite consulta ao suporte do fabricante.

### Fontes prioritárias:
1. Site oficial do fabricante
2. Lojas especializadas (Kabum, Pichau, Fast Shop)
3. Reviews técnicos

### Evitar: Mercado Livre, OLX, fóruns

---

## ESPECIFICAÇÕES POR TIPO

| Tipo | Specs críticas | Specs complementares |
|------|----------------|---------------------|
| **Notebook** | Processador, RAM, Armazenamento | Tela, Placa vídeo, SO |
| **Ar-condicionado** | BTUs, Tecnologia (Inverter), Ciclo | Tensão, Selo Procel |
| **Impressora** | Tecnologia (Laser/Jato), Funções | Velocidade, Conectividade, Duplex |
| **Monitor** | Tamanho, Resolução | Painel, Taxa Hz, Conectores |

---

## FORMATO DE SAÍDA

```json
{{{{
  "tipo_produto": "notebook | ar_condicionado | impressora | monitor",
  "identificacao": {{{{
    "marca": "string",
    "modelo": "string",
    "part_number": "string ou null"
  }}}},
  "especificacoes": {{{{
    "// campos conforme tipo do produto": "valores encontrados ou null"
  }}}},
  "fonte": {{{{
    "url": "URL da fonte",
    "tipo": "fabricante | loja | review",
    "confiabilidade": "alta | media | baixa"
  }}}},
  "observacoes": "notas relevantes"
}}}}
```

### Specs por tipo:

**Notebook:**
```json
"especificacoes": {{{{
  "processador": "Intel Core i5-1135G7",
  "geracao": "11ª geração",
  "ram": "8GB DDR4",
  "armazenamento": "SSD 256GB NVMe",
  "tela": "15.6\\" Full HD",
  "placa_video": "Integrada ou modelo",
  "sistema_operacional": "Windows 11"
}}}}
```

**Ar-condicionado:**
```json
"especificacoes": {{{{
  "capacidade_btus": "12000",
  "tecnologia": "Inverter | Convencional",
  "ciclo": "Frio | Quente/Frio",
  "tensao": "220V",
  "classificacao_energetica": "A"
}}}}
```

**Impressora:**
```json
"especificacoes": {{{{
  "tecnologia": "Laser Mono | Laser Color | Jato de Tinta",
  "funcoes": "Impressora | Multifuncional",
  "velocidade_ppm": "40",
  "conectividade": ["WiFi", "USB", "Ethernet"],
  "duplex": "Automático | Manual"
}}}}
```

**Monitor:**
```json
"especificacoes": {{{{
  "tamanho": "24\\"",
  "resolucao": "1920x1080",
  "tipo_painel": "IPS | VA | TN",
  "taxa_atualizacao": "60Hz",
  "conectores": ["HDMI", "VGA"]
}}}}
```

### Se não encontrar:
```json
{{{{
  "tipo_produto": "{tipo}",
  "identificacao": {{{{ "marca": "{marca}", "modelo": "{modelo}", "part_number": null }}}},
  "especificacoes": null,
  "fonte": null,
  "erro": "Especificações não encontradas",
  "tentativas": ["query 1", "query 2"],
  "sugestao": "alternativa para busca manual"
}}}}
```

---

## REGRAS

1. Usar `web_search` na ordem de prioridade
2. **Marca + Modelo primeiro** - busca mais direta
3. Usar **Part Number** para refinar quando houver variantes
4. Validar specs conflitantes: fabricante > loja > review
5. **Não inventar dados** - retornar `null` se não encontrar
6. Sempre documentar a fonte (URL)

---

## EXEMPLO

**Entrada:**
```
Marca: Dell | Modelo: Inspiron 15 3501 | Tipo: notebook
Part Number: i3501-5081BLK | Número de Série: 7XK9M33
```

**Ação:** `web_search("Dell Inspiron 15 3501 ficha técnica especificações")`

**Saída:**
```json
{{{{
  "tipo_produto": "notebook",
  "identificacao": {{{{
    "marca": "Dell",
    "modelo": "Inspiron 15 3501",
    "part_number": "i3501-5081BLK"
  }}}},
  "especificacoes": {{{{
    "processador": "Intel Core i5-1135G7",
    "geracao": "11ª geração",
    "ram": "8GB DDR4 2666MHz",
    "armazenamento": "SSD 256GB PCIe NVMe",
    "tela": "15.6\\" Full HD (1920x1080)",
    "placa_video": "Intel Iris Xe (integrada)",
    "sistema_operacional": "Windows 11 Home"
  }}}},
  "fonte": {{{{
    "url": "https://www.dell.com/pt-br/shop/notebooks/inspiron-15/spd/inspiron-15-3501-laptop",
    "tipo": "fabricante",
    "confiabilidade": "alta"
  }}}},
  "observacoes": "Modelo possui variantes (i3/i5/i7). Part Number i3501-5081BLK confirma configuração i5/8GB/256GB."
}}}}
```

---

## INSTRUÇÃO FINAL

1. Execute `web_search` priorizando **Marca + Modelo**
2. Use **Part Number** para refinar se houver variantes
3. Extraia specs de fontes confiáveis
4. Retorne **APENAS o JSON**
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
        """Analisa apenas texto (sem imagem) de forma direta.
        Suporta veículos (retorna dados para API FIPE) e bens gerais (Google Shopping).
        """
        logger.info("Analisando texto puro (sem imagem)")

        # Usar o prompt do arquivo de templates
        prompt = PROMPT_ANALISE_PATRIMONIAL.replace("{input_text}", input_text)

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
        """Transforma resposta do formato patrimonial para formato ItemAnalysisResult.
        Suporta tanto veículos (FIPE) quanto bens gerais (Google Shopping).
        """
        tipo_processamento = raw_data.get('tipo_processamento', 'GOOGLE_SHOPPING')
        bem = raw_data.get('bem_patrimonial', {})
        specs = raw_data.get('especificacoes', {})
        avaliacao = raw_data.get('avaliacao', {})

        # Combinar especificações essenciais e complementares
        especificacoes_tecnicas = {}
        especificacoes_tecnicas.update(specs.get('essenciais', {}))
        especificacoes_tecnicas.update(specs.get('complementares', {}))

        # Base result
        result = {
            'tipo_processamento': tipo_processamento,
            'nome_canonico': bem.get('nome_canonico', ''),
            'marca': bem.get('marca'),
            'modelo': bem.get('modelo'),
            'categoria': bem.get('categoria'),
            'natureza': bem.get('natureza'),
            'part_number': None,
            'codigo_interno': None,
            'especificacoes_tecnicas': especificacoes_tecnicas,
            'especificacoes': specs,  # Manter formato original {essenciais: {}, complementares: {}}
            'observacoes': avaliacao.get('observacoes', ''),
            'nivel_confianca': avaliacao.get('confianca', 0.0),
            'dados_faltantes': avaliacao.get('dados_faltantes', []),
        }

        # Processar conforme tipo
        if tipo_processamento == 'FIPE':
            # Veículo - dados para API FIPE
            fipe_api_data = raw_data.get('fipe_api', {})
            result['fipe_api'] = FipeApiParams(
                vehicle_type=fipe_api_data.get('vehicle_type'),
                codigo_fipe=fipe_api_data.get('codigo_fipe'),
                busca_marca=fipe_api_data.get('busca_marca'),
                busca_modelo=fipe_api_data.get('busca_modelo'),
                year_id_estimado=fipe_api_data.get('year_id_estimado'),
                fluxo_recomendado=fipe_api_data.get('fluxo_recomendado'),
                endpoints=fipe_api_data.get('endpoints')
            )
            result['fallback_google_shopping'] = raw_data.get('fallback_google_shopping', {})

            # Query principal vazia para veículos (usa FIPE)
            result['query_principal'] = ''
            result['query_alternativas'] = []
            result['palavras_chave'] = []
            result['termos_excluir'] = []
            result['sinonimos'] = []
        else:
            # Bem geral - dados para Google Shopping
            queries = raw_data.get('queries', {})
            busca = raw_data.get('busca', {})

            result['query_principal'] = queries.get('principal', '')
            result['query_alternativas'] = queries.get('alternativas', [])
            result['palavras_chave'] = busca.get('palavras_chave', [])
            result['termos_excluir'] = busca.get('termos_excluir', [])
            result['sinonimos'] = []
            result['fipe_api'] = None
            result['fallback_google_shopping'] = None

        return result

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
