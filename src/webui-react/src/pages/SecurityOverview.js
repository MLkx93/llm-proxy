import React, { useState, useEffect, useCallback } from 'react';
import SecurityLayout from '../components/SecurityLayout';
import { MOCK_LOGS, computeStats } from '../mockAuditData';
import { getAuditStats } from '../services/api';

const BLOCK_COLORS = {
  MALICIOUS_CODE_PATTERN:     '#e53e3e',
  SECRET_DETECTED:            '#7c52aa',
  PII_DETECTED:               '#e040a0',
  BLOCKED_VULNERABLE_PACKAGE: '#0096cc',
  RATE_LIMITED:               '#f59e0b',
  PROMPT_INJECTION:           '#10b981',
};

const FINDING_ICONS = {
  EMAIL_ADDRESS: 'mail',
  API_KEY:       'key',
  PERSON_NAME:   'person',
  CREDIT_CARD:   'credit_card',
  PHONE_NUMBER:  'phone',
  AWS_ACCESS_KEY:'cloud',
  GITHUB_TOKEN:  'code',
  OPENAI_API_KEY:'smart_toy',
};

function StatCard({ label, value, sub, subColor, bg, border, shadow, icon, iconColor }) {
  return (
    <div className="sa-card" style={{ padding: 20, background: bg || 'var(--sa-surface)', border: `1px solid ${border || 'var(--sa-outline-variant)'}`, boxShadow: shadow || '' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--sa-on-surface-variant)' }}>{label}</span>
        <span className="sa-icon" style={{ color: iconColor || 'var(--sa-tertiary)' }}>{icon}</span>
      </div>
      <div className="sa-mono" style={{ fontSize: 28, fontWeight: 700, color: 'var(--sa-on-surface)' }}>{value}</div>
      {sub && (
        <div style={{ marginTop: 8, fontSize: 11, fontWeight: 700, color: subColor || 'var(--sa-tertiary)', display: 'flex', alignItems: 'center', gap: 4 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function TrafficChart({ logs }) {
  // Build 24 hourly buckets
  const now = Date.now();
  const buckets = Array.from({ length: 24 }, (_, i) => ({ hour: i, allowed: 0, blocked: 0 }));
  logs.forEach(l => {
    const age = (now - new Date(l.timestamp)) / 3600000;
    const bucket = Math.min(23, Math.floor(age));
    if (bucket >= 0 && bucket < 24) {
      if (l.action === 'ALLOWED') buckets[23 - bucket].allowed++;
      else if (l.action === 'BLOCKED') buckets[23 - bucket].blocked++;
    }
  });

  const maxVal = Math.max(...buckets.map(b => b.allowed + b.blocked), 1);
  const w = 600; const h = 160; const pad = { left: 32, right: 8, top: 10, bottom: 28 };
  const innerW = w - pad.left - pad.right;
  const innerH = h - pad.top - pad.bottom;

  const pointsAllowed = buckets.map((b, i) => {
    const x = pad.left + (i / 23) * innerW;
    const y = pad.top + innerH - (b.allowed / maxVal) * innerH;
    return `${x},${y}`;
  }).join(' ');

  const pointsBlocked = buckets.map((b, i) => {
    const x = pad.left + (i / 23) * innerW;
    const y = pad.top + innerH - (b.blocked / maxVal) * innerH;
    return `${x},${y}`;
  }).join(' ');

  const areaAllowed = `${pad.left},${pad.top + innerH} ${pointsAllowed} ${pad.left + innerW},${pad.top + innerH}`;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 'auto' }} preserveAspectRatio="none">
      <defs>
        <linearGradient id="gradAllowed" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#0096cc" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#0096cc" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* Grid lines */}
      {[0.25, 0.5, 0.75, 1].map(f => (
        <line key={f} x1={pad.left} y1={pad.top + innerH * (1 - f)} x2={pad.left + innerW} y2={pad.top + innerH * (1 - f)}
          stroke="rgba(220,200,224,0.4)" strokeWidth="1" />
      ))}
      {/* Area fill */}
      <polygon points={areaAllowed} fill="url(#gradAllowed)" />
      {/* Allowed line */}
      <polyline points={pointsAllowed} fill="none" stroke="#0096cc" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {/* Blocked line */}
      <polyline points={pointsBlocked} fill="none" stroke="#e53e3e" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {/* X-axis */}
      {['00:00','06:00','12:00','18:00','Now'].map((label, i) => (
        <text key={label} x={pad.left + (i / 4) * innerW} y={h - 6}
          fontSize="9" fill="rgba(96,72,104,0.6)" textAnchor="middle" fontFamily="Space Mono">
          {label}
        </text>
      ))}
      {/* Y-axis */}
      {[0, Math.round(maxVal / 2), maxVal].map((v, i) => (
        <text key={i} x={pad.left - 4} y={pad.top + innerH - (v / maxVal) * innerH + 3}
          fontSize="9" fill="rgba(96,72,104,0.6)" textAnchor="end" fontFamily="Space Mono">
          {v}
        </text>
      ))}
    </svg>
  );
}

function DonutChart({ blockReasons }) {
  const total = Object.values(blockReasons).reduce((a, b) => a + b, 0) || 1;
  const entries = Object.entries(blockReasons).sort((a, b) => b[1] - a[1]).slice(0, 5);

  let cumulativePct = 0;
  const segments = entries.map(([code, count]) => {
    const pct = count / total;
    const start = cumulativePct;
    cumulativePct += pct;
    return { code, count, pct, start };
  });

  const gradient = segments.map(s => {
    const color = BLOCK_COLORS[s.code] || '#aaa';
    return `${color} ${(s.start * 100).toFixed(1)}% ${((s.start + s.pct) * 100).toFixed(1)}%`;
  }).join(', ');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
      <div style={{ position: 'relative', width: 160, height: 160 }}>
        <div style={{
          width: 160, height: 160, borderRadius: '50%',
          background: `conic-gradient(${gradient}, #dcc8e0 ${(cumulativePct * 100).toFixed(1)}% 100%)`,
        }} />
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 100, height: 100, borderRadius: '50%',
          background: 'var(--sa-surface)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
        }}>
          <span className="sa-mono" style={{ fontSize: 20, fontWeight: 700 }}>{total}</span>
          <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--sa-on-surface-variant)' }}>Total</span>
        </div>
      </div>
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {segments.map(s => (
          <div key={s.code} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div className="sa-dot" style={{ background: BLOCK_COLORS[s.code] || '#aaa' }} />
              <span style={{ fontWeight: 700, color: 'var(--sa-on-surface)' }}>
                {s.code.replace(/_/g, ' ').replace('BLOCKED ', '')}
              </span>
            </div>
            <span className="sa-mono" style={{ color: 'var(--sa-on-surface-variant)', fontWeight: 700 }}>
              {(s.pct * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopFindings({ findingCounts }) {
  const entries = Object.entries(findingCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const max = entries[0]?.[1] || 1;
  const colors = ['var(--sa-tertiary)', 'var(--sa-secondary)', 'var(--sa-primary)', '#f59e0b', '#10b981'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {entries.map(([type, count], i) => (
        <div key={type}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontWeight: 700, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="sa-icon" style={{ fontSize: 16, color: colors[i] }}>{FINDING_ICONS[type] || 'info'}</span>
              {type}
            </span>
            <span className="sa-mono" style={{ fontSize: 13, fontWeight: 700, color: colors[i] }}>{count.toLocaleString()}</span>
          </div>
          <div className="sa-bar-track">
            <div className="sa-bar-fill" style={{ width: `${(count / max) * 100}%`, background: colors[i] }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function SecurityOverview() {
  const [timeRange, setTimeRange] = useState('24h');
  const [logs, setLogs] = useState(MOCK_LOGS);          // drives the time-bucketed traffic chart
  const [stats, setStats] = useState(computeStats(MOCK_LOGS));
  const [usingMock, setUsingMock] = useState(false);

  // Fetch real aggregated stats; fall back to mock data if the API/DB is down.
  const fetchStats = useCallback(async (range) => {
    try {
      const res = await getAuditStats(range);
      setStats(res.data);
      setUsingMock(false);
    } catch {
      const hours = range === '1h' ? 1 : range === '24h' ? 24 : 168;
      const cutoff = Date.now() - hours * 3600000;
      const filtered = MOCK_LOGS.filter(l => new Date(l.timestamp) > cutoff);
      setLogs(filtered);
      setStats(computeStats(filtered));
      setUsingMock(true);
    }
  }, []);

  useEffect(() => {
    fetchStats(timeRange);
    const interval = setInterval(() => fetchStats(timeRange), 5000);
    return () => clearInterval(interval);
  }, [timeRange, fetchStats]);

  const filterByRange = (range) => setTimeRange(range);

  return (
    <SecurityLayout timeRange={timeRange} onTimeRange={filterByRange} onRefresh={() => filterByRange(timeRange)}>
      {/* Warning banner when using mock data */}
      {usingMock && (
        <div style={{
          background: 'var(--sa-error-container)',
          border: '1px solid rgba(229,62,62,0.3)',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '13px',
          color: 'var(--sa-on-error-container)',
          fontWeight: '500',
        }}>
          <span className="sa-icon" style={{ fontSize: '16px' }}>warning</span>
          Could not reach the audit API — showing demo data. Check that the proxy is running on port 8080.
        </div>
      )}

      {/* Page header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 32 }}>
        <div>
          <h2 style={{ fontSize: 28, fontWeight: 900, letterSpacing: '-0.5px', color: 'var(--sa-on-surface)' }}>Security Overview</h2>
          <p style={{ color: 'var(--sa-on-surface-variant)', marginTop: 4, fontSize: 14, fontWeight: 500 }}>
            Real-time analysis of LLM proxy traffic and interventions.
          </p>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: 'var(--sa-surface-container)', borderRadius: 9999,
          padding: '6px 16px', fontSize: 13, fontFamily: 'Space Mono, monospace',
          color: 'var(--sa-on-surface-variant)',
        }}>
          <div className="sa-pulse" />
          {usingMock ? 'Demo Data' : 'System Active'}
        </div>
      </div>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16, marginBottom: 28 }}>
        <StatCard label="Total Requests" value={stats.total.toLocaleString()} sub="↑ Last 24h" icon="swap_horiz" iconColor="var(--sa-tertiary)" />
        <StatCard label="Blocked" value={stats.blocked.toLocaleString()}
          bg="var(--sa-error-container)" border="rgba(229,62,62,0.2)"
          shadow="0 4px 16px rgba(229,62,62,0.15)"
          sub={<><span className="sa-icon" style={{fontSize:12}}>trending_up</span> {((stats.blocked/stats.total)*100||0).toFixed(1)}% rate</>}
          subColor="var(--sa-error)" icon="block" iconColor="var(--sa-error)" />
        <StatCard label="Secrets Detected" value={stats.secretsDetected.toLocaleString()}
          bg="var(--sa-secondary-container)" border="rgba(124,82,170,0.2)"
          shadow="0 4px 16px rgba(124,82,170,0.15)"
          sub={<><span className="sa-icon" style={{fontSize:12}}>lock</span> Blocked</>}
          subColor="var(--sa-secondary)" icon="lock" iconColor="var(--sa-secondary)" />
        <StatCard label="PII Redacted" value={stats.piiRedacted.toLocaleString()}
          bg="var(--sa-primary-fixed)" border="rgba(224,64,160,0.2)"
          shadow="0 4px 16px rgba(224,64,160,0.15)"
          sub="Stable" subColor="var(--sa-primary)" icon="shield_person" iconColor="var(--sa-primary)" />
        <StatCard label="Avg. Latency" value={<>{stats.avgLatency}<span style={{fontSize:18,color:'var(--sa-on-surface-variant)'}}>ms</span></>}
          sub={<><span className="sa-icon" style={{fontSize:12}}>check_circle</span> Within SLA</>}
          icon="speed" iconColor="var(--sa-tertiary)" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* Traffic chart */}
        <div className="sa-card" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Traffic Flow</h3>
            <div style={{ display: 'flex', gap: 16, fontSize: 12, fontWeight: 700 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div className="sa-dot" style={{ background: 'var(--sa-tertiary)' }} /> Allowed
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div className="sa-dot" style={{ background: 'var(--sa-error)' }} /> Blocked
              </div>
            </div>
          </div>
          <TrafficChart logs={logs} />
        </div>

        {/* Donut chart */}
        <div className="sa-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Intervention Reasons</h3>
          <DonutChart blockReasons={stats.blockReasons} />
        </div>
      </div>

      {/* Top findings bar chart */}
      <div className="sa-card" style={{ padding: 24 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Top Data Entities Detected</h3>
        <TopFindings findingCounts={stats.findingCounts} />
      </div>
    </SecurityLayout>
  );
}
