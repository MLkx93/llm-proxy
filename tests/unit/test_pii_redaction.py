"""
Unit tests for PII redaction functionality in the Input Policy Engine.

Tests the _redact_text() function which handles PII_ACTION=redact.
Each test verifies that sensitive data is properly replaced with [REDACTED]
while preserving the surrounding text and context.
"""
import pytest
from src.input_policy.engine import _redact_text


class TestPIIRedaction:
    """Test suite for the _redact_text() function."""

    def test_email_address_redaction(self, monkeypatch):
        """Test that email addresses are redacted."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        prompt = "Please send the report to john.doe@example.com for review."
        result = _redact_text(prompt)
        
        # Assert the email is redacted
        assert "[REDACTED]" in result
        assert "john.doe@example.com" not in result
        # Assert surrounding text is preserved
        assert "Please send the report to" in result
        assert "for review." in result

    def test_phone_number_redaction(self, monkeypatch):
        """Test that phone numbers are redacted."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        # Phone number with strong contextual signals for high confidence detection
        prompt = "My employee John Smith's work phone number is (212) 555-1234. Please call him for urgent HR matters."
        result = _redact_text(prompt)
        
        # Assert the phone number is redacted
        assert "[REDACTED]" in result
        assert "(212) 555-1234" not in result
        # Assert surrounding text is preserved
        assert "work phone number is" in result
        assert "Please call" in result

    def test_credit_card_redaction(self, monkeypatch):
        """Test that credit card numbers are redacted."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        prompt = "My payment card number is 4111111111111111 and it expires next year."
        result = _redact_text(prompt)
        
        # Assert the credit card is redacted
        assert "[REDACTED]" in result
        assert "4111111111111111" not in result
        # Assert surrounding text is preserved
        assert "My payment card number is" in result
        assert "and it expires next year." in result

    def test_ssn_redaction(self, monkeypatch):
        """Test that Social Security Numbers are redacted."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        # SSN with strong contextual signals for high confidence detection
        prompt = "Employee John Smith's social security number is 123-45-6789. Use this SSN for payroll processing and tax records."
        result = _redact_text(prompt)
        
        # Assert the SSN is redacted
        assert "[REDACTED]" in result
        assert "123-45-6789" not in result
        # Assert surrounding text is preserved
        assert "social security number is" in result
        assert "Use this SSN for" in result

    def test_physical_address_redaction(self, monkeypatch):
        """Test that physical addresses are redacted (via LOCATION entity if detected)."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        # Note: LOCATION is excluded from PII_ENTITIES in engine.py due to false positives,
        # but we can test with IP addresses which are included
        prompt = "The server is hosted at IP address 192.168.1.100 in the datacenter."
        result = _redact_text(prompt)
        
        # Assert the IP address is redacted
        assert "[REDACTED]" in result
        assert "192.168.1.100" not in result
        # Assert surrounding text is preserved
        assert "The server is hosted at IP address" in result
        assert "in the datacenter." in result

    def test_multiple_pii_types_redaction(self, monkeypatch):
        """Test that multiple PII types in the same prompt are all redacted."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        # Enhanced with strong contextual signals for each PII type
        prompt = "Contact employee Jane Doe at her work email jane.doe@company.com or call her office phone (555) 123-4567. Her social security number 987-65-4321 is needed for payroll."
        result = _redact_text(prompt)
        
        # Assert all PII elements are redacted
        assert "[REDACTED]" in result
        assert "jane.doe@company.com" not in result
        assert "(555) 123-4567" not in result
        assert "987-65-4321" not in result
        # Assert surrounding text is preserved
        assert "Contact employee" in result
        assert "at her work email" in result
        assert "or call her office phone" in result
        assert "is needed for payroll" in result

    def test_clean_prompt_unchanged(self, monkeypatch):
        """Test that prompts without PII pass through unchanged."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        prompt = "What is the capital of France? Please explain the history of Paris."
        result = _redact_text(prompt)
        
        # Assert the prompt is unchanged
        assert result == prompt
        assert "[REDACTED]" not in result

    def test_pii_mid_sentence_preserves_context(self, monkeypatch):
        """Test that PII appearing mid-sentence preserves surrounding text."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        prompt = "The customer's email address is support@example.com and they requested a callback."
        result = _redact_text(prompt)
        
        # Assert the email is redacted but surrounding text is preserved
        assert "[REDACTED]" in result
        assert "support@example.com" not in result
        assert "The customer's email address is" in result
        assert "and they requested a callback." in result
        # Verify the sentence structure is maintained
        assert "The customer's email address is [REDACTED] and they requested a callback." == result

    def test_credential_redaction_in_pii_function(self, monkeypatch):
        """Test that credentials are also redacted by _redact_text()."""
        # Set PII_ACTION to redact mode
        monkeypatch.setenv("PII_ACTION", "redact")
        
        prompt = "Use this API key: sk-abcdefghijklmnopqrstuvwxyz123456 for authentication."
        result = _redact_text(prompt)
        
        # Assert the credential is redacted
        assert "[REDACTED]" in result
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        # Assert surrounding text is preserved
        assert "Use this API key:" in result
        assert "for authentication." in result
