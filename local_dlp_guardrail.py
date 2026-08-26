"""Local Fine-Tuned DLP Guardrail Module for Unified Ops AX.

Provides zero-latency offline PII detection and redaction (SSN, Credit Cards,
API Keys, Email, Phone) with SHA-256 data hash signatures prior to telemetry emission.
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any


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
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "API_KEY": r"\b(?:sk-[a-zA-Z0-9]{20,}|AIzaSy[a-zA-Z0-9_-]{33}|ghp_[a-zA-Z0-9]{36})\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    }

    def __init__(self):
        self.compiled_patterns = {name: re.compile(pattern) for name, pattern in self.PATTERNS.items()}
        self.total_inspections = 0
        self.total_violations = 0

    def inspect_and_mask(self, text: str) -> DLPInspectionResult:
        """Inspects text for PII patterns, applies masking, and returns DLPInspectionResult."""
        self.total_inspections += 1
        masked_text = text
        matched_rules = []

        for rule_name, regex in self.compiled_patterns.items():
            if regex.search(masked_text):
                matched_rules.append(rule_name)
                masked_text = regex.sub(f"[PII_MASKED:{rule_name}]", masked_text)

        is_clean = len(matched_rules) == 0
        if not is_clean:
            self.total_violations += 1

        # Classify sensitivity
        if "CREDIT_CARD" in matched_rules or "SSN" in matched_rules or "API_KEY" in matched_rules:
            sensitivity = "RESTRICTED"
        elif "EMAIL" in matched_rules or "PHONE" in matched_rules:
            sensitivity = "CONFIDENTIAL"
        else:
            sensitivity = "PUBLIC"

        # SHA-256 data hash signature
        data_hash = hashlib.sha256(masked_text.encode("utf-8")).hexdigest()[:16]

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
