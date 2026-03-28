# NEYĒN MVP — Deployment & Infrastructure Guide

**Version:** 1.0.0
**Last Updated:** 2026-03-28
**Environment:** Production & Staging
**Maintained by:** The Spiral Within SLU — Infrastructure Team

---

## Table of Contents

1. [Infrastructure Architecture](#infrastructure-architecture)
2. [Environment Variables & Secrets](#environment-variables--secrets)
3. [Deployment Process](#deployment-process)
4. [Monitoring & Observability](#monitoring--observability)
5. [Backup & Disaster Recovery](#backup--disaster-recovery)
6. [Security Hardening](#security-hardening)
7. [Operational Runbooks](#operational-runbooks)
8. [Cost Optimization](#cost-optimization)

---

## Infrastructure Architecture

### Production Environment Topology

```
┌───────────────────────────────────────────────────────────────┐
│                         CLOUDFLARE CDN                        │
│                  (SSL/TLS Termination, DDoS Protection)       │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────────┐
│                    NGINX (API Gateway)                        │
│            Rate Limiting, CORS, Load Balancing                │
│            Location: EU-West (Frankfurt)                      │
└────────────────────────────┬──────────────────────────────────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
        ┌─────────────────┐   ┌─────────────────┐
        │   Node.js API   │   │   Node.js API   │
        │   Instance 1    │   │   Instance 2    │
        │  (2 vCPU/4GB)   │   │  (2 vCPU/4GB)   │
        └────────┬────────┘   └────────┬────────┘
                 │                     │
                 └──────────┬──────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │PostgreSQL│  │  Redis   │  │   n8n    │
      │  (RDS)   │  │  Cache   │  │  Cloud   │
      │ Primary  │  │          │  │          │
      └──────────┘  └──────────┘  └──────────┘
           │
           ▼
      ┌──────────┐
      │PostgreSQL│
      │  (RDS)   │
      │ Read Rep.│
      └──────────┘

External Services:
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│  Claude    │  │  Calendly  │  │   Stripe   │  │   Slack    │
│  API       │  │  Webhooks  │  │  Webhooks  │  │  Webhooks  │
└────────────┘  └────────────┘  └────────────┘  └────────────┘
```

---

### Hosting Provider & Services

**Primary:** Render.com (Node.js API, n8n Docker)
**Database:** Supabase (PostgreSQL + Auth + Realtime)
**CDN/DNS:** Cloudflare (SSL, DDoS protection, caching)
**Domain:** thespiralwithin.ai / neyen.app
**Automation:** n8n Cloud (hosted on Render via Docker)
**Static Assets:** GitHub Pages (docs, about.html)

| Service | Provider | Tier | Region |
|---------|----------|------|--------|
| API Server | Render.com | Starter | EU (Frankfurt) |
| n8n Workflows | Render.com (Docker) | Starter | EU (Frankfurt) |
| Database | Supabase | Free/Pro | EU (Frankfurt) |
| Redis Cache | Render.com | Starter | EU (Frankfurt) |
| CDN/DNS | Cloudflare | Free | Global |
| Static Docs | GitHub Pages | Free | Global |
| CI/CD | GitHub Actions | Free | Global |

---

## Environment Variables & Secrets

### `.env.example` Reference

```bash
# ===== SERVER =====
NODE_ENV=production
PORT=3000
API_VERSION=v1
BASE_URL=https://api.neyen.app

# ===== DATABASE =====
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
DATABASE_URL=postgresql://user:pass@host:5432/neyen_production

# ===== AUTHENTICATION =====
JWT_SECRET=your-256-bit-secret
JWT_EXPIRATION=3600
REFRESH_TOKEN_EXPIRATION=2592000

# ===== OAUTH PROVIDERS =====
SLACK_CLIENT_ID=your-slack-client-id
SLACK_CLIENT_SECRET=your-slack-client-secret
SLACK_REDIRECT_URI=https://api.neyen.app/v1/auth/oauth/callback

GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=https://api.neyen.app/v1/auth/oauth/callback

# ===== CLAUDE API =====
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_MAX_TOKENS=4096
NEYEN_DIAGNOSTIC_PROMPT_VERSION=v1.2

# ===== EXTERNAL SERVICES =====
CALENDLY_WEBHOOK_SECRET=your-calendly-webhook-secret
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# ===== n8n =====
N8N_BASE_URL=https://n8n-docker-t9sr.onrender.com
N8N_WEBHOOK_URL=https://n8n-docker-t9sr.onrender.com/webhook
N8N_API_KEY=your-n8n-api-key

# ===== SLACK NOTIFICATIONS =====
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_NEYEN_CORE=C0...

# ===== REDIS =====
REDIS_URL=redis://user:pass@host:6379

# ===== MONITORING =====
SENTRY_DSN=https://your-sentry-dsn
LOG_LEVEL=info
```

### Secrets Management

**Storage:** Render Environment Groups (encrypted at rest)
**Rotation Policy:**
- JWT secrets: rotate every 90 days
- API keys: rotate every 180 days
- OAuth secrets: rotate on provider request
- Webhook secrets: rotate every 90 days

**Access Control:**
- Production secrets: admin-only access
- Staging secrets: team lead + admin
- Development: local `.env` files (never committed)

**Critical Rule:** Never commit `.env` files. The `.gitignore` must include:
```
.env
.env.local
.env.production
.env.staging
```

---

## Deployment Process

### CI/CD Pipeline (GitHub Actions)

**Trigger:** Push to `main` branch
**Pipeline File:** `.github/workflows/deploy.yml`

```yaml
name: Deploy NEYĒN API

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm run test
      - run: npm run lint

  deploy-staging:
    needs: test
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render (Staging)
        run: curl -X POST $RENDER_STAGING_DEPLOY_HOOK

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Deploy to Render (Production)
        run: curl -X POST $RENDER_PRODUCTION_DEPLOY_HOOK
```

### Deployment Steps

1. **Code Push** → Developer pushes to `main`
2. **Tests Run** → Jest + Supertest (>80% coverage required)
3. **Lint Check** → ESLint + Prettier validation
4. **Staging Deploy** → Auto-deploy to staging environment
5. **Smoke Tests** → Automated health check on staging
6. **Production Deploy** → Manual approval, then deploy
7. **Health Check** → Verify `/health` endpoint returns 200
8. **Notification** → Slack notification to `#neyen-core`

### Zero-Downtime Deployment

**Strategy:** Rolling deployment (Render native)
- New instance spins up alongside old instance
- Health check passes on new instance
- Traffic shifts to new instance
- Old instance drains connections and shuts down

### Rollback Procedure

1. **Immediate:** Render dashboard → Deploys → Select previous deploy → "Rollback"
2. **Git-based:** `git revert HEAD && git push origin main`
3. **Emergency:** Render dashboard → Manual Deploy → Select known-good commit hash

**Rollback SLA:** <5 minutes for production rollback

---

## Monitoring & Observability

### Health Check Endpoint

**Endpoint:** `GET /health`
**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-28T12:00:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "claude_api": "available",
    "n8n": "connected"
  },
  "uptime_seconds": 86400
}
```

### Logging

**Framework:** Winston (structured JSON logs)
**Log Levels:** `error` > `warn` > `info` > `debug`
**Production Level:** `info`
**Staging Level:** `debug`

**Log Format:**
```json
{
  "timestamp": "2026-03-28T12:45:00Z",
  "level": "info",
  "service": "neyen-api",
  "request_id": "req_abc123",
  "method": "POST",
  "path": "/api/diagnostic/analyze",
  "status": 200,
  "duration_ms": 3200,
  "user_id": "usr_abc123"
}
```

### Error Tracking

**Provider:** Sentry
**Configuration:**
- Capture all unhandled exceptions
- Capture 10% of transactions (performance monitoring)
- Alert on error rate >1% in 5-minute window
- PII scrubbing enabled (GDPR compliance)

### Uptime Monitoring

**Provider:** UptimeRobot (free tier)
**Monitored Endpoints:**
- `GET /health` — every 5 minutes
- `GET /auth/token` — every 10 minutes
- n8n webhook: `GET /webhook/system` — every 10 minutes

**Alert Channels:**
- Slack `#neyen-core` (immediate)
- Email: ana@thespiralwithin.ai (immediate)

### Key Metrics Dashboard

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API Response Time (p95) | <500ms | >2000ms |
| Claude API Latency (p95) | <5s | >10s |
| Error Rate | <0.1% | >1% |
| Uptime | 99.9% | <99.5% |
| Database Connections | <80% pool | >90% pool |
| Memory Usage | <70% | >85% |
| Diagnostics/hour | Baseline | >200% spike |

---

## Backup & Disaster Recovery

### Database Backups

**Supabase Automatic Backups:**
- **Frequency:** Daily (Pro plan)
- **Retention:** 7 days (Pro), 30 days (Enterprise)
- **Type:** Full database snapshot
- **Location:** Same region (EU-West)

**Manual Backup (monthly):**
```bash
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql
gzip backup_$(date +%Y%m%d).sql
# Upload to secure storage
```

### n8n Workflow Backups

**Frequency:** Weekly (every Monday)
**Method:** n8n API export
```bash
curl -H "X-N8N-API-KEY: $N8N_API_KEY" \
  https://n8n-docker-t9sr.onrender.com/api/v1/workflows \
  > n8n_workflows_backup_$(date +%Y%m%d).json
```

### Disaster Recovery Plan

| Scenario | RTO | RPO | Action |
|----------|-----|-----|--------|
| API server down | 5 min | 0 | Render auto-restart |
| Database corruption | 1 hour | 24 hours | Restore from Supabase backup |
| Complete region failure | 4 hours | 24 hours | Redeploy to new region |
| Secret compromise | 30 min | 0 | Rotate all keys, redeploy |
| DDoS attack | 0 | 0 | Cloudflare auto-mitigation |

**RTO** = Recovery Time Objective
**RPO** = Recovery Point Objective

---

## Security Hardening

### Network Security

- **SSL/TLS:** Enforced via Cloudflare (TLS 1.3)
- **HSTS:** Enabled with 1-year max-age
- **CORS:** Restricted to `*.neyen.app` and `*.thespiralwithin.ai`
- **Rate Limiting:** Nginx + application-level (see API-ENDPOINTS.md)
- **DDoS Protection:** Cloudflare (free tier)

### Application Security

- **Input Validation:** Joi/Zod schema validation on all endpoints
- **SQL Injection:** Prevented via Supabase client (parameterized queries)
- **XSS Prevention:** Content-Security-Policy headers
- **CSRF Protection:** OAuth state parameter validation
- **Helmet.js:** Security headers middleware enabled

### Authentication Security

- **JWT Algorithm:** HS256 with 256-bit secret
- **Token Expiration:** Access (1 hour), Refresh (30 days)
- **Password Storage:** N/A (OAuth-only, no passwords stored)
- **Session Management:** Stateless JWT (no server-side sessions)

### Webhook Security

- **Calendly:** HMAC-SHA256 signature verification
- **Stripe:** HMAC-SHA256 signature verification
- **Replay Protection:** Timestamp validation (5-minute window)

### GDPR Compliance

- **Data Encryption:** AES-256 at rest (Supabase default)
- **Data Export:** `GET /api/user/data-export`
- **Data Deletion:** `DELETE /api/user/delete`
- **Cookie Policy:** Minimal cookies, no tracking
- **Privacy Policy:** Published at `/privacy`

---

## Operational Runbooks

### Runbook 1: API Not Responding

1. Check Render dashboard for deploy status
2. Check `/health` endpoint manually
3. Review Sentry for recent errors
4. Check Supabase dashboard for database status
5. If unresponsive: trigger manual redeploy from last known-good commit
6. Notify team in `#neyen-core`

### Runbook 2: Claude API Errors (502)

1. Check Anthropic status page: https://status.anthropic.com
2. Review error logs for specific error codes
3. If rate limited: reduce diagnostic request frequency
4. If outage: enable fallback response mode (cached responses)
5. Monitor resolution and re-enable live diagnostics

### Runbook 3: Database Connection Issues

1. Check Supabase dashboard for status
2. Verify connection pool usage (<90%)
3. Check for long-running queries
4. If pool exhausted: restart API instances
5. If Supabase down: wait for provider resolution

### Runbook 4: Webhook Failures (Calendly/Stripe)

1. Check webhook delivery logs in Calendly/Stripe dashboards
2. Verify webhook secret hasn't been rotated
3. Check API logs for signature verification failures
4. Re-send failed webhooks from provider dashboard
5. If persistent: rotate webhook secret and update env vars

### Runbook 5: n8n Workflow Failures

1. Access n8n dashboard: https://n8n-docker-t9sr.onrender.com
2. Check execution history for failed workflows
3. Verify Supabase credentials are valid
4. Check Render logs for n8n container health
5. If container crashed: restart via Render dashboard

---

## Cost Optimization

### Current Monthly Costs (Estimated)

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Render.com (API) | Starter | $7/month |
| Render.com (n8n Docker) | Starter | $7/month |
| Supabase | Free/Pro | $0–$25/month |
| Cloudflare | Free | $0/month |
| GitHub | Free | $0/month |
| Sentry | Free | $0/month |
| UptimeRobot | Free | $0/month |
| **Claude API** | **Pay-per-use** | **$10–$50/month** |
| **Total** | | **$24–$89/month** |

### Cost Reduction Strategies

1. **Cache diagnostic results:** Redis cache for repeated queries (reduce Claude API calls by ~30%)
2. **Batch n8n executions:** Group Slack messages for batch processing
3. **Supabase Free Tier:** Stay within limits (500MB database, 50K auth users)
4. **Render auto-scaling:** Only scale during peak hours (EU business hours)
5. **Claude prompt optimization:** Minimize token usage with concise system prompts

### Scaling Triggers

| Metric | Current | Scale Action |
|--------|---------|-------------|
| Monthly active users | <100 | Stay on free/starter tiers |
| Monthly active users | 100–1,000 | Upgrade Supabase to Pro |
| Monthly active users | 1,000–10,000 | Add second API instance, Redis cache |
| Monthly active users | >10,000 | Evaluate dedicated infrastructure |

---

## Changelog

### v1.0.0 (2026-03-28)
- Initial deployment guide
- Infrastructure architecture diagram
- Environment variables reference
- CI/CD pipeline configuration
- Monitoring and alerting setup
- Backup and disaster recovery plan
- Security hardening checklist
- Operational runbooks
- Cost optimization analysis

---

## Contact

**Ana Ballesteros Benavent** — CSO, The Spiral Within SLU
Slack: `#neyen-core` | Email: ana@thespiralwithin.ai
