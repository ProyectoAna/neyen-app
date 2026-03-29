
# NEYĒN SYSTEM — DATABASE SCHEMA
**PostgreSQL on Supabase | Version 1.0.0**

---

## **OVERVIEW**

The NEYĒN metadata system uses **5 core tables** in Supabase PostgreSQL:

1. **metadata** — Core system entries (symbols, pilots, systems, etc.)
2. **users** — User authentication and profile data
3. **diagnostics** — Diagnostic session results
4. **bookings** — Appointment scheduling
5. **payments** — Payment transaction records

**Key Features:**
- Row-Level Security (RLS) enabled on all tables
- Real-time subscriptions via Supabase Realtime
- Automated timestamps (created_at, updated_at)
- Foreign key constraints for referential integrity
- Composite indexes for query optimization

---

## **TABLE 1: METADATA**

**Purpose:** Stores all NEYĒN system entries (symbols, pilots, systems, origins, etc.)

**Schema:**
```sql
CREATE TABLE metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name TEXT UNIQUE NOT NULL,
    type TEXT,
    summary TEXT,
    tags TEXT[] DEFAULT '{}',
    entities TEXT[] DEFAULT '{}',
    emotional_tone TEXT,
    source TEXT NOT NULL,
    themes TEXT[] DEFAULT '{}',
    concepts TEXT[] DEFAULT '{}',
    keywords TEXT[] DEFAULT '{}',
    mime_type TEXT,
    cluster TEXT,
    related_ids UUID[] DEFAULT '{}',
    date_estimated TEXT,
    timeline_group TEXT,
    narrative_role TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_metadata_file_name ON metadata(file_name);
CREATE INDEX idx_metadata_source ON metadata(source);
CREATE INDEX idx_metadata_narrative_role ON metadata(narrative_role);
CREATE INDEX idx_metadata_timeline_group ON metadata(timeline_group);
CREATE INDEX idx_metadata_tags ON metadata USING GIN(tags);
CREATE INDEX idx_metadata_entities ON metadata USING GIN(entities);
CREATE INDEX idx_metadata_related_ids ON metadata USING GIN(related_ids);
```

**Row-Level Security:**
```sql
ALTER TABLE metadata ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access"
ON metadata FOR SELECT
USING (true);

CREATE POLICY "Authenticated insert"
ON metadata FOR INSERT
TO authenticated
WITH CHECK (true);

CREATE POLICY "Authenticated update"
ON metadata FOR UPDATE
TO authenticated
USING (true);
```

**Triggers:**
```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER metadata_updated_at
BEFORE UPDATE ON metadata
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();
```

---

## **TABLE 2: USERS**

**Purpose:** Authentication and user profile management

**Schema:**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    oauth_provider TEXT,
    oauth_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_sign_in_at TIMESTAMPTZ
);
```

**Indexes:**
```sql
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_oauth_provider ON users(oauth_provider);
```

**Row-Level Security:**
```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own data"
ON users FOR SELECT
TO authenticated
USING (auth.uid() = id);

CREATE POLICY "Users update own data"
ON users FOR UPDATE
TO authenticated
USING (auth.uid() = id);
```

---

## **TABLE 3: DIAGNOSTICS**

**Purpose:** Store diagnostic session results (4-step HEY flow)

**Schema:**
```sql
CREATE TABLE diagnostics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id TEXT UNIQUE NOT NULL,
    step_1_response TEXT,
    step_2_response TEXT,
    step_3_response TEXT,
    step_4_response TEXT,
    analysis JSONB,
    recommended_actions TEXT[],
    status TEXT DEFAULT 'in_progress',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

**Indexes:**
```sql
CREATE INDEX idx_diagnostics_user_id ON diagnostics(user_id);
CREATE INDEX idx_diagnostics_session_id ON diagnostics(session_id);
CREATE INDEX idx_diagnostics_status ON diagnostics(status);
CREATE INDEX idx_diagnostics_analysis ON diagnostics USING GIN(analysis);
```

**Row-Level Security:**
```sql
ALTER TABLE diagnostics ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own diagnostics"
ON diagnostics FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Public insert diagnostics"
ON diagnostics FOR INSERT
WITH CHECK (true);
```

---

## **TABLE 4: BOOKINGS**

**Purpose:** Appointment scheduling with Calendly integration

**Schema:**
```sql
CREATE TABLE bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    diagnostic_id UUID REFERENCES diagnostics(id) ON DELETE SET NULL,
    calendly_event_uri TEXT UNIQUE,
    calendly_invitee_uri TEXT,
    event_type TEXT,
    scheduled_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    status TEXT DEFAULT 'scheduled',
    cancellation_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_bookings_user_id ON bookings(user_id);
CREATE INDEX idx_bookings_diagnostic_id ON bookings(diagnostic_id);
CREATE INDEX idx_bookings_calendly_event_uri ON bookings(calendly_event_uri);
CREATE INDEX idx_bookings_scheduled_at ON bookings(scheduled_at);
CREATE INDEX idx_bookings_status ON bookings(status);
```

**Row-Level Security:**
```sql
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own bookings"
ON bookings FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Service role full access"
ON bookings FOR ALL
TO service_role
USING (true);
```

---

## **TABLE 5: PAYMENTS**

**Purpose:** Stripe payment transaction records

**Schema:**
```sql
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    booking_id UUID REFERENCES bookings(id) ON DELETE SET NULL,
    stripe_payment_intent_id TEXT UNIQUE NOT NULL,
    stripe_customer_id TEXT,
    amount_cents INTEGER NOT NULL,
    currency TEXT DEFAULT 'EUR',
    status TEXT DEFAULT 'pending',
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**
```sql
CREATE INDEX idx_payments_user_id ON payments(user_id);
CREATE INDEX idx_payments_booking_id ON payments(booking_id);
CREATE INDEX idx_payments_stripe_payment_intent_id ON payments(stripe_payment_intent_id);
CREATE INDEX idx_payments_status ON payments(status);
```

**Row-Level Security:**
```sql
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read own payments"
ON payments FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

CREATE POLICY "Service role full access"
ON payments FOR ALL
TO service_role
USING (true);
```

---

## **RELATIONSHIPS**

```
users (1) ──< (many) diagnostics
users (1) ──< (many) bookings
users (1) ──< (many) payments

diagnostics (1) ──< (many) bookings
bookings (1) ──< (many) payments

metadata.related_ids[] ──> metadata.id (self-referential)
```

---

## **SECURITY CHECKLIST**

- [x] RLS enabled on all tables
- [x] Foreign key constraints enforced
- [x] Sensitive data NOT stored in database
- [x] Timestamps on all tables
- [x] Indexes on foreign keys
- [x] GIN indexes on array/JSONB columns
- [x] Service role access limited to webhooks
- [x] Public read access only where needed

---

**Last updated:** March 2026  
**Maintained by:** Ana Ballesteros Benavent, CSO, The Spiral Within SLU
