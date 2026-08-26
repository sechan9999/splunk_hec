"""Local Fine-Tuned DLP Guardrail Module for Unified Ops AX.

Provides zero-latency offline PII detection and redaction (SSN, KR_RRN, Credit Cards,
API Keys, Email, Phone) with Luhn validation and HMAC-SHA256 data signatures.
"""

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any


def is_luhn_valid(card_number_str: str) -> bool:
    """Validates credit card numbers using the Luhn checksum algorithm."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


@dataclass
class DLPInspectionResult:
    is_clean: bool
    matched_rules: List[str]
    masked_text: str
    original_length: int
    masked_length: int
    data_hash: str
    sensitivity: str  # "RESTRICTED", "CONFIDENTIAL", "PUBLIC"


class LocalDLPGuardrail:
    """Offline PII Classification & Data Masking Engine."""

    PATTERNS = {
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "KR_RRN": r"\b\d{6}-[1-4]\d{6}\b",
        "API_KEY": r"\b(?:sk-[a-zA-Z0-9_-]{16,}|AIzaSy[a-zA-Z0-9_-]{30,}|ghp_[a-zA-Z0-9]{30,})\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    }

    # Credit card raw pattern
    CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

    def __init__(self, secret_key: str = "unified-ops-dlp-secret"):
        self.compiled_patterns = {name: re.compile(pattern) for name, pattern in self.PATTERNS.items()}
        self.secret_key = secret_key.encode("utf-8")
        self.total_inspections = 0
        self.total_violations = 0

    def inspect_and_mask(self, text: str) -> DLPInspectionResult:
        """Inspects text for PII patterns (with Luhn validation for cards), applies masking, and computes HMAC-SHA256."""
        self.total_inspections += 1
        masked_text = text
        matched_rules = []

        # 1. Standard pattern checks (SSN, KR_RRN, API_KEY, EMAIL, PHONE)
        for rule_name, regex in self.compiled_patterns.items():
            if regex.search(masked_text):
                matched_rules.append(rule_name)
                masked_text = regex.sub(f"[PII_MASKED:{rule_name}]", masked_text)

        # 2. Credit Card check with Luhn validation to avoid false positives on trace/order IDs
        card_matches = self.CARD_REGEX.findall(masked_text)
        found_card = False
        for card_candidate in card_matches:
            clean_digits = re.sub(r"\D", "", card_candidate)
            if is_luhn_valid(clean_digits):
                found_card = True
                masked_text = masked_text.replace(card_candidate, "[PII_MASKED:CREDIT_CARD]")

        if found_card and "CREDIT_CARD" not in matched_rules:
            matched_rules.append("CREDIT_CARD")

        is_clean = len(matched_rules) == 0
        if not is_clean:
            self.total_violations += 1

        # Classify sensitivity
        if any(r in matched_rules for r in ("CREDIT_CARD", "SSN", "KR_RRN", "API_KEY")):
            sensitivity = "RESTRICTED"
        elif any(r in matched_rules for r in ("EMAIL", "PHONE")):
            sensitivity = "CONFIDENTIAL"
        else:
            sensitivity = "PUBLIC"

        # Keyed HMAC-SHA256 signature computed over the ORIGINAL text for integrity verification
        data_hash = hmac.new(self.secret_key, text.encode("utf-8"), hashlib.sha256).hexdigest()[:16]

        return DLPInspectionResult(
            is_clean=is_clean,
            matched_rules=matched_rules,
            masked_text=masked_text,
            original_length=len(text),
            masked_length=len(masked_text),
            data_hash=data_hash,
            sensitivity=sensitivity
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_inspections": self.total_inspections,
            "total_violations": self.total_violations,
            "clean_rate_pct": round(((self.total_inspections - self.total_violations) / self.total_inspections) * 100, 2) if self.total_inspections > 0 else 100.0
        }
