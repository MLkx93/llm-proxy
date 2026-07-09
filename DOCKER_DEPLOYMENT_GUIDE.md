# Docker Deployment Guide — LLM Security Proxy

Complete step-by-step guide to deploy the LLM Proxy using Docker.

---

## 📋 Prerequisites Check

Before starting, verify you have Docker installed:

```bash
# Check Docker installation
docker --version
# Should show: Docker version 24.x.x or higher

# Check Docker Compose
docker compose version
# Should show: Docker Compose version v2.x.x or higher
```

**If Docker is not installed:**

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (logout and login after this)
sudo usermod -aG docker $USER
```

---

## 🚀 Step-by-Step Deployment

### Step 1: Navigate to Project Directory

```bash
cd /home/malakx/LLM-proxy\ \(Copy\)
```

### Step 2: Create Environment Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file
nano .env
```

**Fill in these required fields:**

```bash
# Choose ONE of these options:

# Option A: OpenRouter (Recommended - easiest setup)
OPENROUTER_API_KEY=sk-or-v1-YOUR_OPENROUTER_KEY_HERE
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Option B: LiteLLM Proxy (If you have a LiteLLM server)
# LITELLM_API_BASE=http://your-litellm-server:4000/api
# LITELLM_API_KEY=your-litellm-key

# Option C: Direct Provider Keys
# OPENAI_API_KEY=sk-proj-YOUR_OPENAI_KEY
# ANTHROPIC_API_KEY=sk-ant-YOUR_ANTHROPIC_KEY

# Optional: Nexus Firewall (leave blank if not using)
# NEXUS_BASE_URL=
# NEXUS_API_KEY=

# Audit log path (keep default)
AUDIT_LOG_PATH=logs/audit.jsonl
```

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step 3: Create Required Directories

```bash
# Create logs directory for audit logs
mkdir -p logs

# Create config directory if it doesn't exist
mkdir -p config
```

### Step 4: Verify Docker Compose Configuration

Let's check the docker-compose file:

```bash
cat docker/docker-compose.yml
```

You should see:
- PostgreSQL service on port 5433
- Proxy service on port 8080
- WebUI API service on port 8000
- Frontend (React via nginx) service on port 3000
- Volume mounts for logs and database

### Step 5: Build and Start Services

```bash
# Navigate to docker directory
cd docker

# Build and start all services
docker compose up --build -d
```

**What this does:**
- `--build`: Rebuilds images if needed
- `-d`: Runs containers in detached mode (background)

**Expected output:**
```
[+] Running 5/5
 ✔ Network llm-proxy_default      Created
 ✔ Volume "llm-proxy_shield_pgdata" Created
 ✔ Container llm-proxy-postgres-1  Started
 ✔ Container llm-proxy-proxy-1     Started
 ✔ Container llm-proxy-webui-1     Started
 ✔ Container llm-proxy-frontend-1  Started
```

### Step 6: Verify Services are Running

```bash
# Check container status
docker compose ps
```

**Expected output:**
```
NAME                    STATUS              PORTS
llm-proxy-postgres-1    Up 2 minutes        0.0.0.0:5433->5432/tcp
llm-proxy-proxy-1       Up 2 minutes        0.0.0.0:8080->8080/tcp
llm-proxy-webui-1       Up 2 minutes        0.0.0.0:8000->8000/tcp
llm-proxy-frontend-1    Up 2 minutes        0.0.0.0:3000->3000/tcp
```

All four should show "Up" (or "healthy") status.

### Step 7: Check Logs

```bash
# View proxy logs
docker compose logs proxy

# View webui API logs
docker compose logs webui

# View frontend (nginx) logs
docker compose logs frontend

# View PostgreSQL logs
docker compose logs postgres

# Follow logs in real-time
docker compose logs -f proxy
```

**Press Ctrl+C to stop following logs**

### Step 8: Test the Deployment

#### Test 1: Health Check

```bash
curl http://localhost:8080/health
```

**Expected response:**
```json
{"status":"ok"}
```

#### Test 2: Proxy API Test

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer dev-local-key-1234" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say hello"}]
  }'
```

#### Test 3: Admin Console (served by the proxy)

Open your browser and navigate to:
```
http://localhost:8080/admin
```

**Login credentials:**
- Username: `admin`
- Password: `admin`

#### Test 4: React WebUI (served by nginx, backed by webui API)

Open your browser and navigate to:
```
http://localhost:3000
```

This is the React frontend, served by the `frontend` (nginx) container. It proxies
`/api/*` and `/v1/*` requests to the `webui` container, which in turn talks to
`postgres` (chat history / dashboard persistence) and to the `proxy` container
(`http://proxy:8080`) for actual LLM calls with security scanning applied.

```bash
# Sanity check the full chain: frontend -> webui -> postgres
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```

You should get back a JSON object containing a JWT `token`.

---

## 🔧 Common Issues & Solutions

### Issue 1: Port Already in Use

**Error:** `bind: address already in use`

**Solution:**
```bash
# Check what's using port 8080
sudo lsof -i :8080

# Kill the process or change the port in docker-compose.yml
```

### Issue 2: Permission Denied on .env

**Error:** `Permission denied`

**Solution:**
```bash
# Fix permissions
chmod 644 .env
```

### Issue 3: Container Won't Start

**Check logs:**
```bash
docker compose logs proxy
```

**Common fixes:**
```bash
# Rebuild containers
docker compose down
docker compose up --build -d

# Remove volumes and start fresh (WARNING: deletes data)
docker compose down -v
docker compose up --build -d
```

### Issue 4: Database Connection Issues

**Solution:**
```bash
# Restart PostgreSQL
docker compose restart postgres

# Check PostgreSQL logs
docker compose logs postgres
```

### Issue 5: API Key Errors

**Solution:**
```bash
# Stop containers
docker compose down

# Edit .env file
nano ../.env

# Restart containers
docker compose up -d
```

---

## 📊 Monitoring Your Deployment

### View Container Stats

```bash
# Real-time resource usage
docker stats

# Or for specific containers
docker stats llm-proxy-proxy-1 llm-proxy-postgres-1
```

### Check Disk Usage

```bash
# Docker disk usage
docker system df

# Clean up unused resources
docker system prune -a
```

### View Audit Logs

```bash
# View audit log file
cat ../logs/audit.jsonl | python3 -m json.tool

# Follow audit logs in real-time
tail -f ../logs/audit.jsonl | python3 -m json.tool
```

---

## 🛑 Stopping and Restarting

### Stop Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (deletes database data)
docker compose down -v
```

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart proxy
```

### Update and Rebuild

```bash
# Pull latest changes (if using git)
git pull

# Rebuild and restart
docker compose down
docker compose up --build -d
```

---

## 🔒 Security Hardening for Production

### 1. Change Default API Keys

```bash
# Generate secure keys
openssl rand -hex 32

# Edit config/api_keys.yaml
nano ../config/api_keys.yaml
```

Replace `dev-local-key-1234` with your generated keys.

### 2. Enable HTTPS (Recommended)

Create an `nginx.conf` file:

```bash
cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream proxy {
        server localhost:8080;
    }

    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate /path/to/cert.pem;
        ssl_certificate_key /path/to/key.pem;

        location / {
            proxy_pass http://proxy;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }

    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$server_name$request_uri;
    }
}
EOF
```

Run nginx as a reverse proxy:
```bash
docker run -d \
  --name nginx-proxy \
  -p 80:80 -p 443:443 \
  -v $(pwd)/nginx.conf:/etc/nginx/nginx.conf:ro \
  -v /path/to/certs:/etc/nginx/certs:ro \
  --link llm-proxy-proxy-1:proxy \
  nginx:alpine
```

### 3. Configure Firewall

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 4. Set Up Log Rotation

Create `/etc/logrotate.d/llm-proxy`:

```
/home/malakx/LLM-proxy\ \(Copy\)/logs/*.jsonl {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 malakx malakx
}
```

---

## 🚀 Production Deployment Checklist

- [ ] Change all default passwords and API keys
- [ ] Configure HTTPS/TLS
- [ ] Set up firewall rules
- [ ] Configure log rotation
- [ ] Set up database backups
- [ ] Configure monitoring and alerting
- [ ] Review and adjust security feature thresholds
- [ ] Test disaster recovery procedures
- [ ] Document deployment procedures
- [ ] Set up CI/CD pipeline

---

## 📈 Scaling for Production

### Horizontal Scaling

Edit `docker/docker-compose.yml`:

```yaml
services:
  proxy:
    # ... existing config ...
    deploy:
      replicas: 3  # Run 3 instances
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### Load Balancing

Use nginx or HAProxy as a load balancer:

```bash
docker run -d \
  --name load-balancer \
  -p 80:80 \
  --link llm-proxy-proxy-1:proxy1 \
  --link llm-proxy-proxy-2:proxy2 \
  --link llm-proxy-proxy-3:proxy3 \
  nginx:alpine
```

---

## 🐛 Debugging Tips

### Access Container Shell

```bash
# Access proxy container
docker exec -it llm-proxy-proxy-1 /bin/bash

# Access webui API container
docker exec -it llm-proxy-webui-1 /bin/bash

# Access frontend (nginx) container
docker exec -it llm-proxy-frontend-1 /bin/sh

# Access PostgreSQL container
docker exec -it llm-proxy-postgres-1 psql -U shield -d shield
```

### View Container Environment

```bash
docker exec llm-proxy-proxy-1 env
```

### Inspect Container Details

```bash
docker inspect llm-proxy-proxy-1
```

### Copy Files from Container

```bash
# Copy logs from container
docker cp llm-proxy-proxy-1:/app/logs/audit.jsonl ./backup_audit.jsonl
```

---

## 📚 Next Steps

1. **Test thoroughly:** Use the test scripts in `tests/` directory
2. **Configure monitoring:** Set up Prometheus/Grafana or CloudWatch
3. **Set up alerts:** Configure alerts for errors and high latency
4. **Document procedures:** Create runbooks for common operations
5. **Plan backups:** Implement automated database backups
6. **Review security:** Conduct security audit of configuration

---

## 🆘 Getting Help

If you encounter issues:

1. Check logs: `docker compose logs -f proxy`
2. Verify configuration: `docker compose config`
3. Check container status: `docker compose ps`
4. Review this guide's troubleshooting section
5. Check project documentation in `docs/` directory

---

## ✅ Success Criteria

Your deployment is successful when:

- [ ] Both containers show "Up" status in `docker compose ps`
- [ ] Health check returns `{"status":"ok"}`
- [ ] Admin console loads at http://localhost:8080/admin
- [ ] API test requests complete successfully
- [ ] Audit logs are being written to `logs/audit.jsonl`
- [ ] No errors in container logs

Congratulations! Your LLM Security Proxy is now running in Docker! 🎉