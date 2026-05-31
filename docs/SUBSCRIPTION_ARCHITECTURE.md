# Account-Based Subscription Integration Architecture

## Current State vs. Proposed System

### Current (API Key Authentication)
- API keys stored in `config/api_keys.yaml`
- Bearer token validation via SHA-256 hash
- No user accounts, logins, or subscriptions
- Static rate limiting per API key

### Proposed (Account-Based)
- User accounts with login credentials
- JWT-based session management
- Subscription tiers (Free/Pro/Enterprise)
- Dynamic rate limiting per subscription
- Audit trails per user
- Team management capabilities

---

## System Architecture

```
┌─────────────┐
│  React UI   │
│  (Login)    │
└──────┬──────┘
       │ JWT token
       ▼
┌──────────────────────┐
│  Web API Server      │
│  (FastAPI)           │
│  • Auth middleware   │
│  • Rate limiting     │
│  • User management   │
└──────┬───────────────┘
       │ Service token
       ▼
┌──────────────────────┐
│  LLM Security Proxy  │
│  (Port 8080)         │
│  • Input policy      │
│  • Output security   │
│  • Audit logging     │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  LLM Providers       │
│  (OpenRouter, etc)   │
└──────────────────────┘
```

### Data Layer

```
Database (PostgreSQL/SQLite)
├── users table
│   ├── id (PK)
│   ├── username (unique)
│   ├── email (unique)
│   ├── password_hash (bcrypt)
│   ├── created_at
│   └── updated_at
│
├── subscriptions table
│   ├── id (PK)
│   ├── user_id (FK → users)
│   ├── plan_type (free/pro/enterprise)
│   ├── rate_limit (requests/minute)
│   ├── started_at
│   ├── expires_at
│   └── features_enabled (JSON)
│
├── usage_logs table
│   ├── id (PK)
│   ├── user_id (FK → users)
│   ├── request_date
│   ├── request_count
│   ├── blocked_count
│   └── last_request_time
│
├── api_keys table (optional)
│   ├── id (PK)
│   ├── user_id (FK → users)
│   ├── key_hash
│   ├── created_at
│   └── expires_at
│
└── team_members table (optional)
    ├── id (PK)
    ├── user_id (FK → users)
    ├── team_user_id (FK → users)
    └── role (admin/member/viewer)
```

---

## 1. Authentication Layer

### Login Flow

```
1. User enters credentials on React UI
   POST /api/auth/login
   {
     "username": "alice",
     "password": "secure_password"
   }

2. Web API validates credentials
   - Query users table: username = "alice"
   - bcrypt.verify(password, user.password_hash)
   - If invalid → return 401 Unauthorized

3. Web API generates JWT
   JWT = {
     "user_id": "user-123",
     "username": "alice",
     "plan_type": "pro",
     "exp": "2026-06-30T12:34:56Z"
   }

4. React stores JWT
   - localStorage.setItem('access_token', jwt)
   - OR cookie with httpOnly flag

5. React uses JWT for future requests
   Authorization: Bearer <jwt>
```

### Request Validation

```
1. React sends request with JWT
   POST /api/chat/completions
   Authorization: Bearer <jwt>

2. Web API validates JWT
   - Decode JWT with JWT_SECRET
   - Check signature validity
   - Check expiration time
   - If invalid → return 401

3. Extract user context
   user_id = decoded_jwt['user_id']
   plan_type = decoded_jwt['plan_type']

4. Check rate limits
   subscription = db.query(Subscription).filter_by(
     user_id=user_id
   ).first()
   
   if request_count >= subscription.rate_limit:
     return 429 Too Many Requests

5. Forward to proxy
   Proxy sees: user_id = "user-123" (in app_id field)
```

---

## 2. Subscription Plans

### Plan Tiers

| Feature | Free | Pro | Enterprise |
|---------|------|-----|------------|
| **Cost** | $0 | $29/month | Custom |
| **Requests/minute** | 100 | 1,000 | 10,000+ |
| **PII Redaction** | ✓ | ✓ | ✓ |
| **Credential Blocking** | ✓ | ✓ | ✓ |
| **Injection Detection** | ✓ | ✓ | ✓ |
| **Vulnerability Scanning** | ✗ | ✓ | ✓ |
| **Sandbox Execution** | ✗ | ✓ | ✓ |
| **Audit Logs** | 7 days | 90 days | 1 year |
| **Team Members** | 1 | 5 | unlimited |
| **API Support** | Community | Priority | Dedicated |
| **SLA** | None | 99.5% | 99.99% |

### Features Per Plan

```python
PLAN_FEATURES = {
    "free": {
        "rate_limit": 100,  # requests per minute
        "audit_retention": 7,  # days
        "features": {
            "pii_redaction": True,
            "credential_blocking": True,
            "injection_detection": True,
            "vulnerability_scanning": False,
            "sandbox_execution": False,
        }
    },
    "pro": {
        "rate_limit": 1000,
        "audit_retention": 90,
        "features": {
            "pii_redaction": True,
            "credential_blocking": True,
            "injection_detection": True,
            "vulnerability_scanning": True,
            "sandbox_execution": True,
        }
    },
    "enterprise": {
        "rate_limit": 10000,
        "audit_retention": 365,
        "features": {
            "pii_redaction": True,
            "credential_blocking": True,
            "injection_detection": True,
            "vulnerability_scanning": True,
            "sandbox_execution": True,
        }
    }
}
```

---

## 3. Rate Limiting Implementation

### Per-Subscription Rate Limiting

```python
@app.post("/api/chat/completions")
async def chat(
    request: ChatRequest,
    db: Session,
    user_id: str = Depends(verify_jwt)
):
    # 1. Get subscription
    subscription = db.query(Subscription).filter_by(
        user_id=user_id
    ).first()
    
    if not subscription:
        return 403 "No active subscription"
    
    # 2. Get today's usage
    today = datetime.date.today()
    usage = db.query(UsageLog).filter(
        UsageLog.user_id == user_id,
        UsageLog.request_date == today
    ).first()
    
    if not usage:
        usage = UsageLog(user_id=user_id, request_date=today, request_count=0)
        db.add(usage)
    
    # 3. Check rate limit
    # Rate limit = requests per minute × 1440 minutes per day
    daily_limit = subscription.rate_limit * 1440
    
    if usage.request_count >= daily_limit:
        return 429 {
            "error": "Rate limit exceeded",
            "limit": daily_limit,
            "used": usage.request_count,
            "reset_at": (today + timedelta(days=1)).isoformat()
        }
    
    # 4. Process request
    try:
        # Validate input
        sanitized_messages, policy, redaction_details = \
            input_policy.check_and_sanitize_openai(request.messages)
        
        if not policy.allowed:
            return 400 policy.error_message
        
        # Call LLM via proxy
        response = await proxy_client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {PROXY_SERVICE_TOKEN}"},
            json={
                "model": request.model,
                "messages": sanitized_messages,
                "app_id": user_id,  # Track by user
            }
        )
        
        # 5. Log usage
        usage.request_count += 1
        usage.last_request_time = datetime.datetime.utcnow()
        
        if not policy.allowed:
            usage.blocked_count += 1
        
        db.commit()
        
        return response.json()
    
    except Exception as e:
        logger.error(f"Chat error for user {user_id}", exc_info=e)
        return 500 "Internal server error"
```

---

## 4. Integration with LLM Proxy

### Minimal Proxy Changes

The proxy currently authenticates via API key. With accounts:

1. **App ID Mapping**: Web API sends `app_id = user_id` instead of API key
2. **Audit Logging**: Proxy logs still work, just with user ID instead of API key
3. **No Auth Changes**: Proxy still uses Bearer tokens (now from Web API service account)

```python
# Proxy continues to receive:
Authorization: Bearer <SERVICE_TOKEN>  # From Web API
X-App-ID: user-123  # Identifying the user

# Audit log entry:
{
    "timestamp": "2026-05-31T12:34:56Z",
    "app_id": "user-123",  # Changed from API key
    "action": "ALLOWED",
    "findings": ["EMAIL_ADDRESS"],
    "redaction_details": {
        "redacted": true,
        "pii_types": ["EMAIL_ADDRESS"],
        "redaction_count": 1
    }
}
```

---

## 5. Implementation Phases

### Phase 1: Database + User Management (1-2 weeks)
- [ ] Set up PostgreSQL/SQLite
- [ ] Create database schema (users, subscriptions, usage_logs)
- [ ] Write database migrations
- [ ] Create SQLAlchemy ORM models
- [ ] Implement user registration endpoint
- [ ] Implement password hashing (bcrypt)
- [ ] Implement password reset flow

### Phase 2: JWT Authentication (1 week)
- [ ] Install JWT library (PyJWT)
- [ ] Create JWT generation logic
- [ ] Create JWT validation middleware
- [ ] Implement refresh token logic
- [ ] Add JWT expiration handling
- [ ] Create login endpoint

### Phase 3: Subscription Management (1 week)
- [ ] Create subscription creation logic
- [ ] Implement plan selection on signup
- [ ] Add subscription upgrade/downgrade endpoints
- [ ] Create usage tracking logic
- [ ] Implement rate limit checking

### Phase 4: Web API Gateway (1-2 weeks)
- [ ] Add JWT validation middleware to all routes
- [ ] Implement rate limiting per subscription
- [ ] Create usage tracking endpoints
- [ ] Create account dashboard endpoints
- [ ] Create subscription management endpoints
- [ ] Add error handling for rate limits

### Phase 5: React Login UI (1 week)
- [ ] Create login page component
- [ ] Create signup page component
- [ ] Create account settings page
- [ ] Create subscription management page
- [ ] Implement JWT storage and persistence
- [ ] Add session timeout handling
- [ ] Add logout functionality

### Phase 6: Integration Testing (1 week)
- [ ] Test login → proxy flow
- [ ] Test rate limiting enforcement
- [ ] Test subscription feature access
- [ ] Test logout and session cleanup
- [ ] Test JWT expiration and refresh
- [ ] Load test rate limiting

---

## 6. Technology Stack

### Backend
- **Framework**: FastAPI (already using)
- **Database**: PostgreSQL (prod) or SQLite (dev)
- **ORM**: SQLAlchemy
- **Authentication**: PyJWT + bcrypt
- **Password Hashing**: bcrypt
- **API Client**: httpx (async)

### Frontend
- **Framework**: React (already using)
- **State Management**: localStorage or React Context
- **HTTP Client**: axios or fetch
- **Session**: JWT in localStorage or httpOnly cookie

### Optional
- **Caching**: Redis (for JWT validation, rate limit counters)
- **Payments**: Stripe, Paddle, or Lemonsqueezy
- **Email**: SendGrid or AWS SES (password resets)
- **Analytics**: Segment or custom logging

---

## 7. Code Examples

### User Registration

```python
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    plan_type: str = "free"

@app.post("/api/auth/register")
async def register(request: UserRegisterRequest, db: Session):
    # Check if user exists
    existing = db.query(User).filter(
        (User.username == request.username) |
        (User.email == request.email)
    ).first()
    
    if existing:
        return 400 "Username or email already exists"
    
    # Create user
    user = User(
        username=request.username,
        email=request.email,
        password_hash=pwd_context.hash(request.password),
        created_at=datetime.datetime.utcnow()
    )
    db.add(user)
    db.flush()  # Get user ID
    
    # Create subscription
    subscription = Subscription(
        user_id=user.id,
        plan_type=request.plan_type,
        rate_limit=PLAN_FEATURES[request.plan_type]["rate_limit"],
        started_at=datetime.datetime.utcnow()
    )
    db.add(subscription)
    db.commit()
    
    return {
        "user_id": user.id,
        "username": user.username,
        "plan_type": request.plan_type,
        "message": "Registration successful"
    }
```

### Login Endpoint

```python
class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/login")
async def login(request: LoginRequest, db: Session):
    # Find user
    user = db.query(User).filter_by(username=request.username).first()
    
    if not user:
        return 401 "Invalid username or password"
    
    # Verify password
    if not pwd_context.verify(request.password, user.password_hash):
        return 401 "Invalid username or password"
    
    # Get subscription
    subscription = db.query(Subscription).filter_by(
        user_id=user.id
    ).first()
    
    # Generate JWT
    token_data = {
        "user_id": str(user.id),
        "username": user.username,
        "plan_type": subscription.plan_type,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
    }
    
    access_token = jwt.encode(
        token_data,
        settings.JWT_SECRET,
        algorithm="HS256"
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "plan_type": subscription.plan_type
        }
    }
```

### JWT Validation Middleware

```python
from fastapi import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthenticationCredentials

security = HTTPBearer()

async def verify_jwt(credentials: HTTPAuthenticationCredentials) -> str:
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"]
        )
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### React Login Component

```javascript
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!response.ok) {
        setError('Invalid username or password');
        return;
      }

      const data = await response.json();
      
      // Store JWT
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      // Redirect to dashboard
      navigate('/dashboard');
    } catch (err) {
      setError('Login failed: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <h1>🛡️ LLM Security Proxy</h1>
      <form onSubmit={handleLogin}>
        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          disabled={loading}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          disabled={loading}
        />
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  );
}

export default Login;
```

---

## 8. Migration Strategy

### Option A: Dual System (Recommended for 6 months)
- Keep API key authentication for programmatic access
- Add account-based auth for web UI users
- Gradually migrate users to accounts
- Remove API keys after 6 months

**Pros**:
- Non-breaking change
- Backward compatible
- Time for migration

**Cons**:
- Maintain two auth systems
- More complex code

### Option B: Pure Account System (After 6 months)
- Replace API keys entirely
- Users generate API keys from their account dashboard
- One consistent auth method

**Pros**:
- Single system
- Simpler code
- Better security (tokens revokable)

**Cons**:
- Breaking change
- Need migration period first

---

## 9. Security Considerations

### Password Security
- Use bcrypt with at least 12 rounds
- Enforce minimum password length (12+ characters)
- Implement password reset via email
- Never store plaintext passwords

### JWT Security
- Use strong JWT_SECRET (32+ bytes, random)
- Set short expiration (30 days max)
- Implement refresh tokens for longer sessions
- Use httpOnly cookies for JWT (not localStorage)
- Validate JWT signature on every request

### Rate Limiting
- Check rate limits BEFORE processing request
- Use daily reset at UTC midnight
- Store usage in database (not memory)
- Add burst allowance (1.5x limit for small periods)

### Database Security
- Use parameterized queries (SQLAlchemy prevents SQL injection)
- Hash all sensitive data (passwords, tokens)
- Implement database backups
- Use environment variables for secrets (never commit DB credentials)

### API Security
- Use HTTPS only (no HTTP)
- Implement CORS properly
- Add request body size limits
- Validate all inputs
- Use security headers (HSTS, CSP, X-Frame-Options)

---

## 10. Decision Points

Before implementing, decide on:

1. **Payment Processing**
   - [ ] Manual billing (email invoices)
   - [ ] Stripe (most mature)
   - [ ] Paddle (better international)
   - [ ] Lemonsqueezy (simpler SaaS alternative)

2. **Free Tier**
   - [ ] Yes, with limits
   - [ ] No, paid only
   - [ ] Limited trial period

3. **Team Management**
   - [ ] Single user only
   - [ ] Team invites
   - [ ] Role-based access (admin/member/viewer)

4. **API Key Generation**
   - [ ] Users can generate API keys from dashboard
   - [ ] No API key access (JWT only)
   - [ ] Temporary API keys (auto-expire)

5. **Audit Logs**
   - [ ] Per-user (users see own logs)
   - [ ] Shared (admin sees all)
   - [ ] Compliance-required retention (GDPR, SOC 2)

6. **Database**
   - [ ] PostgreSQL (production)
   - [ ] SQLite (simple, local)
   - [ ] Managed (AWS RDS, Heroku)

7. **Deployment**
   - [ ] Self-hosted (your servers)
   - [ ] Cloud platform (AWS, GCP, Azure)
   - [ ] PaaS (Heroku, Railway)

---

## Next Steps

1. **Review Architecture**: Ensure this aligns with your goals
2. **Decide on Payment**: Choose payment processor (if any)
3. **Plan Database**: Finalize schema and migration strategy
4. **Create Implementation Plan**: Break into sprints (2 weeks each)
5. **Start Phase 1**: Database + User Management

See `/docs/INDEX.md` for other documentation.
