"""
Custom regex patterns for secrets and credentials not covered by Presidio's
standard PII recognizers. These are compiled once at module load.
"""
import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class SecretPattern:
    name: str
    pattern: Pattern[str]


# Each pattern targets a distinct secret format.
# Patterns are ordered from most specific to least specific.
SECRET_PATTERNS: list[SecretPattern] = [
    SecretPattern("OPENAI_API_KEY",        re.compile(r'\bsk-[A-Za-z0-9]{20,}\b')),
    SecretPattern("ANTHROPIC_API_KEY",     re.compile(r'\bsk-ant-[A-Za-z0-9\-_]{20,}\b')),
    SecretPattern("GITHUB_TOKEN",          re.compile(r'\bghp_[A-Za-z0-9]{36}\b|\bgho_[A-Za-z0-9]{36}\b|\bghu_[A-Za-z0-9]{36}\b')),
    SecretPattern("AWS_ACCESS_KEY",        re.compile(r'\b(AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b')),
    SecretPattern("AWS_SECRET_KEY",        re.compile(r'(?i)aws.{0,20}secret.{0,20}["\']?([A-Za-z0-9/+=]{40})["\']?')),
    SecretPattern("GENERIC_API_KEY",       re.compile(r'(?i)(api[_\-\s]?key|apikey)\s*[=:]\s*["\']?([A-Za-z0-9\-_]{16,})["\']?')),
    SecretPattern("BEARER_TOKEN",          re.compile(r'(?i)bearer\s+[A-Za-z0-9\-_=.]{20,}')),
    SecretPattern("BASIC_AUTH",            re.compile(r'(?i)basic\s+[A-Za-z0-9+/=]{20,}')),
    SecretPattern("PRIVATE_KEY_BLOCK",     re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    SecretPattern("PASSWORD_ASSIGNMENT",   re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?.{6,}["\']?')),
    SecretPattern("CONNECTION_STRING",     re.compile(r'(?i)(mongodb(\+srv)?|postgresql|mysql|redis|amqp)://[^\s<>"\']+')),
]


def find_secrets(text: str) -> list[str]:
    """Return list of matched secret type names found in text."""
    found = []
    for sp in SECRET_PATTERNS:
        if sp.pattern.search(text):
            found.append(sp.name)
    return found
