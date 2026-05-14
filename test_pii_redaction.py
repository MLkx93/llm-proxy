#!/usr/bin/env python3

import os
import asyncio
from src.input_policy.engine import check_and_sanitize_anthropic

# Test PII redaction vs blocking
async def test_pii_behavior():
    # Test message with PII in last user message
    test_body = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "My name is John Doe and my email is john.doe@example.com"}
        ]
    }

    print("Testing PII handling...")
    print(f"Original message: {test_body['messages'][1]['content']}")

    # Test with PII_ACTION = "redact" (default)
    os.environ["PII_ACTION"] = "redact"

    # Reload settings to pick up the environment variable
    import importlib
    import config.settings
    importlib.reload(config.settings)
    from src.input_policy.engine import _redact_text, check_text, check_and_sanitize_anthropic

    sanitized_body, policy = check_and_sanitize_anthropic(test_body)

    print(f"With PII_ACTION='redact':")
    print(f"  Allowed: {policy.allowed}")
    print(f"  Sanitized message: {sanitized_body['messages'][1]['content']}")
    print(f"  Policy findings: {policy.findings}")

    # Test with PII_ACTION = "block"
    os.environ["PII_ACTION"] = "block"
    importlib.reload(config.settings)

    sanitized_body, policy = check_and_sanitize_anthropic(test_body)

    print(f"With PII_ACTION='block':")
    print(f"  Allowed: {policy.allowed}")
    if not policy.allowed:
        print(f"  Blocked with code: {policy.block_code}")
        print(f"  Block reason: {policy.block_reason}")
    else:
        print(f"  Sanitized message: {sanitized_body['messages'][1]['content']}")

if __name__ == "__main__":
    asyncio.run(test_pii_behavior())