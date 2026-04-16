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
EXTRACTION_SYSTEM_PROMPT = """You are an expert invoice data extraction specialist. You can read invoices from ANY country and format — including Indian GST invoices, international commercial invoices, freight invoices, service invoices, and more.

Given the text/markdown content of an invoice, extract the following fields:

REQUIRED FIELDS:
- vendor_name: Name of the vendor/supplier/seller company or individual
- invoice_number: The unique invoice identifier (any format: INV-001, GSTIN-based, alphanumeric)
- invoice_date: Date the invoice was issued (format: YYYY-MM-DD). Convert Indian formats like "15/03/2024" or "15-Mar-2024" to YYYY-MM-DD.
- currency: Currency code — INR for Indian invoices, USD for US, EUR for Europe, etc. Infer from ₹/Rs/INR symbols.
- incoterms: Shipping incoterms if present (e.g., "FOB Mumbai", "CIF Los Angeles") — null if not a freight invoice
- line_items: Array of all line items / charges / products, each with:
  - description: What the product/service/charge is
  - quantity: Number of units (use 1.0 if not specified)
  - unit_price: Price per unit (exclude tax — use base price)
  - total: Total for this line item before tax
- total_amount: The GRAND TOTAL including all taxes (GST/IGST/CGST/SGST, VAT, etc.)

INDIAN INVOICE NOTES:
- GSTIN: Goods and Services Tax Identification Number — not the invoice number
- HSN/SAC codes are product codes — not part of line item description needed
- CGST + SGST = 2 halves of the same GST (add both to get total tax)
- IGST = inter-state GST (use as-is)
- ₹ or Rs or INR = Indian Rupee → currency = "INR"
- "Bill To" / "Ship To" → the buyer, NOT the vendor
- Vendor = the company that ISSUED the invoice (usually top of document)

IMPORTANT:
- Extract amounts as plain floats — no currency symbols, no commas: 15000.00 not "₹15,000.00"
- If a field cannot be found, use null
- Respond ONLY with valid JSON — no markdown fences, no extra text

JSON FORMAT:
{
    "vendor_name": "...",
    "invoice_number": "...",
    "invoice_date": "YYYY-MM-DD",
    "currency": "INR",
    "incoterms": null,
    "line_items": [
        {"description": "...", "quantity": 1.0, "unit_price": 5000.0, "total": 5000.0}
    ],
    "total_amount": 5900.0
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

    def parse_file_to_markdown(self, file_path: str) -> str:
        """
        Convert any supported invoice file to text/markdown.

        Strategy:
          1. Docling (primary) — best quality, preserves tables, handles PDF/images/DOCX
          2. PyMuPDF fallback  — fast plain-text extraction for PDF and images
          3. python-docx fallback — plain-text for DOCX / DOC when Docling fails

        Cache is checked before any parsing and written after a successful parse.
        """
        logger.info("Parsing file: %s", Path(file_path).name)

        if self.docling_cache:
            cached = self.docling_cache.get(file_path)
            if cached is not None:
                logger.info("Cache HIT for %s", Path(file_path).name)
                return cached

        markdown = self._try_docling(file_path) or self._fallback_extract(file_path)

        if self.docling_cache:
            self.docling_cache.set(file_path, markdown)

        return markdown

    def _try_docling(self, file_path: str) -> str | None:
        """Attempt Docling conversion. Returns None on failure or empty output."""
        try:
            result = self.docling_converter.convert(source=Path(file_path))
            text = result.document.export_to_markdown()
            if text.strip():
                logger.info("Docling: %d chars from %s", len(text), Path(file_path).name)
                return text
            logger.warning("Docling returned empty content for %s", Path(file_path).name)
        except Exception as exc:
            logger.warning("Docling failed for %s (%s) — trying fallback", Path(file_path).name, exc)
        return None

    def _fallback_extract(self, file_path: str) -> str:
        """
        Fallback text extraction using PyMuPDF (PDF/images) or python-docx (DOCX/DOC).
        Raises if no fallback succeeds.
        """
        ext = Path(file_path).suffix.lower()
        name = Path(file_path).name

        if ext in (".pdf", ".jpg", ".jpeg", ".png"):
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                pages = [page.get_text() for page in doc]
                doc.close()
                text = "\n\n".join(pages).strip()
                if text:
                    logger.info("PyMuPDF fallback: %d chars from %s", len(text), name)
                    return text
                raise ValueError("PyMuPDF returned empty text")
            except Exception as exc:
                logger.error("PyMuPDF fallback failed for %s: %s", name, exc)
                raise

        if ext in (".docx", ".doc"):
            try:
                from docx import Document
                doc = Document(file_path)
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                if text:
                    logger.info("python-docx fallback: %d chars from %s", len(text), name)
                    return text
                raise ValueError("python-docx returned empty text")
            except Exception as exc:
                logger.error("python-docx fallback failed for %s: %s", name, exc)
                raise

        raise ValueError(f"No parser available for format '{ext}' — file: {name}")

    # Backward-compat alias used by orchestrator classify step
    def parse_pdf_to_markdown(self, pdf_path: str) -> str:
        return self.parse_file_to_markdown(pdf_path)

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
        """Full pipeline: file → Docling markdown → Groq extraction → InvoiceData."""
        filename = Path(pdf_path).name
        markdown = self.parse_file_to_markdown(pdf_path)
        return self.extract_from_markdown(markdown, filename)
