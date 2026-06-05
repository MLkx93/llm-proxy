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
  const { user, logout } = useAuth();

  const isAdminConsole = window.location.port === '8080';

  if (location.pathname === '/login') {
    return <Routes><Route path="/login" element={<Login />} /></Routes>;
  }

  // ADMIN CONSOLE MODE (port 8080): only security pages
  if (isAdminConsole) {
    return (
      <Routes>
        <Route path="/" element={<RequireAdmin><SecurityOverview /></RequireAdmin>} />
        <Route path="/audit" element={<RequireAdmin><AuditLog /></RequireAdmin>} />
        <Route path="/login" element={<Login />} />
      </Routes>
    );
  }

  // DEMO MODE (port 8000): chat + dashboard, security panel hidden
  if (location.pathname === '/login') {
    return <Routes><Route path="/login" element={<Login />} /></Routes>;
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
  // When served from proxy at /admin, use /admin as basename.
  // When served from 8000, use / (root).
  const basename = window.location.port === '8080' ? '/admin' : '/';

  return (
    <Router basename={basename}>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </Router>
  );
}

export default App;
