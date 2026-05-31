# Test Execution Template

Use this template to track your test runs for all 34 test cases.

## Test Run Date: ________________

**Tester Name:** ________________
**API Key Used:** ________________
**Proxy URL:** ________________

---

## PII Redaction Tests (Should return 200 OK)

### Test 1: Email Address
- [ ] **PASS** - Status 200, email replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 2: Phone Number (Formatted)
- [ ] **PASS** - Status 200, phone replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 3: Phone Number (Parentheses)
- [ ] **PASS** - Status 200, phone replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 4: International Phone
- [ ] **PASS** - Status 200, both phones replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 5: SSN (Hyphenated)
- [ ] **PASS** - Status 200, SSN replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 6: SSN (Bare)
- [ ] **PASS** - Status 200, SSN replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 7: Credit Card (VISA)
- [ ] **PASS** - Status 200, card replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 8: Credit Card (Mastercard)
- [ ] **PASS** - Status 200, card replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 9: Driver's License (With Hyphen)
- [ ] **PASS** - Status 200, license replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 10: Driver's License (Without Hyphen)
- [ ] **PASS** - Status 200, license replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 11: Passport Number
- [ ] **PASS** - Status 200, passport replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 12: Private IP Address
- [ ] **PASS** - Status 200, IP replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 13: IBAN
- [ ] **PASS** - Status 200, IBAN replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 14: Person Name
- [ ] **PASS** - Status 200, name replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 15: Medical License
- [ ] **PASS** - Status 200, license replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 16: Multiple PII Types
- [ ] **PASS** - Status 200, all 5 items replaced with [REDACTED]
- [ ] **FAIL** - Status code: _____, Issue: _______________________

**PII Tests Summary:** ___/16 PASSED

---

## Credential Blocking Tests (Should return 400 Bad Request)

### Test 17: OpenAI API Key
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 18: Anthropic API Key
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 19: GitHub Token
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 20: AWS Access Key
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 21: Bearer Token
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 22: Private Key Block
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 23: Password Assignment
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 24: MongoDB Connection String
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 25: PostgreSQL Connection String
- [ ] **PASS** - Status 400, error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

**Credential Tests Summary:** ___/9 PASSED

---

## Injection Attack Blocking Tests (Should return 400 Bad Request)

### Test 26: Ignore Instructions
- [ ] **PASS** - Status 400, injection error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 27: Disregard Prompt
- [ ] **PASS** - Status 400, injection error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 28: DAN Jailbreak
- [ ] **PASS** - Status 400, injection error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 29: Role Hijack
- [ ] **PASS** - Status 400, injection error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 30: System Prompt Leak
- [ ] **PASS** - Status 400, injection error message correct
- [ ] **FAIL** - Status code: _____, Issue: _______________________

**Injection Tests Summary:** ___/5 PASSED

---

## Safe Content Tests (Should return 200 OK, unchanged)

### Test 31: Safe Technical Question
- [ ] **PASS** - Status 200, content unchanged
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 32: Safe Code Review
- [ ] **PASS** - Status 200, content unchanged
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 33: Safe Business Question
- [ ] **PASS** - Status 200, content unchanged
- [ ] **FAIL** - Status code: _____, Issue: _______________________

### Test 34: Mixed Safe + PII
- [ ] **PASS** - Status 200, PII redacted, safe text unchanged
- [ ] **FAIL** - Status code: _____, Issue: _______________________

**Safe Content Tests Summary:** ___/4 PASSED

---

## Overall Results

| Category | Passed | Total | % |
|----------|--------|-------|---|
| PII Redaction | ___ | 16 | ___% |
| Credential Blocking | ___ | 9 | ___% |
| Injection Blocking | ___ | 5 | ___% |
| Safe Content | ___ | 4 | ___% |
| **TOTAL** | **___** | **34** | **___% |

---

## Audit Log Verification

### PII Redaction Log Check
- [ ] Logs contain `action: "ALLOWED"`
- [ ] Logs contain `findings` array with detected types
- [ ] Logs contain `redaction_details` with:
  - [ ] `redacted: true`
  - [ ] `pii_types` array
  - [ ] `redaction_count` > 0
  - [ ] `redaction_method: "presidio"` or `"regex"`

### Credential Block Log Check
- [ ] Logs contain `action: "BLOCKED"`
- [ ] Logs contain `block_code: "BLOCKED_CREDENTIALS"`
- [ ] Logs contain `findings` with credential type

### Injection Block Log Check
- [ ] Logs contain `action: "BLOCKED"`
- [ ] Logs contain `block_code: "BLOCKED_INJECTION"`
- [ ] Logs contain `findings` with injection type

---

## Issues Found

| Test # | Issue | Severity | Action Taken |
|--------|-------|----------|--------------|
| | | | |
| | | | |
| | | | |

---

## Notes

_Use this space for additional observations or comments:_

________________________________________________________________________

________________________________________________________________________

________________________________________________________________________

---

## Sign-off

- **Testing Completed:** ________________ (Date/Time)
- **All Tests Passed:** [ ] Yes [ ] No
- **Ready for Production:** [ ] Yes [ ] No
- **Notes:** _____________________________________________________________

