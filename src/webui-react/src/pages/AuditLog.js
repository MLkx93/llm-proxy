import React, { useState, useEffect, useCallback } from 'react';
import SecurityLayout from '../components/SecurityLayout';
import { MOCK_LOGS } from '../mockAuditData';
import { getAuditLogs } from '../services/api';

const PAGE_SIZE = 25;

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    + '.' + String(d.getMilliseconds()).padStart(3, '0');
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function StatusBadge({ action }) {
  const cfg = {
    BLOCKED: { cls: 'sa-badge sa-badge-blocked', dot: '#e53e3e', label: 'BLOCKED' },
    ALLOWED: { cls: 'sa-badge sa-badge-allowed', dot: '#0096cc', label: 'ALLOWED' },
    ERROR:   { cls: 'sa-badge sa-badge-error', dot: '#907898', label: 'ERROR' },
  }[action] || { cls: 'sa-badge sa-badge-error', dot: '#ccc', label: action };
  return (
    <span className={cfg.cls}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.dot, display: 'inline-block' }} />
      {cfg.label}
    </span>
  );
}

function Drawer({ entry, onClose }) {
  if (!entry) return null;

  return (
    <div className="sa-drawer">
      {/* Header */}
      <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--sa-outline-variant)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: 16, fontWeight: 700 }}>Request Details</h2>
        <button className="sa-btn-ghost" onClick={onClose}>
          <span className="sa-icon">close</span>
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Meta grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Time</div>
            <div className="sa-mono" style={{ fontSize: 12 }}>{formatDate(entry.timestamp)} {formatTime(entry.timestamp)}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status</div>
            <StatusBadge action={entry.action} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Model</div>
            <div style={{ fontWeight: 600 }}>{entry.model || '—'}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Latency</div>
            <div className="sa-mono" style={{ color: entry.latency_ms > 5000 ? 'var(--sa-error)' : 'inherit' }}>
              {entry.latency_ms?.toLocaleString()}ms
            </div>
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 4, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Request ID</div>
            <div className="sa-mono" style={{ fontSize: 11, wordBreak: 'break-all' }}>{entry.request_id}</div>
          </div>
        </div>

        {/* Vulnerable package block */}
        {entry.action === 'BLOCKED' && entry.vuln_info && (
          <div style={{ background: 'var(--sa-error-container)', borderRadius: '1rem', padding: 16, border: '1px solid rgba(229,62,62,0.2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontWeight: 700, color: 'var(--sa-on-error-container)' }}>
              <span className="sa-icon" style={{ fontSize: 18 }}>warning</span>
              Vulnerability Detected
            </div>
            <div style={{ fontSize: 13, marginBottom: 12, color: 'var(--sa-on-surface)' }}>
              The model suggested a package with a known CVE.
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
              <span style={{ padding: '4px 10px', borderRadius: 6, background: 'var(--sa-surface)', fontSize: 12, fontFamily: 'Space Mono', border: '1px solid var(--sa-outline-variant)' }}>
                {entry.vuln_info.name}
              </span>
              <span style={{ padding: '4px 10px', borderRadius: 6, background: 'var(--sa-surface)', fontSize: 12, fontFamily: 'Space Mono', border: '1px solid var(--sa-outline-variant)' }}>
                {entry.vuln_info.cve}
              </span>
              <span style={{ padding: '4px 10px', borderRadius: 6, background: 'var(--sa-error)', color: '#fff', fontSize: 12, fontWeight: 700 }}>
                CVSS: {entry.vuln_info.cvss}
              </span>
            </div>
            <div style={{ background: 'var(--sa-surface)', borderRadius: 8, padding: '8px 12px', fontSize: 13, color: 'var(--sa-secondary)', fontWeight: 600, border: '1px solid rgba(124,82,170,0.2)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="sa-icon" style={{ fontSize: 16 }}>verified</span>
              Safe version available: use &gt;={entry.vuln_info.safe_version} instead
            </div>
          </div>
        )}

        {/* Block reason (other) */}
        {entry.action === 'BLOCKED' && entry.block_code && !entry.vuln_info && (
          <div style={{ background: 'var(--sa-error-container)', borderRadius: '1rem', padding: 14, border: '1px solid rgba(229,62,62,0.2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: 'var(--sa-on-error-container)', marginBottom: 6 }}>
              <span className="sa-icon" style={{ fontSize: 16 }}>block</span>
              {entry.block_code.replace(/_/g, ' ')}
            </div>
            <div style={{ fontSize: 12, color: 'var(--sa-on-surface-variant)' }}>
              This request was blocked by the security pipeline.
            </div>
          </div>
        )}

        {/* Findings chips */}
        {entry.findings?.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Detected Entities</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {entry.findings.map((f, i) => (
                <span key={i} className="sa-badge sa-badge-finding">{f}</span>
              ))}
            </div>
          </div>
        )}

        {/* Sanitized prompt */}
        {entry.sanitized_prompt && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Sanitized Prompt</div>
            <div className="sa-glass" style={{ padding: 12, fontFamily: 'Space Mono, monospace', fontSize: 12, lineHeight: 1.6, color: 'var(--sa-on-surface)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {entry.sanitized_prompt.replace(/\[([A-Z_]+)\]/g, (_, type) =>
                `<mark style="background:var(--sa-secondary-container);color:var(--sa-on-secondary-container);padding:1px 5px;border-radius:4px">[${type}]</mark>`
              ).split(/<mark[^>]*>|<\/mark>/g).reduce((acc, part, i) => {
                // Simple way to render marked-up text
                if (i % 2 === 1) {
                  const typeMatch = part.match(/\[([A-Z_]+)\]/);
                  const type = typeMatch ? typeMatch[1] : part;
                  acc.push(<mark key={i} style={{ background: 'var(--sa-secondary-container)', color: 'var(--sa-on-secondary-container)', padding: '1px 6px', borderRadius: 4, fontWeight: 700 }}>[{type}]</mark>);
                } else if (part) {
                  acc.push(<span key={i}>{part}</span>);
                }
                return acc;
              }, [])}
            </div>
          </div>
        )}

        {/* LLM output */}
        {entry.llm_output && (
          <div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginBottom: 8, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Model Output {entry.action === 'BLOCKED' ? '(Intercepted)' : ''}
            </div>
            <pre className="sa-code" style={{ fontSize: 11, lineHeight: 1.7 }}>{entry.llm_output}</pre>
          </div>
        )}
      </div>

      <div style={{ padding: 14, borderTop: '1px solid var(--sa-outline-variant)', background: 'var(--sa-surface)' }}>
        <button style={{ width: '100%', padding: '10px', borderRadius: 9999, border: 'none', background: 'var(--sa-surface-container-high)', color: 'var(--sa-on-surface)', fontWeight: 700, fontSize: 13, cursor: 'pointer', fontFamily: 'DM Sans, sans-serif', transition: 'background 0.2s' }}
          onMouseOver={e => e.target.style.background = 'var(--sa-surface-variant)'}
          onMouseOut={e => e.target.style.background = 'var(--sa-surface-container-high)'}>
          View Full Trace
        </button>
      </div>
    </div>
  );
}

export default function AuditLog() {
  const [timeRange, setTimeRange] = useState('24h');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [blockFilter, setBlockFilter] = useState('ALL');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);

  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [usingMock, setUsingMock] = useState(false);

  // Fetch from the API (server-side filter + pagination); fall back to mock.
  const fetchLogs = useCallback(async () => {
    try {
      const res = await getAuditLogs({
        time_range: timeRange, status: statusFilter,
        block_code: blockFilter, search: search || undefined,
        page, page_size: PAGE_SIZE,
      });
      setEntries(res.data.entries || []);
      setTotal(res.data.total || 0);
      setUsingMock(false);
    } catch {
      // Fallback: client-side filter of mock data
      const hours = timeRange === '1h' ? 1 : timeRange === '24h' ? 24 : 168;
      const cutoff = Date.now() - hours * 3600000;
      const filtered = MOCK_LOGS.filter(l => {
        if (new Date(l.timestamp) < cutoff) return false;
        if (statusFilter !== 'ALL' && l.action !== statusFilter) return false;
        if (blockFilter !== 'ALL' && l.block_code !== blockFilter) return false;
        if (search) {
          const q = search.toLowerCase();
          return l.request_id.includes(q) || (l.model || '').toLowerCase().includes(q) || (l.block_code || '').toLowerCase().includes(q);
        }
        return true;
      });
      setTotal(filtered.length);
      setEntries(filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE));
      setUsingMock(true);
    }
  }, [timeRange, statusFilter, blockFilter, search, page]);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageEntries = entries;

  const blockCodes = [...new Set(MOCK_LOGS.filter(l => l.block_code).map(l => l.block_code))];

  return (
    <SecurityLayout
      timeRange={timeRange} onTimeRange={t => { setTimeRange(t); setPage(1); }}
      searchValue={search} onSearch={v => { setSearch(v); setPage(1); }}
      onRefresh={() => setPage(1)}
    >
      {/* Warning banner when using mock data */}
      {usingMock && (
        <div style={{
          background: 'var(--sa-error-container)',
          border: '1px solid rgba(229,62,62,0.3)',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '16px',
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

      <div style={{ display: 'flex', gap: 0, height: 'calc(100vh - 120px)', overflow: 'hidden' }}>
        {/* Table section */}
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Page header + filters */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h2 style={{ fontSize: 24, fontWeight: 900, letterSpacing: '-0.5px' }}>Audit Log</h2>
              <p style={{ fontSize: 13, color: 'var(--sa-on-surface-variant)', marginTop: 2 }}>
                {total} entries · page {currentPage} of {totalPages}{usingMock ? ' · demo data' : ''}
              </p>
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <select className="sa-select" value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
                <option value="ALL">All Statuses</option>
                <option value="ALLOWED">Allowed</option>
                <option value="BLOCKED">Blocked</option>
                <option value="ERROR">Error</option>
              </select>
              <select className="sa-select" value={blockFilter} onChange={e => { setBlockFilter(e.target.value); setPage(1); }}>
                <option value="ALL">All Reasons</option>
                {blockCodes.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
          </div>

          {/* Table */}
          <div className="sa-glass" style={{ overflow: 'hidden', flex: 1 }}>
            <div style={{ overflowX: 'auto', height: '100%' }}>
              <table className="sa-table" style={{ minWidth: 700 }}>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Status</th>
                    <th>Model</th>
                    <th>Block Reason</th>
                    <th>Findings</th>
                    <th style={{ textAlign: 'right' }}>Latency</th>
                  </tr>
                </thead>
                <tbody>
                  {pageEntries.length === 0 ? (
                    <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: 'var(--sa-on-surface-variant)' }}>No entries match the current filters.</td></tr>
                  ) : pageEntries.map(entry => (
                    <tr key={entry.request_id}
                      className={selected?.request_id === entry.request_id ? 'selected' : ''}
                      onClick={() => setSelected(selected?.request_id === entry.request_id ? null : entry)}>
                      <td>
                        <div className="sa-mono" style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)' }}>{formatTime(entry.timestamp)}</div>
                        <div style={{ fontSize: 10, color: 'var(--sa-outline)' }}>{formatDate(entry.timestamp)}</div>
                      </td>
                      <td><StatusBadge action={entry.action} /></td>
                      <td style={{ fontWeight: 600, fontSize: 13, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>{entry.model || '—'}</td>
                      <td style={{ color: entry.action === 'BLOCKED' ? 'var(--sa-error)' : 'var(--sa-on-surface-variant)', fontWeight: entry.action === 'BLOCKED' ? 600 : 400, fontSize: 12 }}>
                        {entry.block_code ? entry.block_code.replace(/_/g, ' ') : '—'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                          {(entry.findings || []).slice(0, 2).map((f, i) => (
                            <span key={i} className="sa-badge sa-badge-finding" style={{ fontSize: 10 }}>{f}</span>
                          ))}
                          {(entry.findings || []).length > 2 && (
                            <span className="sa-badge" style={{ background: 'var(--sa-surface-container)', color: 'var(--sa-on-surface-variant)', fontSize: 10 }}>+{entry.findings.length - 2}</span>
                          )}
                          {!(entry.findings?.length) && <span style={{ color: 'var(--sa-outline)', fontSize: 12 }}>—</span>}
                        </div>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <span className="sa-mono" style={{ fontSize: 12, color: entry.latency_ms > 5000 ? 'var(--sa-error)' : 'var(--sa-on-surface-variant)' }}>
                          {entry.latency_ms > 5000 ? `>${(entry.latency_ms / 1000).toFixed(0)}s` : `${entry.latency_ms}ms`}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 6, paddingBottom: 8 }}>
            <button className="sa-page-btn" disabled={currentPage === 1} onClick={() => setPage(p => p - 1)}>
              <span className="sa-icon" style={{ fontSize: 18 }}>chevron_left</span>
            </button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let p;
              if (totalPages <= 7) p = i + 1;
              else if (currentPage <= 4) p = i + 1;
              else if (currentPage >= totalPages - 3) p = totalPages - 6 + i;
              else p = currentPage - 3 + i;
              return (
                <button key={p} className={`sa-page-btn ${p === currentPage ? 'active' : ''}`} onClick={() => setPage(p)}>
                  {p}
                </button>
              );
            })}
            <button className="sa-page-btn" disabled={currentPage === totalPages} onClick={() => setPage(p => p + 1)}>
              <span className="sa-icon" style={{ fontSize: 18 }}>chevron_right</span>
            </button>
          </div>
        </div>

        {/* Side drawer */}
        {selected && <Drawer entry={selected} onClose={() => setSelected(null)} />}
      </div>
    </SecurityLayout>
  );
}
