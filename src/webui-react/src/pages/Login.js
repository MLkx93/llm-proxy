import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import '../security.css';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const from = location.state?.from || '/';

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed. Check your credentials.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="shield-ai" style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--sa-background)',
    }}>
      <div className="sa-card" style={{ padding: 40, width: 380, textAlign: 'center' }}>
        <div style={{
          width: 56, height: 56, borderRadius: '50%', background: 'var(--sa-primary)',
          color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 900, fontSize: 28, margin: '0 auto 16px',
          boxShadow: '0 4px 16px rgba(224,64,160,0.25)',
        }}>S</div>
        <h1 style={{ fontSize: 24, fontWeight: 900, color: 'var(--sa-primary)', letterSpacing: '-0.5px' }}>Shield AI</h1>
        <p style={{ fontSize: 13, color: 'var(--sa-on-surface-variant)', marginBottom: 28 }}>LLM Security Proxy — sign in</p>

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <input
            className="sa-input" style={{ paddingLeft: 16, textAlign: 'left' }}
            placeholder="Username" value={username}
            onChange={(e) => setUsername(e.target.value)} autoFocus
          />
          <input
            className="sa-input" style={{ paddingLeft: 16, textAlign: 'left' }}
            type="password" placeholder="Password" value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && (
            <div className="sa-badge sa-badge-blocked" style={{ justifyContent: 'center', padding: '8px' }}>
              {error}
            </div>
          )}
          <button className="sa-btn-primary" type="submit" disabled={busy} style={{ padding: '10px', marginTop: 4 }}>
            {busy ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p style={{ fontSize: 11, color: 'var(--sa-on-surface-variant)', marginTop: 20 }}>
          Demo accounts — <strong>admin / admin</strong> (full) · <strong>user / user</strong> (chat only)
        </p>
      </div>
    </div>
  );
}
