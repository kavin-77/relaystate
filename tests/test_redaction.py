import pytest
from app.redaction import redact_content, is_source_excluded, EXCLUDED_SOURCES

def test_secret_and_pii_redaction():
    sample_text = (
        "Deployment notice: here is the key AKIAIOSFODNN7EXAMPLE for staging. "
        "Contact support at devops@company.org or dial +1-555-019-2834. "
        "Also token: 'sk-994820491829384918293849'."
    )
    redacted, events = redact_content(sample_text)
    
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED_AWS_KEY]" in redacted
    assert "devops@company.org" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "+1-555-019-2834" not in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert len(events) >= 3

def test_excluded_sources_and_justifications():
    for src, expected_reason in EXCLUDED_SOURCES.items():
        is_excl, reason = is_source_excluded(src)
        assert is_excl is True
        assert reason == expected_reason

    # Normal public sources should not be excluded
    is_excl, reason = is_source_excluded("#engineering-general")
    assert is_excl is False
    assert reason == ""
