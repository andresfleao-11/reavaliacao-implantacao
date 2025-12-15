from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel
from decimal import Decimal
import httpx
import logging
import re
import asyncio
import math

logger = logging.getLogger(__name__)

# Retry configuration for rate limits
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds

# Domains with anti-bot protection that cause timeouts/failures
# These are skipped during search to avoid wasting API calls
BLOCKED_DOMAINS = {
    # Marketplaces com proteção anti-bot forte
    "mercadolivre.com.br",
    "mercadoshops.com.br",
    "amazon.com.br",
    "amazon.com",
    "aliexpress.com",
    "aliexpress.com.br",
    "shopee.com.br",
    "shein.com",
    "shein.com.br",
    "wish.com",
    "temu.com",
    # Grandes varejistas com Cloudflare/anti-bot
    "carrefour.com.br",
    "casasbahia.com.br",
    "pontofrio.com.br",
    "extra.com.br",
    "magazineluiza.com.br",
    "magalu.com.br",
    "americanas.com.br",
    "submarino.com.br",
    "shoptime.com.br",
}

# Foreign domains to skip (only allow Brazilian stores)
FOREIGN_DOMAIN_PATTERNS = {
    ".com",      # Generic .com (but not .com.br)
    ".net",
    ".org",
    ".us",
    ".uk",
    ".de",
    ".fr",
    ".es",
    ".it",
    ".cn",
    ".jp",
    ".co.uk",
    ".eu",
}

# Allowed foreign domains (exceptions to the foreign domain filter)
# These are legitimate stores that use .com but sell in Brazil
ALLOWED_FOREIGN_DOMAINS = {
    "www.lenovo.com",
    "lenovo.com",
    "www.dell.com",
    "dell.com",
    "www.hp.com",
    "hp.com",
    "www.samsung.com",
    "samsung.com",
    "www.lg.com",
    "lg.com",
    "www.apple.com",
    "apple.com",
    "www.asus.com",
    "asus.com",
    "www.acer.com",
    "acer.com",
}


class SearchResult(BaseModel):
    url: str
    title: str
    domain: Optional[str] = None
    snippet: Optional[str] = None
    price: Optional[str] = None
    extracted_price: Optional[Decimal] = None
    store_name: Optional[str] = None


class SearchLog(BaseModel):
    """Detailed log of search operations for debugging and audit"""
    query: str
    limit: int
    variacao_maxima: float
    total_raw_products: int = 0
    after_source_filter: int = 0
    blocked_sources: int = 0
    after_price_filter: int = 0
    invalid_prices: int = 0
    total_blocks_created: int = 0
    valid_blocks: int = 0
    blocks_tried: int = 0
    successful_block_index: Optional[int] = None
    immersive_api_calls: int = 0
    results_obtained: int = 0
    skipped_reasons: List[dict] = []  # [{reason: "blocked_domain", domain: "...", count: N}, ...]
    block_details: List[dict] = []  # [{index: 1, size: 5, min_price: 100, max_price: 125, result: "success/failed"}, ...]


class ShoppingProduct(BaseModel):
    """Intermediate product from Google Shopping (before getting store link)"""
    title: str
    price: str
    extracted_price: Optional[float]
    source: str
    serpapi_immersive_product_api: Optional[str]  # Full URL to call Immersive API
    product_link: Optional[str]
    link: Optional[str]


class SearchProvider(ABC):
    @abstractmethod
    async def search_products(
        self,
        query: str,
        limit: int = 3,
        variacao_maxima: float = 0.25
    ) -> Tuple[List[SearchResult], SearchLog]:
        """Returns (results, search_log) tuple"""
        pass


class SerpApiProvider(SearchProvider):
    """
    SerpAPI Provider optimized for minimal API calls with variation blocks:

    Flow:
    1. ONE Google Shopping API call → get ALL products
    2. Filter by blocked sources (using 'source' field)
    3. Filter by valid prices (extracted_price > 0)
    4. Sort by price and limit to MAX_VALID_PRODUCTS (150)
    5. Create variation blocks (sliding window):
       - Each block starts from a different product
       - Block includes consecutive products within variation limit
       - Only blocks with at least N products are valid (N = numero_cotacoes)
    6. Sort blocks by priority:
       - More products first (higher chance of success)
       - Lower starting price (cheaper options preferred)
    7. Try to get N quotes from each block in order:
       - If block succeeds (N quotes obtained) → done
       - If block fails → try next block

    Example with limit=3 and variacao_maxima=25%:
    Products: [100, 102, 104, 110, 125, 130, 140, 150]
    Block 1: [100, 102, 104, 110, 125] (5 products, starts at R$100)
    Block 2: [102, 104, 110, 125] (4 products, starts at R$102)
    Block 3: [104, 110, 125, 130] (4 products, starts at R$104)
    ...
    Sorted: Block 1 first (most products, lowest price)
    Try Block 1 → if 3 quotes obtained, done; else try Block 2, etc.
    """

    # Maximum valid products to process after source/price filtering
    MAX_VALID_PRODUCTS = 150

    def __init__(self, api_key: str, engine: str = "google_shopping", location: str = "Brazil"):
        self.api_key = api_key
        self.engine = engine
        self.location = location
        self.base_url = "https://serpapi.com/search"
        self.api_calls_made = []  # Track all API calls made

    async def search_products(
        self,
        query: str,
        limit: int = 3,
        variacao_maxima: float = 0.25
    ) -> Tuple[List[SearchResult], SearchLog]:
        """
        Main search method with optimized API calls and variation blocks.

        Returns:
            Tuple of (results, search_log) for debugging and audit
        """
        logger.info(f"=== Starting search: '{query}' ===")
        logger.info(f"Parameters: limit={limit}, variacao_maxima={variacao_maxima * 100}%")

        # Initialize search log
        search_log = SearchLog(
            query=query,
            limit=limit,
            variacao_maxima=variacao_maxima
        )

        # Step 1: ONE Google Shopping API call - get ALL products
        all_products = await self._search_google_shopping_raw(query)

        if not all_products:
            logger.warning("No products found from Google Shopping")
            return [], search_log

        search_log.total_raw_products = len(all_products)
        logger.info(f"Step 1: Got {len(all_products)} raw products from Google Shopping")

        # Step 2: Filter by blocked sources
        products_after_source_filter = [
            p for p in all_products if not self._is_blocked_source(p.source)
        ]
        blocked_count = len(all_products) - len(products_after_source_filter)
        search_log.after_source_filter = len(products_after_source_filter)
        search_log.blocked_sources = blocked_count
        logger.info(f"Step 2: {len(products_after_source_filter)} products after source filter ({blocked_count} blocked)")

        if not products_after_source_filter:
            logger.warning("All products were from blocked sources")
            return [], search_log

        # Step 3: Filter by valid prices
        products_with_valid_prices = [
            p for p in products_after_source_filter
            if p.extracted_price is not None and p.extracted_price > 0
        ]
        invalid_price_count = len(products_after_source_filter) - len(products_with_valid_prices)
        search_log.after_price_filter = len(products_with_valid_prices)
        search_log.invalid_prices = invalid_price_count
        logger.info(f"Step 3: {len(products_with_valid_prices)} products with valid prices ({invalid_price_count} without price)")

        if not products_with_valid_prices:
            logger.warning("No products with valid prices found")
            return [], search_log

        # Sort by price
        products_with_valid_prices.sort(key=lambda x: x.extracted_price)

        # Step 4: Limit to MAX_VALID_PRODUCTS (150)
        if len(products_with_valid_prices) > self.MAX_VALID_PRODUCTS:
            logger.info(f"Step 4: Limiting from {len(products_with_valid_prices)} to {self.MAX_VALID_PRODUCTS} products")
            products_limited = products_with_valid_prices[:self.MAX_VALID_PRODUCTS]
        else:
            logger.info(f"Step 4: {len(products_with_valid_prices)} products (under limit of {self.MAX_VALID_PRODUCTS})")
            products_limited = products_with_valid_prices

        # Step 5: Create variation blocks (sliding window approach)
        # Each block starts from a different product and includes all products within variation limit
        # Only blocks with at least 'limit' products are valid (to ensure enough quotes per block)
        variation_blocks, total_blocks = self._create_variation_blocks(products_limited, variacao_maxima, min_block_size=limit)
        search_log.total_blocks_created = total_blocks
        search_log.valid_blocks = len(variation_blocks)

        if not variation_blocks:
            logger.warning("No variation blocks could be created")
            return [], search_log

        # Step 6: Sort blocks by priority:
        # 1. More products first (higher chance of getting N quotes)
        # 2. Lower starting price (cheaper options preferred)
        sorted_blocks = sorted(
            variation_blocks,
            key=lambda block: (-len(block), block[0].extracted_price)
        )

        logger.info(f"Step 5-6: Created {total_blocks} blocks, {len(sorted_blocks)} valid (min size: {limit})")
        for i, block in enumerate(sorted_blocks[:5]):  # Show top 5 blocks
            prices = [p.extracted_price for p in block]
            logger.info(
                f"    Block {i+1}: {len(block)} products "
                f"(R$ {min(prices):.2f} - R$ {max(prices):.2f})"
            )
        if len(sorted_blocks) > 5:
            logger.info(f"    ... and {len(sorted_blocks) - 5} more blocks")

        # Step 7: Try to get N quotes using iterative block recalculation
        # Logic:
        # 1. Keep valid products in the list (they participate in block calculation)
        # 2. Mark failed products as "tried" (remove from list)
        # 3. Recalculate blocks after each failure
        # 4. Prioritize blocks containing all valid products
        # 5. If no block with valid products has enough untried products:
        #    - Save current valid as "reserve"
        #    - Try a new block without the reserve products
        #    - If new block fails, return to reserve
        # 6. Continue until we have N results or exhaust all products

        results = []
        results_by_key = {}  # {product_key: store_result} - for reusing valid results
        domains_seen = set()
        immersive_calls = 0
        failed_product_keys = set()  # Products that failed (remove from future blocks)
        all_products = list(products_limited)  # All products available
        iteration = 0
        max_iterations = 15  # Safety limit

        # Reserve system: save valid results when trying alternative blocks
        reserve_results = []
        reserve_results_by_key = {}
        reserve_domains_seen = set()
        trying_alternative_block = False
        alternative_failed = False

        while len(results) < limit and iteration < max_iterations:
            iteration += 1

            # Build list for block calculation (exclude failed products)
            products_for_blocks = [
                p for p in all_products
                if f"{p.title}_{p.extracted_price}" not in failed_product_keys
            ]

            if not products_for_blocks:
                logger.info(f"  No products remaining after iteration {iteration}")
                break

            # Recalculate blocks
            current_blocks, total_blocks = self._create_variation_blocks(
                products_for_blocks, variacao_maxima, min_block_size=1
            )

            if not current_blocks:
                logger.info(f"  No valid blocks remaining after iteration {iteration}")
                break

            # Get valid product keys
            valid_keys = set(results_by_key.keys())
            needed = limit - len(results)

            # Separate blocks into categories:
            # 1. Blocks containing ALL valid products with enough untried to reach N
            # 2. Blocks containing ALL valid products (but not enough untried)
            # 3. Blocks without all valid products but with >= N products

            blocks_with_all_valid_and_enough = []
            blocks_with_all_valid_not_enough = []
            blocks_without_valid_but_big = []

            for blk in current_blocks:
                block_keys = {f"{p.title}_{p.extracted_price}" for p in blk}
                valid_in_block = len(valid_keys & block_keys)
                contains_all_valid = valid_in_block == len(valid_keys) if valid_keys else True
                untried_in_block = len([p for p in blk if f"{p.title}_{p.extracted_price}" not in valid_keys])

                if contains_all_valid:
                    if untried_in_block >= needed - valid_in_block or len(blk) >= limit:
                        blocks_with_all_valid_and_enough.append(blk)
                    else:
                        blocks_with_all_valid_not_enough.append(blk)
                elif len(blk) >= limit:
                    blocks_without_valid_but_big.append(blk)

            # Sort each category by (more products, lower price)
            sort_key = lambda b: (-len(b), b[0].extracted_price)
            blocks_with_all_valid_and_enough.sort(key=sort_key)
            blocks_with_all_valid_not_enough.sort(key=sort_key)
            blocks_without_valid_but_big.sort(key=sort_key)

            # Decision logic
            block = None

            if blocks_with_all_valid_and_enough:
                # Best case: block with all valid and enough untried
                block = blocks_with_all_valid_and_enough[0]
                logger.info(f"  Using block with all {len(valid_keys)} valid products + untried")
            elif blocks_with_all_valid_not_enough and not trying_alternative_block:
                # Block with valid but not enough untried - check if we should try alternative
                if blocks_without_valid_but_big and not alternative_failed:
                    # Save current as reserve and try alternative block
                    logger.info(f"  Block with valid products doesn't have enough untried. Saving as reserve and trying alternative.")
                    reserve_results = list(results)
                    reserve_results_by_key = dict(results_by_key)
                    reserve_domains_seen = set(domains_seen)

                    # Clear current results to try fresh block
                    results = []
                    results_by_key = {}
                    domains_seen = set()
                    trying_alternative_block = True

                    block = blocks_without_valid_but_big[0]
                    logger.info(f"  Trying alternative block with {len(block)} products")
                else:
                    # No alternative or alternative already failed - use what we have
                    block = blocks_with_all_valid_not_enough[0]
                    logger.info(f"  Using block with valid products (limited options)")
            elif trying_alternative_block and blocks_without_valid_but_big:
                # Continue with alternative block
                block = blocks_without_valid_but_big[0]
            else:
                # Fallback: any available block
                all_sorted = sorted(current_blocks, key=sort_key)
                if all_sorted:
                    block = all_sorted[0]
                    logger.info(f"  Using fallback block")

            if not block:
                logger.info(f"  No suitable block found")
                break

            search_log.blocks_tried += 1
            block_min_price = block[0].extracted_price
            block_max_price = block[-1].extracted_price
            block_keys = {f"{p.title}_{p.extracted_price}" for p in block}
            valid_in_block = len(valid_keys & block_keys)

            logger.info(
                f"Step 7 (iteration {iteration}): Block with "
                f"{len(block)} products (R$ {block_min_price:.2f} - R$ {block_max_price:.2f}), "
                f"{valid_in_block} valid, need {needed} more"
            )

            block_results_count = 0
            block_skipped = {
                "blocked_domain": [], "foreign_domain": [], "duplicate_domain": [],
                "listing_url": [], "no_store_link": [], "price_mismatch": [],
                "reused_valid": []
            }
            new_failures = []

            for product in block:
                if len(results) >= limit:
                    break

                product_key = f"{product.title}_{product.extracted_price}"

                # Check if this product already has a valid result
                if product_key in results_by_key:
                    store_result = results_by_key[product_key]
                    if store_result.domain not in domains_seen:
                        domains_seen.add(store_result.domain)
                        results.append(store_result)
                        block_results_count += 1
                        block_skipped["reused_valid"].append(store_result.domain)
                        logger.info(
                            f"    ✓ Reused [{len(results)}/{limit}]: "
                            f"{store_result.store_name or store_result.domain} "
                            f"- R$ {store_result.extracted_price}"
                        )
                    continue

                if product_key in failed_product_keys:
                    continue

                logger.info(
                    f"  Getting store link for '{product.title[:40]}...' "
                    f"(R$ {product.extracted_price}) from {product.source}"
                )

                store_result = await self._get_store_link(product)
                immersive_calls += 1

                if not store_result:
                    block_skipped["no_store_link"].append(product.source)
                    logger.info(f"    ↳ Skipped: no store link found")
                    new_failures.append(product_key)
                    continue

                if self._is_blocked_domain(store_result.domain):
                    block_skipped["blocked_domain"].append(store_result.domain)
                    logger.info(f"    ↳ Skipped: blocked domain '{store_result.domain}'")
                    new_failures.append(product_key)
                    continue

                if self._is_foreign_domain(store_result.domain):
                    block_skipped["foreign_domain"].append(store_result.domain)
                    logger.info(f"    ↳ Skipped: foreign domain '{store_result.domain}'")
                    new_failures.append(product_key)
                    continue

                if store_result.domain in domains_seen:
                    block_skipped["duplicate_domain"].append(store_result.domain)
                    logger.info(f"    ↳ Skipped: duplicate domain '{store_result.domain}'")
                    new_failures.append(product_key)
                    continue

                if self._is_listing_url(store_result.url):
                    block_skipped["listing_url"].append(store_result.url[:50])
                    logger.info(f"    ↳ Skipped: listing URL")
                    new_failures.append(product_key)
                    continue

                # Success!
                domains_seen.add(store_result.domain)
                results.append(store_result)
                results_by_key[product_key] = store_result
                block_results_count += 1
                logger.info(
                    f"    ✓ Added [{len(results)}/{limit}]: "
                    f"{store_result.store_name or store_result.domain} "
                    f"- R$ {store_result.extracted_price}"
                )

            # Update failures
            failed_product_keys.update(new_failures)

            # Record block details
            block_detail = {
                "iteration": iteration,
                "size": len(block),
                "min_price": float(block_min_price),
                "max_price": float(block_max_price),
                "results_obtained": block_results_count,
                "total_results_so_far": len(results),
                "valid_reused": len(block_skipped["reused_valid"]),
                "new_failures": len(new_failures),
                "total_failed": len(failed_product_keys),
                "trying_alternative": trying_alternative_block,
                "skipped": {k: len(v) for k, v in block_skipped.items() if v and k != "reused_valid"}
            }

            # Check results
            if len(results) >= limit:
                logger.info(f"  ✓ SUCCESS: Got {len(results)} quotes after {iteration} iterations")
                block_detail["result"] = "success"
                search_log.block_details.append(block_detail)
                search_log.successful_block_index = iteration
                break
            elif trying_alternative_block and new_failures:
                # Alternative block had a failure - return to reserve
                logger.info(f"  Alternative block failed. Returning to reserve ({len(reserve_results)} results)")
                results = reserve_results
                results_by_key = reserve_results_by_key
                domains_seen = reserve_domains_seen
                trying_alternative_block = False
                alternative_failed = True
                block_detail["result"] = "alternative_failed_returning_to_reserve"
                search_log.block_details.append(block_detail)
            elif not new_failures and block_results_count == 0:
                logger.info(f"  ✗ No progress in iteration {iteration}")
                block_detail["result"] = "stuck"
                search_log.block_details.append(block_detail)
                break
            else:
                logger.info(
                    f"  → Iteration {iteration}: {len(results)}/{limit} quotes, "
                    f"{len(all_products) - len(failed_product_keys)} products remaining"
                )
                block_detail["result"] = "partial"
                search_log.block_details.append(block_detail)

        # Finalize search log
        search_log.immersive_api_calls = immersive_calls
        search_log.results_obtained = len(results)

        logger.info(
            f"=== Search complete: {len(results)} results "
            f"(target: {limit}, used {immersive_calls} Immersive API calls) ==="
        )
        return results, search_log

    def _create_variation_blocks(
        self,
        products: List[ShoppingProduct],
        variacao_maxima: float,
        min_block_size: int = 1
    ) -> Tuple[List[List[ShoppingProduct]], int]:
        """
        Create variation blocks using sliding window approach.

        Each block starts from a different product and includes all consecutive
        products that are within the variation limit relative to the first product.

        Example with variacao_maxima=25% and products [100, 102, 104, 110, 125, 130, 140, 150]:
        - Block 1 starts at 100: includes 100, 102, 104, 110, 125 (125/100-1 = 25% ≤ 25%)
        - Block 2 starts at 102: includes 102, 104, 110, 125 (125/102-1 = 22.5% ≤ 25%)
        - Block 3 starts at 104: includes 104, 110, 125, 130 (130/104-1 = 25% ≤ 25%)
        - ... and so on

        Args:
            products: Sorted list of products (by price, ascending)
            variacao_maxima: Maximum allowed variation (e.g., 0.25 = 25%)
            min_block_size: Minimum number of products required in a block (default: 1)

        Returns:
            Tuple of (valid_blocks, total_blocks_created)
        """
        if not products:
            return [], 0

        # Ensure products are sorted by price
        sorted_products = sorted(products, key=lambda x: x.extracted_price)

        # Filter out products with invalid prices
        sorted_products = [p for p in sorted_products if p.extracted_price and p.extracted_price > 0]

        if not sorted_products:
            return [], 0

        blocks = []
        total_blocks_created = 0

        for start_idx, start_product in enumerate(sorted_products):
            min_price = start_product.extracted_price
            max_allowed_price = min_price * (1 + variacao_maxima)

            # Build block: include all consecutive products within variation limit
            block = []
            for product in sorted_products[start_idx:]:
                if product.extracted_price <= max_allowed_price:
                    block.append(product)
                else:
                    break  # Stop as soon as we exceed the variation limit

            total_blocks_created += 1

            # Only add blocks that meet the minimum size requirement
            if len(block) >= min_block_size:
                blocks.append(block)

        logger.info(
            f"    Created {len(blocks)} valid blocks (min size: {min_block_size}) "
            f"from {total_blocks_created} total blocks, {len(sorted_products)} products"
        )
        return blocks, total_blocks_created

    async def _search_google_shopping_raw(self, query: str) -> List[ShoppingProduct]:
        """
        ONE Google Shopping API call - returns ALL products without filtering.
        Filtering is done in the main search_products method.

        Parameters:
        - num=100: Get maximum products from Google Shopping API
        - No filtering here - all filtering is done in search_products
        """
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "gl": "br",
            "hl": "pt-br",
            "google_domain": "google.com.br",
            "location": self.location,
            "num": 100,  # Google Shopping max per request
        }

        logger.info(f"API Call: Google Shopping - '{query}'")

        # Build full URL for logging (include all relevant params except api_key)
        search_url = f"{self.base_url}?engine={params['engine']}&q={params['q']}&gl={params['gl']}&hl={params['hl']}&google_domain={params['google_domain']}&location={params['location']}&num={params['num']}"

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(self.base_url, params=params)

                    if response.status_code == 429:
                        if attempt < MAX_RETRIES - 1:
                            backoff = INITIAL_BACKOFF * (2 ** attempt)
                            logger.warning(f"Rate limited. Retry in {backoff}s ({attempt + 1}/{MAX_RETRIES})")
                            await asyncio.sleep(backoff)
                            continue
                        logger.error("Rate limit exceeded")
                        return []

                    response.raise_for_status()
                    data = response.json()

                # Register the API call
                self.api_calls_made.append({
                    "api_used": "google_shopping",
                    "search_url": search_url,
                    "activity": f"Busca inicial no Google Shopping: {query}",
                    "product_link": None  # N/A for initial search
                })

                products = []

                # Process shopping_results - NO filtering here, just collect all
                shopping_results = data.get("shopping_results", [])
                logger.info(f"  → Raw shopping_results count: {len(shopping_results)}")

                for item in shopping_results:
                    immersive_url = item.get("serpapi_immersive_product_api")

                    products.append(ShoppingProduct(
                        title=item.get("title", ""),
                        price=item.get("price", ""),
                        extracted_price=item.get("extracted_price"),
                        source=item.get("source", ""),
                        serpapi_immersive_product_api=immersive_url,
                        product_link=item.get("product_link"),
                        link=item.get("link"),
                    ))

                # Process inline_shopping_results - NO filtering here
                inline_results = data.get("inline_shopping_results", [])
                logger.info(f"  → Raw inline_shopping_results count: {len(inline_results)}")

                for item in inline_results:
                    products.append(ShoppingProduct(
                        title=item.get("title", ""),
                        price=item.get("price", ""),
                        extracted_price=item.get("extracted_price"),
                        source=item.get("source", ""),
                        serpapi_immersive_product_api=None,
                        product_link=None,
                        link=item.get("link"),
                    ))

                logger.info(f"  → Total: {len(products)} raw products from Google Shopping")
                return products

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF * (2 ** attempt)
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"HTTP error: {e}")
                return []
            except Exception as e:
                logger.error(f"Error: {e}")
                return []

        return []

    async def _get_store_link(self, product: ShoppingProduct) -> Optional[SearchResult]:
        """
        Get direct store link for a product.

        Priority:
        1. Call serpapi_immersive_product_api to get store link
        2. Fallback to direct link from shopping results (product_link or link)
        """
        # Log available options
        has_immersive = "Yes" if product.serpapi_immersive_product_api else "No"
        logger.info(f"  immersive_api: {has_immersive}, link: {product.link}")

        # Priority 1: Use Immersive API to get the actual store link
        if product.serpapi_immersive_product_api:
            result = await self._call_immersive_api(product)
            if result:
                return result
            logger.info(f"  Immersive API returned no store link, trying fallback...")

        # Priority 2: Fallback to direct link if available
        direct_link = product.product_link or product.link
        if direct_link and "google.com" not in direct_link:
            # Limpar parâmetros de rastreamento que podem causar redirecionamentos
            cleaned_url = self._clean_tracking_params(direct_link)
            domain = self._extract_domain(cleaned_url)
            logger.info(f"  Using fallback direct link: {cleaned_url[:80]}...")
            return SearchResult(
                url=cleaned_url,
                title=product.title,
                domain=domain,
                snippet=product.source,
                price=product.price,
                extracted_price=Decimal(str(product.extracted_price)) if product.extracted_price else None,
                store_name=product.source
            )

        logger.warning(f"  No store link found for '{product.title[:40]}...'")
        return None

    async def _call_immersive_api(self, product: ShoppingProduct) -> Optional[SearchResult]:
        """
        Call Google Immersive Product API using the full URL from serpapi_immersive_product_api.
        This URL already contains all necessary parameters including api_key.
        """
        if not product.serpapi_immersive_product_api:
            return None

        logger.info(f"  API Call: Immersive Product (using full URL)")

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # The serpapi_immersive_product_api URL doesn't include api_key, so we need to add it
                    url = product.serpapi_immersive_product_api
                    separator = "&" if "?" in url else "?"
                    url_with_key = f"{url}{separator}api_key={self.api_key}"

                    response = await client.get(url_with_key)

                    if response.status_code == 429:
                        if attempt < MAX_RETRIES - 1:
                            backoff = INITIAL_BACKOFF * (2 ** attempt)
                            logger.warning(f"  Rate limited. Retry in {backoff}s")
                            await asyncio.sleep(backoff)
                            continue
                        logger.error("  Rate limit exceeded on Immersive API")
                        return None

                    response.raise_for_status()
                    data = response.json()

                # Register the API call (product_link will be updated when we find a valid store)
                api_call_entry = {
                    "api_used": "google_immersive_product",
                    "search_url": url_with_key.replace(self.api_key, "***"),  # Hide API key in logs
                    "activity": f"Busca de loja para produto: {product.title[:50]}...",
                    "product_link": None  # Will be set when a store is found
                }
                self.api_calls_made.append(api_call_entry)

                # Log available keys for debugging
                logger.info(f"  → Immersive API response keys: {list(data.keys())}")

                # The stores array is inside product_results
                product_results = data.get("product_results", {})
                stores = product_results.get("stores", [])
                logger.info(f"  → Got {len(stores)} stores from product_results")

                for store in stores:
                    url = store.get("link", "")

                    if not url or "google.com" in url:
                        continue

                    domain = self._extract_domain(url)
                    store_name = store.get("name", "")
                    store_price = store.get("price", "")

                    # Obter preço da loja
                    store_extracted = store.get("extracted_price") or store.get("base_price")

                    # Validar preço da loja contra preço do Google Shopping
                    # Se diferença > 5%, produto FALHA (PRICE_MISMATCH)
                    if store_extracted and product.extracted_price:
                        price_diff_percent = abs(float(store_extracted) - float(product.extracted_price)) / float(product.extracted_price) * 100
                        if price_diff_percent > 5:
                            logger.info(f"    ↳ PRICE_MISMATCH store {store_name}: R$ {store_extracted} vs Google R$ {product.extracted_price} (diff: {price_diff_percent:.1f}%)")
                            continue

                    final_price = store_extracted or product.extracted_price

                    # Limpar parâmetros de rastreamento que podem causar redirecionamentos
                    cleaned_url = self._clean_tracking_params(url)

                    # Update the product_link in the last api_call_entry
                    if self.api_calls_made:
                        self.api_calls_made[-1]["product_link"] = cleaned_url

                    return SearchResult(
                        url=cleaned_url,
                        title=product.title,
                        domain=domain,
                        snippet=store_name,
                        price=store_price or product.price,
                        extracted_price=Decimal(str(final_price)) if final_price else None,
                        store_name=store_name
                    )

                # Try online_sellers as fallback (some products use this instead of stores)
                sellers = data.get("online_sellers", [])
                if sellers:
                    logger.info(f"  → Trying online_sellers: {len(sellers)} sellers")
                    for seller in sellers:
                        url = seller.get("link", "") or seller.get("direct_link", "")
                        if not url or "google.com" in url:
                            continue

                        domain = self._extract_domain(url)
                        seller_name = seller.get("name", "")
                        seller_price = seller.get("base_price", "") or seller.get("price", "")

                        # Obter preço do seller
                        seller_extracted = seller.get("extracted_price") or seller.get("base_price")

                        # Validar preço do seller contra preço do Google Shopping
                        # Se diferença > 5%, produto FALHA (PRICE_MISMATCH)
                        if seller_extracted and product.extracted_price:
                            price_diff_percent = abs(float(seller_extracted) - float(product.extracted_price)) / float(product.extracted_price) * 100
                            if price_diff_percent > 5:
                                logger.info(f"    ↳ PRICE_MISMATCH seller {seller_name}: R$ {seller_extracted} vs Google R$ {product.extracted_price} (diff: {price_diff_percent:.1f}%)")
                                continue

                        final_price = seller_extracted or product.extracted_price

                        # Limpar parâmetros de rastreamento que podem causar redirecionamentos
                        cleaned_url = self._clean_tracking_params(url)

                        # Update the product_link in the last api_call_entry
                        if self.api_calls_made:
                            self.api_calls_made[-1]["product_link"] = cleaned_url

                        return SearchResult(
                            url=cleaned_url,
                            title=product.title,
                            domain=domain,
                            snippet=seller_name,
                            price=seller_price or product.price,
                            extracted_price=Decimal(str(final_price)) if final_price else None,
                            store_name=seller_name
                        )

                # Try product_results as another fallback
                product_results = data.get("product_results", {})
                if product_results:
                    direct_link = product_results.get("link", "")
                    if direct_link and "google.com" not in direct_link:
                        logger.info(f"  → Using product_results link")

                        # Limpar parâmetros de rastreamento que podem causar redirecionamentos
                        cleaned_url = self._clean_tracking_params(direct_link)
                        domain = self._extract_domain(cleaned_url)

                        # Update the product_link in the last api_call_entry
                        if self.api_calls_made:
                            self.api_calls_made[-1]["product_link"] = cleaned_url

                        return SearchResult(
                            url=cleaned_url,
                            title=product.title,
                            domain=domain,
                            snippet=product.source,
                            price=product.price,
                            extracted_price=Decimal(str(product.extracted_price)) if product.extracted_price else None,
                            store_name=product.source
                        )

                return None

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                    backoff = INITIAL_BACKOFF * (2 ** attempt)
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"  Immersive API error: {e}")
                return None
            except Exception as e:
                logger.error(f"  Immersive API error: {e}")
                return None

        return None

    def _clean_tracking_params(self, url: str) -> str:
        """Remove tracking parameters from URL that can cause redirect issues"""
        if not url:
            return url

        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        try:
            parsed = urlparse(url)

            # Parâmetros de rastreamento do Google e outros que podem causar problemas
            tracking_params = [
                'srsltid',  # Google Shopping tracking
                'pf', 'mc',  # Tracking genérico
                'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
                'gclid', 'fbclid', 'ref', 'ref_',
                '_ga', '_gl', 'dclid',
            ]

            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=True)
                # Remover parâmetros de rastreamento
                cleaned_params = {
                    k: v for k, v in params.items()
                    if k.lower() not in tracking_params
                }
                # Reconstruir URL
                new_query = urlencode(cleaned_params, doseq=True)
                cleaned_url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    new_query,
                    parsed.fragment
                ))
                return cleaned_url

            return url
        except Exception as e:
            logger.warning(f"Error cleaning URL params: {e}")
            return url

    def _is_listing_url(self, url: str) -> bool:
        """Check if URL is a search/listing page rather than a product page"""
        if not url:
            return True

        url_lower = url.lower()

        listing_patterns = [
            "/busca/", "/busca?", "/search/", "/search?",
            "/s?", "/s/", "?q=", "&q=", "query=",
            "/pesquisa/", "/pesquisa?", "/resultado",
            "/categoria/", "/categorias/", "/category/",
            "/colecao/", "/collection/", "/produtos?",
            "/list/", "/listing/", "/browse/",
            "buscape.com.br", "zoom.com.br", "bondfaro.com.br",
            "/compare/", "/comparar/", "/ofertas?"
        ]

        for pattern in listing_patterns:
            if pattern in url_lower:
                return True

        if re.search(r'/(notebooks|celulares|eletronicos|informatica|tv|audio)/?(\?|$)', url_lower):
            return True

        return False

    def _is_blocked_domain(self, domain: str) -> bool:
        """Check if domain is in the blocked list (anti-bot protection sites)"""
        if not domain:
            return False

        domain_lower = domain.lower()

        # Check exact match or subdomain match
        for blocked in BLOCKED_DOMAINS:
            if domain_lower == blocked or domain_lower.endswith("." + blocked):
                return True

        return False

    def _is_foreign_domain(self, domain: str) -> bool:
        """Check if domain is from a foreign country (not Brazilian)"""
        if not domain:
            return False

        domain_lower = domain.lower()

        # Allow Brazilian domains
        if domain_lower.endswith(".com.br") or domain_lower.endswith(".br"):
            return False

        # Allow specific foreign domains (major manufacturers that sell in Brazil)
        if domain_lower in ALLOWED_FOREIGN_DOMAINS:
            return False

        # Check for foreign TLDs
        for pattern in FOREIGN_DOMAIN_PATTERNS:
            # Make sure we're checking the TLD, not part of the domain name
            if domain_lower.endswith(pattern) and not domain_lower.endswith(".com.br"):
                return True

        return False

    def _is_blocked_source(self, source: str) -> bool:
        """
        Check if the source (from Google Shopping results) matches a blocked domain.
        This filters products early, before making Immersive API calls.

        Args:
            source: The 'source' field from Google Shopping (e.g., "Mercado Livre", "Amazon.com.br")

        Returns:
            True if the source is blocked, False otherwise
        """
        if not source:
            return False

        source_lower = source.lower()

        # Map common source names to their domains
        source_to_domain_map = {
            "mercado livre": "mercadolivre.com.br",
            "mercadolivre": "mercadolivre.com.br",
            "amazon": "amazon.com.br",
            "amazon.com.br": "amazon.com.br",
            "shopee": "shopee.com.br",
            "aliexpress": "aliexpress.com",
            "shein": "shein.com",
            "wish": "wish.com",
            "temu": "temu.com",
            "carrefour": "carrefour.com.br",
            "casas bahia": "casasbahia.com.br",
            "ponto frio": "pontofrio.com.br",
            "extra": "extra.com.br",
            "magazine luiza": "magazineluiza.com.br",
            "magalu": "magalu.com.br",
            "americanas": "americanas.com.br",
            "submarino": "submarino.com.br",
            "shoptime": "shoptime.com.br",
        }

        # Check if the source matches any blocked domain mapping
        for source_name, domain in source_to_domain_map.items():
            if source_name in source_lower:
                # Check if this domain is in the blocked list
                if domain in BLOCKED_DOMAINS:
                    return True

        # Also check if the source directly contains a blocked domain
        for blocked_domain in BLOCKED_DOMAINS:
            # Extract base domain name (e.g., "mercadolivre" from "mercadolivre.com.br")
            base_name = blocked_domain.split('.')[0]
            if base_name in source_lower:
                return True

        return False

    def _extract_domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return ""
