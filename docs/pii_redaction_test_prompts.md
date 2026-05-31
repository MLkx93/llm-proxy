# PII Redaction Test Prompts

Comprehensive test prompt list for validating Presidio-based PII redaction across different contexts.

## Email Addresses

```
My email is john.doe@company.com and you can reach me there.
Contact me at sarah.smith@gmail.com for more details.
Please send the report to admin@example.org
```

## Phone Numbers

```
Call me at 555-123-4567 if you have questions.
My phone number is (212) 555-0123 during business hours.
You can reach me at +1-415-555-0190 or +44-20-7946-0958
```

## Social Security Numbers

```
My SSN is 123-45-6789 for the background check.
The patient's SSN is 987-65-4321.
Please file under SSN 555-12-3456
```

## Credit Card Numbers

```
Charge it to 4532-1488-0343-6467
Use card number 5105105105105100 for payment
My VISA is 4111111111111111
```

## API Keys & Secrets

```
Use this API key: sk-proj-abc123def456ghi789jkl0
My OpenAI key is sk-abc123...xyz789
GitHub token: ghp_1234567890abcdefghijklmnopqrstuvwxyz
```

## URLs (Internal Infrastructure)

```
Access the internal dashboard at https://admin.internal.company.com
Database is hosted at http://192.168.1.100:5432
SSH to server@10.0.0.50
```

## Medical/Healthcare Context

```
Patient ID: MRN12345678, DOB: 01/15/1985
The patient's medical license number is MD-123456
Insurance provider ID: INS-9876543
```

## Financial Context

```
The account number is ACC-987654321
Wire transfer to IBAN: DE89370400440532013000
Routing number: 021000021, Account: 1234567890
```

## Mixed/Complex Prompts (Multiple PII Types)

**Test 1 - Full Profile (5 PII types):**
```
Hi, I'm John Smith (john@example.com, 555-1234). My SSN is 123-45-6789 and my driver's license is CA-12345678. Please process my application.
```
**Expected redactions:** Name (John Smith), Email, SSN, Driver's License
**Detected types:** PERSON, EMAIL_ADDRESS, SSN_HYPHENATED, DRIVERS_LICENSE

**Test 2 - Profile Update:**
```
Please update my profile:
- Name: Jane Doe
- Email: jane.doe@company.com
- Phone: (415) 555-0123
- Medical License: MD-987654
```

**Test 3 - Payment Info:**
```
Contact me at sarah@example.com or call 212-555-0123. My credit card 4532-1488-0343-6467 is on file.
```

## Tech Terms (Should NOT be redacted - False Positive Tests)

```
I'm using Flask and Django for my project.
We use Kafka and Redis for our infrastructure.
The team includes Alice, Bob, and Charlie working on the MongoDB database.
Can you help me with NumPy and Pandas?
```

**Expected:** No redaction. If these are redacted, they're false positives.

## Multi-turn Conversation (Test Redaction History)

**Turn 1:**
```
I need help with my account recovery.
```

**Turn 2:**
```
My email is john@example.com and SSN is 123-45-6789.
```

**Turn 3:**
```
Can you also add my phone number 555-1234?
```

**Expected:** Last message allowed through. Older messages should have PII redacted.

## Edge Cases

**Multiple Same-Type PII:**
```
My email is test@example.com and backup is test.backup@example.com
```

**Multiple Emails:**
```
Multiple emails: contact@example.com, support@example.com, admin@example.com
```

**Multiple Phone Numbers:**
```
Phone numbers: primary 555-1111, secondary (555) 2222, emergency 555-3333
```

**Driver's License Variations:**
```
License: CA-12345678
License: CA 12345678  
License: CA12345678
License: NY-1234567
```

**Passport Variations:**
```
Passport: AB-123456
Passport: AB123456
Passport: ABC1234567
```

## Real-world Scenarios

### Customer Support

```
Customer complaint: Order #12345 placed by john.doe@company.com (phone: 555-1234) regarding defective item received. SSN on file: 123-45-6789.
```

### Code Review Context

```
Can you review this code? It connects to the database at db.internal.company.com using credentials. The API key sk-abc123xyz789 should be rotated. Credit card 4532-1488-0343-6467 should not be hardcoded.
```

### Data Migration

```
Migrating user data:
ID: 1, Name: John Smith, Email: john@example.com, Phone: 555-1234, SSN: 123-45-6789
ID: 2, Name: Jane Doe, Email: jane@example.com, Phone: 555-5678, SSN: 987-65-4321
```

## Testing Checklist

### Verification Steps

- [ ] Redactions appear as `[REDACTED]` in the response
- [ ] `findings` field in logs lists detected PII types correctly
- [ ] `redaction_details.redaction_count` matches number of actual redactions
- [ ] Tech terms (Django, Flask, Alice, etc.) are NOT redacted
- [ ] Conversation history is handled correctly (old messages redacted, current message allowed)
- [ ] Proxy logs show `redaction` field with `pii_types`, `count`, and `method`
- [ ] Audit log (`logs/audit.jsonl`) includes full `redaction_details` object
- [ ] Original and sanitized hashes differ (proving content was modified)

### Expected Log Output

**Proxy Application Log:**
```json
{
  "timestamp": "2026-05-30T23:44:09.847553+00:00",
  "level": "INFO",
  "logger": "proxy",
  "message": "request_completed",
  "request_id": "0f4456ef-259d-4252-815f-5745ee3b474e",
  "app_id": "local-dev",
  "model": "deepseek/deepseek-chat-v3-0324",
  "latency_ms": 3804,
  "redaction": {
    "pii_types": ["EMAIL_ADDRESS"],
    "count": 1,
    "method": "presidio"
  }
}
```

**Audit Log Entry:**
```json
{
  "timestamp": "2026-05-30T23:44:09.847994+00:00",
  "request_id": "0f4456ef-259d-4252-815f-5745ee3b474e",
  "app_id": "local-dev",
  "action": "ALLOWED",
  "model": "deepseek/deepseek-chat-v3-0324",
  "latency_ms": 3804,
  "findings": ["EMAIL_ADDRESS"],
  "redaction_details": {
    "redacted": true,
    "pii_types": ["EMAIL_ADDRESS"],
    "redaction_count": 1,
    "original_hash": "94d0ce7eb062ad99b64a8d9385688549a207d211b53aebe0cadc7397f0ba4c1b",
    "sanitized_hash": "b2c0582d162880a47d83e68c7bdbf3d94fcd175a6a7103f81e551f763a442b47",
    "redaction_method": "presidio"
  }
}
```

## Environment Variables

These settings control redaction behavior:

- `PII_ACTION` — `"redact"` (default) or `"block"` — whether to redact or block PII
- `CREDENTIAL_ACTION` — `"block"` (default) or `"redact"` — whether to redact or block credentials
- `PRESIDIO_SCORE_THRESHOLD` — confidence threshold for PII detection (0.7 default)

## Detection Layers

The system uses **3-layer detection** for comprehensive PII coverage:

### Layer 1: Secret/Credential Patterns (Regex)
Fast pattern matching for API keys, passwords, connection strings:
- OpenAI API keys: `sk-...`
- Anthropic API keys: `sk-ant-...`
- GitHub tokens: `ghp_...`
- AWS credentials
- Connection strings (MongoDB, PostgreSQL, etc.)

### Layer 2: Enhanced PII Patterns (Regex)
Catches format variations that NLP might miss:
- **Phone numbers**: 555-1234, (555) 123-4567, +1-555-1234, +44-20-7946-0958
- **SSN**: 123-45-6789, 123456789
- **Credit cards**: VISA (4532-...), Mastercard (5105-...), AMEX (3782-...)
- **Passport/ID**: AB1234567, CA12345678
- **Bank accounts**: ACC-123456789
- **IBAN**: DE89370400440532013000
- **IP addresses**: 192.168.1.100 (private only)
- **Medical licenses**: MD-123456
- **Driver's licenses**: CA12345678
- **Social handles**: @username

### Layer 3: Presidio NLP (Entity Recognition)
Deep learning-based NLP analysis:
- `PERSON` — Person names (John, Alice, Bob, etc.)
- `EMAIL_ADDRESS` — Email addresses (john@example.com)
- `PHONE_NUMBER` — Phone numbers (when Presidio's NLP recognizes them)
- `CREDIT_CARD` — Credit card patterns
- `IBAN_CODE` — IBAN bank codes
- `IP_ADDRESS` — IP addresses
- `US_SSN` — US Social Security Numbers
- `US_PASSPORT` — US Passport numbers
- `US_DRIVER_LICENSE` — US Driver License numbers
- `MEDICAL_LICENSE` — Medical license numbers
- `URL` — URLs (catches internal infrastructure URLs)

Note: `LOCATION` is explicitly excluded due to high false-positive rate with normal language.

## Why 3 Layers?

**Presidio NLP alone has limitations:**
- Phone numbers in formats like "555-1234" or "Call me at 5551234" might not be recognized
- Bare SSNs without hyphens (123456789) might be missed
- Context-dependent PII detection varies

**The 3-layer approach ensures:**
✅ Fast credential detection (Layer 1)
✅ Format-variant PII catching (Layer 2)
✅ Entity-based context understanding (Layer 3)
✅ No false negatives for common PII formats
