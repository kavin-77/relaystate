import re
from typing import Tuple, List, Dict, Any

# Excluded sources and specific justifications
EXCLUDED_SOURCES = {
    "#hr-confidential": "Contains confidential HR personnel reviews, salary discussions, and internal escalations.",
    "dm-dave-sarah": "Private 1-on-1 direct message conversation protected by employee privacy policy.",
    "hr-payroll-tools": "Restricted payroll calculation engine and compensation database repository."
}

def is_source_excluded(source_name: str) -> Tuple[bool, str]:
    """Check if a repository, channel, or stream should be excluded from ingestion."""
    if not source_name:
        return False, ""
    clean_name = source_name.strip()
    for excl, reason in EXCLUDED_SOURCES.items():
        if excl.lower() in clean_name.lower():
            return True, reason
    return False, ""

# Regex rules for secrets, PII, and credentials
REDACTION_RULES = [
    (
        "AWS_KEY",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]"
    ),
    (
        "API_SECRET",
        re.compile(r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}|bearer\s+[a-zA-Z0-9_\-\.]{20,})\b", re.IGNORECASE),
        "[REDACTED_API_SECRET]"
    ),
    (
        "PASSWORD_ASSIGNMENT",
        re.compile(r'(?i)(password|secret|api_key|token)\s*[:=]\s*["\']([^"\'\s]{8,})["\']'),
        r'\1: "[REDACTED_CREDENTIAL]"'
    ),
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "[REDACTED_EMAIL]"
    ),
    (
        "PHONE",
        re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "[REDACTED_PHONE]"
    )
]

def redact_content(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Scrub secrets and personal identifiers from text prior to storage or LLM processing.
    Returns (redacted_text, list_of_redaction_events).
    """
    if not text:
        return "", []
    
    current_text = text
    applied_redactions = []
    
    for rule_name, pattern, replacement in REDACTION_RULES:
        matches = list(pattern.finditer(current_text))
        if matches:
            for match in matches:
                applied_redactions.append({
                    "rule": rule_name,
                    "matched_snippet": match.group(0)[:12] + "..." if len(match.group(0)) > 12 else match.group(0),
                    "replacement": replacement if isinstance(replacement, str) else "[REDACTED]"
                })
            current_text = pattern.sub(replacement, current_text)
            
    return current_text, applied_redactions
