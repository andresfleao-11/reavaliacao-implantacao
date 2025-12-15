"""
Google Lens Service for product identification using SerpAPI.

Flow:
1. Upload image to a temporary URL (imgbb or similar)
2. Call Google Lens API with type=products
3. Extract product info from visual_matches
4. Access product link to get detailed specifications
5. Return product info for quotation flow
"""

from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel
import httpx
import logging
import asyncio
import os
import base64
from datetime import datetime

logger = logging.getLogger(__name__)


async def upload_image_to_imgbb(image_data: bytes, api_key: str) -> Optional[str]:
    """
    Upload image to imgbb.com and return the public URL.

    imgbb offers free image hosting with API.
    Get a free API key at: https://api.imgbb.com/

    Args:
        image_data: Raw image bytes
        api_key: imgbb API key

    Returns:
        Public URL of the uploaded image, or None on failure
    """
    if not api_key:
        logger.error("imgbb API key not configured")
        return None

    try:
        # Convert image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.imgbb.com/1/upload",
                data={
                    "key": api_key,
                    "image": image_base64,
                    "expiration": 600,  # 10 minutes expiration
                }
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    url = data["data"]["url"]
                    logger.info(f"Image uploaded to imgbb: {url}")
                    return url
                else:
                    logger.error(f"imgbb upload failed: {data}")
            else:
                logger.error(f"imgbb upload failed with status {response.status_code}: {response.text}")

    except Exception as e:
        logger.error(f"Error uploading to imgbb: {e}")

    return None

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds


class LensProduct(BaseModel):
    """Product identified by Google Lens"""
    title: str
    link: str
    source: str
    price: Optional[str] = None
    extracted_price: Optional[float] = None
    thumbnail: Optional[str] = None
    position: int = 0


class LensResult(BaseModel):
    """Result from Google Lens search"""
    products: List[LensProduct] = []
    visual_matches: List[Dict[str, Any]] = []
    knowledge_graph: Optional[Dict[str, Any]] = None
    search_metadata: Dict[str, Any] = {}
    total_results: int = 0


class ProductSpecs(BaseModel):
    """Extracted product specifications"""
    nome: Optional[str] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    tipo_produto: Optional[str] = None
    especificacoes: Dict[str, Any] = {}
    preco: Optional[float] = None
    url_fonte: Optional[str] = None


class GoogleLensService:
    """
    Service for identifying products using Google Lens via SerpAPI.

    Usage:
    1. Upload image and get products
    2. Select best product match
    3. Extract specs from product page
    4. Continue with regular quotation flow
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://serpapi.com/search"
        self.api_calls_made = []

    async def search_by_image_url(
        self,
        image_url: str,
        refine_query: Optional[str] = None
    ) -> LensResult:
        """
        Search Google Lens using an image URL.

        Args:
            image_url: Public URL of the image
            refine_query: Optional query to refine results

        Returns:
            LensResult with products and visual matches
        """
        params = {
            "engine": "google_lens",
            "url": image_url,
            "type": "products",  # Focus on product results
            "api_key": self.api_key,
            "country": "br",
            "hl": "pt",
            "no_cache": "true",  # Always get fresh results for accuracy
        }

        if refine_query:
            params["q"] = refine_query

        logger.info(f"Google Lens search: {image_url[:100]}...")

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(self.base_url, params=params)

                    if response.status_code == 429:
                        if attempt < MAX_RETRIES - 1:
                            backoff = INITIAL_BACKOFF * (2 ** attempt)
                            logger.warning(f"Rate limited. Retry in {backoff}s ({attempt + 1}/{MAX_RETRIES})")
                            await asyncio.sleep(backoff)
                            continue
                        logger.error("Rate limit exceeded on Google Lens")
                        return LensResult()

                    response.raise_for_status()
                    data = response.json()

                # Register API call
                self.api_calls_made.append({
                    "api_used": "google_lens",
                    "search_url": f"{self.base_url}?engine=google_lens&url={image_url[:50]}...&type=products",
                    "activity": "Identificação de produto via Google Lens",
                    "timestamp": datetime.utcnow().isoformat()
                })

                return self._parse_lens_response(data)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF * (2 ** attempt)
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"HTTP error on Google Lens: {e}")
                return LensResult()
            except Exception as e:
                logger.error(f"Error on Google Lens search: {e}")
                return LensResult()

        return LensResult()

    async def search_by_image_data(
        self,
        image_data: bytes,
        image_filename: str = "image.jpg"
    ) -> Tuple[LensResult, Optional[str]]:
        """
        Search Google Lens using image data (base64).

        Note: SerpAPI requires a public URL, so we need to first upload
        the image to a temporary hosting service or use a data URL.

        For now, we'll save the image locally and use file:// URL
        (works only for local development) or return error suggesting
        to use a URL instead.

        Args:
            image_data: Raw image bytes
            image_filename: Original filename

        Returns:
            Tuple of (LensResult, error_message)
        """
        # SerpAPI Google Lens requires a public URL
        # For production, you would:
        # 1. Upload to S3/GCS with signed URL
        # 2. Use imgur or similar temporary hosting
        # 3. Host image on your own server

        # For now, we'll try with a data URL (may not work with all images)
        # or save locally and serve via backend

        from app.core.config import settings

        # Save image to storage
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"lens_{timestamp}_{image_filename}"
        storage_path = os.path.join(settings.STORAGE_PATH, "lens_temp", safe_filename)
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)

        with open(storage_path, "wb") as f:
            f.write(image_data)

        # Generate public URL (requires backend to serve static files)
        # This URL format depends on your backend configuration
        base_url = os.environ.get("BACKEND_PUBLIC_URL", "http://localhost:8000")
        image_url = f"{base_url}/api/files/lens_temp/{safe_filename}"

        logger.info(f"Image saved for Lens: {storage_path}")
        logger.info(f"Public URL: {image_url}")

        # Search using the URL
        result = await self.search_by_image_url(image_url)

        return result, None

    def _parse_lens_response(self, data: Dict[str, Any]) -> LensResult:
        """Parse Google Lens API response"""
        result = LensResult(
            search_metadata=data.get("search_metadata", {})
        )

        # Parse visual_matches
        visual_matches = data.get("visual_matches", [])
        result.visual_matches = visual_matches
        logger.info(f"Google Lens found {len(visual_matches)} visual matches")

        # Parse products from visual_matches
        products = []
        for idx, match in enumerate(visual_matches):
            # Visual matches may have product info
            title = match.get("title", "")
            link = match.get("link", "")
            source = match.get("source", "")

            # Price info may be in price object
            price_info = match.get("price", {})
            if isinstance(price_info, dict):
                price_str = price_info.get("value", "") or price_info.get("currency", "")
                extracted_price = price_info.get("extracted_value")
            elif isinstance(price_info, str):
                price_str = price_info
                extracted_price = None
            else:
                price_str = None
                extracted_price = None

            if link:  # Only add if we have a link
                products.append(LensProduct(
                    title=title,
                    link=link,
                    source=source,
                    price=price_str,
                    extracted_price=extracted_price,
                    thumbnail=match.get("thumbnail"),
                    position=idx + 1
                ))

        # Also check for shopping_results if type=products
        shopping_results = data.get("shopping_results", [])
        for idx, item in enumerate(shopping_results):
            products.append(LensProduct(
                title=item.get("title", ""),
                link=item.get("link", ""),
                source=item.get("source", ""),
                price=item.get("price"),
                extracted_price=item.get("extracted_price"),
                thumbnail=item.get("thumbnail"),
                position=len(visual_matches) + idx + 1
            ))

        result.products = products
        result.total_results = len(products)

        # Parse knowledge_graph if available
        result.knowledge_graph = data.get("knowledge_graph")

        logger.info(f"Parsed {len(products)} products from Google Lens response")

        return result

    async def extract_product_specs_from_url(
        self,
        url: str,
        claude_client=None
    ) -> ProductSpecs:
        """
        Extract product specifications from a product page URL.

        This method:
        1. Fetches the product page
        2. Uses Claude to extract specs if provided
        3. Falls back to basic HTML parsing

        Args:
            url: Product page URL
            claude_client: Optional ClaudeClient for AI extraction

        Returns:
            ProductSpecs with extracted information
        """
        specs = ProductSpecs(url_fonte=url)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                }
                response = await client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

                html_content = response.text

                # Try to extract JSON-LD structured data first
                specs = self._extract_from_jsonld(html_content, specs)

                # If we have a Claude client, use it for better extraction
                if claude_client and (not specs.nome or not specs.especificacoes):
                    specs = await self._extract_with_claude(html_content, url, claude_client, specs)

                return specs

        except Exception as e:
            logger.error(f"Error extracting specs from {url}: {e}")
            return specs

    def _extract_from_jsonld(self, html: str, specs: ProductSpecs) -> ProductSpecs:
        """Extract product info from JSON-LD structured data"""
        import re
        import json

        # Find JSON-LD scripts
        jsonld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        matches = re.findall(jsonld_pattern, html, re.DOTALL | re.IGNORECASE)

        for match in matches:
            try:
                data = json.loads(match.strip())

                # Handle array of objects
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            data = item
                            break

                if data.get("@type") == "Product":
                    specs.nome = data.get("name", specs.nome)
                    specs.marca = data.get("brand", {}).get("name") if isinstance(data.get("brand"), dict) else data.get("brand")
                    specs.modelo = data.get("model") or data.get("sku")

                    # Extract price from offers
                    offers = data.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    if offers.get("price"):
                        try:
                            specs.preco = float(offers.get("price"))
                        except:
                            pass

                    # Extract additional properties
                    additional_props = data.get("additionalProperty", [])
                    if additional_props:
                        for prop in additional_props:
                            name = prop.get("name", "")
                            value = prop.get("value", "")
                            if name and value:
                                specs.especificacoes[name] = value

                    logger.info(f"Extracted from JSON-LD: {specs.nome}, {specs.marca}")
                    break

            except json.JSONDecodeError:
                continue

        return specs

    async def _extract_with_claude(
        self,
        html: str,
        url: str,
        claude_client,
        specs: ProductSpecs
    ) -> ProductSpecs:
        """Use Claude to extract product specs from HTML"""
        # Truncate HTML to avoid token limits
        html_truncated = html[:50000]

        prompt = f"""Analise o HTML desta página de produto e extraia as especificações técnicas.

URL: {url}

HTML (truncado):
{html_truncated}

Retorne um JSON com:
{{
    "nome": "nome completo do produto",
    "marca": "marca do produto",
    "modelo": "código do modelo",
    "tipo_produto": "notebook/ar_condicionado/impressora/etc",
    "especificacoes": {{
        "processador": "...",
        "ram": "...",
        "armazenamento": "...",
        "tela": "...",
        // outras specs relevantes
    }},
    "preco": 0.00
}}

Retorne APENAS o JSON, sem texto adicional."""

        try:
            response = claude_client.client.messages.create(
                model=claude_client.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = response.content[0].text

            import json
            # Find JSON in response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)

                specs.nome = data.get("nome", specs.nome)
                specs.marca = data.get("marca", specs.marca)
                specs.modelo = data.get("modelo", specs.modelo)
                specs.tipo_produto = data.get("tipo_produto", specs.tipo_produto)
                specs.especificacoes = data.get("especificacoes", specs.especificacoes)
                if data.get("preco"):
                    specs.preco = float(data.get("preco"))

                logger.info(f"Claude extracted: {specs.nome}, {specs.marca}, {specs.modelo}")

        except Exception as e:
            logger.error(f"Error using Claude for extraction: {e}")

        return specs

    def get_api_calls(self) -> List[Dict[str, Any]]:
        """Return list of API calls made for logging/billing"""
        return self.api_calls_made
