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
        <h1>📊 System Dashboard</h1>
        <p>Real-time monitoring and statistics</p>
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
            <h2>🛡️ Security Features</h2>
            <div className="features-list">
              {features.map((feature, index) => (
                <div key={index} className="feature-item">
                  <span className={`feature-badge ${feature.badge === 'Active' ? 'active' : 'configurable'}`}>
                    {feature.badge === 'Active' ? '✅' : '⚙️'}
                  </span>
                  <span className="feature-name">{feature.name}</span>
                  <span className="feature-description">{feature.description}</span>
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