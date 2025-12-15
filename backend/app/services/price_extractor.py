from playwright.async_api import async_playwright, Page, Browser, Playwright
from typing import Optional, Tuple
import re
import json
import logging
from decimal import Decimal
from app.models.quote_source import ExtractionMethod

logger = logging.getLogger(__name__)


class PriceExtractor:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.playwright: Optional[Playwright] = None

    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        # Configurações do browser para melhor compatibilidade
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
            ]
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def extract_price_and_screenshot(
        self, url: str, screenshot_path: str
    ) -> Tuple[Optional[Decimal], Optional[ExtractionMethod]]:
        if not self.browser:
            raise RuntimeError("Browser not initialized. Use 'async with PriceExtractor()' context manager.")

        # Criar contexto com user agent realista
        # Altura do viewport aumentada em 60% (768 -> 1229) para melhor captura
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1366, 'height': 1229},
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
        )
        page = await context.new_page()

        try:
            # Usar domcontentloaded em vez de networkidle para evitar timeout
            # em sites com polling constante (analytics, chat widgets, etc.)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"First load attempt failed for {url}: {e}")
                # Tentar novamente com timeout maior
                await page.goto(url, wait_until="load", timeout=45000)

            # Aguardar um pouco para recursos adicionais carregarem
            await page.wait_for_timeout(3000)

            # Fechar popups e modais antes do screenshot
            await self._close_popups(page)

            # IMPORTANTE: Rolar para o topo da página antes do screenshot
            # Alguns sites (VTEX, etc.) podem rolar automaticamente para outras seções
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)  # Pequena pausa para garantir que o scroll foi aplicado

            # Capture top portion of the page (title, image, price area)
            # Increased by 25% to capture more product details
            viewport_size = page.viewport_size
            page_height = await page.evaluate("document.body.scrollHeight")

            # Calculate ~45% of page height (37.5% + 20%), with min/max bounds
            # Min: 900px (750 + 20%), Max: 1800px (1500 + 20%)
            clip_height = min(max(int(page_height * 0.45), 900), 1800)

            await page.screenshot(
                path=screenshot_path,
                clip={
                    "x": 0,
                    "y": 0,
                    "width": viewport_size["width"],
                    "height": clip_height
                }
            )

            price, method = await self._extract_price(page)

            return price, method

        finally:
            await page.close()
            await context.close()

    async def _close_popups(self, page: Page) -> None:
        """
        Fecha popups, modais, banners de cookies e overlays comuns em sites de e-commerce.
        Estratégia em 4 fases:
        1. Clicar em botões de aceitar/concordar (cookies, LGPD)
        2. Clicar em botões de fechar (X, close)
        3. Remover elementos via JavaScript
        4. Repetir fases 1-2 para popups sequenciais (alguns sites têm múltiplos popups)
        """

        # Executar até 3 vezes para fechar popups sequenciais
        for attempt in range(3):
            closed_any = await self._close_popups_single_pass(page)
            if not closed_any:
                break
            await page.wait_for_timeout(500)  # Aguardar animação e próximo popup

        # Fase final: remoção via JavaScript
        await self._remove_overlays_js(page)
        await page.wait_for_timeout(300)

    async def _close_popups_single_pass(self, page: Page) -> bool:
        """Executa uma passagem tentando fechar popups. Retorna True se fechou algo."""
        closed_any = False

        # FASE 1: Aceitar cookies e políticas (prioridade alta)
        accept_selectors = [
            # Textos em português
            'button:has-text("Aceitar")',
            'button:has-text("Aceito")',
            'button:has-text("Aceitar todos")',
            'button:has-text("Aceitar tudo")',
            'button:has-text("Concordo")',
            'button:has-text("Concordar")',
            'button:has-text("Entendi")',
            'button:has-text("Entendido")',
            'button:has-text("Prosseguir")',
            'button:has-text("Continuar")',
            'button:has-text("OK")',
            'button:has-text("Ok")',
            'a:has-text("Aceitar")',
            'a:has-text("Concordo")',
            'a:has-text("Entendi")',
            # Textos em inglês
            'button:has-text("Accept")',
            'button:has-text("Accept all")',
            'button:has-text("Accept All")',
            'button:has-text("I agree")',
            'button:has-text("Agree")',
            'button:has-text("Got it")',
            'button:has-text("Allow")',
            'button:has-text("Allow all")',
            # Seletores específicos de cookies
            '[class*="cookie"] button:has-text("Aceitar")',
            '[class*="cookie"] button:has-text("Accept")',
            '[class*="consent"] button:has-text("Aceitar")',
            '[class*="consent"] button:has-text("Accept")',
            '[class*="lgpd"] button',
            '[class*="LGPD"] button',
            '[id*="onetrust"] button',
            '[id*="cookie"] button',
            '#accept-cookie',
            '.accept-cookie',
            '.cookie-accept',
            '#lgpd-accept',
            '.lgpd-accept',
            '[data-testid*="accept"]',
            '[data-testid*="cookie"]',
        ]

        for selector in accept_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    if is_visible:
                        await element.click(timeout=2000)
                        await page.wait_for_timeout(300)
                        closed_any = True
            except:
                pass

        # FASE 2: Fechar popups genéricos
        close_selectors = [
            # Botões de fechar com X
            '.modal-close',
            '.btn-close',
            '.close-button',
            '.close-btn',
            '.popup-close',
            '.overlay-close',
            '.close-modal',
            '.fechar',
            '[class*="close-icon"]',
            '[class*="closeIcon"]',
            '[class*="icon-close"]',
            '[class*="iconClose"]',
            # Aria labels
            '[aria-label="close"]',
            '[aria-label="Close"]',
            '[aria-label="fechar"]',
            '[aria-label="Fechar"]',
            '[aria-label="Dismiss"]',
            # Title
            '[title="Fechar"]',
            '[title="Close"]',
            # Data attributes
            '[data-dismiss="modal"]',
            '[data-close]',
            '[data-action="close"]',
            # Classes genéricas
            'button[class*="close"]',
            'button[class*="Close"]',
            'a[class*="close"]',
            'span[class*="close"]',
            'div[class*="close"][role="button"]',
            # Newsletter popups
            '[class*="newsletter"] [class*="close"]',
            '[class*="Newsletter"] [class*="close"]',
            '[class*="popup"] [class*="close"]',
            '[class*="modal"] [class*="close"]',
            '[class*="dialog"] [class*="close"]',
            # SVG close icons
            'button:has(svg[class*="close"])',
            'button:has(svg[class*="x"])',
            # Sites brasileiros específicos - VTEX (Positivo, etc)
            '.vtex-modal__close',
            '.vtex-store-components-3-x-closeButton',
            '[class*="vtex"] [class*="close"]',
            '[class*="vtex"] button[class*="Close"]',
            # Minitela/splash screen (Positivo)
            '[class*="minitela"] [class*="close"]',
            '[class*="splash"] [class*="close"]',
            '[class*="Splash"] [class*="close"]',
            # Botões "Não, obrigado" / "Agora não"
            'button:has-text("Não, obrigado")',
            'button:has-text("Agora não")',
            'button:has-text("Não quero")',
            'button:has-text("Fechar")',
            'a:has-text("Fechar")',
            'a:has-text("Não, obrigado")',
            # Ícones X genéricos
            'button:has-text("×")',
            'button:has-text("✕")',
            'button:has-text("X")',
            '[class*="icon-x"]',
            '[class*="icon-X"]',
        ]

        for selector in close_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements[:5]:
                    try:
                        is_visible = await element.is_visible()
                        if is_visible:
                            # Verificar se está em um container de popup/modal
                            await element.click(timeout=1500)
                            await page.wait_for_timeout(200)
                            closed_any = True
                    except:
                        pass
            except:
                pass

        return closed_any

    async def _remove_overlays_js(self, page: Page) -> None:
        """Remove overlays via JavaScript (mais agressivo)"""
        try:
            await page.evaluate("""
                () => {
                    // Lista de seletores para remover/esconder
                    const removeSelectors = [
                        // Backdrops e overlays
                        '.modal-backdrop',
                        '.overlay',
                        '.modal-overlay',
                        '.popup-overlay',
                        '.dialog-overlay',
                        '[class*="backdrop"]',
                        '[class*="Backdrop"]',
                        // Cookies e LGPD
                        '[class*="cookie-banner"]',
                        '[class*="cookie-notice"]',
                        '[class*="cookie-consent"]',
                        '[class*="cookieBanner"]',
                        '[class*="cookieNotice"]',
                        '[class*="lgpd"]',
                        '[class*="LGPD"]',
                        '[id*="cookie"]',
                        '[id*="Cookie"]',
                        '[id*="lgpd"]',
                        '[id*="onetrust"]',
                        '[id*="CookieConsent"]',
                        // Newsletter e promoções
                        '[class*="newsletter-popup"]',
                        '[class*="newsletterPopup"]',
                        '[class*="promo-popup"]',
                        '[class*="promoPopup"]',
                        '[class*="exit-intent"]',
                        '[class*="exitIntent"]',
                        // Genéricos
                        '[class*="lightbox"]',
                        '[class*="Lightbox"]',
                    ];

                    removeSelectors.forEach(selector => {
                        try {
                            document.querySelectorAll(selector).forEach(el => {
                                el.style.display = 'none';
                                el.style.visibility = 'hidden';
                                el.style.opacity = '0';
                            });
                        } catch(e) {}
                    });

                    // Remover qualquer elemento com position fixed e z-index alto
                    // (provavelmente é um popup)
                    document.querySelectorAll('*').forEach(el => {
                        try {
                            const style = window.getComputedStyle(el);
                            const zIndex = parseInt(style.zIndex) || 0;
                            const isFixed = style.position === 'fixed';
                            const isAbsolute = style.position === 'absolute';
                            const coversScreen = el.offsetWidth > window.innerWidth * 0.5 &&
                                                el.offsetHeight > window.innerHeight * 0.3;

                            // Se é fixed/absolute com z-index alto e cobre parte da tela
                            if ((isFixed || (isAbsolute && zIndex > 1000)) &&
                                zIndex > 100 && coversScreen) {
                                // Não remover se for o conteúdo principal
                                const isMain = el.tagName === 'MAIN' ||
                                              el.tagName === 'HEADER' ||
                                              el.tagName === 'NAV' ||
                                              el.id === 'root' ||
                                              el.id === 'app' ||
                                              el.id === '__next';
                                if (!isMain) {
                                    el.style.display = 'none';
                                }
                            }
                        } catch(e) {}
                    });

                    // Restaurar scroll do body
                    document.body.style.overflow = 'auto';
                    document.body.style.overflowY = 'auto';
                    document.documentElement.style.overflow = 'auto';
                    document.body.classList.remove('modal-open', 'no-scroll', 'overflow-hidden');

                    // Remover padding adicionado por modais (Bootstrap style)
                    document.body.style.paddingRight = '0';
                }
            """)
        except:
            pass

    async def _extract_price(self, page: Page) -> Tuple[Optional[Decimal], Optional[ExtractionMethod]]:
        price, method = await self._try_jsonld(page)
        if price:
            return price, method

        price, method = await self._try_meta_tags(page)
        if price:
            return price, method

        price, method = await self._try_dom_extraction(page)
        if price:
            return price, method

        return None, None

    async def _try_jsonld(self, page: Page) -> Tuple[Optional[Decimal], Optional[ExtractionMethod]]:
        try:
            scripts = await page.query_selector_all('script[type="application/ld+json"]')

            for script in scripts:
                content = await script.inner_text()
                data = json.loads(content)

                if isinstance(data, list):
                    data_list = data
                else:
                    data_list = [data]

                for item in data_list:
                    if item.get("@type") == "Product":
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            price_str = offers.get("price")
                            currency = offers.get("priceCurrency", "BRL")
                            if price_str and currency == "BRL":
                                price = self._parse_price(str(price_str))
                                if price:
                                    return price, ExtractionMethod.JSONLD

        except Exception as e:
            pass

        return None, None

    async def _try_meta_tags(self, page: Page) -> Tuple[Optional[Decimal], Optional[ExtractionMethod]]:
        try:
            # Seletores confiáveis de meta tags de preço
            meta_selectors = [
                'meta[property="product:price:amount"]',
                'meta[property="og:price:amount"]',
            ]

            for selector in meta_selectors:
                element = await page.query_selector(selector)
                if element:
                    content = await element.get_attribute("content")
                    if content:
                        price = self._parse_price(content)
                        if price:
                            return price, ExtractionMethod.META

            # Twitter Card: só usar twitter:data1 se twitter:label1 indicar preço
            # Isso evita interpretar SKUs como preços (ex: "MEL-327-P" → 327)
            label_element = await page.query_selector('meta[name="twitter:label1"]')
            if label_element:
                label = await label_element.get_attribute("content")
                if label and any(p in label.lower() for p in ["preço", "preco", "price", "valor"]):
                    data_element = await page.query_selector('meta[name="twitter:data1"]')
                    if data_element:
                        content = await data_element.get_attribute("content")
                        if content:
                            price = self._parse_price(content)
                            if price:
                                return price, ExtractionMethod.META

        except Exception as e:
            pass

        return None, None

    async def _try_dom_extraction(self, page: Page) -> Tuple[Optional[Decimal], Optional[ExtractionMethod]]:
        try:
            price_selectors = [
                '[data-testid*="price"]',
                '[class*="price"]',
                '[id*="price"]',
                '.price-tag',
                '.product-price',
                '.sale-price',
                'span[itemprop="price"]',
            ]

            for selector in price_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if "R$" in text or "," in text or "." in text:
                        price = self._parse_price(text)
                        if price and price > Decimal("1"):
                            return price, ExtractionMethod.DOM

            body_text = await page.inner_text("body")
            price = self._find_price_in_text(body_text)
            if price:
                return price, ExtractionMethod.DOM

        except Exception as e:
            pass

        return None, None

    def _parse_price(self, text: str) -> Optional[Decimal]:
        text = text.strip()

        text = re.sub(r'[^\d,.]', '', text)

        if not text:
            return None

        if ',' in text and '.' in text:
            if text.rfind(',') > text.rfind('.'):
                text = text.replace('.', '').replace(',', '.')
            else:
                text = text.replace(',', '')
        elif ',' in text:
            if text.count(',') == 1 and len(text.split(',')[1]) == 2:
                text = text.replace(',', '.')
            else:
                text = text.replace(',', '')

        try:
            return Decimal(text)
        except:
            return None

    def _find_price_in_text(self, text: str) -> Optional[Decimal]:
        patterns = [
            r'R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})',
            r'R\$\s*(\d+,\d{2})',
            r'(\d{1,3}(?:\.\d{3})*,\d{2})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                price = self._parse_price(match)
                if price and price > Decimal("1"):
                    return price

        return None
