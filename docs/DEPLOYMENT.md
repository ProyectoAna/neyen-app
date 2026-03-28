# NEYEN MVP — Deployment & Infrastructure Guide

**Version:** 1.0.1
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
HOSTINGER DNS (Domain: api.neyen.app)
        |
        v
SUPABASE EDGE NETWORK
  (SSL/TLS Termination, Global CDN)
  Project: gsmtzdramqzcqdywboro
  Region: EU-Central-1 (Frankfurt)
        |
   +---------+---------+
   |                   |
   v                   v
Supabase Edge      Supabase Edge
 Function 1         Function 2
(breathing-start)  (breathing-complete)
   |                   |
   +--------+----------+
            |
   +--------+--------+--------+
   |        |        |        |
   v        v        v        v
PostgreSQL Supabase  n8n    External
  15.4      Auth    Cloud   Services
(Primary)                  (Claude API,
   |                        Calendly,
   v                        Stripe,
PostgreSQL                  Slack)
 Replica
 (Read)
```

### Hosting Provider & Services

**Primary Infrastructure:**
- **Database:** Supabase PostgreSQL 15.4 (managed)
- **Edge Functions:** Supabase Edge Runtime (Deno-based)
- **Authentication:** Supabase Auth (GitHub OAuth, Google OAuth, Email Magic Link)
- **Storage:** Supabase Storage (S3-compatible object storage)
- **Automation:** n8n Cloud Professional
- **Domain/DNS:** Hostinger (thespiralwithin.ai, api.neyen.app)

**Region:** EU-Central-1 (Frankfurt, Germany) — GDPR-compliant

**Service Tier:**
- Supabase: **Pro Plan** ($25/month)
- n8n Cloud: **Professional** ($50/month)
- Hostinger: **Web Hosting Premium** (~$5/month)

---

### Staging vs Production Environments

| Component | Production | Staging |
|-----------|-----------|---------|
| **Database** | `gsmtzdramqzcqdywboro` (Supabase Pro) | Separate Supabase project (Free tier) |
| **Edge Functions** | 3 deployed (breathing-start, breathing-complete, achievements-check) | Same functions, test data |
| **n8n Workflows** | n8n Cloud (production workspace) | n8n Cloud (staging workspace) |
| **Domain** | `api.neyen.app` | `staging-api.neyen.app` |
| **OAuth Providers** | Production credentials | Localhost redirect URLs |

---

### Database Architecture

**PostgreSQL 15.4 (Supabase Managed)**

**Connection Details:**
- **Primary:** Direct connection via Supabase pooler (port 6543)
- **Replica:** Read replicas enabled for recommendation queries
- **Connection Pooling:** PgBouncer (transaction mode, max 15 connections)
- **SSL:** Required (Supabase enforces TLS 1.2+)

**Tables (Confirmed Production):**
- `users` — User accounts (GitHub/Google OAuth)
- `diagnostics` — NEYEN diagnostic sessions
- `orders` — Calendly bookings
- `metadata` — System configuration (NEYEN framework definitions)
- `webhooks_log` — Webhook delivery tracking (Calendly, Stripe)

**Row-Level Security (RLS):**
- Enabled on all tables
- Users can only access their own diagnostics
- Admin role bypasses RLS for support queries

**Indexes:**
- `diagnostics(user_id, created_at)` — Diagnostic history queries
- `orders(user_id, status)` — Payment tracking
- `webhooks_log(source, processed_at)` — Webhook audit trail

---

### Edge Functions Deployment

**Runtime:** Deno 1.38.5
**Deployment Method:** Supabase CLI + GitHub Actions
**Authentication:** JWT Bearer tokens (issued by Supabase Auth)
**CORS:** Enabled for `https://app.neyen.app`, `http://localhost:3000`

**Deployed Functions:**
1. **breathing-start** (`/functions/v1/breathing-start`) — Creates breathing session, ~300ms latency
2. **breathing-complete** (`/functions/v1/breathing-complete`) — Calculates XP/score, ~500ms latency
3. **achievements-check** (`/functions/v1/achievements-check`) — Verifies achievements, ~200ms latency

**RPC Functions (SQL):**
- `increment_xp(user_id, amount)` — Auto-levels users (level = XP/100 + 1)

---

### Key Differences from AWS Architecture

| AWS (Originally Documented) | Supabase (Actual) |
|----|-----|
| AWS RDS PostgreSQL Multi-AZ | Supabase PostgreSQL 15.4 (managed, auto-failover) |
| Redis ElastiCache | Not used (Supabase handles caching via PgBouncer) |
| EC2 instances (2x Node.js) | Supabase Edge Functions (serverless Deno) |
| Nginx API Gateway | Supabase Edge Network (built-in load balancing) |
| CloudWatch logs | Supabase Dashboard + Sentry |
| S3 for storage | Supabase Storage (S3-compatible) |
| CloudFormation IaC | Supabase CLI + GitHub Actions |

**Why Supabase instead of AWS:**
- Faster MVP deployment (no infrastructure provisioning)
- Built-in auth (GitHub, Google OAuth)
- PostgreSQL + Edge Functions + Storage in one platform
- Automatic SSL, CDN, and scaling
- Lower operational overhead ($25/month vs. $100+ AWS baseline)

---

## Environment Variables & Secrets

**Complete `.env.example` Reference**

```bash
# SUPABASE CONFIGURATION
SUPABASE_URL=https://gsmtzdramqzcqdywboro.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=[REDACTED]
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@[PROJECT_REF].supabase.co:6543/postgres?pgbouncer=true

# AUTHENTICATION
GITHUB_CLIENT_ID=[FROM_GITHUB_DEVELOPER_SETTINGS]
GITHUB_CLIENT_SECRET=[FROM_GITHUB_DEVELOPER_SETTINGS]
GOOGLE_CLIENT_ID=[FROM_GOOGLE_CLOUD_CONSOLE]
GOOGLE_CLIENT_SECRET=[FROM_GOOGLE_CLOUD_CONSOLE]
JWT_SECRET=[GENERATED_VIA_openssl_rand_-base64_32]
JWT_ACCESS_TOKEN_EXPIRY=3600
JWT_REFRESH_TOKEN_EXPIRY=2592000

# EXTERNAL SERVICES
CLAUDE_API_KEY=[FROM_ANTHROPIC_CONSOLE]
CLAUDE_MODEL=claude-sonnet-4-20250514
CALENDLY_WEBHOOK_SECRET=[FROM_CALENDLY_DEVELOPER_PORTAL]
STRIPE_SECRET_KEY=[FROM_STRIPE_DASHBOARD]
STRIPE_WEBHOOK_SECRET=[FROM_STRIPE_WEBHOOK_SETTINGS]
SLACK_BOT_TOKEN=xoxb-[FROM_SLACK_APP_OAUTH]
SLACK_SIGNING_SECRET=[FROM_SLACK_APP_BASIC_INFO]
TELEGRAM_BOT_TOKEN=[FROM_@BOTFATHER]
N8N_WEBHOOK_URL=https://ana-tsw.app.n8n.cloud/webhook/slack-auto-ingest

# APPLICATION CONFIGURATION
NODE_ENV=production
API_BASE_URL=https://api.neyen.app/v1
FRONTEND_URL=https://app.neyen.app

# MONITORING
SENTRY_DSN=[FROM_SENTRY_PROJECT_SETTINGS]
SENTRY_ENVIRONMENT=production
```

**Secrets Storage:**
- **Supabase Secrets:** Dashboard > Project Settings > Edge Function Secrets
- **GitHub Secrets:** Repo > Settings > Secrets and variables > Actions
- **Local Development:** `.env.local` (never committed)

**Rotation Policy:**
- JWT secrets: Every 90 days
- OAuth secrets: Annually or on breach
- Claude API key: On-demand
- Database password: Every 6 months

---

## 3. Deployment Process

### Supabase CLI Deployment

**Prerequisites:**
- Supabase CLI installed (`npm install -g supabase`)
- Project linked: `supabase link --project-ref gsmtzdramqzcqdywboro`
- Git repository: `ProyectoAna/neyen-app`

**Deployment Workflow:**

```bash
# 1. Pull latest changes
git pull origin main
# 2. Run database migrations (if any)
supabase db push
# 3. Deploy Edge Functions
supabase functions deploy breathing-start
supabase functions deploy breathing-complete
supabase functions deploy achievements-check
# 4. Verify deployment
supabase functions list
```

### CI/CD Pipeline (GitHub Actions)

**Workflow File:** `.github/workflows/deploy.yml`
**Trigger:** Push to `main` branch

**Steps:**
1. Checkout code
2. Install dependencies (`npm ci`)
3. Run tests (`npm test`)
4. Deploy to Supabase (Edge Functions via CLI + migrations)
5. Health check (ping `/health` endpoint)
6. Notify Slack (`#neyen-core` on success/failure)

**Zero-Downtime Strategy:**
- Supabase Edge Functions are serverless (no instances to rotate)
- New deployments are atomic (old version remains until new succeeds)
- Database migrations use `supabase db push --dry-run` before applying

### Rollback Procedures

**Edge Functions:** `supabase functions deploy breathing-start --version 2`
**Database:** Manual rollback via SQL (always test migrations in staging first)

---

## 4. Monitoring & Observability

### Supabase Dashboard Metrics
**Access:** https://supabase.com/dashboard/project/gsmtzdramqzcqdywboro

**Key Metrics:** Database connections (<15 PgBouncer limit), query performance, Edge Function invocations/errors/latency, storage bucket sizes.

### Sentry Error Tracking
**Project:** https://sentry.io/neyen-mvp
- P0 (Critical): >10 errors/min -> Slack #neyen-core
- P1 (High): >5 errors/min -> Email Ana
- P2 (Medium): >2 errors/min -> Log only

### UptimeRobot
- `https://api.neyen.app/health` (5-min interval)
- Email + SMS after 2 consecutive failures

### Performance Targets

| Metric | Target |
|--------|--------|
| Diagnostic API latency (p95) | <5s |
| Database query time (p95) | <200ms |
| Edge Function cold start | <500ms |
| Uptime | 99.5% |

---

## 5. Backup & Disaster Recovery

### Database Backups
- **Automated:** Hourly (last 24h), Daily (last 30 days) on Pro plan
- **PITR:** Restore to any point within last 7 days
- **Manual:** `pg_dump` before major changes

### RTO/RPO

| Scenario | RTO | RPO |
|----------|-----|-----|
| Edge Function failure | <1 min | 0 |
| Database corruption | <30 min | <5 min |
| Complete Supabase outage | <2 hours | <1 hour |

### Disaster Recovery
1. Verify outage (Supabase status page)
2. Activate backup project (EU-West-2)
3. Update DNS
4. Restore database + deploy Edge Functions
5. Notify users

---

## 6. Security Hardening

### Network Security
- SSL/TLS 1.3 enforced
- DDoS protection (Cloudflare-powered)
- Rate limiting: 1000 req/min per IP
- CORS: `https://app.neyen.app`, `http://localhost:3000`

### Application Security
- Row-Level Security (RLS) enabled on all tables
- JWT: HS256, 1h access / 30d refresh tokens
- Secret rotation: 90 days (JWT), annually (OAuth), on-demand (API keys)

### GDPR Compliance
- Data Residency: EU-Central-1 (Frankfurt)
- Right to Access: `GET /api/user/data-export`
- Right to Deletion: `DELETE /api/user/account`
- Retention: 12 months active, 7 years archived

---

## 7. Operational Runbooks

### Runbook 1: Claude API Down
**Symptoms:** 502 on `/api/diagnostic/analyze`, Sentry timeout alerts
**Resolution:** Check status.anthropic.com; queue diagnostics if down; rotate key if expired; exponential backoff if rate limited.

### Runbook 2: Database Connection Failure
**Symptoms:** Edge Functions return connection errors
**Resolution:** Check Supabase status; verify PgBouncer limit (15); redeploy if connection leak.

### Runbook 3: Webhook Delivery Failing
**Symptoms:** Calendly bookings/Stripe payments not logging
**Resolution:** Check function logs; verify webhook secrets; implement retry queue via n8n.

### Runbook 4: Sudden Traffic Spike
**Symptoms:** 10x traffic, latency >10s
**Resolution:** Supabase auto-scales; Cloudflare DDoS protection; block abuse IPs if needed.

### Runbook 5: User Reports Diagnostic Stuck
**Symptoms:** Analyzing >30s, no results
**Resolution:** Query database for diagnostic ID; check Sentry; retry or manually reprocess.

---

## 8. Cost Optimization

### Current Monthly Costs

| Service | Plan | Cost (USD) |
|---------|------|------------|
| Supabase | Pro | $25 |
| n8n Cloud | Professional | $50 |
| Hostinger | Web Hosting Premium | $5 |
| Sentry | Team | $26 |
| Claude API | Pay-as-you-go | ~$15-30 |
| **Total** | | **$121-136** |

### Claude API Cost Monitoring
- ~150 diagnostics/month, 2,500 tokens avg
- $0.10/diagnostic = $15/month
- Scaling: 1K=$100, 5K=$500, 10K=$1,000/month

### Cost-Saving Measures (Implemented)
- Supabase PgBouncer (saves ~$15/mo vs Redis)
- Supabase Storage (saves ~$5/mo vs S3)
- Serverless Edge Functions (saves ~$60/mo vs EC2)

### Scaling Triggers
- Database >400GB -> Upgrade Supabase Team ($599/mo)
- Edge Functions >500K/mo -> Pay overages ($10/100K)
- Diagnostic latency >7s -> Review Claude prompt length
