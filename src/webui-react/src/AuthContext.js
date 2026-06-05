import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { login as apiLogin, getMe } from './services/api';

const AuthContext = createContext(null);

// 'keycloak' → proxy-served admin console using corporate SSO.
// 'demo'     → the demo chat app's simple username/password login (default).
const AUTH_MODE = process.env.REACT_APP_AUTH_MODE || 'demo';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);     // { sub, name, role }
  const [loading, setLoading] = useState(true);

  // ── Keycloak (SSO) mode ────────────────────────────────────────────────────
  useEffect(() => {
    if (AUTH_MODE !== 'keycloak') return;
    let cancelled = false;
    (async () => {
      try {
        const { getKeycloak, initKeycloak } = await import('./keycloak');
        await initKeycloak();                    // redirects to Keycloak if needed
        const kc = getKeycloak();
        // Store the access token where the axios interceptor reads it.
        localStorage.setItem('shield_token', kc.token);
        kc.onAuthRefreshSuccess = () => localStorage.setItem('shield_token', kc.token);
        const roles = kc.tokenParsed?.realm_access?.roles || [];
        const adminRole = process.env.REACT_APP_KEYCLOAK_ADMIN_ROLE || 'security-admin';
        if (!cancelled) {
          setUser({
            sub: kc.tokenParsed?.sub,
            name: kc.tokenParsed?.preferred_username || kc.tokenParsed?.name,
            role: roles.includes(adminRole) ? 'admin' : 'user',
          });
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // ── Demo mode ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (AUTH_MODE === 'keycloak') return;
    const token = localStorage.getItem('shield_token');
    if (!token) { setLoading(false); return; }
    getMe()
      .then((res) => setUser(res.data))
      .catch(() => { localStorage.removeItem('shield_token'); setUser(null); })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username, password) => {
    const res = await apiLogin(username, password);
    localStorage.setItem('shield_token', res.data.token);
    setUser(res.data.user);
    return res.data.user;
  }, []);

  const logout = useCallback(async () => {
    localStorage.removeItem('shield_token');
    setUser(null);
    if (AUTH_MODE === 'keycloak') {
      const { getKeycloak } = await import('./keycloak');
      getKeycloak().logout();
    }
  }, []);

  const value = {
    user, loading, login, logout,
    isAdmin: user?.role === 'admin',
    authMode: AUTH_MODE,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
