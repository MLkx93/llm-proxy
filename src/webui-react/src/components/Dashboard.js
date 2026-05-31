import React, { useState, useEffect } from 'react';
import {
  getHealth,
  getMetrics,
  getFeatures,
  getPipeline,
  getIssues,
  getCodebaseStats,
  getComponents,
  getRoadmap
} from '../services/api';
import './Dashboard.css';

function Dashboard() {
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [features, setFeatures] = useState([]);
  const [pipeline, setPipeline] = useState([]);
  const [issues, setIssues] = useState([]);
  const [codebaseStats, setCodebaseStats] = useState(null);
  const [components, setComponents] = useState([]);
  const [roadmap, setRoadmap] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAllData = async () => {
      try {
        setLoading(true);

        // Fetch all data sequentially for better error handling
        const healthRes = await getHealth();
        const metricsRes = await getMetrics();
        const featuresRes = await getFeatures();
        const pipelineRes = await getPipeline();
        const issuesRes = await getIssues();
        const statsRes = await getCodebaseStats();
        const componentsRes = await getComponents();
        const roadmapRes = await getRoadmap();

        setHealth(healthRes.data);
        setMetrics(metricsRes.data);
        setFeatures(featuresRes.data?.features || []);
        setPipeline(pipelineRes.data?.phases || []);
        setIssues(issuesRes.data?.issues || []);
        setCodebaseStats(statsRes.data);
        setComponents(componentsRes.data?.components || []);
        setRoadmap(roadmapRes.data?.items || []);
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
        setError(err.response?.data?.detail || err.message || 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    fetchAllData();
  }, []);

  const getStatusColor = (status) => {
    if (!status) return 'unknown';

    switch (status.toLowerCase()) {
      case 'ok':
      case 'healthy':
      case 'running':
        return 'success';
      case 'warning':
      case 'degraded':
        return 'warning';
      case 'error':
      case 'critical':
      case 'failed':
        return 'error';
      default:
        return 'unknown';
    }
  };

  const getSeverityColor = (severity) => {
    if (!severity) return 'info';

    switch (severity.toLowerCase()) {
      case 'critical':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      case 'low':
        return 'success';
      default:
        return 'info';
    }
  };

  const getFeatureDescription = (featureName) => {
    const descriptions = {
      'PII Detection': 'Detects 11+ types of PII: emails, phones (3 formats), SSNs, credit cards (VISA/MC/AMEX), driver\'s licenses, passports, private IPs, IBANs, person names, and medical licenses. Uses 3-layer detection: fast regex secrets (10μs), format patterns, and Presidio NLP entity recognition.',
      'Credential Detection': 'Catches API keys (OpenAI, Anthropic, GitHub, AWS), Bearer tokens, private keys, passwords, and connection strings. Uses regex patterns matched against exact secret formats. Found credentials = 400 Bad Request block (not redacted).',
      'Prompt Injection': 'Blocks 8 jailbreak patterns: ignore instructions, disregard prompt, DAN mode, role hijack, system prompt leak, context escape, translator trick, and more. Pattern-based detection catches explicit attempts. Always blocks (non-configurable).',
      'Smart Redaction': 'Replaces detected PII with [REDACTED]. Presidio handles context (names in text vs. code), preserves utility for LLM processing. Logs original hash, sanitized hash, and redaction count in audit trail.',
      'Nexus Validation': 'Extracts package names from generated code and checks if they exist in your approved Nexus/internal repository. If package not found → blocks with error. Optional feature (NEXUS_BASE_URL env var).',
      'Vulnerability Scan': 'Queries OSV database and NVD/CVE for known vulnerabilities. Checks if package versions have advisories. Results scored by severity (CRITICAL/HIGH/MEDIUM/LOW). Configurable via VULN_SCAN_ENABLED env var.',
      'Version Validation': 'Parses semantic versioning and matches against SQLite advisory database. Determines if a specific version is vulnerable (e.g., "1.2.3 is bad, 1.2.4+ is safe"). Helps validate LLM-generated version numbers.',
      'Dependency Tree': 'Recursively resolves transitive dependencies. Catches indirect vulnerabilities (e.g., your package is safe, but it depends on a vulnerable package). Prevents supply chain attacks. Optional feature.',
      'Sandbox Execution': 'Runs suspicious code in isolated Docker containers with resource limits (CPU, memory, timeout). Detects runtime behavior anomalies. Behavioral detection finds obfuscation, network requests, and malicious patterns.',
      'Risk Scoring': 'Weighs 5 factors: vulnerability severity, code origin, execution behavior, dependency chain depth, and anomaly detection. Final score: 0-100. Helps prioritize which generated code needs review.',
      'Rate Limiting': 'Token bucket algorithm: configurable requests/minute per API key and app. Prevents abuse and ensures fair resource distribution. Returns 429 Too Many Requests when limit exceeded.',
      'Circuit Breaker': 'Monitors LLM provider health. After 3 consecutive failures, temporarily stops requests (30-60s). Prevents cascading failures and gives upstream time to recover. Auto-recovers with exponential backoff.'
    };

    return descriptions[featureName] || 'Provides advanced security protection for LLM interactions.';
  };

  if (loading) {
    return (
      <div className="dashboard loading">
        <div className="loading-container">
          <div className="loading-spinner">🔄 Loading dashboard...</div>
          <p>Make sure the LLM Security Proxy is running on port 8080</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard error">
        <div className="error-message">
          <h2>❌ Error Loading Dashboard</h2>
          <p>{error}</p>
          <p>Please ensure the LLM Security Proxy is running on port 8080</p>
        </div>
      </div>
    );
  }

  // If no error but also no data, show empty state
  if (!health && !metrics && !features) {
    return (
      <div className="dashboard empty">
        <div className="empty-state">
          <h2>📊 Dashboard</h2>
          <p>No data available. Check if the API server is running on port 8000.</p>
          <button onClick={() => window.location.reload()} className="refresh-btn">
            🔄 Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>📊 LLM Security Proxy Dashboard</h1>
        <p>Monitor and understand your LLM security infrastructure</p>
      </div>

      {/* Project Overview Section */}
      <div className="card overview-full">
        <h2>🎯 What is the LLM Security Proxy?</h2>
        <p className="overview-description">
          The LLM Security Proxy is a centralized security gateway that sits between your applications
          and LLM providers (OpenAI, Anthropic, etc.), protecting against sensitive data leaks, malicious
          prompts, unsafe code generation, and vulnerable dependencies. It provides real-time threat detection,
          smart redaction, and comprehensive audit logging.
        </p>

        <div className="overview-grid">
          <div className="overview-card">
            <div className="overview-icon">🔒</div>
            <div className="overview-content">
              <h3>Input Security (What Happens to Your Prompts)</h3>
              <p>
                <strong>PII Redaction:</strong> Detects emails, phone numbers, SSNs, credit cards, driver's licenses,
                and person names → automatically replaces with [REDACTED]<br/>
                <strong>Credential Blocking:</strong> Catches API keys, passwords, tokens, connection strings
                → blocks the request with 400 error<br/>
                <strong>Injection Protection:</strong> Stops jailbreak attempts and prompt manipulation
                → blocks harmful instructions instantly
              </p>
            </div>
          </div>
          <div className="overview-card">
            <div className="overview-icon">🛡️</div>
            <div className="overview-content">
              <h3>Output Validation (What Happens to LLM Responses)</h3>
              <p>
                <strong>Dependency Checking:</strong> Verifies packages exist in approved repositories<br/>
                <strong>Vulnerability Scanning:</strong> Checks against OSV/CVE databases for known issues<br/>
                <strong>Sandbox Execution:</strong> Runs generated code in isolated Docker containers<br/>
                <strong>Risk Scoring:</strong> Combines multiple factors to flag unsafe content
              </p>
            </div>
          </div>
          <div className="overview-card">
            <div className="overview-icon">🔄</div>
            <div className="overview-content">
              <h3>Universal Coverage (Works Everywhere)</h3>
              <p>
                <strong>Provider Agnostic:</strong> Works with OpenAI, Anthropic, Google, DeepSeek,
                and any OpenRouter model<br/>
                <strong>Format Support:</strong> OpenAI-compatible and Anthropic-compatible endpoints<br/>
                <strong>Smart Redaction:</strong> Preserves legitimate content while removing threats
              </p>
            </div>
          </div>
          <div className="overview-card">
            <div className="overview-icon">📊</div>
            <div className="overview-content">
              <h3>Enterprise-Grade Security</h3>
              <p>
                <strong>Audit Logging:</strong> SHA-256 hashed requests with detection findings and
                redaction details<br/>
                <strong>Real-Time Monitoring:</strong> Dashboard shows health, metrics, and blocked threats<br/>
                <strong>Rate Limiting:</strong> Prevents abuse and ensures fair usage across apps
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* How It Works Section */}
      <div className="card how-it-works-full">
        <h2>⚙️ How Every Request is Protected (5-Stage Pipeline)</h2>
        <p className="how-it-works-description">
          Every LLM request and response is scanned through 5 security layers. Threats are detected
          using NLP-based entity recognition (Presidio), pattern matching, and behavioral analysis:
        </p>
        <div className="pipeline-container-full">
          <div className="pipeline-step-full">
            <div className="step-circle">1</div>
            <div className="step-label">🔑 Auth & Rate Limiting</div>
            <div className="step-description">
              Verify API keys and enforce rate limits. Identify which application is making the request
              for proper audit logging and policy enforcement.
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">2</div>
            <div className="step-label">🛡️ Input Policy (Scan & Redact/Block)</div>
            <div className="step-description">
              <strong>Layer 1 - Fast Secrets:</strong> Regex patterns for API keys, passwords, tokens<br/>
              <strong>Layer 2 - Format Patterns:</strong> SSN formats, credit cards, phone numbers<br/>
              <strong>Layer 3 - NLP Recognition:</strong> Presidio entity recognition for PII in context<br/>
              <strong>Action:</strong> PII → [REDACTED], Credentials → Block (400), Injections → Block (400)
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">3</div>
            <div className="step-label">🚀 Forward to LLM</div>
            <div className="step-description">
              Send cleaned/redacted prompt to your selected provider (OpenAI, Anthropic, DeepSeek,
              Gemini, etc.). Proxy translates between OpenAI and Anthropic formats transparently.
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">4</div>
            <div className="step-label">🔬 Output Validation (Code Safety)</div>
            <div className="step-description">
              <strong>Parse Code:</strong> Extract packages from generated responses<br/>
              <strong>Verify Packages:</strong> Check dependencies exist in approved Nexus repository<br/>
              <strong>Scan Vulnerabilities:</strong> Check versions against OSV/CVE databases<br/>
              <strong>Test Code:</strong> Run suspicious code in isolated Docker sandbox with limits
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">5</div>
            <div className="step-label">✅ Return Safe Response</div>
            <div className="step-description">
              Return validated response to your app or block with detailed error. Log everything
              to audit.jsonl with redaction details, findings, and threat analysis.
            </div>
          </div>
        </div>
      </div>

      {/* Security Features Section */}
      {features && features.length > 0 && (
        <div className="card security-features-full">
          <h2>🛡️ Complete Security Features</h2>
          <p className="features-intro">
            12 active protections working together to secure your LLM interactions:
          </p>
          <div className="features-list-grid">
            {features.map((feature, index) => (
              <div key={index} className="feature-card">
                <div className="feature-icon">{feature.icon}</div>
                <div className="feature-info">
                  <h4 className="feature-name">{feature.name}</h4>
                  <span className={`feature-badge ${feature.badge === 'Active' ? 'active' : 'configurable'}`}>
                    {feature.badge === 'Active' ? '🟢 Active' : '⚙️ Configurable'}
                  </span>
                </div>
                <p className="feature-description">
                  {getFeatureDescription(feature.name)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;