import React from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import ModelTester from './components/ModelTester';
import Dashboard from './components/Dashboard';
import StateReport from './components/StateReport';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        {/* Header */}
        <header className="header">
          <h1>🛡️ LLM Security Proxy</h1>
          <p>Secure Multi-Provider LLM Gateway</p>
          <nav className="nav-links">
            <NavLink
              to="/"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              end
            >
              🔬 Model Testing
            </NavLink>
            <NavLink
              to="/dashboard"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              📊 Dashboard
            </NavLink>
            <NavLink
              to="/state"
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              📋 State Report
            </NavLink>
          </nav>
        </header>

        {/* Main Content */}
        <main className="container">
          <Routes>
            <Route path="/" element={<ModelTester />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/state" element={<StateReport />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="footer">
          <p>LLM Security Proxy v1.0.0 · React Frontend → API Server → Security Proxy → LLM Providers</p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
