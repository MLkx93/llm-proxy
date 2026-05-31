"""
Enhanced PII regex patterns for cases Presidio's NLP misses.
These patterns catch format variations that the Presidio analyzer doesn't reliably detect.
"""
import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class PIIPattern:
    name: str
    pattern: Pattern[str]
    description: str


# PII patterns for common formats that Presidio NLP sometimes misses
PII_PATTERNS: list[PIIPattern] = [
    # Phone numbers - multiple formats (more permissive)
    PIIPattern(
        "PHONE_US_SIMPLE",
        re.compile(r'(?:tel|phone|number|call)[\s:]*\(?(\d{3})\)?[\s.\-]?(\d{3})[\s.\-]?(\d{4})', re.IGNORECASE),
        "US phone: phone: 555-123-4567 or tel (555) 123-4567"
    ),
    PIIPattern(
        "PHONE_PARENS",
        re.compile(r'\(\d{3}\)\s*\d{3}[.\-\s]?\d{4}'),
        "US phone with parens: (555) 123-4567"
    ),
    PIIPattern(
        "PHONE_INTL",
        re.compile(r'\+\d{1,3}[\s\-]?\d{1,4}[\s\-]?\d{1,4}[\s\-]?\d{1,9}'),
        "International phone: +1 555 123 4567"
    ),
    PIIPattern(
        "PHONE_DASH_ONLY",
        re.compile(r'(?:tel|phone|number|call|reach|contact)[\s:]*\d{3}[\-\.]\d{3}[\-\.]\d{4}', re.IGNORECASE),
        "Phone with dashes: phone: 555-123-4567"
    ),
    PIIPattern(
        "PHONE_IN_CONTEXT",
        re.compile(r'(?:phone|tel|call|contact|reach|dial)[\s:]*\d{3}[\-\s]\d{4}', re.IGNORECASE),
        "Short phone in context: phone: 555-1234"
    ),

    # Social Security Numbers - variations
    PIIPattern(
        "SSN_HYPHENATED",
        re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "SSN with hyphens: 123-45-6789"
    ),
    PIIPattern(
        "SSN_BARE",
        re.compile(r'(?<!\d)\d{3}\d{2}\d{4}(?!\d)'),
        "SSN without hyphens: 123456789"
    ),

    # IP Addresses - IPv4
    PIIPattern(
        "IP_ADDRESS_PRIVATE",
        re.compile(r'\b(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b'),
        "Private IP addresses: 10.0.0.1, 192.168.1.1"
    ),

    # Passport/ID numbers (with optional hyphens)
    PIIPattern(
        "PASSPORT_FORMAT",
        re.compile(r'\b[A-Z]{1,2}[\-]?\d{6,9}\b'),
        "Passport/ID: AB123456, AB-123456, ABC1234567"
    ),

    # Driver's License (with optional hyphens and spaces)
    PIIPattern(
        "DRIVERS_LICENSE",
        re.compile(r'\b[A-Z]{1,2}[\-\s]?\d{5,8}\b'),
        "Driver's license: CA12345678, CA-12345678, CA 12345678"
    ),

    # Bank Account Numbers (broad pattern)
    PIIPattern(
        "ACCOUNT_NUMBER",
        re.compile(r'\b(?:account|acc|acct)\s*[#:]?\s*\d{8,17}\b', re.IGNORECASE),
        "Account number: ACC-123456789"
    ),

    # IBAN
    PIIPattern(
        "IBAN",
        re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{1,30}\b'),
        "IBAN: DE89370400440532013000"
    ),

    # Credit Card (common patterns)
    PIIPattern(
        "CREDIT_CARD_VISA",
        re.compile(r'\b4[0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b'),
        "VISA: 4532-1488-0343-6467"
    ),
    PIIPattern(
        "CREDIT_CARD_MASTERCARD",
        re.compile(r'\b5[1-5][0-9]{2}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}\b'),
        "Mastercard: 5105-1051-0510-5100"
    ),
    PIIPattern(
        "CREDIT_CARD_AMEX",
        re.compile(r'\b3[47][0-9]{2}[\s\-]?[0-9]{6}[\s\-]?[0-9]{5}\b'),
        "AMEX: 3782-822463-10005"
    ),

    # Date of Birth patterns
    PIIPattern(
        "DOB_US_FORMAT",
        re.compile(r'\b(?:DOB|dob|birth\s*date|birthdate)\s*[=:]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b', re.IGNORECASE),
        "DOB: 01/15/1985 or 01-15-1985"
    ),

    # Medical License Numbers
    PIIPattern(
        "MEDICAL_LICENSE",
        re.compile(r'\b(?:MD|MEDICAL|LICENSE)\s*[#=:]?\s*\d{6,8}\b', re.IGNORECASE),
        "Medical License: MD-123456"
    ),

    # Social Media Handles (conservative - only ones explicitly marked)
    PIIPattern(
        "SOCIAL_HANDLE",
        re.compile(r'(?:twitter|instagram|handle|username)\s*[=:]?\s*@[A-Za-z0-9_]{3,}\b', re.IGNORECASE),
        "Social handle: @username"
    ),
]


def find_pii_patterns(text: str) -> list[str]:
    """Return list of matched PII pattern names found in text."""
    found = []
    for pii_pattern in PII_PATTERNS:
        if pii_pattern.pattern.search(text):
            found.append(pii_pattern.name)
    return found
