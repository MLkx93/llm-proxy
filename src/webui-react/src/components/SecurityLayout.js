import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import '../security.css';

export default function SecurityLayout({ children, timeRange, onTimeRange, onRefresh, searchValue, onSearch }) {
  const navigate = useNavigate();

  return (
    <div className="shield-ai" style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>

      {/* Sidebar */}
      <aside style={{
        width: 240, minWidth: 240, height: '100vh',
        background: 'var(--sa-surface-dim)',
        borderRight: '1px solid rgba(220,200,224,0.3)',
        display: 'flex', flexDirection: 'column', padding: '16px',
        position: 'fixed', left: 0, top: 0, zIndex: 40,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32, padding: '4px 8px' }}>
          <div style={{
            width: 40, height: 40, borderRadius: '50%',
            background: 'var(--sa-primary)', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 900, fontSize: 20,
            boxShadow: '0 4px 16px rgba(224,64,160,0.25)',
          }}>S</div>
          <div>
            <div style={{ fontWeight: 900, fontSize: 18, color: 'var(--sa-primary)', letterSpacing: '-0.5px' }}>Shield AI</div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', fontWeight: 500 }}>Proxy Admin Console</div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
          <NavLink to="/security" end className={({ isActive }) => `sa-nav-item ${isActive ? 'active' : ''}`}>
            <span className="sa-icon sa-icon-filled">dashboard</span>
            Overview
          </NavLink>
          <NavLink to="/security/audit" className={({ isActive }) => `sa-nav-item ${isActive ? 'active' : ''}`}>
            <span className="sa-icon">list_alt</span>
            Audit Log
          </NavLink>
        </nav>

        {/* Footer */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px', borderRadius: '1rem',
          background: 'var(--sa-surface-container-low)',
          border: '1px solid rgba(220,200,224,0.4)',
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            background: 'var(--sa-tertiary-container)',
            color: 'var(--sa-on-tertiary-container)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 700, fontSize: 12,
          }}>SA</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--sa-on-surface)' }}>System Admin</div>
            <div style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)' }}>Admin</div>
          </div>
        </div>
      </aside>

      {/* Main area */}
      <div style={{ marginLeft: 240, flex: 1, display: 'flex', flexDirection: 'column', minHeight: '100vh', overflow: 'hidden' }}>

        {/* Top nav */}
        <header style={{
          position: 'sticky', top: 0, zIndex: 30,
          background: 'var(--sa-surface)',
          borderBottom: '1px solid var(--sa-outline-variant)',
          padding: '10px 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 16,
        }}>
          {/* Time range */}
          <div className="sa-time-toggle">
            {['1h','24h','7d'].map(t => (
              <button key={t} className={`sa-time-btn ${timeRange === t ? 'active' : ''}`} onClick={() => onTimeRange && onTimeRange(t)}>
                Last {t}
              </button>
            ))}
          </div>

          {/* Right controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {onSearch !== undefined && (
              <div style={{ position: 'relative' }}>
                <span className="sa-icon" style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--sa-on-surface-variant)', fontSize: 18 }}>search</span>
                <input
                  className="sa-input"
                  placeholder="Search by request ID or model…"
                  value={searchValue || ''}
                  onChange={e => onSearch(e.target.value)}
                  style={{ width: 280 }}
                />
              </div>
            )}
            <button className="sa-btn-ghost" title="Filter">
              <span className="sa-icon">filter_list</span>
            </button>
            <button className="sa-btn-ghost" title="Settings" onClick={() => navigate('/')}>
              <span className="sa-icon">settings</span>
            </button>
            <button className="sa-btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={onRefresh}>
              <span className="sa-icon" style={{ fontSize: 16, color: '#fff' }}>refresh</span>
              Auto-refresh
            </button>
          </div>
        </header>

        {/* Page content */}
        <main style={{ flex: 1, overflow: 'auto', padding: '32px', background: 'var(--sa-background)' }}>
          {children}
        </main>
      </div>
    </div>
  );
}
