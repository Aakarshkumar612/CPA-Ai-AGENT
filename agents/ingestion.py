"""
Ingestion Agent — Classifies incoming PDF documents.

What it does:
1. Scans the input_docs folder for PDF files
2. Uses Groq LLM to classify each PDF as: invoice, bill_of_lading, or other
3. Returns a ClassificationResult (Pydantic model)

Why an LLM for classification?
- Rule-based approaches (keyword matching) break easily
- An LLM reads the actual content and understands context
- Same infrastructure (Groq call) we already use for extraction — no extra dependencies
"""

import logging
from pathlib import Path
from groq import Groq

from models.pydantic_models import ClassificationResult
from utils.cache import get_llm_cache
from utils.retry import retry_function
from utils.settings import settings

logger = logging.getLogger(__name__)

# System prompt tells the LLM how to classify documents
CLASSIFICATION_SYSTEM_PROMPT = """You are a document classification expert. Your job is to identify whether a document is an invoice.

An INVOICE is ANY commercial document that requests payment or records a transaction. This includes:
- Tax invoice (India GST invoice with GSTIN, CGST, SGST, IGST, HSN/SAC codes)
- Commercial invoice (international trade)
- Freight / shipping invoice
- Service invoice
- Purchase invoice / bill
- Proforma invoice
- E-invoice (Indian IRN/QR code invoices)
- Utility bill requesting payment
- Any document with: invoice number, vendor/seller name, line items or charges, and a total/amount due

A BILL_OF_LADING is specifically a shipping document (not a payment request) with vessel, port, consignee, and cargo details — but NO payment line items or totals.

OTHER is anything else: contracts, letters, bank statements, delivery receipts without charges, etc.

IMPORTANT RULES:
- If the document has an invoice/bill number AND an amount/total AND a seller — classify as "invoice" even if the format is unfamiliar
- Indian GST invoices, tally invoices, and local business invoices ARE invoices
- When in doubt between "invoice" and "other", choose "invoice"
- Confidence should be >= 0.7 for any document with a clear invoice number and total amount

Respond ONLY with a JSON object — no markdown fences, no extra text:
{
    "document_type": "invoice" | "bill_of_lading" | "other",
    "confidence": 0.0 to 1.0,
    "reason": "Brief explanation"
}"""


class IngestionAgent:
    """
    Monitors input documents and classifies them using Groq LLM.
    
    Usage:
        agent = IngestionAgent()
        results = agent.classify_documents("./input_docs")
        for result in results:
            print(f"{result.filename}: {result.classification.document_type}")
    """

    def __init__(self, model: str | None = None, use_cache: bool = True):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = model or settings.GROQ_MODEL
        self.use_cache = use_cache
        self.llm_cache = get_llm_cache() if use_cache else None
        logger.info("IngestionAgent initialized with model: %s (cache=%s)", self.model, use_cache)

    def classify_document(self, pdf_text: str, filename: str) -> ClassificationResult:
        """
        Classify a single document based on its extracted text.
        
        Args:
            pdf_text: The text content extracted from the PDF by Docling
            filename: Original filename (for logging purposes)
            
        Returns:
            ClassificationResult with document_type, confidence, and reason
        """
        logger.info("Classifying document: %s", filename)

        # Check LLM cache first
        if self.llm_cache:
            cached = self.llm_cache.get(
                self.model, CLASSIFICATION_SYSTEM_PROMPT, pdf_text[:3000]
            )
            if cached is not None:
                logger.info("LLM cache HIT for classification of %s", filename)
                import json
                return ClassificationResult(**json.loads(cached))

        try:
            response = retry_function(
                lambda: self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Classify this document:\n\n{pdf_text[:3000]}"},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                ),
                max_retries=3,
                backoff_base=2.0,
            )

            # Parse the LLM's JSON response
            import json
            raw_text = response.choices[0].message.content.strip()
            
            # Handle markdown code fences if LLM adds them
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            result_dict = json.loads(raw_text)
            classification = ClassificationResult(**result_dict)

            # Cache the response
            if self.llm_cache:
                self.llm_cache.set(
                    self.model, CLASSIFICATION_SYSTEM_PROMPT, pdf_text[:3000], raw_text
                )

            logger.info(
                "Classification result for %s: type=%s, confidence=%.2f",
                filename, classification.document_type, classification.confidence,
            )
            return classification

        except Exception as e:
            logger.error("Failed to classify document %s: %s", filename, e)
            # Return a safe default — treat as "other" if classification fails
            return ClassificationResult(
                document_type="other",
                confidence=0.0,
                reason=f"Classification failed: {str(e)}",
            )

    def scan_and_classify(self, input_dir: str = "input_docs") -> list[dict]:
        """
        Scan a directory for PDFs and classify each one.
        
        Args:
            input_dir: Path to folder containing PDF files
            
        Returns:
            List of dicts with 'filename', 'classification', and 'text' keys
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            logger.warning("Input directory does not exist: %s", input_dir)
            return []

        from utils.file_utils import find_supported_files
        pdf_files = find_supported_files(input_path)
        if not pdf_files:
            logger.info("No supported files found in %s", input_dir)
            return []

        logger.info("Found %d file(s) in %s", len(pdf_files), input_dir)

        results = []
        for pdf_file in pdf_files:
            # For now, we just return the file info
            # In the full pipeline, Docling will extract the text first
            results.append({
                "filename": pdf_file.name,
                "filepath": str(pdf_file),
            })

        return results
