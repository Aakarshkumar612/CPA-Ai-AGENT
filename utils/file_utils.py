"""Shared utilities for multi-format file handling."""

from pathlib import Path

# Formats Docling can parse: PDFs, images (OCR), and Word documents
SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".doc"}

# Human-readable label for UI
SUPPORTED_FORMATS_LABEL = "PDF, JPG, PNG, DOCX, DOC"


def find_supported_files(directory: Path) -> list[Path]:
    """Return all supported invoice files in a directory, sorted by name."""
    files: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(directory.glob(f"*{ext}"))
        files.extend(directory.glob(f"*{ext.upper()}"))
    return sorted(set(files), key=lambda p: p.name)


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS
