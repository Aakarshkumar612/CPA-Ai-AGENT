from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import date


class LineItem(BaseModel):
    """
    Represents a single line item on an invoice.
    
    Example:
        description: "Freight - Shanghai to Los Angeles"
        quantity: 20
        unit_price: 1500.00
        total: 30000.00
    """
    description: str = Field(..., description="Description of the goods/service")
    quantity: float = Field(..., description="Quantity of items")
    unit_price: float = Field(..., description="Price per unit")
    total: float = Field(..., description="Total price (quantity * unit_price)")


class InvoiceData(BaseModel):
    """
    Fully extracted and validated invoice data from a PDF.
    
    This is the output of the Extraction Agent.
    Every field is validated by Pydantic automatically.
    """
    vendor_name: str = Field(..., description="Name of the vendor/supplier")
    invoice_number: str = Field(..., description="Unique invoice identifier from vendor")
    invoice_date: date = Field(..., description="Date the invoice was issued")
    currency: str = Field(default="USD", description="Currency code (e.g., USD, EUR, CNY)")
    incoterms: Optional[str] = Field(default=None, description="Shipping incoterms (e.g., FOB, CIF, EXW)")
    line_items: list[LineItem] = Field(..., description="List of line items on the invoice")
    total_amount: float = Field(..., description="Grand total of the invoice")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vendor_name": "Shanghai Freight Co.",
                "invoice_number": "INV-2024-0042",
                "invoice_date": "2024-03-15",
                "currency": "USD",
                "incoterms": "FOB Shanghai",
                "line_items": [
                    {
                        "description": "Freight - Shanghai to Los Angeles",
                        "quantity": 20,
                        "unit_price": 1500.00,
                        "total": 30000.00,
                    }
                ],
                "total_amount": 30000.00,
            }
        }
    )


class ClassificationResult(BaseModel):
    """
    Output of the Ingestion Agent's document classification.
    
    The LLM determines what type of document we're dealing with
    so we route it to the correct extraction pipeline.
    """
    document_type: str = Field(..., description="Type: invoice, bill_of_lading, other")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0")
    reason: str = Field(..., description="Why the LLM classified it this way")


class BenchmarkResult(BaseModel):
    """
    Output of the Market Benchmarking Agent.
    
    Compares invoice prices against market rates.
    """
    route: str = Field(..., description="Shipping route (e.g., Shanghai -> Los Angeles)")
    invoice_price: float = Field(..., description="Price from the invoice")
    market_average: float = Field(..., description="Average market price for this route")
    deviation_percent: float = Field(..., description="How much invoice differs from market (%)")
    is_overpriced: bool = Field(..., description="True if deviation > 15%")


class AnomalyReport(BaseModel):
    """
    Output of the Analysis Agent.
    
    Flags issues found during audit.
    """
    invoice_number: str
    vendor_name: str
    anomalies: list[str] = Field(default_factory=list)
    severity: str = Field(..., description="low, medium, high, critical")
    summary: str = Field(..., description="Human-readable summary of findings")
