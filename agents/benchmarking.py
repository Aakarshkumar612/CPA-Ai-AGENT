"""
Market Benchmarking Agent — Compares invoice prices against market freight rates.

What it does:
1. For each line item in an invoice, identifies the shipping route (e.g., Shanghai → LA)
2. Fetches the current market rate for that route via FreightRateService
3. Compares invoice price vs. market average
4. Flags items that are >15% over market rate

Architecture:
    BenchmarkingAgent
         │
         ├── uses FreightRateService (interface)
         │       │
         │       ├── MockApifyService (fake data — default, free)
         │       └── ApifyFreightRateService (real Apify scraping)
         │
         └── Strategy Pattern: swap by changing USE_MOCK_APIFY in .env

Why the service abstraction?
- Agent code never changes when we swap data sources
- Testing is easy: always inject MockApifyService
- Production: just set USE_MOCK_APIFY=false in .env
"""

import json
import logging
from typing import Optional
from groq import Groq

from models.pydantic_models import InvoiceData, LineItem, BenchmarkResult
from utils.freight_rate_service import create_rate_service, FreightRateService
from utils.cache import get_llm_cache
from utils.retry import retry_function
from utils.settings import settings

logger = logging.getLogger(__name__)

_ROUTE_EXTRACTION_PROMPT = """You are a shipping logistics assistant.
Given a line item description and optional incoterms, extract the shipping route.

Respond ONLY with a JSON object:
{"origin": "City Name", "destination": "City Name"}

If you cannot determine origin or destination, use null.
Do NOT add markdown or extra text."""


class BenchmarkingAgent:
    """
    Benchmarks invoice prices against market freight rates.
    
    Usage:
        agent = BenchmarkingAgent(use_mock=True)
        results = agent.benchmark(invoice_data)
        for r in results:
            print(f"{r.route}: invoice=${r.invoice_price}, market=${r.market_average}")
    """

    def __init__(
        self,
        use_mock: Optional[bool] = None,
        threshold_percent: Optional[float] = None,
        rate_service: Optional[FreightRateService] = None,
    ):
        """
        Args:
            use_mock: If True, use mock rates. If None, reads from .env.
            threshold_percent: Deviation threshold for flagging (default 15%)
            rate_service: Optional pre-built service (for dependency injection in tests).
                          If None, created automatically via factory.
        """
        self.threshold_percent = threshold_percent

        self.threshold_percent = threshold_percent if threshold_percent is not None else settings.BENCHMARK_THRESHOLD_PERCENT

        if rate_service is not None:
            self.rate_service = rate_service
        else:
            self.rate_service = create_rate_service(use_mock=use_mock)

        self._groq_client = Groq(api_key=settings.GROQ_API_KEY)
        self._llm_cache = get_llm_cache()

        logger.info(
            "BenchmarkingAgent initialized (service=%s, threshold=%.1f%%)",
            type(self.rate_service).__name__,
            self.threshold_percent,
        )

    def _extract_route_via_llm(self, description: str, incoterms: str | None) -> str:
        """
        Use Groq to extract the shipping route from a line item description.

        Only called when the heuristic finds no recognisable city names.
        Response is cached so the same description never triggers a second API call.

        Returns:
            Route string like "Shanghai -> Los Angeles", or "Unknown Route"
        """
        user_prompt = f"Line item: {description}\nIncoterms: {incoterms or 'not specified'}"

        # Check LLM cache first
        cached = self._llm_cache.get(settings.GROQ_MODEL, _ROUTE_EXTRACTION_PROMPT, user_prompt)
        if cached is not None:
            try:
                data = json.loads(cached)
                origin = data.get("origin")
                destination = data.get("destination")
                if origin and destination:
                    return f"{origin} -> {destination}"
            except (json.JSONDecodeError, AttributeError):
                pass
            return "Unknown Route"

        try:
            response = retry_function(
                lambda: self._groq_client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": _ROUTE_EXTRACTION_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=60,
                ),
                max_retries=2,
                backoff_base=1.0,
            )

            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            # Cache the raw response
            self._llm_cache.set(settings.GROQ_MODEL, _ROUTE_EXTRACTION_PROMPT, user_prompt, raw)

            data = json.loads(raw)
            origin = data.get("origin")
            destination = data.get("destination")
            if origin and destination:
                logger.debug("LLM route extraction: '%s' -> '%s'", origin, destination)
                return f"{origin} -> {destination}"

        except Exception as e:
            logger.debug("LLM route extraction failed: %s", e)

        return "Unknown Route"

    def _extract_route_from_line_item(self, item: LineItem, invoice: InvoiceData) -> str:
        """
        Guess the shipping route from line item description + invoice incoterms.
        
        This is a simple heuristic. In production, you'd use an LLM to parse routes.
        
        Args:
            item: The line item being analyzed
            invoice: The parent invoice (has incoterms info)
            
        Returns:
            Route string like "Shanghai -> Los Angeles"
        """
        description = item.description.lower()

        # Try to find origin/destination in the description
        cities = [
            "shanghai", "ningbo", "shenzhen", "qingdao", "hong kong",
            "singapore", "busan", "tokyo", "mumbai",
            "los angeles", "long beach", "new york", "seattle",
            "rotterdam", "hamburg",
        ]

        found_cities = [city.title() for city in cities if city in description]

        if len(found_cities) >= 2:
            return f"{found_cities[0]} -> {found_cities[1]}"

        # Try to extract from incoterms (origin defaults to Shanghai if not in description)
        if invoice.incoterms:
            port = invoice.incoterms.split()[-1].lower().strip(".,")
            port_title = port.title()
            if len(found_cities) == 1:
                return f"{found_cities[0]} -> {port_title}"
            return f"Shanghai -> {port_title}"

        # Heuristic failed — ask the LLM
        logger.debug(
            "Heuristic found no route in '%s' — falling back to LLM extraction",
            item.description,
        )
        return self._extract_route_via_llm(item.description, invoice.incoterms)

    def benchmark_line_item(self, item: LineItem, invoice: InvoiceData) -> BenchmarkResult:
        """
        Benchmark a single line item against market rates.
        
        Steps:
        1. Identify the shipping route from the item description
        2. Get market rate (mock or Apify)
        3. Compare invoice unit_price vs market average
        4. Calculate deviation percentage
        
        Args:
            item: The line item to benchmark
            invoice: Parent invoice for route context
            
        Returns:
            BenchmarkResult with comparison data
        """
        route = self._extract_route_from_line_item(item, invoice)

        # Get market rate from the injected service (mock or real)
        market_avg = self.rate_service.get_rate(route)

        # Calculate deviation
        if market_avg > 0:
            deviation = ((item.unit_price - market_avg) / market_avg) * 100
        else:
            deviation = 0.0

        deviation = round(deviation, 2)
        is_overpriced = deviation > self.threshold_percent

        logger.info(
            "Benchmark [%s]: invoice=$%.2f vs market=$%.2f (%+.1f%%) %s",
            route,
            item.unit_price,
            market_avg,
            deviation,
            "⚠️ OVERPRICED" if is_overpriced else "✅ OK",
        )

        return BenchmarkResult(
            route=route,
            invoice_price=item.unit_price,
            market_average=market_avg,
            deviation_percent=deviation,
            is_overpriced=is_overpriced,
        )

    def benchmark(self, invoice: InvoiceData) -> list[BenchmarkResult]:
        """
        Benchmark all line items in an invoice against market rates.
        
        Args:
            invoice: The full invoice to benchmark
            
        Returns:
            List of BenchmarkResult — one per line item
        """
        logger.info(
            "Benchmarking invoice: vendor=%s, number=%s, %d line items",
            invoice.vendor_name,
            invoice.invoice_number,
            len(invoice.line_items),
        )

        results = []
        for item in invoice.line_items:
            # Only benchmark freight/shipping related items
            if any(
                keyword in item.description.lower()
                for keyword in ["freight", "ocean", "shipping", "container", "cargo"]
            ):
                result = self.benchmark_line_item(item, invoice)
                results.append(result)

        if not results:
            logger.info("No freight line items found to benchmark")

        return results
