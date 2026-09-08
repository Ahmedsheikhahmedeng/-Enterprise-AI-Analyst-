"""Deterministic regex-based PII detector and sensitivity classifier."""

import re
from typing import Any

from app.ingestion.domain.enums import DataClassification, PIIClassification


class PIIDetector:
    """Detects personally identifiable information (PII) using deterministic pattern analysis."""

    # Regex patterns for high-confidence PII markers
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    PHONE_PATTERN = re.compile(r"^(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}$")
    CREDIT_CARD_PATTERN = re.compile(r"^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$")
    # US SSN (XXX-XX-XXXX) or TR TC Kimlik (11 digits)
    NATIONAL_ID_PATTERN = re.compile(r"^(\d{3}-\d{2}-\d{4}|\d{11})$")

    # Column name heuristics
    NAME_HEURISTICS: dict[str, PIIClassification] = {
        "email": PIIClassification.EMAIL,
        "e_mail": PIIClassification.EMAIL,
        "phone": PIIClassification.PHONE,
        "tel": PIIClassification.PHONE,
        "mobile": PIIClassification.PHONE,
        "credit_card": PIIClassification.CREDIT_CARD,
        "card_number": PIIClassification.CREDIT_CARD,
        "ssn": PIIClassification.NATIONAL_ID,
        "national_id": PIIClassification.NATIONAL_ID,
        "tc_kimlik": PIIClassification.NATIONAL_ID,
        "identity_number": PIIClassification.NATIONAL_ID,
    }

    def detect_column_pii(self, column_name: str, sample_values: list[Any]) -> PIIClassification:
        """Analyze column name and sample values to detect PII classification."""
        cleaned_col = column_name.lower().strip()

        # Check name heuristics first
        for key, pii_type in self.NAME_HEURISTICS.items():
            if key in cleaned_col:
                return pii_type

        # Scan non-null string samples
        str_samples = [
            str(val).strip() for val in sample_values if val is not None and str(val).strip()
        ]
        if not str_samples:
            return PIIClassification.NONE

        card_matches = 0
        email_matches = 0
        phone_matches = 0
        id_matches = 0

        for val in str_samples[:100]:
            if self.CREDIT_CARD_PATTERN.match(val):
                card_matches += 1
            elif self.EMAIL_PATTERN.match(val):
                email_matches += 1
            elif self.NATIONAL_ID_PATTERN.match(val):
                id_matches += 1
            elif self.PHONE_PATTERN.match(val):
                phone_matches += 1

        sample_len = len(str_samples[:100])
        threshold = 0.2  # 20% match rate triggers classification

        if card_matches / sample_len >= threshold:
            return PIIClassification.CREDIT_CARD
        if email_matches / sample_len >= threshold:
            return PIIClassification.EMAIL
        if id_matches / sample_len >= threshold:
            return PIIClassification.NATIONAL_ID
        if phone_matches / sample_len >= threshold:
            return PIIClassification.PHONE

        return PIIClassification.NONE

    def determine_dataset_classification(
        self,
        column_pii_map: dict[str, PIIClassification],
    ) -> DataClassification:
        """Derive overall dataset classification from column classifications."""
        has_sensitive = any(
            pii in (PIIClassification.CREDIT_CARD, PIIClassification.NATIONAL_ID)
            for pii in column_pii_map.values()
        )
        if has_sensitive:
            return DataClassification.SENSITIVE

        has_internal = any(
            pii in (PIIClassification.EMAIL, PIIClassification.PHONE)
            for pii in column_pii_map.values()
        )
        if has_internal:
            return DataClassification.INTERNAL

        return DataClassification.PUBLIC
