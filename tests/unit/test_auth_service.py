"""
Unit tests for the admin console's demo auth gate
(src/webui_api/services/auth_service.py).
"""
from datetime import datetime, timedelta, timezone

import jwt

from config.settings import settings
from src.webui_api.services.auth_service import (
    _parse_accounts,
    authenticate,
    decode_token,
    identity_from_header,
    issue_token,
)
from src.webui_api.main import check_insecure_auth_defaults


# ---------------------------------------------------------------------------
# authenticate() — against the live default DEMO_ACCOUNTS (admin/admin, user/user)
# ---------------------------------------------------------------------------
class TestAuthenticate:
    def test_valid_admin_credentials(self):
        identity = authenticate("admin", "admin")
        assert identity == {"sub": "admin", "name": "admin", "role": "admin"}

    def test_valid_user_credentials(self):
        identity = authenticate("user", "user")
        assert identity == {"sub": "user", "name": "user", "role": "user"}

    def test_wrong_password_rejected(self):
        assert authenticate("admin", "wrong-password") is None

    def test_unknown_user_rejected(self):
        assert authenticate("nobody", "whatever") is None

    def test_empty_password_rejected(self):
        assert authenticate("admin", "") is None


# ---------------------------------------------------------------------------
# _parse_accounts() — passwords must never be retained in plaintext
# ---------------------------------------------------------------------------
class TestParseAccounts:
    def test_password_not_stored_as_plaintext(self):
        accounts = _parse_accounts()
        for entry in accounts.values():
            assert "password" not in entry
            assert entry["password_hash"] != b"admin"
            assert entry["password_hash"] != b"user"

    def test_password_hash_is_bcrypt(self):
        accounts = _parse_accounts()
        for entry in accounts.values():
            # bcrypt hashes are versioned ($2b$...) — a cheap sanity check
            # that we're not accidentally storing/comparing raw strings.
            assert entry["password_hash"].startswith(b"$2b$")

    def test_malformed_entries_skipped(self, monkeypatch):
        monkeypatch.setattr(
            settings, "DEMO_ACCOUNTS", "admin:admin:admin,not-enough-parts,also:bad"
        )
        accounts = _parse_accounts()
        assert list(accounts.keys()) == ["admin"]


# ---------------------------------------------------------------------------
# issue_token() / decode_token() round-trip
# ---------------------------------------------------------------------------
class TestTokenRoundTrip:
    def test_valid_token_decodes_to_identity(self):
        identity = {"sub": "admin", "name": "admin", "role": "admin"}
        token = issue_token(identity)
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "admin"
        assert decoded["role"] == "admin"

    def test_tampered_token_rejected(self):
        token = issue_token({"sub": "admin", "name": "admin", "role": "admin"})
        tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        assert decode_token(tampered) is None

    def test_garbage_token_rejected(self):
        assert decode_token("not-a-jwt") is None

    def test_expired_token_rejected(self, monkeypatch):
        # Sign a token that already expired instead of waiting real time out.
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "admin",
            "name": "admin",
            "role": "admin",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        assert decode_token(expired_token) is None

    def test_token_signed_with_wrong_secret_rejected(self):
        payload = {
            "sub": "admin",
            "name": "admin",
            "role": "admin",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, "some-other-secret", algorithm="HS256")
        assert decode_token(token) is None


# ---------------------------------------------------------------------------
# identity_from_header()
# ---------------------------------------------------------------------------
class TestIdentityFromHeader:
    def test_missing_header_rejected(self):
        assert identity_from_header(None) is None

    def test_empty_header_rejected(self):
        assert identity_from_header("") is None

    def test_no_bearer_prefix_rejected(self):
        token = issue_token({"sub": "admin", "name": "admin", "role": "admin"})
        assert identity_from_header(token) is None

    def test_bearer_with_no_token_rejected(self):
        assert identity_from_header("Bearer") is None
        assert identity_from_header("Bearer ") is None

    def test_valid_header_end_to_end(self):
        token = issue_token({"sub": "user", "name": "user", "role": "user"})
        identity = identity_from_header(f"Bearer {token}")
        assert identity is not None
        assert identity["sub"] == "user"

    def test_case_insensitive_bearer_prefix(self):
        token = issue_token({"sub": "admin", "name": "admin", "role": "admin"})
        identity = identity_from_header(f"BEARER {token}")
        assert identity is not None


# ---------------------------------------------------------------------------
# check_insecure_auth_defaults() — startup warning for unchanged defaults
# ---------------------------------------------------------------------------
class TestCheckInsecureAuthDefaults:
    def test_warns_when_defaults_untouched(self, monkeypatch):
        monkeypatch.setattr(settings, "OIDC_ENABLED", False)
        monkeypatch.setattr(settings, "JWT_SECRET", "shield-demo-secret-change-me")
        monkeypatch.setattr(settings, "DEMO_ACCOUNTS", "admin:admin:admin,user:user:user")
        assert check_insecure_auth_defaults() is True

    def test_no_warning_when_both_overridden(self, monkeypatch):
        monkeypatch.setattr(settings, "OIDC_ENABLED", False)
        monkeypatch.setattr(settings, "JWT_SECRET", "a-real-random-secret")
        monkeypatch.setattr(settings, "DEMO_ACCOUNTS", "ops:s3cr3t!:admin")
        assert check_insecure_auth_defaults() is False

    def test_no_warning_when_oidc_enabled_even_with_defaults(self, monkeypatch):
        monkeypatch.setattr(settings, "OIDC_ENABLED", True)
        monkeypatch.setattr(settings, "JWT_SECRET", "shield-demo-secret-change-me")
        monkeypatch.setattr(settings, "DEMO_ACCOUNTS", "admin:admin:admin,user:user:user")
        assert check_insecure_auth_defaults() is False

    def test_warns_if_only_jwt_secret_is_default(self, monkeypatch):
        monkeypatch.setattr(settings, "OIDC_ENABLED", False)
        monkeypatch.setattr(settings, "JWT_SECRET", "shield-demo-secret-change-me")
        monkeypatch.setattr(settings, "DEMO_ACCOUNTS", "ops:s3cr3t!:admin")
        assert check_insecure_auth_defaults() is True
