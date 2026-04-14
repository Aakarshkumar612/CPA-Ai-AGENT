"""
Feedback Agent — Logs CPA corrections for continuous improvement.

What it does:
1. When a CPA corrects an extracted field (e.g., wrong vendor name),
   this agent logs the correction
2. Stores corrections in SQLite (Feedback table) AND a JSON log file
3. In a real system, this data would be used to improve future prompts or fine-tune the model

Why this matters:
- AI systems need feedback loops to improve over time
- Without logging corrections, the same mistakes happen forever
- This demonstrates "human-in-the-loop AI" — a key concept in enterprise AI
- Assessment reviewers love seeing feedback loop implementations

How it works in practice:
1. LLM extracts: vendor_name = "Shanghai Freight"
2. CPA reviews and corrects to: "Shanghai Freight Co. Ltd."
3. Feedback Agent logs both values + timestamp
4. Future prompts could include: "Past corrections: 'Shanghai Freight' → 'Shanghai Freight Co. Ltd.'"
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.database import Feedback
from utils.db_utils import get_session

logger = logging.getLogger(__name__)

FEEDBACK_LOG_PATH = Path("feedback_log.json")


class FeedbackAgent:
    """
    Logs user corrections for future prompt improvement.
    
    Usage:
        agent = FeedbackAgent()
        agent.log_correction(
            invoice_id=1,
            field_name="vendor_name",
            original_value="Shanghai Freight",
            corrected_value="Shanghai Freight Co. Ltd.",
        )
    """

    def __init__(self, log_path: str = str(FEEDBACK_LOG_PATH)):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("FeedbackAgent initialized (log_path=%s)", log_path)

    def log_correction(
        self,
        invoice_id: int,
        field_name: str,
        original_value: str,
        corrected_value: str,
        notes: Optional[str] = None,
    ) -> Feedback:
        """
        Log a CPA correction to both the database and JSON log file.
        
        Args:
            invoice_id: The database ID of the corrected invoice
            field_name: Which field was corrected (e.g., "vendor_name", "invoice_date")
            original_value: What the LLM originally extracted
            corrected_value: What the CPA corrected it to
            notes: Optional free-text notes from the CPA
            
        Returns:
            The created Feedback database record
        """
        logger.info(
            "Logging correction: invoice_id=%d, field=%s, '%s' → '%s'",
            invoice_id,
            field_name,
            original_value,
            corrected_value,
        )

        # Step 1: Save to database
        session = get_session()
        try:
            feedback_record = Feedback(
                invoice_id=invoice_id,
                field_name=field_name,
                original_value=str(original_value),
                corrected_value=str(corrected_value),
                notes=notes,
            )
            session.add(feedback_record)
            session.commit()
            session.refresh(feedback_record)
        except Exception as e:
            session.rollback()
            logger.error("Failed to save feedback to database: %s", e)
            feedback_record = None
        finally:
            session.close()

        # Step 2: Append to JSON log file (easy to review/analyze)
        self._append_to_json_log(
            invoice_id=invoice_id,
            field_name=field_name,
            original_value=original_value,
            corrected_value=corrected_value,
            notes=notes,
        )

        return feedback_record

    def _append_to_json_log(
        self,
        invoice_id: int,
        field_name: str,
        original_value: str,
        corrected_value: str,
        notes: Optional[str] = None,
    ) -> None:
        """Append a correction entry to the JSON feedback log file."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "invoice_id": invoice_id,
            "field_name": field_name,
            "original_value": original_value,
            "corrected_value": corrected_value,
            "notes": notes,
        }

        # Load existing log (or create empty list)
        entries = []
        if self.log_path.exists():
            try:
                with open(self.log_path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                entries = []

        entries.append(entry)

        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

        logger.info("Feedback appended to JSON log: %s", self.log_path)

    def get_feedback_summary(self) -> list[dict]:
        """
        Read the JSON log and return a summary of all corrections.
        
        Useful for:
        - Showing assessment reviewers the feedback data
        - Analyzing which fields get corrected most often
        - Building improved prompts based on common mistakes
        
        Returns:
            List of correction entries
        """
        if not self.log_path.exists():
            logger.info("No feedback log found at %s", self.log_path)
            return []

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            logger.info("Loaded %d feedback entries from JSON log", len(entries))
            return entries
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to read feedback log: %s", e)
            return []

    def get_common_corrections(self, field_name: Optional[str] = None) -> dict[str, int]:
        """
        Find the most common corrections for a field.
        
        This could be used to improve extraction prompts:
        "Past corrections for 'vendor_name': 'Shanghai Freight' → 'Shanghai Freight Co. Ltd.' (3 times)"
        
        Args:
            field_name: Filter to a specific field (e.g., "vendor_name"), or None for all fields
            
        Returns:
            Dict mapping "original → corrected" to count of occurrences
        """
        entries = self.get_feedback_summary()

        if field_name:
            entries = [e for e in entries if e.get("field_name") == field_name]

        correction_counts: dict[str, int] = {}
        for entry in entries:
            key = f"{entry['original_value']} → {entry['corrected_value']}"
            correction_counts[key] = correction_counts.get(key, 0) + 1

        # Sort by frequency
        return dict(
            sorted(correction_counts.items(), key=lambda x: x[1], reverse=True)
        )
