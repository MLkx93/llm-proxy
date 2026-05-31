# 📚 LLM Proxy Documentation Index

**Central hub for all documentation, guides, and test suites.**

---

## 🎯 START HERE

### For Testing the Input Policy
→ **[QUICK_TEST_PROMPTS.md](QUICK_TEST_PROMPTS.md)** ⭐ **START HERE**
- 19 simple, copy-paste ready prompts
- Test credentials blocking, injection attacks, PII redaction
- Includes ready-to-use curl commands
- Quick testing checklist

---

## 📖 Documentation Organization

### Input Policy Documentation

| Document | Purpose | Use When |
|----------|---------|----------|
| **[input_policy_behavior.md](input_policy_behavior.md)** | Complete reference on block vs redact behavior | Need to understand what blocks/redacts |
| **[multiple_pii_logging_example.md](multiple_pii_logging_example.md)** | Logging format examples | Reading/interpreting audit logs |
| **[README_TESTING.md](README_TESTING.md)** | Master testing guide | Understand complete test structure |

---

### Test Suites

| Document | Scope | Use When |
|----------|-------|----------|
| **[QUICK_TEST_PROMPTS.md](QUICK_TEST_PROMPTS.md)** ⭐ | 19 copy-paste prompts | Quick testing, immediate feedback |
| **[IMPLICIT_DETECTION_TEST.md](IMPLICIT_DETECTION_TEST.md)** | 30 realistic scenarios | Test implicit/hidden threat detection |
| **[pii_redaction_test_prompts.md](pii_redaction_test_prompts.md)** | 34 comprehensive tests | Complete test coverage documentation |
| **[TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md)** | Master test overview | Understand all test categories |
| **[testing_quick_reference.md](testing_quick_reference.md)** | Quick reference matrix | Fast lookup during testing |

---

### Test Execution & Reporting

| Document | Purpose | Use When |
|----------|---------|----------|
| **[test_execution_template.md](test_execution_template.md)** | Printable test report form | Recording test results formally |

---

### Legacy/Infrastructure

| Document | Purpose |
|----------|---------|
| **[nexus_fix_spec.md](nexus_fix_spec.md)** | Nexus firewall specifications |

---

## 🗺️ Quick Navigation Map

```
docs/
├── INDEX.md (YOU ARE HERE)
│
├── 📍 TESTING ENTRY POINTS
│   ├── QUICK_TEST_PROMPTS.md ⭐ (Start here for quick testing)
│   ├── IMPLICIT_DETECTION_TEST.md (Test real-world scenarios)
│   └── README_TESTING.md (Understand full test structure)
│
├── 📚 REFERENCE DOCUMENTATION
│   ├── input_policy_behavior.md (Complete behavior reference)
│   ├── multiple_pii_logging_example.md (Log format guide)
│   ├── testing_quick_reference.md (Quick lookup matrix)
│   └── TEST_SUITE_OVERVIEW.md (Test categories overview)
│
├── 📋 TEST CATALOGS
│   ├── pii_redaction_test_prompts.md (34 comprehensive tests)
│   └── test_execution_template.md (Record results)
│
└── 🔧 INFRASTRUCTURE
    └── nexus_fix_spec.md (Nexus specifications)
```

---

## 📊 What Each Test Suite Tests

### QUICK_TEST_PROMPTS.md (19 tests) ⭐ **START HERE**
```
✅ PII Redaction (4):
  - Email address
  - Phone number
  - SSN
  - Multiple PII combined

❌ Credentials Blocking (7):
  - OpenAI API key
  - GitHub token
  - AWS access key
  - Bearer token
  - Password assignment
  - MongoDB connection string
  - PostgreSQL connection string

❌ Injection Attacks (5):
  - Ignore instructions
  - Disregard prompt
  - DAN jailbreak
  - Role hijack
  - System prompt leak

✅ Safe Content (3):
  - Tech question
  - Code review
  - Business question
```

### IMPLICIT_DETECTION_TEST.md (30 tests)
```
Realistic scenarios where threats are embedded naturally:

✅ PII (14 tests):
  - Emails in casual mentions
  - Phones in different formats
  - SSN/IDs in applications
  - Credit cards in "test" contexts
  - Private IPs in troubleshooting
  - IBANs in transfers

❌ Credentials (6 tests):
  - API keys in stack traces
  - Tokens in code
  - Passwords in configs
  - Connection strings

❌ Injections (7 tests):
  - Jailbreaks as questions
  - Academic interest framing
  - Roleplay requests

🔀 Mixed Real-World (3 tests):
  - Customer profiles
  - Code commits
  - Social engineering
```

### pii_redaction_test_prompts.md (34 tests)
```
Complete comprehensive test catalog with:
- All 16 PII types detailed
- All 9 credential types detailed
- All 5 injection patterns detailed
- All 4 safe content scenarios
- Real-world examples
- Expected outputs
- Audit log verification
```

---

## 🚀 Quick Start Paths

### Path 1: Fast Testing (10 minutes)
1. Open **[QUICK_TEST_PROMPTS.md](QUICK_TEST_PROMPTS.md)**
2. Copy a prompt
3. Test with curl command provided
4. Check status code and audit log
5. Done

### Path 2: Thorough Testing (1-2 hours)
1. Read **[README_TESTING.md](README_TESTING.md)** - understand structure
2. Use **[IMPLICIT_DETECTION_TEST.md](IMPLICIT_DETECTION_TEST.md)** - realistic scenarios
3. Record results in **[test_execution_template.md](test_execution_template.md)**
4. Reference **[input_policy_behavior.md](input_policy_behavior.md)** as needed
5. Verify logs with **[multiple_pii_logging_example.md](multiple_pii_logging_example.md)**

### Path 3: Comprehensive Coverage (2-4 hours)
1. Read **[TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md)** - complete overview
2. Use **[pii_redaction_test_prompts.md](pii_redaction_test_prompts.md)** - all 34 tests
3. Use **[testing_quick_reference.md](testing_quick_reference.md)** - checklist
4. Record in **[test_execution_template.md](test_execution_template.md)**
5. Create formal test report

### Path 4: Understanding Behavior
1. Read **[input_policy_behavior.md](input_policy_behavior.md)** - complete reference
2. Reference **[multiple_pii_logging_example.md](multiple_pii_logging_example.md)** - log format
3. Check **[README_TESTING.md](README_TESTING.md)** - troubleshooting section

---

## 📝 File Descriptions

### QUICK_TEST_PROMPTS.md ⭐
- **Lines:** ~200
- **Format:** Copy-paste ready prompts
- **Includes:** Curl commands, checklist, log examples
- **Best for:** Quick testing, getting started
- **Time:** 10-30 minutes

### IMPLICIT_DETECTION_TEST.md
- **Lines:** ~600
- **Format:** Realistic scenarios with explanations
- **Tests:** 30 real-world situations
- **Best for:** Testing detection in realistic contexts
- **Time:** 1-2 hours

### pii_redaction_test_prompts.md
- **Lines:** ~675
- **Format:** Comprehensive test catalog
- **Tests:** 34 complete scenarios
- **Includes:** Expected outputs, audit log verification
- **Best for:** Complete test coverage
- **Time:** 2-4 hours

### input_policy_behavior.md
- **Lines:** ~500
- **Format:** Complete reference documentation
- **Covers:** Block vs redact, all threat types, configuration
- **Best for:** Understanding behavior, troubleshooting, changing config
- **Time:** Reference as needed

### README_TESTING.md
- **Lines:** ~400
- **Format:** Master guide with navigation
- **Includes:** Workflow, checklist, troubleshooting
- **Best for:** Understanding complete test structure
- **Time:** 30-60 minutes

### TEST_SUITE_OVERVIEW.md
- **Lines:** ~400
- **Format:** Test categories summary
- **Includes:** Test matrix, workflow, troubleshooting
- **Best for:** Comprehensive overview
- **Time:** Reference as needed

### testing_quick_reference.md
- **Lines:** ~150
- **Format:** Quick reference matrix
- **Best for:** Checklist during testing
- **Time:** Lookup as needed

### test_execution_template.md
- **Lines:** ~350
- **Format:** Printable form
- **Best for:** Recording test results formally
- **Time:** Fill in as you test

### multiple_pii_logging_example.md
- **Lines:** ~100
- **Format:** Log format examples
- **Best for:** Reading/interpreting audit logs
- **Time:** Reference as needed

---

## 📊 File Statistics

| File | Lines | Type | Status |
|------|-------|------|--------|
| QUICK_TEST_PROMPTS.md | ~200 | Copy-paste prompts | ⭐ START HERE |
| IMPLICIT_DETECTION_TEST.md | ~600 | Realistic scenarios | Core |
| pii_redaction_test_prompts.md | ~675 | Comprehensive tests | Core |
| input_policy_behavior.md | ~500 | Reference | Reference |
| README_TESTING.md | ~400 | Master guide | Navigation |
| TEST_SUITE_OVERVIEW.md | ~400 | Test overview | Reference |
| testing_quick_reference.md | ~150 | Quick lookup | Checklist |
| test_execution_template.md | ~350 | Test form | Reporting |
| multiple_pii_logging_example.md | ~100 | Log examples | Reference |
| nexus_fix_spec.md | ~150 | Infrastructure | Legacy |
| **TOTAL** | **~3,525** | | |

---

## 🎯 Recommended Reading Order

**First Time?**
1. This file (INDEX.md) - You are here ✓
2. [QUICK_TEST_PROMPTS.md](QUICK_TEST_PROMPTS.md) - Get started immediately
3. [input_policy_behavior.md](input_policy_behavior.md) - Understand behavior

**Thorough Understanding?**
1. [README_TESTING.md](README_TESTING.md) - Master guide
2. [IMPLICIT_DETECTION_TEST.md](IMPLICIT_DETECTION_TEST.md) - Real scenarios
3. [input_policy_behavior.md](input_policy_behavior.md) - Complete reference
4. [pii_redaction_test_prompts.md](pii_redaction_test_prompts.md) - All 34 tests

**Need to Record Results?**
1. [test_execution_template.md](test_execution_template.md) - Print and fill in
2. [testing_quick_reference.md](testing_quick_reference.md) - Checklist
3. [multiple_pii_logging_example.md](multiple_pii_logging_example.md) - Log verification

**Troubleshooting?**
1. [input_policy_behavior.md](input_policy_behavior.md) - Understand what blocks/redacts
2. [multiple_pii_logging_example.md](multiple_pii_logging_example.md) - Read logs correctly
3. [README_TESTING.md](README_TESTING.md) - Troubleshooting section

---

## ✅ No Duplication

- **QUICK_TEST_PROMPTS.md** - Simple entry point
- **IMPLICIT_DETECTION_TEST.md** - Real-world scenarios (not in QUICK_TEST)
- **pii_redaction_test_prompts.md** - Comprehensive 34 tests (extends QUICK_TEST)
- **input_policy_behavior.md** - Complete behavior reference (not repeated elsewhere)
- **README_TESTING.md** - Master navigation guide (links to others)
- **TEST_SUITE_OVERVIEW.md** - Test overview (complements README_TESTING)
- **testing_quick_reference.md** - Quick matrix (summary format)
- **test_execution_template.md** - Formal reporting form
- **multiple_pii_logging_example.md** - Log format guide
- **nexus_fix_spec.md** - Infrastructure docs

**Each file has a specific purpose and complements others without repetition.**

---

## 🔍 Finding What You Need

| Need | Go To |
|------|-------|
| Quick start testing | QUICK_TEST_PROMPTS.md |
| Test everything | IMPLICIT_DETECTION_TEST.md |
| Understand blocking/redaction | input_policy_behavior.md |
| Record test results | test_execution_template.md |
| Read audit logs | multiple_pii_logging_example.md |
| Full test coverage | pii_redaction_test_prompts.md |
| Navigate all docs | README_TESTING.md |
| Quick checklist | testing_quick_reference.md |
| Test overview | TEST_SUITE_OVERVIEW.md |

---

## 📌 Bookmarks

**Most Used:**
- ⭐ [QUICK_TEST_PROMPTS.md](QUICK_TEST_PROMPTS.md) - For testing
- 📖 [input_policy_behavior.md](input_policy_behavior.md) - For understanding
- 📋 [test_execution_template.md](test_execution_template.md) - For reporting

**Navigation:**
- 🗺️ [README_TESTING.md](README_TESTING.md) - Master guide
- 📊 [TEST_SUITE_OVERVIEW.md](TEST_SUITE_OVERVIEW.md) - Test overview

**Reference:**
- 📝 [multiple_pii_logging_example.md](multiple_pii_logging_example.md) - Log format
- ⚡ [testing_quick_reference.md](testing_quick_reference.md) - Quick lookup

---

**Last Updated:** 2026-05-31

All documentation is centralized here. Start with **QUICK_TEST_PROMPTS.md** for immediate testing.
