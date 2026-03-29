
# WF-01 IMPLEMENTATION GUIDE
**Auto-Classification Ingestion Pipeline**

---

## **OVERVIEW**

WF-01 is the core ingestion pipeline that automatically classifies and stores content from multiple sources (Slack, Telegram, manual input) into the NEYĒN metadata system.

**Location:** `workflows/WF-01-ingestion-pipeline.json`

**Purpose:**
- Accept raw content from various sources
- Use Claude API to classify and extract metadata
- Insert structured entries into Supabase
- Trigger cross-linking (WF-02) automatically
- Respond with success confirmation

---

## **ARCHITECTURE**

### **Pipeline Flow**

```
Input Sources → Validation → Classification → Storage → Cross-linking
```

| Stage | Component | Technology |
|-------|-----------|-----------|
| Input | Slack/Telegram Webhooks, Manual API | Message Queue |
| Validation | Schema Validation | JSON Schema |
| Classification | Claude API | LLM Processing |
| Storage | Supabase | PostgreSQL |
| Cross-linking | WF-02 Trigger | Event System |
