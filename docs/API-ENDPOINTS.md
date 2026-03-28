# NEYĒN MVP — API Endpoint Specification

**Version:** 1.0.0
**Last Updated:** 2026-03-28
**Base URL (Production):** `https://api.neyen.app/v1`
**Base URL (Staging):** `https://staging-api.neyen.app/v1`
**Authentication:** OAuth 2.0 (Slack, GitHub, Email) + JWT Bearer tokens

All responses are JSON. Timestamps are in ISO 8601 format.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Diagnostic Endpoints](#diagnostic-endpoints)
3. [User Management](#user-management)
4. [Booking & Payment Integration](#booking--payment-integration)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Rate Limits & Quotas](#rate-limits--quotas)
8. [Claude API Integration Points](#claude-api-integration-points)
9. [Testing Strategy](#testing-strategy)
10. [Security Notes](#security-notes)

---

## Authentication

### OAuth Flow Initialization

**Endpoint:** `POST /auth/oauth/start`
**Method:** `POST`
**Description:** Initiates OAuth flow with specified provider (Slack, GitHub, or email magic link).

**Request Body:**
```json
{
  "provider": "slack",
  "redirect_uri": "https://app.neyen.app/callback"
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `provider` | string | Yes | One of: `slack`, `github`, `email` |
| `redirect_uri` | string | No | Client redirect URI (optional override) |

**Response (200 OK):**
```json
{
  "auth_url": "https://slack.com/oauth/v2/authorize?client_id=...&state=xyz789"
}
```

**Error Codes:**
- `400` — Invalid provider or missing parameters
- `500` — OAuth configuration error

---

### OAuth Callback Handler

**Endpoint:** `GET /auth/oauth/callback`
**Method:** `GET`
**Description:** Handles OAuth provider callback, exchanges authorization code for NEYĒN access token.

**Query Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `code` | string | Yes | OAuth authorization code |
| `state` | string | Yes | CSRF protection token |

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "rt_abc123...",
  "expires_in": 3600,
  "user_id": "usr_abc123",
  "email": "user@example.com"
}
```

**Error Codes:**
- `400` — Invalid authorization code
- `401` — State mismatch (CSRF protection triggered)
- `500` — Token exchange failed

---

### Token Refresh

**Endpoint:** `POST /auth/refresh`
**Method:** `POST`
**Description:** Refreshes expired access token using refresh token.

**Request Body:**
```json
{
  "refresh_token": "rt_abc123..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Error Codes:**
- `401` — Invalid or expired refresh token
- `500` — Token generation failed

---

### Token Validation

**Endpoint:** `GET /auth/token`
**Method:** `GET`
**Authentication:** Required (Bearer token)
**Description:** Validates current access token and returns user session info.

**Headers:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK):**
```json
{
  "valid": true,
  "user": {
    "id": "usr_abc123",
    "email": "ana@thespiralwithin.ai",
    "name": "Ana Ballesteros",
    "provider": "slack"
  },
  "expires_at": "2026-03-28T14:30:00Z"
}
```

**Error Codes:**
- `401` — Invalid or expired token
- `403` — Token revoked

---

## Diagnostic Endpoints

### Analyze Temporal Cycles (Axioma E'A)

**Endpoint:** `POST /api/diagnostic/analyze`
**Method:** `POST`
**Authentication:** Required (Bearer token)
**Description:** Analyzes organizational temporal patterns using the Axioma E'A framework (Ciclo-Nodo-Vórtice). Calls Claude API with NEYĒN diagnostic prompt.

**Request Body:**
```json
{
  "user_input": "Me siento perdido en mi propósito de vida.",
  "avatar_mascot": "HEY",
  "context": {
    "organization_name": "DINIBA SL",
    "industry": "industrial_installations",
    "team_size": 15,
    "founding_year": 1974,
    "current_challenge": "Succession planning and digital transformation"
  },
  "temporal_data": {
    "project_cycles": [
      {
        "name": "Installation Project Alpha",
        "start_date": "2025-01-15",
        "end_date": "2025-03-20",
        "team_members": 8,
        "outcome": "completed_on_time"
      }
    ],
    "decision_patterns": [
      {
        "decision_type": "resource_allocation",
        "frequency": "weekly",
        "participants": ["owner", "general_manager", "project_leads"]
      }
    ]
  }
}
```

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_input` | string | Yes | User's diagnostic question or concern |
| `avatar_mascot` | string | No | Mascot personality (default: `HEY`) |
| `context` | object | No | Organizational context metadata |
| `temporal_data` | object | No | Project cycles and decision patterns |

**Response (200 OK):**
```json
{
  "diagnostic_id": "diag_xyz789",
  "timestamp": "2026-03-28T12:45:00Z",
  "user_input": "Me siento perdido en mi propósito de vida.",
  "axioma_ea_score": 0.87,
  "patterns": ["indecision", "search_for_meaning"],
  "analysis": {
    "ciclo_detection": {
      "primary_cycle": "Ciclo de Entrega (Delivery Cycle)",
      "cycle_length_days": 45,
      "efficiency_score": 0.72,
      "bottleneck_nodes": [
        {
          "node_name": "Client Acceptance",
          "delay_average_days": 8,
          "frequency": "occurs_in_80_percent_of_projects"
        }
      ]
    },
    "nodo_analysis": {
      "critical_nodes": [
        {
          "name": "Handoff Protocol",
          "type": "decision_node",
          "health_status": "degraded",
          "recommendation": "Implement structured handoff checklist with 48hr client pre-approval window"
        }
      ]
    },
    "vortice_identification": {
      "vortices_detected": 1,
      "vortex_type": "communication_breakdown",
      "impact": "Delays cascade into subsequent projects, affecting Q2 capacity",
      "intervention_priority": "high"
    }
  },
  "recommendations": [
    {
      "category": "innerwork",
      "messaging": "Explora tu historia familiar y decisiones pasadas que te han llevado aquí.",
      "mascot_message": "HEY te dice: 'Tu propósito no está fuera, está en cómo te tratas cada día.'"
    }
  ],
  "hey_mascot_response": {
    "tone": "supportive",
    "message": "I see a pattern here — your delivery cycle is strong (72% efficiency), but there's friction at the handoff node. This isn't about working harder; it's about smoothing the transition.",
    "next_steps": [
      "Schedule diagnostic session (€198)",
      "Review detailed vortex analysis",
      "Access Libro 0: Claridad Organizacional"
    ]
  },
  "claude_api_metadata": {
    "model": "claude-sonnet-4-20250514",
    "tokens_used": 2847,
    "latency_ms": 3200,
    "prompt_version": "neyen_diagnostic_v1.2"
  }
}
```

**Claude Integration Point:**
- **Trigger:** User submits diagnostic request
- **Model:** `claude-sonnet-4-20250514`
- **Expected Latency:** 1.5–5 seconds (varies with input complexity)
- **Token Usage:** 1,500–4,000 tokens per diagnostic

**Error Codes:**
- `400` — Invalid request (missing `user_input`)
- `401` — Authentication required
- `429` — Rate limit exceeded (max 10 diagnostics/hour for free tier)
- `500` — Internal server error
- `502` — Claude API call failed
- `503` — Claude API temporarily unavailable

---

### Get Recommendations

**Endpoint:** `GET /api/diagnostic/{diagnostic_id}/recommendations`
**Method:** `GET`
**Authentication:** Required
**Description:** Retrieves actionable recommendations based on completed diagnostic analysis.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `diagnostic_id` | string | Yes | Diagnostic session ID from `/analyze` |
| `detail_level` | string | No | `summary` or `detailed` (default: `summary`) |

**Example Request:**
```bash
GET /api/diagnostic/diag_xyz789/recommendations?detail_level=detailed
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response (200 OK):**
```json
{
  "diagnostic_id": "diag_xyz789",
  "recommendations": [
    {
      "id": "rec_001",
      "category": "process_optimization",
      "priority": "high",
      "title": "Implement 48hr Pre-Approval Protocol",
      "description": "Create structured handoff checklist with client pre-approval 48 hours before final installation completion.",
      "expected_impact": {
        "cycle_time_reduction_days": 6,
        "efficiency_gain_percent": 15,
        "implementation_effort": "medium"
      },
      "implementation_steps": [
        "Design checklist template (1 day)",
        "Pilot with next 3 projects (2 weeks)",
        "Review and adjust based on client feedback (1 week)",
        "Roll out company-wide (1 day)"
      ],
      "neyen_methodology_connection": {
        "step": "Decision",
        "principle": "No romper lo que funciona — add clarity to existing handoff, don't rebuild process"
      }
    }
  ],
  "booking_cta": {
    "message": "Ready to implement these recommendations with expert guidance?",
    "calendly_url": "https://calendly.com/ana-tsw/diagnostico-ciclos-temporales",
    "price_eur": 198,
    "session_duration_min": 90
  }
}
```

**Error Codes:**
- `404` — Diagnostic ID not found
- `401` — Unauthorized (diagnostic belongs to different user)
- `500` — Recommendation generation failed

---

## User Management

### Get User Profile

**Endpoint:** `GET /api/user/profile`
**Method:** `GET`
**Authentication:** Required

**Response (200 OK):**
```json
{
  "id": "usr_abc123",
  "email": "ana@thespiralwithin.ai",
  "name": "Ana Ballesteros",
  "organization": "The Spiral Within SLU",
  "created_at": "2026-03-15T10:30:00Z",
  "subscription": {
    "tier": "free",
    "diagnostics_used": 3,
    "diagnostics_limit": 10,
    "reset_date": "2026-04-01T00:00:00Z"
  },
  "diagnostic_history": [
    {
      "id": "diag_xyz789",
      "created_at": "2026-03-28T12:45:00Z",
      "organization_name": "DINIBA SL"
    }
  ]
}
```

---

### Update User Preferences

**Endpoint:** `PATCH /api/user/preferences`
**Method:** `PATCH`
**Authentication:** Required

**Request Body:**
```json
{
  "language": "es",
  "timezone": "Europe/Madrid",
  "notification_preferences": {
    "email_diagnostics": true,
    "email_recommendations": false
  }
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "preferences": {
    "language": "es",
    "timezone": "Europe/Madrid",
    "notification_preferences": {
      "email_diagnostics": true,
      "email_recommendations": false
    }
  }
}
```

---

## Booking & Payment Integration

### Calendly Webhook Handler

**Endpoint:** `POST /api/integrations/calendly/webhook`
**Method:** `POST`
**Authentication:** Calendly webhook signature verification (`X-Calendly-Webhook-Signature`)
**Description:** Receives Calendly booking events when user books €198 NEYĒN diagnostic session.

**Request Body (from Calendly):**
```json
{
  "event": "invitee.created",
  "payload": {
    "event_type": {
      "uuid": "q67abc123",
      "name": "1:1 Axioma E'A Deep Dive (€198)",
      "duration": 90
    },
    "invitee": {
      "email": "client@example.com",
      "first_name": "Cliente",
      "last_name": "Ejemplo"
    },
    "event": {
      "start_time": "2026-04-05T10:00:00Z",
      "end_time": "2026-04-05T11:30:00Z"
    }
  }
}
```

**Backend Actions Triggered:**
1. **Validate event signature** using `CALENDLY_WEBHOOK_SECRET`
2. **Check `event_type.uuid`** matches NEYĒN diagnostic workflow (`q67abc123`)
3. **Upsert order record:**
   - `amount`: 198
   - `currency`: "EUR"
   - `user_email`: `client@example.com`
   - `calendly_invitee_id`: `inv_xyz789`
4. **Send pre-work questionnaire** to `client@example.com` via email/Slack
5. **Notify `#neyen-core` Slack channel** of new booking

**Response (200 OK):**
```json
{
  "received": true,
  "user_id": "usr_def456",
  "session_id": "sess_ghi789",
  "notification_sent": true
}
```

**Error Codes:**
- `400` — Invalid payload or signature mismatch
- `500` — Failed to process booking

---

### Stripe Payment Confirmation

**Endpoint:** `POST /api/webhooks/stripe`
**Method:** `POST`
**Authentication:** Stripe webhook signature verification
**Description:** Handles Stripe payment events for direct purchases (Libro 0, future products).

**Request Body (from Stripe):**
```json
{
  "type": "payment_intent.succeeded",
  "data": {
    "object": {
      "id": "pi_abc123",
      "amount": 860,
      "currency": "eur",
      "metadata": {
        "product": "libro_0_kindle",
        "user_email": "ana@thespiralwithin.ai"
      }
    }
  }
}
```

**Backend Actions:**
- Log purchase in accounting system
- Send download link or access credentials to user
- Update user subscription tier (if applicable)

**Response (200 OK):**
```json
{
  "received": true,
  "order_id": "ord_jkl012"
}
```

---

## Data Models

### Standard Success Response

All successful responses follow this wrapper:
```json
{
  "success": true,
  "data": { ... }
}
```

### Standard Error Response

All error responses follow this structure:
```json
{
  "success": false,
  "error": {
    "code": "invalid_request",
    "message": "The user_input field is required.",
    "details": {
      "invalid_fields": ["user_input"]
    }
  }
}
```

---

### Diagnostic Request Schema

```typescript
interface DiagnosticRequest {
  user_input: string;
  avatar_mascot?: string; // default: "HEY"
  context?: {
    organization_name?: string;
    industry?: string;
    team_size?: number;
    founding_year?: number;
    current_challenge?: string;
  };
  temporal_data?: {
    project_cycles?: ProjectCycle[];
    decision_patterns?: DecisionPattern[];
  };
}

interface ProjectCycle {
  name: string;
  start_date: string; // ISO 8601
  end_date: string;   // ISO 8601
  team_members: number;
  outcome: 'completed_on_time' | 'delayed' | 'cancelled';
}

interface DecisionPattern {
  decision_type: string;
  frequency: 'daily' | 'weekly' | 'monthly' | 'ad_hoc';
  participants: string[];
}
```

---

### Diagnostic Response Schema

```typescript
interface DiagnosticResponse {
  diagnostic_id: string;
  timestamp: string; // ISO 8601
  user_input: string;
  axioma_ea_score: number; // 0.0–1.0
  patterns: string[];
  analysis: {
    ciclo_detection: CicloDetection;
    nodo_analysis: NodoAnalysis;
    vortice_identification: VorticeIdentification;
  };
  recommendations: Recommendation[];
  hey_mascot_response: {
    tone: 'supportive' | 'challenging' | 'celebratory';
    message: string;
    next_steps: string[];
  };
  claude_api_metadata: {
    model: string;
    tokens_used: number;
    latency_ms: number;
    prompt_version: string;
  };
}

interface CicloDetection {
  primary_cycle: string;
  cycle_length_days: number;
  efficiency_score: number; // 0.0–1.0
  bottleneck_nodes: BottleneckNode[];
}

interface BottleneckNode {
  node_name: string;
  delay_average_days: number;
  frequency: string;
}

interface NodoAnalysis {
  critical_nodes: CriticalNode[];
}

interface CriticalNode {
  name: string;
  type: 'decision_node' | 'execution_node' | 'communication_node';
  health_status: 'healthy' | 'degraded' | 'critical';
  recommendation: string;
}

interface VorticeIdentification {
  vortices_detected: number;
  vortex_type?: string;
  impact?: string;
  intervention_priority?: 'low' | 'medium' | 'high' | 'critical';
}

interface Recommendation {
  category: string;
  messaging: string;
  mascot_message: string;
}
```

---

## Error Handling

### Error Code Reference

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `invalid_request` | Malformed request body or missing required fields |
| 401 | `unauthorized` | Missing or invalid authentication token |
| 403 | `forbidden` | Valid token but insufficient permissions |
| 404 | `not_found` | Requested resource does not exist |
| 429 | `rate_limit_exceeded` | Too many requests in given time window |
| 429 | `quota_exceeded` | User has exceeded diagnostic quota |
| 500 | `internal_error` | Unexpected server error |
| 502 | `claude_api_error` | Claude API returned error |
| 503 | `service_unavailable` | Service temporarily unavailable |

---

### Example Error Responses

**400 Invalid Request:**
```json
{
  "success": false,
  "error": {
    "code": "invalid_request",
    "message": "The user_input field is required.",
    "details": {
      "invalid_fields": ["user_input"]
    }
  }
}
```

**429 Rate Limit Exceeded:**
```json
{
  "success": false,
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many diagnostic requests. Try again in 15 minutes.",
    "details": {
      "retry_after": 900,
      "limit": 10,
      "window": "15 minutes"
    }
  }
}
```

---

## Rate Limits & Quotas

### Public Diagnostics (Unauthenticated)

**Endpoint:** `POST /api/diagnostic/analyze`
**Limit:** 10 requests per 15 minutes per IP address

**Rate Limit Headers:**
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1640995200
```

---

### Authenticated Diagnostics (Logged-in Users)

**Free Tier:**
- **Diagnostics:** 10 per month (resets on 1st of each month)
- **API Requests:** 100 per hour per user
- **Claude API calls:** Shared pool (no SLA guarantee)

**Premium Tier (€198 diagnostic session):**
- **Diagnostics:** 100 per month during active subscription
- **API Requests:** 500 per hour per user
- **Claude API calls:** Priority queue, guaranteed <5s response time
- **Storage:** 100 diagnostic sessions retained indefinitely

---

### Quota Exceeded Response

When user exceeds diagnostic quota:
```json
{
  "success": false,
  "error": {
    "code": "quota_exceeded",
    "message": "You have used all 10 free diagnostics this month. Upgrade to premium or wait until April 1.",
    "details": {
      "used": 10,
      "limit": 10,
      "reset_date": "2026-04-01T00:00:00Z"
    }
  }
}
```

**HTTP Status:** `429 Too Many Requests`
**Header:** `Retry-After: 259200` (3 days in seconds)

---

## Claude API Integration Points

### Where Backend Calls Claude

1. **`POST /api/diagnostic/analyze`**
   - **Trigger:** User submits diagnostic request
   - **Claude API Call:** Send NEYĒN diagnostic prompt with user context
   - **Model:** `claude-sonnet-4-20250514`
   - **Expected Latency:** 1.5–5 seconds
   - **Token Usage:** 1,500–4,000 tokens per diagnostic

2. **`GET /api/diagnostic/{id}/recommendations`**
   - **Trigger:** User requests detailed recommendations
   - **Claude API Call:** Generate implementation roadmap based on diagnostic results
   - **Model:** `claude-sonnet-4-20250514`
   - **Expected Latency:** 3–6 seconds
   - **Token Usage:** 2,000–5,000 tokens

3. **Slack Auto-Ingestion (via n8n webhook)**
   - **Trigger:** New message in monitored Slack channels
   - **Claude API Call:** Extract action items, summarize decisions
   - **Model:** `claude-sonnet-4-20250514`
   - **Expected Latency:** 1–3 seconds
   - **Token Usage:** 500–2,000 tokens per message

---

### NEYĒN Diagnostic Prompt Template (v1.2)

```
You are the NEYĒN diagnostic system, analyzing organizational temporal patterns using the Axioma E'A framework (Ciclo-Nodo-Vórtice structures within set theory).

**Context:**
- Organization: {organization_name}
- Industry: {industry}
- Team Size: {team_size}
- Founded: {founding_year}
- Current Challenge: {current_challenge}

**Temporal Data:**
{temporal_data}

**User Input:**
"{user_input}"

**Analysis Framework:**
1. **Ciclo Detection:** Identify recurring temporal patterns (project cycles, decision cycles, communication cycles)
2. **Nodo Analysis:** Locate critical decision/execution/communication nodes within cycles
3. **Vórtice Identification:** Detect where cycles break down, energy dissipates, or friction accumulates
4. **Axioma E'A Scoring:** Calculate overall organizational health (0.0–1.0)

**Output Requirements:**
- Respond in JSON format matching DiagnosticResponse schema
- HEY mascot tone: Supportive, direct, no corporate jargon
- Recommendations must follow "no romper" principle (don't break what works, add clarity)
- Include 2-4 actionable next steps

**CRITICAL:** Base analysis ONLY on provided data. Do not fabricate KPIs or case studies.
```

---

## Testing Strategy

### Local Development

**Base URL:** `http://localhost:3000/v1`

**Test Authentication (development only):**
```bash
curl -X POST http://localhost:3000/v1/auth/test/token \
  -H "Content-Type: application/json" \
  -d '{"email": "test@thespiralwithin.ai"}'
```

---

### curl Examples

**Unauthenticated diagnostic:**
```bash
curl -X POST https://api.neyen.app/v1/api/diagnostic/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "No sé si mi relación actual me está sirviendo.",
    "avatar_mascot": "HEY"
  }'
```

**Authenticated diagnostic (with Bearer token):**
```bash
curl -X POST https://api.neyen.app/v1/api/diagnostic/analyze \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "No sé si dejar mi trabajo.",
    "avatar_mascot": "HEY",
    "context": {
      "organization_name": "DINIBA SL",
      "industry": "industrial_installations"
    }
  }'
```

---

### Postman Collection

**Collection URL:** `https://www.postman.com/neyen/workspace/neyen-mvp`

**Included Tests:**
- OAuth flow (Slack, GitHub, email simulation)
- Token refresh and validation
- Diagnostic endpoints (analyze, recommendations)
- Calendly webhook simulation (`invitee.created`)
- Stripe webhook simulation (`payment_intent.succeeded`)

---

### Automated Testing (CI/CD)

**Test Suite:** Jest + Supertest
**Coverage Target:** >80% for all endpoints
**Run Command:** `npm run test:api`

**Key Test Cases:**
- ✅ OAuth flow completes successfully
- ✅ Invalid tokens return 401
- ✅ Diagnostic analysis returns valid JSON schema
- ✅ Rate limiting blocks after quota exceeded
- ✅ Claude API errors return 502 with request_id
- ✅ Calendly webhook creates user account
- ✅ Stripe webhook logs payment correctly

---

## Security Notes

1. **OAuth State Validation:** All OAuth flows validate `state` parameter to prevent CSRF
2. **JWT Expiration:** Access tokens expire after 1 hour, refresh tokens after 30 days
3. **Webhook Signature Verification:** Calendly and Stripe webhooks verified via HMAC signature
4. **Rate Limiting:** Implemented at API gateway (Nginx) + application level
5. **Data Encryption:** All diagnostic data encrypted at rest (AES-256)
6. **GDPR Compliance:** Users can request data export or deletion via `/api/user/data-export` and `/api/user/delete`

---

## Changelog

### v1.0.0 (2026-03-28)
- Initial API specification
- Authentication endpoints (OAuth + JWT)
- Diagnostic endpoints with Claude API integration
- Calendly + Stripe webhook handlers
- Rate limiting and error handling
- TypeScript data model schemas

---

## Next Steps

- [ ] Implement API versioning strategy (v2 path)
- [ ] Add GraphQL endpoint for complex queries
- [ ] Build admin dashboard API (`/api/admin/*`)
- [ ] Create webhook retry mechanism for failed deliveries
- [ ] Add real-time diagnostic progress tracking (WebSocket endpoint)
- [ ] Generate OpenAPI 3.0 spec for auto-documentation

---

## Contact

**Ana Ballesteros Benavent** — CSO, The Spiral Within SLU
Slack: `#neyen-core` | Email: ana@thespiralwithin.ai
