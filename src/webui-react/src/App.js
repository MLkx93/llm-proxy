import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom';
import Chat from './components/Chat';
import Dashboard from './components/Dashboard';
import SecurityOverview from './pages/SecurityOverview';
import AuditLog from './pages/AuditLog';
import Login from './pages/Login';
import { AuthProvider, useAuth } from './AuthContext';
import './App.css';

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>Loading…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return children;
}

function RequireAdmin({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>Loading…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (user.role !== 'admin') return <Navigate to="/" replace />;
  return children;
}

function AppShell() {
  const location = useLocation();
  const { user, logout, isAdmin } = useAuth();

  if (location.pathname === '/login') {
    return <Routes><Route path="/login" element={<Login />} /></Routes>;
  }

  // Security panel uses its own full-screen layout (admin-gated)
  if (location.pathname.startsWith('/security')) {
    return (
      <Routes>
        <Route path="/security" element={<RequireAdmin><SecurityOverview /></RequireAdmin>} />
        <Route path="/security/audit" element={<RequireAdmin><AuditLog /></RequireAdmin>} />
      </Routes>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🛡️ LLM Security Proxy</h1>
        <p>Secure Multi-Provider LLM Gateway</p>
        <nav className="nav-links">
          <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`} end>
            💬 Chat
          </NavLink>
          <NavLink to="/dashboard" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            📊 Dashboard
          </NavLink>
          {isAdmin && (
            <NavLink to="/security" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              🛡️ Security Panel
            </NavLink>
          )}
          {user && (
            <button className="nav-link" onClick={logout} style={{ cursor: 'pointer', background: 'none', border: '1px solid transparent' }}>
              🚪 {user.name} · Logout
            </button>
          )}
        </nav>
      </header>

      <main className="container">
        <Routes>
          <Route path="/" element={<RequireAuth><Chat /></RequireAuth>} />
          <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
        </Routes>
      </main>

      <footer className="footer">
        <p>LLM Security Proxy v2 · React → API Server → Security Proxy → LLM Providers</p>
      </footer>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </Router>
  );
}

export default App;
