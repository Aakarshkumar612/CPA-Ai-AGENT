"""
Extraction Agent — Converts PDF invoices into structured data.

What it does:
1. Uses Docling to parse the PDF into structured markdown (preserves tables!)
2. Sends the markdown to Groq LLM with a prompt to extract specific fields
3. Returns validated InvoiceData (Pydantic model)

Why Docling + LLM (not just LLM)?
- LLMs can't read PDFs directly — they need text input
- Simple text extractors lose table structure (line items become garbled)
- Docling preserves tables as markdown → LLM reads clean structured data
- This two-step approach is cheaper and more accurate than sending raw PDF bytes

Why not just regex?
- Invoice formats vary wildly between vendors
- Regex breaks when vendor changes layout
- LLMs understand semantic meaning ("this number is the total") regardless of layout
"""

import json
import logging
from pathlib import Path
from typing import Optional
from groq import Groq
from docling.document_converter import DocumentConverter

from models.pydantic_models import InvoiceData, LineItem
from utils.cache import get_docling_cache, get_llm_cache
from utils.retry import retry_function
from utils.settings import settings

logger = logging.getLogger(__name__)

# System prompt instructs the LLM on exactly what fields to extract
EXTRACTION_SYSTEM_PROMPT = """You are an expert invoice data extraction specialist.

Given the text/markdown content of a shipping/logistics invoice, extract the following fields:

REQUIRED FIELDS:
- vendor_name: Name of the vendor/supplier company
- invoice_number: The unique invoice identifier (e.g., "INV-2024-0042")
- invoice_date: Date the invoice was issued (format: YYYY-MM-DD)
- currency: Currency code (e.g., "USD", "EUR", "CNY") — default "USD"
- incoterms: Shipping incoterms if present (e.g., "FOB Shanghai", "CIF Los Angeles") — null if not found
- line_items: Array of line items, each with:
  - description: What the charge is for
  - quantity: Number of units
  - unit_price: Price per single unit
  - total: Total for this line item (quantity × unit_price)
- total_amount: The grand total of the invoice

IMPORTANT:
- Extract numbers as plain floats (no currency symbols, no commas): 1500.00 not "$1,500.00"
- If a field cannot be found, use null (not "N/A" or "unknown")
- Respond ONLY with a valid JSON object — no markdown fences, no extra text
- Double-check that the sum of line item totals is close to the invoice total

JSON FORMAT:
{
    "vendor_name": "...",
    "invoice_number": "...",
    "invoice_date": "YYYY-MM-DD",
    "currency": "USD",
    "incoterms": "...",
    "line_items": [
        {"description": "...", "quantity": 20, "unit_price": 1500.0, "total": 30000.0}
    ],
    "total_amount": 35650.0
}"""


class ExtractionAgent:
    """
    Extracts structured data from PDF invoices using Docling + Groq LLM.
    
    Usage:
        agent = ExtractionAgent()
        invoice_data = agent.extract_from_pdf("input_docs/invoice.pdf")
        print(invoice_data.vendor_name)
        print(invoice_data.total_amount)
    """

    def __init__(self, model: str | None = None, use_cache: bool = True):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = model or settings.GROQ_MODEL
        self.docling_converter = DocumentConverter()
        self.use_cache = use_cache
        self.docling_cache = get_docling_cache() if use_cache else None
        self.llm_cache = get_llm_cache() if use_cache else None
        logger.info("ExtractionAgent initialized with model: %s (cache=%s)", self.model, use_cache)

    def parse_pdf_to_markdown(self, pdf_path: str) -> str:
        """
        Use Docling to convert a PDF file to structured markdown.
        
        Checks cache first — if the PDF hasn't changed, returns cached result.
        This saves 3-5 seconds per PDF on re-runs.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Markdown string representation of the PDF
        """
        logger.info("Parsing PDF to markdown: %s", pdf_path)

        # Check cache first
        if self.docling_cache:
            cached = self.docling_cache.get(pdf_path)
            if cached is not None:
                logger.info("Docling cache HIT for %s (skipping parse)", Path(pdf_path).name)
                return cached

        try:
            result = self.docling_converter.convert(
                source=Path(pdf_path),
            )
            markdown = result.document.export_to_markdown()
            logger.info(
                "Docling extracted %d characters from %s",
                len(markdown), Path(pdf_path).name,
            )

            # Store in cache
            if self.docling_cache:
                self.docling_cache.set(pdf_path, markdown)

            return markdown

        except Exception as e:
            logger.error("Docling failed to parse %s: %s", pdf_path, e)
            raise

    def extract_from_markdown(self, markdown: str, filename: str) -> InvoiceData:
        """
        Use Groq LLM to extract structured fields from markdown text.
        
        Checks LLM cache first — same markdown + same prompts = cached response.
        This saves API costs on re-runs.
        
        Args:
            markdown: The markdown text from Docling
            filename: Original filename (for logging)
            
        Returns:
            InvoiceData — validated and structured invoice
        """
        logger.info("Extracting structured data from: %s", filename)

        # Check LLM cache first
        if self.llm_cache:
            cached_response = self.llm_cache.get(
                self.model, EXTRACTION_SYSTEM_PROMPT, markdown
            )
            if cached_response is not None:
                logger.info("LLM cache HIT for %s (skipping API call)", filename)
                raw_text = cached_response
                return self._parse_llm_response(raw_text, filename)

        try:
            response = retry_function(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Extract data from this invoice:\n\n{markdown}"},
                    ],
                    temperature=0.1,
                    max_tokens=2000,
                ),
                max_retries=3,
                backoff_base=2.0,
            )

            raw_text = response.choices[0].message.content.strip()

            # Cache the response
            if self.llm_cache:
                self.llm_cache.set(
                    self.model, EXTRACTION_SYSTEM_PROMPT, markdown, raw_text
                )

            return self._parse_llm_response(raw_text, filename)

        except Exception as e:
            logger.error("Extraction failed for %s: %s", filename, e)
            raise

    def _parse_llm_response(self, raw_text: str, filename: str) -> InvoiceData:
        """Parse and validate LLM response text as InvoiceData."""
        # Handle markdown code fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        extracted_dict = json.loads(raw_text)
        
        # Validate with Pydantic — this catches missing/invalid fields
        invoice_data = InvoiceData(**extracted_dict)

        logger.info(
            "Successfully extracted invoice: vendor=%s, number=%s, total=%s",
            invoice_data.vendor_name,
            invoice_data.invoice_number,
            invoice_data.total_amount,
        )
        return invoice_data

    def extract_from_pdf(self, pdf_path: str) -> InvoiceData:
        """
        Full pipeline: PDF → Docling markdown → Groq extraction → InvoiceData.
        
        This is the main method called by the orchestrator.
        
        Args:
            pdf_path: Path to the PDF invoice file
            
        Returns:
            InvoiceData — fully validated structured invoice
        """
        filename = Path(pdf_path).name
        markdown = self.parse_pdf_to_markdown(pdf_path)
        return self.extract_from_markdown(markdown, filename)
