import React from 'react';
import './Chat.css';

/**
 * Rich block card — renders WHY a turn was blocked, so the proxy's security
 * value is visible. Different visuals per block category.
 */

const BLOCK_META = {
  BLOCKED_CREDENTIALS:          { icon: '🔑', title: 'Secret / Credential Blocked',
    desc: 'Your message contained an API key or credential. It was blocked before reaching the model.' },
  BLOCKED_PII:                  { icon: '🛡️', title: 'Personal Data Blocked',
    desc: 'Your message contained personal data (PII) and was blocked.' },
  BLOCKED_INJECTION:            { icon: '⚠️', title: 'Prompt Injection Blocked',
    desc: 'A prompt-injection attempt was detected and blocked.' },
  MALICIOUS_CODE_PATTERN:       { icon: '☠️', title: 'Malicious Code Intercepted',
    desc: 'The model generated code matching a dangerous pattern. It was intercepted before reaching you.' },
  BLOCKED_VULNERABLE_PACKAGE:   { icon: '📦', title: 'Vulnerable Package Blocked',
    desc: 'The model suggested a package with a known vulnerability.' },
  BLOCKED_VULNERABLE_VERSION:   { icon: '📦', title: 'Vulnerable Version Blocked',
    desc: 'The suggested package version has a known vulnerability.' },
  RATE_LIMITED:                 { icon: '⏱️', title: 'Rate Limited',
    desc: 'Too many requests. Please slow down.' },
};

const DEFAULT_META = { icon: '🚫', title: 'Request Blocked', desc: 'This request was blocked by the security proxy.' };

// System/network errors — NOT security blocks. Rendered with a neutral style.
const SYSTEM_ERRORS = {
  LLM_ERROR:         { icon: '🔌', title: 'Connection Problem',
    desc: 'Could not reach the language model. This is a network/provider issue, not a security block.' },
  LLM_TIMEOUT:       { icon: '⏳', title: 'Model Timed Out',
    desc: 'The language model took too long to respond. Please try again.' },
  PROXY_UNREACHABLE: { icon: '🔌', title: 'Proxy Unreachable',
    desc: 'Could not connect to the security proxy. Make sure it is running on port 8080.' },
  STREAM_ERROR:      { icon: '🔌', title: 'Stream Interrupted',
    desc: 'The streaming connection was interrupted. Please try again.' },
  ERROR:             { icon: '⚠️', title: 'Something Went Wrong',
    desc: 'An unexpected error occurred. Please try again.' },
  STREAMING_NOT_SUPPORTED: { icon: '⚙️', title: 'Streaming Not Enabled',
    desc: 'The proxy is running without streaming. Restart it with STREAMING_ENABLED=true, or untick "Live streaming" to use buffered mode.' },
};

export default function BlockCard({ block, partial }) {
  const sysMeta = SYSTEM_ERRORS[block.block_code];
  const meta = sysMeta || BLOCK_META[block.block_code] || DEFAULT_META;
  const safe = block.safe_version;
  const isSystem = Boolean(sysMeta);

  return (
    <div className={isSystem ? 'block-card block-card-system' : 'block-card'}>
      <div className="block-card-head">
        <span className="block-card-icon">{meta.icon}</span>
        <div>
          <div className="block-card-title">{meta.title}</div>
          <div className="block-card-code">{block.block_code}</div>
        </div>
      </div>

      <div className="block-card-desc">{meta.desc}</div>

      {block.message && (
        <div className="block-card-reason">{block.message}</div>
      )}

      {safe && (
        <div className="block-card-safe">
          ✅ Safe alternative — use <code>&gt;={safe}</code> instead
        </div>
      )}

      {partial && (
        <details className="block-card-partial">
          <summary>View intercepted output</summary>
          <pre>{partial}</pre>
        </details>
      )}

      <div className="block-card-note">
        {isSystem
          ? 'Your conversation is intact — just send your message again.'
          : 'Your conversation continues — this turn was not sent to the model.'}
      </div>
    </div>
  );
}
