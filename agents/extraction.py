"""
Extraction Agent — Converts invoice files into structured data.

Pipeline:
  1. PyMuPDF  → extracts text from PDF / JPG / PNG (OCR via Tesseract for scanned docs)
  2. python-docx → extracts text from DOCX / DOC
  3. Groq LLM  → reads the extracted text and returns structured JSON

Why PyMuPDF instead of Docling?
- Docling pulls in PyTorch + CUDA + transformers (~3.5 GB) — too heavy for free hosting
- PyMuPDF is a C library (~50 MB), fast, and handles all common invoice formats
- Groq does the semantic understanding, so the extractor only needs clean text
"""

import json
import logging
from pathlib import Path
from groq import Groq

from models.pydantic_models import InvoiceData
from utils.cache import get_docling_cache, get_llm_cache
from utils.retry import retry_function
from utils.settings import settings

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """You are an expert invoice data extraction specialist. You can read invoices from ANY country and format — including Indian GST invoices, international commercial invoices, freight invoices, service invoices, and more.

Given the text content of an invoice, extract the following fields:

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
- GSTIN is a tax registration number — NOT the invoice number
- HSN/SAC codes are product codes — skip them in descriptions
- CGST + SGST together = total GST (add both to get tax amount)
- IGST = inter-state GST
- ₹ or Rs or INR = Indian Rupee → currency = "INR"
- "Bill To" / "Ship To" = the buyer, NOT the vendor
- Vendor = the company that ISSUED the invoice (usually at top of document)

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
    """Extracts structured invoice data using PyMuPDF (text) + Groq LLM (understanding)."""

    def __init__(self, model: str | None = None, use_cache: bool = True):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = model or settings.GROQ_MODEL
        self.use_cache = use_cache
        self.docling_cache = get_docling_cache() if use_cache else None
        self.llm_cache = get_llm_cache() if use_cache else None
        logger.info("ExtractionAgent initialized (model=%s, cache=%s)", self.model, use_cache)

    # ── File → text ────────────────────────────────────────────────────────────

    def parse_file_to_markdown(self, file_path: str) -> str:
        """
        Extract text from any supported invoice file.

        Routing:
          PDF / JPG / PNG  → PyMuPDF  (OCR via Tesseract for scanned/image pages)
          DOCX / DOC       → python-docx  (paragraphs + tables)

        Result is cached by file content hash so re-runs skip re-parsing.
        """
        logger.info("Parsing: %s", Path(file_path).name)

        if self.docling_cache:
            cached = self.docling_cache.get(file_path)
            if cached is not None:
                logger.info("Cache HIT — skipping parse for %s", Path(file_path).name)
                return cached

        ext = Path(file_path).suffix.lower()

        if ext in (".pdf", ".jpg", ".jpeg", ".png"):
            text = self._extract_with_pymupdf(file_path)
        elif ext in (".docx", ".doc"):
            text = self._extract_with_docx(file_path)
        else:
            raise ValueError(f"Unsupported format '{ext}' for {Path(file_path).name}")

        if not text.strip():
            raise ValueError(f"No text could be extracted from {Path(file_path).name}")

        if self.docling_cache:
            self.docling_cache.set(file_path, text)

        return text

    def _extract_with_pymupdf(self, file_path: str) -> str:
        """
        Extract text from PDF or image using PyMuPDF.

        For digital PDFs: direct text layer extraction (fast, exact).
        For scanned PDFs / images: falls back to Tesseract OCR when a page
        has no selectable text. Requires 'tesseract-ocr' system package.
        """
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        pages_text: list[str] = []

        for page_num, page in enumerate(doc):
            text = page.get_text().strip()

            if not text:
                # No selectable text — page is an image/scan, try OCR
                try:
                    tp = page.get_textpage_ocr(language="eng", dpi=300, full=True)
                    text = page.get_text(textpage=tp).strip()
                    if text:
                        logger.info("OCR used on page %d of %s", page_num + 1, Path(file_path).name)
                except Exception as ocr_err:
                    logger.warning("OCR unavailable for page %d: %s", page_num + 1, ocr_err)

            if text:
                pages_text.append(text)

        doc.close()

        result = "\n\n".join(pages_text)
        logger.info("PyMuPDF: %d chars from %s", len(result), Path(file_path).name)
        return result

    def _extract_with_docx(self, file_path: str) -> str:
        """Extract text from DOCX/DOC — paragraphs and tables."""
        from docx import Document

        doc = Document(file_path)
        parts: list[str] = []

        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text.strip())

        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(c.text.strip() for c in row.cells if c.text.strip())
                if row_text:
                    parts.append(row_text)

        result = "\n".join(parts)
        logger.info("python-docx: %d chars from %s", len(result), Path(file_path).name)
        return result

    # Backward-compat alias — orchestrator calls this name
    def parse_pdf_to_markdown(self, pdf_path: str) -> str:
        return self.parse_file_to_markdown(pdf_path)

    # ── Text → structured data ─────────────────────────────────────────────────

    def extract_from_markdown(self, markdown: str, filename: str) -> InvoiceData:
        """Send extracted text to Groq LLM and return validated InvoiceData."""
        logger.info("Extracting fields from: %s", filename)

        if self.llm_cache:
            cached = self.llm_cache.get(self.model, EXTRACTION_SYSTEM_PROMPT, markdown)
            if cached is not None:
                logger.info("LLM cache HIT for %s", filename)
                return self._parse_llm_response(cached, filename)

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

        if self.llm_cache:
            self.llm_cache.set(self.model, EXTRACTION_SYSTEM_PROMPT, markdown, raw_text)

        return self._parse_llm_response(raw_text, filename)

    def _parse_llm_response(self, raw_text: str, filename: str) -> InvoiceData:
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(raw_text)
        invoice = InvoiceData(**data)
        logger.info(
            "Extracted: vendor=%s  number=%s  total=%s",
            invoice.vendor_name, invoice.invoice_number, invoice.total_amount,
        )
        return invoice

    def extract_from_pdf(self, pdf_path: str) -> InvoiceData:
        """Convenience method: file → text → InvoiceData."""
        filename = Path(pdf_path).name
        text = self.parse_file_to_markdown(pdf_path)
        return self.extract_from_markdown(text, filename)
