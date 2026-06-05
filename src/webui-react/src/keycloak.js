/**
 * Keycloak (OIDC) client for the proxy-served admin console.
 *
 * Only used when REACT_APP_AUTH_MODE=keycloak (the production admin build served
 * by the proxy at /admin). In demo mode this module is never initialised, so the
 * demo chat app keeps its simple login.
 *
 * Build-time config (set when building the admin bundle):
 *   REACT_APP_KEYCLOAK_URL       e.g. https://sso.company.com
 *   REACT_APP_KEYCLOAK_REALM     e.g. security
 *   REACT_APP_KEYCLOAK_CLIENT_ID e.g. shield-admin
 */
import Keycloak from 'keycloak-js';

let keycloak = null;

export function getKeycloak() {
  if (!keycloak) {
    keycloak = new Keycloak({
      url: process.env.REACT_APP_KEYCLOAK_URL,
      realm: process.env.REACT_APP_KEYCLOAK_REALM,
      clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID,
    });
  }
  return keycloak;
}

/** Initialise SSO: redirects to Keycloak if not already authenticated. */
export async function initKeycloak() {
  const kc = getKeycloak();
  const authenticated = await kc.init({
    onLoad: 'login-required',
    checkLoginIframe: false,
    pkceMethod: 'S256',
  });
  // Keep the token fresh; keycloak-js refreshes silently.
  kc.onTokenExpired = () => kc.updateToken(30).catch(() => kc.login());
  return authenticated;
}
