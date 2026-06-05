# Proxy Admin Dashboard — Keycloak (OIDC) Setup

The proxy serves an internal admin console at **`http://<proxy-host>:8080/admin`**
for the security team. Access is gated by the company Keycloak (SSO): users log in
with their corporate account, and the proxy verifies the token (RS256 via the
realm's public keys) before serving audit data.

## Current state (no Keycloak yet)

`OIDC_ENABLED=false` (default). The proxy runs today on **API-key** auth:

- `GET /v1/audit/*` requires a valid proxy API key (`config/api_keys.yaml`).
- The admin UI is already served at `:8080/admin`.

Nothing else is needed to run/demo right now.

## Enabling Keycloak (when you have the realm details)

You need from the company Keycloak:

| Value | Example | Used by |
|---|---|---|
| Server URL | `https://sso.company.com` | proxy + React |
| Realm | `security` | proxy + React |
| Client ID (public SPA client) | `shield-admin` | proxy + React |
| Audience (token `aud`) | `shield-admin` or `account` | proxy |
| Admin role name | `security-admin` | proxy + React |

The Keycloak client should be a **public** client with:
- Standard flow (Authorization Code + PKCE) enabled
- Valid redirect URI: `http://<proxy-host>:8080/admin/*`
- Web origin: `http://<proxy-host>:8080`
- A realm (or client) role named to match `KEYCLOAK_ADMIN_ROLE`, assigned to the
  security-team users.

### 1. Proxy env (verification side)

```bash
export OIDC_ENABLED=true
export KEYCLOAK_SERVER_URL=https://sso.company.com
export KEYCLOAK_REALM=security
export KEYCLOAK_CLIENT_ID=shield-admin
export KEYCLOAK_AUDIENCE=shield-admin
export KEYCLOAK_ADMIN_ROLE=security-admin
bash scripts/start_proxy.sh
```

With OIDC on, `/v1/audit/*` accepts **only** a valid Keycloak token bearing the
admin role — API keys are no longer accepted for audit data (they still work for
chat).

### 2. Admin React bundle (login side)

Build the console in Keycloak mode and drop it where the proxy serves `/admin`
(`src/webui-react/build`):

```bash
cd src/webui-react
REACT_APP_AUTH_MODE=keycloak \
REACT_APP_KEYCLOAK_URL=https://sso.company.com \
REACT_APP_KEYCLOAK_REALM=security \
REACT_APP_KEYCLOAK_CLIENT_ID=shield-admin \
REACT_APP_KEYCLOAK_ADMIN_ROLE=security-admin \
npm run build
```

Then open `http://<proxy-host>:8080/admin` → redirected to Keycloak → on success
the dashboard loads and reads `/v1/audit/*` with the SSO token.

> Note: this Keycloak build is for the **admin console served by the proxy**. The
> separate demo chat app keeps `REACT_APP_AUTH_MODE=demo` (its simple login).

## Verify

1. User WITH the admin role → `/admin` loads, charts populate.
2. User WITHOUT the role → 403 from `/v1/audit/*` (dashboard denies access).
3. Token expiry → keycloak-js refreshes silently; if refresh fails, re-login.
4. Automation: with OIDC on, audit endpoints reject API keys (by design — SSO-only
   for audit data). Turn `OIDC_ENABLED=false` to allow key-based audit access.
