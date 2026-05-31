# Testing Documentation Index

Complete guide to testing the LLM Proxy input policy (block vs redact).

## 📖 Documentation Guide

### START HERE 👇

**[TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md)** - Master overview
- 34 complete test cases organized by category
- Testing workflow and checklist
- Quick reference table of all tests
- Troubleshooting guide

---

## 📚 Documentation Files

### 1. **[pii_redaction_test_prompts.md](pii_redaction_test_prompts.md)** ⭐ Main Test Catalog
**675 lines | 34 test prompts**

The authoritative test prompt collection with:
- **16 PII Redaction Tests** (should return 200 OK with [REDACTED])
  - Email, phone, SSN, credit cards, driver's license, passport, IP, IBAN, names, etc.
  - Multiple PII types combined in one test
- **9 Credential Blocking Tests** (should return 400 Bad Request)
  - API keys (OpenAI, Anthropic, GitHub, AWS)
  - Tokens, private keys, passwords, connection strings
- **5 Injection Attack Tests** (should return 400 Bad Request)
  - Jailbreak attempts (DAN, role hijack, system prompt leak, etc.)
- **4 Safe Content Tests** (should return 200 OK, unchanged)
  - Tech questions, code reviews, business questions
- Real-world scenario examples
- curl command templates for quick testing
- Testing workflow instructions

**Use for:** Running actual tests with exact prompts and expected outputs

---

### 2. **[testing_quick_reference.md](testing_quick_reference.md)** ⚡ Quick Lookup
**150+ lines | At-a-glance reference**

Fast reference guide while testing:
- Overview table of all 34 tests by category
- Quick test summary matrix
- Testing checklist (16 items)
- Log format verification examples
- curl command templates for each category

**Use for:** During testing, quick reference without reading full prompts

---

### 3. **[test_execution_template.md](test_execution_template.md)** 📋 Test Report Form
**Printable | Checkbox-based tracking**

Structured form for recording test results:
- 34 checkbox items (one per test)
- Pass/fail tracking with space for issue notes
- Summary statistics table by category
- Audit log verification section
- Overall results tallying
- Sign-off section

**Use for:** Recording test run results, creating formal test reports

---

### 4. **[input_policy_behavior.md](input_policy_behavior.md)** 📖 Behavior Reference
**500+ lines | Comprehensive reference**

Detailed explanation of system behavior:
- Current configuration (PII_ACTION, CREDENTIAL_ACTION)
- All 11 PII types documented with examples
- All 7 credential types documented
- All 8 injection patterns documented
- Real-world scenario walkthroughs
- Audit log field reference
- Configuration instructions

**Use for:** Understanding behavior, troubleshooting, changing configuration

---

### 5. **[multiple_pii_logging_example.md](multiple_pii_logging_example.md)** 📊 Logging Guide
**100+ lines | Example outputs**

Detailed logging format reference:
- Example of detecting multiple PII types
- Proxy application log JSON format
- Audit log JSON format
- Log field definitions
- Detection layer explanation

**Use for:** Understanding log format, debugging audit logs

---

### 6. **[TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md)** 🎯 Master Overview
**400+ lines | Complete summary**

Master reference combining all info:
- Overview of all 6 documentation files
- Test categories table (all 34 tests organized)
- Testing workflow steps
- Quick test commands
- Results summary template
- Troubleshooting guide
- Reference matrix

**Use for:** Understanding the complete test suite structure

---

## 🎯 Quick Navigation

### I want to...

**...run tests for the first time**
1. Read [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) - Master overview
2. Use [pii_redaction_test_prompts.md](pii_redaction_test_prompts.md) - Get exact prompts
3. Use [testing_quick_reference.md](testing_quick_reference.md) - Track progress
4. Use [test_execution_template.md](test_execution_template.md) - Record results

**...understand what gets blocked vs redacted**
→ Read [input_policy_behavior.md](input_policy_behavior.md)

**...quickly look up a specific test**
→ Use [testing_quick_reference.md](testing_quick_reference.md) summary table

**...interpret audit logs**
→ Read [multiple_pii_logging_example.md](multiple_pii_logging_example.md)

**...troubleshoot a failing test**
→ Read [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) troubleshooting section

**...create a test report**
→ Use [test_execution_template.md](test_execution_template.md)

**...understand the complete test suite**
→ Read [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md)

---

## 📊 Test Summary

**Total Tests:** 34

| Category | Count | Expected | Docs |
|----------|-------|----------|------|
| PII Redaction | 16 | 200 OK + [REDACTED] | pii_redaction_test_prompts.md |
| Credential Blocking | 9 | 400 Bad Request | pii_redaction_test_prompts.md |
| Injection Blocking | 5 | 400 Bad Request | pii_redaction_test_prompts.md |
| Safe Content | 4 | 200 OK unchanged | pii_redaction_test_prompts.md |

---

## ⚙️ System Configuration

**Current Settings:**
- `PII_ACTION=redact` → PII is redacted with [REDACTED]
- `CREDENTIAL_ACTION=block` → Credentials are rejected with 400 error
- `Injection=always block` → Jailbreaks always rejected (non-configurable)

**To Change:**
- Edit `.env` file for `PII_ACTION` and `CREDENTIAL_ACTION`
- Restart proxy for changes to take effect
- Re-run tests to verify new behavior

See [input_policy_behavior.md](input_policy_behavior.md) for full configuration guide.

---

## 🔄 Testing Workflow

1. **Prepare**
   - Start proxy on `http://localhost:8080`
   - Ensure valid API key configured
   - Open `logs/audit.jsonl` for monitoring

2. **Execute**
   - Open [pii_redaction_test_prompts.md](pii_redaction_test_prompts.md)
   - Run each of 34 test prompts
   - Record results in [test_execution_template.md](test_execution_template.md)

3. **Verify**
   - Check HTTP status codes match expected
   - Verify PII is redacted where expected
   - Verify credentials are blocked where expected
   - Check audit log entries for correct format

4. **Report**
   - Calculate pass/fail by category
   - Note any failures with issues
   - Create test report using template

---

## 📝 Example Test Run

```
Test 1: Email Address
Input:  "My email is john@example.com. Can you help me?"
Output: "My email is [REDACTED]. Can you help me?"
Status: ✅ PASS (200 OK, email redacted)

Test 17: OpenAI API Key
Input:  "My key is sk-proj-abcdefghijklmnopqrstuvwxyz12345"
Output: ERROR 400 Bad Request
Status: ✅ PASS (credential blocked)

Test 31: Safe Tech Question
Input:  "How do I use Flask and Django?"
Output: (unchanged)
Status: ✅ PASS (200 OK, no redaction)
```

---

## 🔗 Related Documentation

- **[input_policy_behavior.md](input_policy_behavior.md)** - Complete behavior reference
- **[multiple_pii_logging_example.md](multiple_pii_logging_example.md)** - Logging format guide
- **[pii_redaction_test_prompts.md](pii_redaction_test_prompts.md)** - Full test catalog

---

## ✅ Checklist Before Testing

- [ ] Proxy is running on `http://localhost:8080`
- [ ] Valid API key is configured
- [ ] `logs/audit.jsonl` is accessible
- [ ] All 6 test documentation files are available
- [ ] Ready to run 34 tests
- [ ] Have test execution template ready

---

## 📞 Questions?

Refer to the appropriate documentation:
- **What should be blocked?** → [input_policy_behavior.md](input_policy_behavior.md)
- **What should be redacted?** → [input_policy_behavior.md](input_policy_behavior.md)
- **How do I run a test?** → [pii_redaction_test_prompts.md](pii_redaction_test_prompts.md)
- **What logs should I see?** → [multiple_pii_logging_example.md](multiple_pii_logging_example.md)
- **How do I record results?** → [test_execution_template.md](test_execution_template.md)

---

**Ready to test?** Start with [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) for the complete guide!
