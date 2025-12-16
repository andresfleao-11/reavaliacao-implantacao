"""
Servico para captura de screenshot do site oficial da FIPE.

REQ-FIPE-002: Screenshot de Comprovacao da Consulta FIPE

Versao Robusta - Baseada na analise da estrutura real do site veiculos.fipe.org.br
Utiliza multiplos seletores CSS e XPath com fallbacks para maior confiabilidade.
"""

import asyncio
from playwright.async_api import async_playwright, Browser, Playwright, Page, TimeoutError as PlaywrightTimeout
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging
import os
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)


class TipoVeiculo(Enum):
    """Tipos de veiculos disponiveis na FIPE"""
    CARRO = "cars"
    MOTO = "motorcycles"
    CAMINHAO = "trucks"


@dataclass
class ResultadoScreenshot:
    """Estrutura de dados para resultado da captura"""
    screenshot_path: Optional[str]
    sucesso: bool
    dados_extraidos: Dict[str, str]
    erro: Optional[str] = None


class FipeScreenshotService:
    """
    Servico robusto para captura de screenshot do site oficial FIPE.

    Desenvolvido com base na analise da estrutura real do site,
    incluindo multiplos seletores de fallback para maior confiabilidade.
    """

    URL_BASE = "https://veiculos.fipe.org.br/"

    # Mapeamento de tipo de veiculo para seletores de accordion
    VEHICLE_TYPE_SELECTORS = {
        TipoVeiculo.CARRO: [
            "//li[contains(@class, 'lista')]//a[contains(text(), 'Consulta de Carros')]",
            "a:has-text('Consulta de Carros e Utilitários')",
            ".lista a:has-text('Carros')",
            "text=Carros e utilitários pequenos",
        ],
        TipoVeiculo.MOTO: [
            "//li[contains(@class, 'lista')]//a[contains(text(), 'Consulta de Motos')]",
            "a:has-text('Consulta de Motos')",
            ".lista a:has-text('Motos')",
            "text=Motos",
        ],
        TipoVeiculo.CAMINHAO: [
            "//li[contains(@class, 'lista')]//a[contains(text(), 'Caminhões')]",
            "a:has-text('Consulta de Caminhões')",
            ".lista a:has-text('Caminhões')",
            "text=Caminhões e micro-ônibus",
        ],
    }

    # Mapeamento de combustivel para sufixo no select
    FUEL_MAP = {
        "Gasolina": "Gasolina",
        "Flex": "Gasolina",  # FIPE mostra Flex como Gasolina no select
        "Diesel": "Diesel",
        "Alcool": "Álcool",
        "Álcool": "Álcool",
        "Eletrico": "Elétrico",
        "Elétrico": "Elétrico",
        "G": "Gasolina",
        "D": "Diesel",
        "A": "Álcool",
        "E": "Elétrico",
    }

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        slow_mo: int = 150
    ):
        self.headless = headless
        self.timeout = timeout
        self.slow_mo = slow_mo
        self.browser: Optional[Browser] = None
        self.playwright: Optional[Playwright] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self._iniciar_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._fechar_browser()

    async def _iniciar_browser(self):
        """Inicia o browser com configuracoes otimizadas"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
            ]
        )

        # Cria contexto com User-Agent realista
        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
        )

        self.page = await context.new_page()
        self.page.set_default_timeout(self.timeout)

    async def _fechar_browser(self):
        """Fecha o browser e libera recursos"""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def _aguardar_carregamento(self, tempo_extra: float = 0.5):
        """Aguarda carregamento completo da pagina"""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        await asyncio.sleep(tempo_extra)

    async def _clicar_com_retry(
        self,
        seletores: List[str],
        descricao: str,
        max_tentativas: int = 3
    ) -> bool:
        """
        Tenta clicar em um elemento usando multiplos seletores.

        Args:
            seletores: Lista de seletores CSS/XPath para tentar
            descricao: Descricao do elemento para logs
            max_tentativas: Numero de tentativas por seletor

        Returns:
            True se conseguiu clicar, False caso contrario
        """
        for seletor in seletores:
            for tentativa in range(max_tentativas):
                try:
                    # Determina se e XPath ou CSS
                    if seletor.startswith("//") or seletor.startswith("xpath="):
                        seletor_formatado = f"xpath={seletor}" if not seletor.startswith("xpath=") else seletor
                    else:
                        seletor_formatado = seletor

                    elemento = await self.page.wait_for_selector(
                        seletor_formatado,
                        state="visible",
                        timeout=5000
                    )

                    if elemento:
                        await elemento.click()
                        await asyncio.sleep(0.3)
                        logger.info(f"[FIPE-SCREENSHOT] Clicou em '{descricao}' com seletor: {seletor[:50]}")
                        return True

                except Exception as e:
                    await asyncio.sleep(0.5)
                    continue

        logger.warning(f"[FIPE-SCREENSHOT] Nao conseguiu clicar em '{descricao}'")
        return False

    async def _selecionar_tipo_veiculo(self, tipo: TipoVeiculo):
        """Expande o accordion do tipo de veiculo selecionado"""
        seletores = self.VEHICLE_TYPE_SELECTORS.get(tipo, self.VEHICLE_TYPE_SELECTORS[TipoVeiculo.CARRO])

        sucesso = await self._clicar_com_retry(seletores, f"Tipo: {tipo.value}")
        if not sucesso:
            raise Exception(f"Nao foi possivel selecionar tipo de veiculo: {tipo.value}")

        await self._aguardar_carregamento()

    async def _selecionar_aba_codigo_fipe(self):
        """Seleciona a aba de pesquisa por codigo FIPE"""
        seletores = [
            "//a[contains(text(), 'código Fipe')]",
            "//a[contains(text(), 'Código Fipe')]",
            "//a[contains(text(), 'codigo Fipe')]",
            "a:has-text('código Fipe')",
            "a:has-text('Código Fipe')",
            ".abas a:nth-child(2)",
            "//ul[contains(@class, 'abas')]//a[2]",
            "text=Pesquisa por código Fipe",
            "text=Pesquisa por Código FIPE",
        ]

        sucesso = await self._clicar_com_retry(seletores, "Aba Codigo FIPE")
        if not sucesso:
            raise Exception("Nao foi possivel selecionar aba de pesquisa por codigo FIPE")

        await self._aguardar_carregamento(1.0)

    async def _preencher_codigo_fipe(self, codigo: str):
        """Preenche o campo de codigo FIPE"""
        # Seletores especificos para o campo de codigo FIPE (baseado no ID real do site)
        seletores_input = [
            "#selectCodigocarroCodigoFipe",  # ID real do campo para carros
            "#selectCodigocaminhaoCodigoFipe",  # ID para caminhoes
            "#selectCodigomotoCodigoFipe",  # ID para motos
            "input[placeholder*='código']",
            "input[placeholder*='Código']",
            "input[placeholder*='codigo']",
            "input[placeholder*='FIPE']",
            "input[id*='codigoFipe']",
            "input[id*='CodigoFipe']",
            "input[id*='Codigo'][id*='Fipe']",
            "input[name*='codigo']",
            "//input[contains(@placeholder, 'Código') or contains(@placeholder, 'código')]",
            ".pesquisa-codigo input[type='text']",
            "#codigoFipe",
            "#selectCodigoModelo",
        ]

        campo_encontrado = None

        for seletor in seletores_input:
            try:
                if seletor.startswith("//"):
                    seletor_formatado = f"xpath={seletor}"
                else:
                    seletor_formatado = seletor

                campo = await self.page.wait_for_selector(
                    seletor_formatado,
                    state="visible",
                    timeout=3000
                )

                if campo:
                    campo_encontrado = campo
                    logger.info(f"[FIPE-SCREENSHOT] Campo codigo encontrado: {seletor[:50]}")
                    break

            except:
                continue

        if not campo_encontrado:
            raise Exception("Campo de codigo FIPE nao encontrado")

        # Limpa e preenche o campo
        await campo_encontrado.click()
        await campo_encontrado.fill("")
        await campo_encontrado.type(codigo, delay=50)

        logger.info(f"[FIPE-SCREENSHOT] Codigo FIPE preenchido: {codigo}")

        # IMPORTANTE: Disparar eventos change/blur para acionar o AJAX que popula o dropdown de anos
        logger.info("[FIPE-SCREENSHOT] Disparando eventos change/blur para carregar dropdown...")
        await campo_encontrado.dispatch_event("change")
        await campo_encontrado.dispatch_event("blur")

        # Aguarda carregamento do dropdown de anos (AJAX)
        await asyncio.sleep(3)

        # Aguarda networkidle para garantir que AJAX completou
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass

        await asyncio.sleep(1)

    async def _selecionar_ano_modelo(self, ano_modelo: int, combustivel: str, max_retries: int = 3):
        """Seleciona o ano/modelo no dropdown com retry"""
        # Mapear combustivel
        fuel_suffix = self.FUEL_MAP.get(combustivel, "Gasolina")
        ano_combustivel = f"{ano_modelo} {fuel_suffix}"

        # Seletores especificos para o dropdown de ano/modelo do site FIPE
        # IMPORTANTE: estes selects sao HIDDEN (nao visiveis) mas funcionais via jQuery UI
        seletores_select = [
            "#selectCodigoAnocarroCodigoFipe",  # ID real para carros (pesquisa por codigo)
            "#selectCodigoAnocaminhaoCodigoFipe",  # ID para caminhoes
            "#selectCodigoAnomotoCodigoFipe",  # ID para motos
            "select[id*='CodigoAno'][id*='CodigoFipe']",  # Padrao generico
            "select[id*='AnoModelo']",
            "select[id*='anoModelo']",
            "#selectAnoModelo",
            "select[name*='ano']",
            "//select[contains(@id, 'CodigoAno')]",
            "//select[contains(@id, 'Ano')]",
        ]

        select_encontrado = None

        # Tenta multiplas vezes esperando o dropdown carregar
        for retry in range(max_retries):
            logger.info(f"[FIPE-SCREENSHOT] Tentativa {retry + 1}/{max_retries} para encontrar select de ano")

            for seletor in seletores_select:
                try:
                    if seletor.startswith("//"):
                        seletor_formatado = f"xpath={seletor}"
                    else:
                        seletor_formatado = seletor

                    # IMPORTANTE: Nao usar state="visible" pois os selects sao hidden
                    select = await self.page.wait_for_selector(
                        seletor_formatado,
                        state="attached",  # Apenas verificar se esta no DOM
                        timeout=3000
                    )

                    if select:
                        # Verifica se tem opcoes
                        opcoes = await select.query_selector_all("option")
                        qtd_opcoes = len(opcoes)
                        logger.info(f"[FIPE-SCREENSHOT] Select encontrado ({seletor[:40]}) com {qtd_opcoes} opcoes")

                        if qtd_opcoes > 1:
                            select_encontrado = select
                            logger.info(f"[FIPE-SCREENSHOT] Select ano encontrado com {qtd_opcoes} opcoes validas")
                            break

                except Exception as e:
                    continue

            if select_encontrado:
                break

            # Se nao encontrou, aguarda mais e tenta novamente
            logger.info(f"[FIPE-SCREENSHOT] Select nao encontrado na tentativa {retry + 1}, aguardando...")
            await asyncio.sleep(2)

            # Tenta forcar reload do dropdown disparando eventos novamente
            if retry == 1:
                try:
                    campo_codigo = await self.page.query_selector("#selectCodigocarroCodigoFipe, input[placeholder*='código']")
                    if campo_codigo:
                        await campo_codigo.dispatch_event("change")
                        await campo_codigo.dispatch_event("blur")
                        await asyncio.sleep(2)
                except:
                    pass

        if not select_encontrado:
            # Log do HTML da pagina para debug
            try:
                selects_na_pagina = await self.page.query_selector_all("select")
                logger.warning(f"[FIPE-SCREENSHOT] Total de selects na pagina: {len(selects_na_pagina)}")
                for i, sel in enumerate(selects_na_pagina[:8]):
                    sel_id = await sel.get_attribute("id")
                    sel_name = await sel.get_attribute("name")
                    opts = await sel.query_selector_all("option")
                    logger.warning(f"[FIPE-SCREENSHOT] Select {i}: id={sel_id}, name={sel_name}, opcoes={len(opts)}")
            except:
                pass
            raise Exception("Select de ano/modelo nao encontrado ou sem opcoes")

        # Obtem todas as opcoes
        opcoes = await select_encontrado.query_selector_all("option")

        opcao_valor = None
        opcoes_disponiveis = []

        for opcao in opcoes:
            texto = await opcao.text_content()
            valor = await opcao.get_attribute("value")

            if texto and texto.strip():
                texto_limpo = texto.strip()
                opcoes_disponiveis.append(texto_limpo)

                # Verifica match parcial
                if ano_combustivel.lower() in texto_limpo.lower():
                    opcao_valor = valor
                    logger.info(f"[FIPE-SCREENSHOT] Opcao encontrada (match exato): {texto_limpo}")
                    break

                # Tenta match so com ano
                if str(ano_modelo) in texto_limpo and not opcao_valor:
                    opcao_valor = valor
                    logger.info(f"[FIPE-SCREENSHOT] Opcao encontrada (match ano): {texto_limpo}")

        if not opcao_valor:
            logger.warning(f"[FIPE-SCREENSHOT] Ano '{ano_combustivel}' nao encontrado. Opcoes: {opcoes_disponiveis[:5]}")
            # Tenta selecionar primeira opcao valida com o ano
            for opcao in opcoes:
                texto = await opcao.text_content()
                valor = await opcao.get_attribute("value")
                if texto and str(ano_modelo) in texto and valor:
                    opcao_valor = valor
                    break

        if opcao_valor:
            # IMPORTANTE: O site usa plugin Chosen para dropdowns
            # Precisa abrir o dropdown visual e setar o valor via jQuery Chosen
            select_id = await select_encontrado.get_attribute("id")
            logger.info(f"[FIPE-SCREENSHOT] Selecionando valor '{opcao_valor}' no select #{select_id}")

            # Passo 1: Abrir o dropdown visual (span com texto "Selecione o ano modelo")
            try:
                dropdown_visual = await self.page.wait_for_selector(
                    'span:has-text("Selecione o ano modelo"):visible',
                    timeout=5000
                )
                if dropdown_visual:
                    await dropdown_visual.click()
                    await asyncio.sleep(0.5)
                    logger.info("[FIPE-SCREENSHOT] Dropdown visual aberto")
            except:
                logger.warning("[FIPE-SCREENSHOT] Dropdown visual nao encontrado, tentando setar valor diretamente")

            # Passo 2: Setar valor via JavaScript e jQuery Chosen trigger
            await self.page.evaluate(f'''
                (function() {{
                    var select = document.getElementById("{select_id}");
                    if (select) {{
                        select.value = "{opcao_valor}";
                        // Trigger do jQuery Chosen para atualizar a interface
                        if (typeof jQuery !== 'undefined') {{
                            jQuery(select).trigger('chosen:updated');
                            jQuery(select).trigger('change');
                        }} else {{
                            var event = new Event("change", {{ bubbles: true }});
                            select.dispatchEvent(event);
                        }}
                    }}
                }})();
            ''')

            await asyncio.sleep(0.5)
            logger.info(f"[FIPE-SCREENSHOT] Ano selecionado via jQuery Chosen: {opcao_valor}")
        else:
            raise ValueError(f"Ano {ano_modelo} nao disponivel. Opcoes: {opcoes_disponiveis[:5]}")

    async def _clicar_pesquisar(self):
        """Clica no botao de pesquisar da aba codigo FIPE"""
        # Seletores especificos para o botao Pesquisar da aba codigo FIPE
        # O site tem multiplos botoes Pesquisar, precisa clicar no correto
        seletores = [
            "#buttonPesquisarcarroPorCodigoFipe",  # Botao especifico para carros por codigo
            "#buttonPesquisarcaminhaoPorCodigoFipe",  # Para caminhoes
            "#buttonPesquisarmotoPorCodigoFipe",  # Para motos
            "//a[contains(@id, 'PorCodigoFipe') and contains(text(), 'Pesquisar')]",
            "a.bt:has-text('Pesquisar'):visible",
            "//a[contains(@class, 'bt') and contains(text(), 'Pesquisar')]",
            "button:has-text('Pesquisar')",
        ]

        sucesso = await self._clicar_com_retry(seletores, "Botao Pesquisar")
        if not sucesso:
            # Tenta clicar via JavaScript no botao visivel
            logger.info("[FIPE-SCREENSHOT] Tentando clicar via JavaScript")
            await self.page.evaluate('''
                () => {
                    // Procurar botao pesquisar visivel da aba codigo FIPE
                    var btn = document.querySelector('#buttonPesquisarcarroPorCodigoFipe, #buttonPesquisarcaminhaoPorCodigoFipe, #buttonPesquisarmotoPorCodigoFipe');
                    if (btn) {
                        btn.click();
                        return true;
                    }
                    return false;
                }
            ''')

        # Aguarda resultado
        await self._aguardar_carregamento(2.0)

        # Aguarda tabela de resultado
        try:
            await self.page.wait_for_selector(
                "table.tabelaResultado, .resultado table, table:has-text('Preço Médio'), table:has-text('Preco Medio')",
                state="visible",
                timeout=15000
            )
            logger.info("[FIPE-SCREENSHOT] Tabela de resultado encontrada")
        except:
            logger.warning("[FIPE-SCREENSHOT] Tabela de resultado nao encontrada no timeout")

    async def _extrair_dados_resultado(self) -> Dict[str, str]:
        """Extrai dados da tabela de resultado"""
        dados = {}

        mapeamento = {
            "mês de referência": "mes_referencia",
            "mes de referencia": "mes_referencia",
            "código fipe": "codigo_fipe",
            "codigo fipe": "codigo_fipe",
            "marca": "marca",
            "modelo": "modelo",
            "ano modelo": "ano_modelo",
            "autenticação": "autenticacao",
            "autenticacao": "autenticacao",
            "data da consulta": "data_consulta",
            "preço médio": "preco_medio",
            "preco medio": "preco_medio",
        }

        seletores_tabela = [
            "table.tabelaResultado",
            ".resultado table",
            "table:has-text('Preço Médio')",
            "table:has-text('Preco Medio')",
        ]

        tabela = None
        for seletor in seletores_tabela:
            try:
                tabela = await self.page.query_selector(seletor)
                if tabela:
                    break
            except:
                continue

        if tabela:
            linhas = await tabela.query_selector_all("tr")

            for linha in linhas:
                celulas = await linha.query_selector_all("td, th")

                if len(celulas) >= 2:
                    label_elem = celulas[0]
                    valor_elem = celulas[1]

                    label = await label_elem.text_content()
                    valor = await valor_elem.text_content()

                    if label:
                        label_normalizado = label.strip().lower().rstrip(":")

                        for chave_label, chave_dict in mapeamento.items():
                            if chave_label in label_normalizado:
                                dados[chave_dict] = valor.strip() if valor else ""
                                break

            logger.info(f"[FIPE-SCREENSHOT] Dados extraidos: {list(dados.keys())}")

        return dados

    async def _capturar_screenshot(self, codigo_fipe: str, quote_id: Optional[int]) -> str:
        """Captura screenshot da pagina com resultado (area especifica: 2162px a 3143px vertical)"""
        from PIL import Image
        import io

        # Criar diretorio para screenshots
        screenshots_dir = os.path.join(settings.STORAGE_PATH, "screenshots", "fipe")
        os.makedirs(screenshots_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        codigo_limpo = codigo_fipe.replace("-", "").replace("/", "").replace(" ", "")
        filename = f"fipe_screenshot_{quote_id or 'temp'}_{timestamp}.png"
        filepath = os.path.join(screenshots_dir, filename)

        # Verificar se ainda estamos na pagina correta
        current_url = self.page.url
        logger.info(f"[FIPE-SCREENSHOT] URL atual antes do screenshot: {current_url}")

        if "veiculos.fipe.org.br" not in current_url:
            logger.warning(f"[FIPE-SCREENSHOT] URL incorreta! Esperado veiculos.fipe.org.br, atual: {current_url}")
            # Tentar voltar para a pagina de veiculos se necessario
            await self.page.goto(self.URL_BASE, wait_until="networkidle", timeout=self.timeout)
            await asyncio.sleep(2)

        # Aguardar um momento para garantir que a tabela esteja renderizada
        await asyncio.sleep(1)

        # Tentar capturar o elemento da tabela de resultado diretamente
        # para garantir que o conteudo correto seja capturado
        seletores_tabela = [
            "table.tabelaResultado",
            ".resultado table",
            "#resultadoConsultacarroCodigoFipe table",
            "#resultadoConsultamotoCodigoFipe table",
            "#resultadoConsultacaminhaoCodigoFipe table",
            "div[id*='resultadoConsulta'] table",
            "table:has(td:text('Código Fipe'))",
        ]

        elemento_tabela = None
        for seletor in seletores_tabela:
            try:
                elemento = self.page.locator(seletor).first
                if await elemento.count() > 0:
                    elemento_tabela = elemento
                    logger.info(f"[FIPE-SCREENSHOT] Tabela encontrada com seletor: {seletor}")
                    break
            except Exception:
                continue

        if elemento_tabela:
            # Scrollar para a tabela ficar visivel
            await elemento_tabela.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)

            # Capturar screenshot do elemento da tabela
            await elemento_tabela.screenshot(path=filepath, type="png")
            logger.info(f"[FIPE-SCREENSHOT] Screenshot da tabela de resultado capturado")
        else:
            logger.warning(f"[FIPE-SCREENSHOT] Tabela nao encontrada, capturando area especifica da pagina")
            # Capturar a pagina inteira primeiro
            full_screenshot = await self.page.screenshot(
                full_page=True,
                type="png"
            )

            # Recortar area especifica: posicao vertical 2162px ate 3143px
            # Isso captura apenas a regiao onde a tabela de resultado geralmente aparece
            img = Image.open(io.BytesIO(full_screenshot))
            img_width, img_height = img.size

            # Definir coordenadas do recorte (y_inicio, y_fim)
            y_inicio = 2162
            y_fim = 3143

            # Ajustar se a imagem for menor que o esperado
            if img_height < y_fim:
                logger.warning(f"[FIPE-SCREENSHOT] Pagina menor que esperado ({img_height}px), ajustando recorte")
                y_fim = img_height
                # Se a pagina for muito menor, capturar do meio para baixo
                if img_height < y_inicio:
                    y_inicio = max(0, img_height - 1000)

            # Recortar: (left, upper, right, lower)
            cropped = img.crop((0, y_inicio, img_width, y_fim))
            cropped.save(filepath, "PNG")
            logger.info(f"[FIPE-SCREENSHOT] Screenshot recortado ({y_inicio}px a {y_fim}px) salvo")

        logger.info(f"[FIPE-SCREENSHOT] Screenshot salvo: {filepath}")
        return filepath

    async def capture_fipe_result(
        self,
        codigo_fipe: str,
        ano_modelo: int,
        combustivel: str,
        vehicle_type: str = "cars",
        quote_id: Optional[int] = None
    ) -> ResultadoScreenshot:
        """
        Captura screenshot do resultado da consulta FIPE.

        Fluxo robusto:
        1. Acessa pagina inicial
        2. Clica no tipo de veiculo (expande accordion)
        3. Clica na aba "Pesquisa por codigo Fipe"
        4. Preenche codigo FIPE
        5. Seleciona ano/combustivel
        6. Clica em Pesquisar
        7. Extrai dados do resultado
        8. Captura screenshot

        Args:
            codigo_fipe: Codigo FIPE do veiculo (ex: "022140-6")
            ano_modelo: Ano do modelo (ex: 2020)
            combustivel: Tipo combustivel (Gasolina, Diesel, Flex, Alcool)
            vehicle_type: cars, motorcycles ou trucks
            quote_id: ID da cotacao (para nome do arquivo)

        Returns:
            ResultadoScreenshot com caminho do arquivo e dados extraidos
        """
        # Mapear vehicle_type para enum
        tipo_map = {
            "cars": TipoVeiculo.CARRO,
            "motorcycles": TipoVeiculo.MOTO,
            "trucks": TipoVeiculo.CAMINHAO,
        }
        tipo = tipo_map.get(vehicle_type, TipoVeiculo.CARRO)

        logger.info(f"[FIPE-SCREENSHOT] Iniciando captura robusta para {codigo_fipe} - {ano_modelo} {combustivel}")

        try:
            # 1. Acessar site FIPE
            logger.info("[FIPE-SCREENSHOT] Passo 1: Acessando veiculos.fipe.org.br")
            await self.page.goto(self.URL_BASE, wait_until="networkidle", timeout=30000)
            await self._aguardar_carregamento(1.0)

            # 2. Selecionar tipo de veiculo
            logger.info(f"[FIPE-SCREENSHOT] Passo 2: Selecionando tipo: {tipo.value}")
            await self._selecionar_tipo_veiculo(tipo)

            # 3. Selecionar aba de pesquisa por codigo
            logger.info("[FIPE-SCREENSHOT] Passo 3: Selecionando aba 'Pesquisa por codigo Fipe'")
            await self._selecionar_aba_codigo_fipe()

            # 4. Preencher codigo FIPE
            logger.info(f"[FIPE-SCREENSHOT] Passo 4: Preenchendo codigo: {codigo_fipe}")
            await self._preencher_codigo_fipe(codigo_fipe)

            # 5. Selecionar ano/modelo
            logger.info(f"[FIPE-SCREENSHOT] Passo 5: Selecionando ano: {ano_modelo} {combustivel}")
            await self._selecionar_ano_modelo(ano_modelo, combustivel)

            # 6. Clicar em pesquisar
            logger.info("[FIPE-SCREENSHOT] Passo 6: Clicando em Pesquisar")
            await self._clicar_pesquisar()

            # 7. Extrair dados
            logger.info("[FIPE-SCREENSHOT] Passo 7: Extraindo dados do resultado")
            dados = await self._extrair_dados_resultado()

            # 8. Capturar screenshot
            logger.info("[FIPE-SCREENSHOT] Passo 8: Capturando screenshot")
            screenshot_path = await self._capturar_screenshot(codigo_fipe, quote_id)

            logger.info(f"[FIPE-SCREENSHOT] Captura concluida com sucesso! Preco: {dados.get('preco_medio', 'N/A')}")

            return ResultadoScreenshot(
                screenshot_path=screenshot_path,
                sucesso=True,
                dados_extraidos=dados,
                erro=None
            )

        except PlaywrightTimeout as e:
            logger.error(f"[FIPE-SCREENSHOT] Timeout: {e}")
            return ResultadoScreenshot(
                screenshot_path=None,
                sucesso=False,
                dados_extraidos={},
                erro=f"Timeout: {str(e)}"
            )

        except Exception as e:
            logger.error(f"[FIPE-SCREENSHOT] Erro: {e}")
            return ResultadoScreenshot(
                screenshot_path=None,
                sucesso=False,
                dados_extraidos={},
                erro=str(e)
            )


async def capture_fipe_screenshot(
    codigo_fipe: str,
    ano_modelo: int,
    combustivel: str,
    vehicle_type: str = "cars",
    quote_id: Optional[int] = None
) -> Optional[str]:
    """
    Funcao helper para captura de screenshot FIPE (compativel com versao anterior).

    Gerencia o ciclo de vida do navegador automaticamente.

    Args:
        codigo_fipe: Codigo FIPE do veiculo
        ano_modelo: Ano do modelo
        combustivel: Tipo de combustivel
        vehicle_type: Tipo de veiculo (cars, motorcycles, trucks)
        quote_id: ID da cotacao

    Returns:
        Caminho do arquivo screenshot ou None se falhar
    """
    try:
        async with FipeScreenshotService(headless=True) as service:
            resultado = await service.capture_fipe_result(
                codigo_fipe=codigo_fipe,
                ano_modelo=ano_modelo,
                combustivel=combustivel,
                vehicle_type=vehicle_type,
                quote_id=quote_id
            )

            if resultado.sucesso:
                return resultado.screenshot_path
            else:
                logger.warning(f"[FIPE-SCREENSHOT] Falha na captura: {resultado.erro}")
                return None

    except Exception as e:
        logger.error(f"[FIPE-SCREENSHOT] Erro ao capturar screenshot: {e}")
        return None
