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
      'PII Detection': 'Automatically detects and blocks personally identifiable information like social security numbers, credit cards, email addresses, and phone numbers from being sent to LLMs.',
      'Credential Detection': 'Prevents API keys, passwords, tokens, and other secrets from leaking in prompts to LLM providers.',
      'Prompt Injection': 'Blocks malicious attempts to manipulate LLM behavior through crafted prompts that ignore safety guidelines.',
      'Smart Redaction': 'Context-aware removal of sensitive information while preserving utility for legitimate LLM processing.',
      'Nexus Validation': 'Verifies that any packages or dependencies mentioned in LLM-generated code exist in your approved internal repository.',
      'Vulnerability Scan': 'Checks packages against public vulnerability databases (OSV, NVD/CVE) to identify known security issues.',
      'Version Validation': 'Ensures that package versions mentioned in generated code are not affected by known vulnerabilities.',
      'Dependency Tree': 'Analyzes the full dependency graph of generated code to catch transitive vulnerabilities.',
      'Sandbox Execution': 'Runs generated code in isolated Docker containers with resource limits to detect malicious behavior.',
      'Risk Scoring': 'Combines multiple risk factors into a weighted score to help prioritize security reviews.',
      'Rate Limiting': 'Prevents abuse and ensures fair usage by limiting the number of requests per application or user.',
      'Circuit Breaker': 'Automatically temporarily stops requests to failing services to prevent cascading failures.'
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
          The LLM Security Proxy is a centralized security gateway designed to protect organizations
          using Large Language Models (LLMs) by providing comprehensive security controls over
          both input prompts and LLM-generated outputs.
        </p>

        <div className="overview-grid">
          <div className="overview-card">
            <div className="overview-icon">🔒</div>
            <div className="overview-content">
              <h3>Input Protection</h3>
              <p>Scans all incoming prompts for sensitive data (PII, credentials),
                 prompt injection attempts, and malicious content before reaching LLMs.</p>
            </div>
          </div>
          <div className="overview-card">
            <div className="overview-icon">🛡️</div>
            <div className="overview-content">
              <h3>Output Validation</h3>
              <p>Analyzes LLM-generated responses for security risks including
                 unsafe code, vulnerable dependencies, and data leakage.</p>
            </div>
          </div>
          <div className="overview-card">
            <div className="overview-icon">🔄</div>
            <div className="overview-content">
              <h3>Provider Agnostic</h3>
              <p>Works with any LLM provider (OpenAI, Anthropic, etc.) through
                 a unified interface, giving you flexibility without compromising security.</p>
            </div>
          </div>
          <div className="overview-card">
            <div className="overview-icon">📊</div>
            <div className="overview-content">
              <h3>Enterprise Ready</h3>
              <p>Provides audit logging, monitoring, and policy enforcement
                 suitable for enterprise deployment and compliance requirements.</p>
            </div>
          </div>
        </div>
      </div>

      {/* How It Works Section */}
      <div className="card how-it-works-full">
        <h2>⚙️ How the Security Pipeline Works</h2>
        <p className="how-it-works-description">
          Every LLM request follows a 5-stage security pipeline designed to catch
          threats at multiple layers while minimizing false positives:
        </p>
        <div className="pipeline-container-full">
          <div className="pipeline-step-full">
            <div className="step-circle">1</div>
            <div className="step-label">Authentication & Rate Limiting</div>
            <div className="step-description">
              Verify API keys, enforce rate limits, and identify the application
              making the request for proper logging and policy application.
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">2</div>
            <div className="step-label">Input Policy Engine</div>
            <div className="step-description">
              Scan prompts for PII (SSN, credit cards, emails), API keys/secrets,
              and prompt injection attacks using NER and pattern matching.
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">3</div>
            <div className="step-label">LLM Provider</div>
            <div className="step-description">
              Forward cleaned request to selected LLM provider (OpenAI, Anthropic,
              etc.) for actual response generation.
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">4</div>
            <div className="step-label">Output Security Engine</div>
            <div className="step-description">
              Validate generated code for safety: check dependencies against
              approved repositories, scan for vulnerabilities, and execute in sandbox.
            </div>
          </div>
          <div className="pipeline-arrow">→</div>
          <div className="pipeline-step-full">
            <div className="step-circle">5</div>
            <div className="step-label">Secure Response Delivery</div>
            <div className="step-description">
              Return validated, safe response to your application or block with
              detailed explanation if security risks are detected.
            </div>
          </div>
        </div>
      </div>

      <div className="dashboard-grid">
        {/* Health Status */}
        {health && health.status && (
          <div className="card health-status">
            <h2>🏥 System Health</h2>
            <div className={`status ${getStatusColor(health.status)}`}>
              {health.status === 'ok' ? '✅' : '⚠️'} {health.status?.toUpperCase() || 'UNKNOWN'}
            </div>
            <p>Service: {health.service || 'Unknown'}</p>
          </div>
        )}

        {/* Metrics */}
        {metrics && metrics.total_requests !== undefined && (
          <div className="card metrics">
            <h2>📈 Request Metrics</h2>
            <div className="metric-grid">
              <div className="metric">
                <div className="metric-value">{metrics.total_requests || 0}</div>
                <div className="metric-label">Total Requests</div>
              </div>
              <div className="metric">
                <div className="metric-value">{metrics.successful_requests || 0}</div>
                <div className="metric-label">Successful</div>
              </div>
              <div className="metric">
                <div className="metric-value">{metrics.blocked_requests || 0}</div>
                <div className="metric-label">Blocked</div>
              </div>
              <div className="metric">
                <div className="metric-value">{(metrics.avg_response_time || 0).toFixed(2)}s</div>
                <div className="metric-label">Avg Response</div>
              </div>
            </div>
          </div>
        )}

        {/* Codebase Stats */}
        {codebaseStats && codebaseStats.total_files !== undefined && (
          <div className="card codebase-stats">
            <h2>📁 Codebase Statistics</h2>
            <div className="stat-grid">
              <div className="stat">
                <div className="stat-value">{codebaseStats.total_files}</div>
                <div className="stat-label">Total Files</div>
              </div>
              <div className="stat">
                <div className="stat-value">{codebaseStats.total_lines}</div>
                <div className="stat-label">Lines of Code</div>
              </div>
              <div className="stat">
                <div className="stat-value">{codebaseStats.total_components}</div>
                <div className="stat-label">Components</div>
              </div>
            </div>
          </div>
        )}

        {/* Security Features */}
        {features && features.length > 0 && (
          <div className="card security-features">
            <h2>🛡️ Security Features Explained</h2>
            <p className="features-intro">
              Here are the security protections actively working to keep your LLM usage safe:
            </p>
            <div className="features-list-enhanced">
              {features.map((feature, index) => (
                <div key={index} className="feature-item-enhanced">
                  <div className="feature-header">
                    <span className={`feature-badge ${feature.badge === 'Active' ? 'active' : 'configurable'}`}>
                      {feature.badge === 'Active' ? 'Active' : 'Configurable'}
                    </span>
                    <h3 className="feature-title">{feature.name}</h3>
                  </div>
                  <p className="feature-description-enhanced">
                    {getFeatureDescription(feature.name)}
                  </p>
                  <div className="feature-category-badge category-{feature.category.toLowerCase()}">
                    {feature.category}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Security Pipeline */}
        <div className="card security-pipeline">
          <h2>🔄 Security Pipeline</h2>
          <div className="pipeline-steps">
            {pipeline.map((phase, index) => (
              <div key={index} className="pipeline-step">
                <div className={`step-icon ${phase.status === 'Active' ? 'active' : 'inactive'}`}>
                  {phase.status === 'Active' ? '✅' : '⏸️'}
                </div>
                <div className="step-info">
                  <div className="step-name">{phase.name}</div>
                  <div className="step-description">{phase.description}</div>
                </div>
                {phase.status === 'Active' && (
                  <div className="step-time">
                    {phase.avg_time_ms ? `${phase.avg_time_ms}ms` : 'N/A'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Issues */}
        {issues && issues.length > 0 && (
          <div className="card issues">
            <h2>⚠️ Known Issues</h2>
            <div className="issues-list">
              {issues.map((issue, index) => (
                <div key={index} className={`issue-item ${getSeverityColor(issue?.severity)}`}>
                  <div className="issue-severity">{issue?.severity?.toUpperCase() || 'INFO'}</div>
                  <div className="issue-title">{issue?.title || 'Untitled Issue'}</div>
                  <div className="issue-description">{issue?.description || 'No description available'}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Components */}
        <div className="card components">
          <h2>🧩 Component Inventory</h2>
          <div className="components-grid">
            {components.map((component, index) => (
              <div key={index} className="component-item">
                <div className="component-name">{component.name}</div>
                <div className="component-type">{component.type}</div>
                <div className="component-status">{component.status}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Roadmap */}
        {roadmap.length > 0 && (
          <div className="card roadmap">
            <h2>🗺️ Improvement Roadmap</h2>
            <div className="roadmap-list">
              {roadmap.map((item, index) => (
                <div key={index} className="roadmap-item">
                  <div className="roadmap-priority">{item.priority}</div>
                  <div className="roadmap-title">{item.title}</div>
                  <div className="roadmap-description">{item.description}</div>
                  <div className="roadmap-eta">{item.eta || 'TBD'}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;