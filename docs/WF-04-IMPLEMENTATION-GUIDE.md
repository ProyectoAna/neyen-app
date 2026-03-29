
# WF-04 IMPLEMENTATION GUIDE
**Timeline Engine — Temporal Clustering & Narrative Arcs**

---

## **OVERVIEW**

WF-04 analyzes all NEYĒN metadata entries and organizes them into three temporal periods, creating a coherent narrative timeline from DINIBA's founding (1974) to current execution (2026).

**Location:** `workflows/WF-04-timeline-engine.json`

**Purpose:**
- Fetch all entries from Supabase
- Parse `date_estimated` field
- Assign `timeline_group` (1974-1990 | 2019-2023 | 2024-2026)
- Detect narrative arc progression
- Update entries in Supabase
- Return clustering analysis

---

## **TEMPORAL PERIODS**

### **Period 1: Origin (1974-1990)**

**Dominant Narrative Role:** Setup/Origin

**Expected Entries:**
- TSW_origin_diniba (DINIBA founding 1974)
- Early "no romper" philosophy development
- Enrique Ballesteros operational foundations

**Characteristics:**
- Industrial installations background
- Core principles establishment
- Foundational practices

---

### **Period 2: Development (2019-2023)**

**Dominant Narrative Role:** Exploration/Realisation

**Expected Entries:**
- TSW_ea_geometry (E'A framework development)
- TSW_personal_awakening (Recursive observation)
- TSW_mirror_water_symbol (Consciousness frameworks)
- TSW_serpent_star_symbol (Geometric principles)
- TSW_libro_0 (Publication, manuscript completion)

**Characteristics:**
- Intellectual framework formation
- Symbol system development
- Mathematical/geometric foundations
- Personal transformation narrative

---

### **Period 3: Execution (2024-2026)**

**Dominant Narrative Role:** Integration/Pilot

**Expected Entries:**
- TSW_pilot_helios (Colegio Elios, 2022-2026)
- TSW_pilot_xmas (Nov 2024)
- TSW_pilot_paterna (2024)
- TSW_trademark (EUIPO registration)
- TSW_company (TSW SLU formation)
- TSW_ops_architecture (System infrastructure)

**Characteristics:**
- Methodology application
- Legal/business formalization
- Active client engagement
- Infrastructure deployment

---

## **ARCHITECTURE**

```
┌─────────────────────────────────────────────────────────┐
│ Node 1: Manual Trigger                                 │
│ • Webhook: POST /wf04-timeline                         │
│ • Or: Scheduled (daily/weekly)                         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Node 2: Fetch All Entries                              │
│ • Supabase: SELECT * FROM metadata                     │
│ • Returns all entries (17+)                            │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Node 3: Temporal Clustering                            │
│ • Parse date_estimated (YYYY, YYYY-MM-DD, etc.)        │
│ • Assign timeline_group based on year                  │
│ • Logic:                                               │
│   - 1974-1990 → "1974-1990"                           │
│   - 2019-2023 → "2019-2023"                           │
│   - 2024-2026 → "2024-2026"                           │
│   - Default: "2024-2026"                              │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Node 4: Narrative Arc Detection                       │
│ • Group entries by timeline_group                      │
│ • Count entries per period                             │
│ • Identify dominant narrative_role per period          │
│ • Detect progression patterns                          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Node 5: Split in Batches                              │
│ • Process entries one by one                           │
│ • Loop through all entries                             │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Node 6: Extract Entry                                  │
│ • Get current entry from batch                         │
│ • Prepare for update                                   │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Node 7: Update Timeline Group                          │
│ • Supabase UPDATE metadata                             │
│ • SET timeline_group = calculated value                │
│ • WHERE id = entry.id                                  │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼ (loops back to Node 5 until all done)
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Node 8: Respond Summary                                │
│ • Return clustering analysis                           │
│ • Show entries per period                              │
│ • Indicate total entries updated                       │
└─────────────────────────────────────────────────────────┘
```

---

## **INSTALLATION**

### **1. Import Workflow**
```bash
# Access n8n
https://n8n-docker-t9sr.onrender.com

# Navigate to: Workflows → Import from File
# Select: workflows/WF-04-timeline-engine.json
# Click: Import
```

### **2. Configure Credentials**

**Supabase API:**
- Same credentials as WF-01 and WF-02
- Verify connection to `metadata` table
- Confirm UPDATE permissions enabled

### **3. Activate Workflow**

- Toggle: **Active**
- Optionally set schedule: Daily at 3:00 AM

---

## **USAGE**

### **Manual Execution (cURL)**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf04-timeline

# Expected response:
# {
#   "status": "complete",
#   "message": "Timeline clustering complete",
#   "analysis": {
#     "1974-1990": {"count": 1, "roles": ["origin"], "dominant": "origin"},
#     "2019-2023": {"count": 6, "roles": ["symbol", "realisation"], "dominant": "exploration"},
#     "2024-2026": {"count": 10, "roles": ["pilot", "integration"], "dominant": "integration"}
#   },
#   "entries_updated": 17
# }
```

### **Scheduled Execution**

**Recommended:** Run daily to keep timeline_group current as new entries are added via WF-01.

**n8n Schedule:**
- Trigger Type: Schedule
- Interval: Every day at 3:00 AM
- Timezone: Europe/Madrid

---

## **CLUSTERING LOGIC**

### **Date Parsing**

The workflow handles multiple date formats:

**Supported Formats:**
- `YYYY` — e.g., "1974", "2023"
- `YYYY-MM-DD` — e.g., "2024-03-29"
- Any string containing 4-digit year — e.g., "March 2023", "2022-Q4"

**Extraction Logic:**
```javascript
// YYYY format
if (/^\d{4}$/.test(dateStr)) {
  year = parseInt(dateStr);
}
// YYYY-MM-DD format
else if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
  year = parseInt(dateStr.split('-')[0]);
}
// Extract any 4-digit year
else {
  const match = dateStr.match(/\d{4}/);
  if (match) year = parseInt(match[0]);
}
```

### **Timeline Assignment**
```javascript
if (year >= 1974 && year <= 1990) {
  timeline_group = '1974-1990';
} else if (year >= 2019 && year <= 2023) {
  timeline_group = '2019-2023';
} else if (year >= 2024 && year <= 2026) {
  timeline_group = '2024-2026';
} else {
  timeline_group = '2024-2026'; // default for missing/invalid dates
}
```

---

## **NARRATIVE ARC DETECTION**

### **Progression Model**

The workflow detects narrative progression across the three periods:

**Expected Progression:**
```
1974-1990: Setup/Origin
    ↓
2019-2023: Exploration/Realisation
    ↓
2024-2026: Integration/Execution
```

### **Analysis Output**

For each period, the workflow calculates:
- **count:** Number of entries in period
- **roles:** Array of all narrative_role values
- **dominant:** Most common or expected role for that period

**Example:**
```json
{
  "1974-1990": {
    "count": 1,
    "roles": ["origin"],
    "dominant": "origin"
  },
  "2019-2023": {
    "count": 6,
    "roles": ["symbol", "symbol", "realisation", "exploration", "exploration", "inciting_event"],
    "dominant": "exploration"
  },
  "2024-2026": {
    "count": 10,
    "roles": ["pilot", "pilot", "pilot", "integration", "integration", "system", "system"],
    "dominant": "integration"
  }
}
```

---

## **TESTING**

### **Pre-Test Verification**
```sql
-- Check current timeline_group values
SELECT timeline_group, COUNT(*) 
FROM metadata 
GROUP BY timeline_group;

-- Should show NULL or inconsistent values before WF-04
```

### **Execute WF-04**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf04-timeline
```

### **Post-Test Verification**
```sql
-- Verify all entries have timeline_group
SELECT file_name, date_estimated, timeline_group 
FROM metadata 
ORDER BY date_estimated;

-- Check distribution
SELECT timeline_group, COUNT(*) 
FROM metadata 
GROUP BY timeline_group 
ORDER BY timeline_group;

-- Expected:
-- 1974-1990: 1 entry (DINIBA)
-- 2019-2023: 5-6 entries (development phase)
-- 2024-2026: 10-11 entries (execution phase)
```

---

## **EXPECTED RESULTS**

### **After First Execution**

**Entries in 1974-1990:**
- TSW_origin_diniba

**Entries in 2019-2023:**
- TSW_ea_geometry (2019)
- TSW_personal_awakening (2023)
- TSW_mirror_water_symbol (~2019-2023)
- TSW_serpent_star_symbol (~2019-2023)
- TSW_libro_0 (2023, manuscript completion)
- TSW_timeline_origins (2019)

**Entries in 2024-2026:**
- TSW_pilot_helios (2022-2026, ongoing)
- TSW_pilot_xmas (Nov 2024)
- TSW_pilot_paterna (2024)
- TSW_trademark (2024)
- TSW_company (2025-2026)
- TSW_ops_architecture (2026)
- TSW_coherence_protocol (2026)
- TSW_ea_portal (2026)
- Plus any auto-generated entries from WF-01

---

## **MAINTENANCE**

### **Adding New Periods**

If the system extends beyond 2026, update the clustering logic in Node 3:
```javascript
// Add new period
else if (year >= 2027 && year <= 2030) {
  timeline_group = '2027-2030';
}
```

Also update narrative analysis in Node 4 to include the new period.

### **Reclassification**

To reclassify all entries (e.g., after manual date corrections):

1. Update `date_estimated` values in Supabase manually
2. Execute WF-04 again
3. Verify new `timeline_group` assignments

---

## **TROUBLESHOOTING**

**Issue: All entries assigned to default period (2024-2026)**
- Check `date_estimated` values in Supabase
- Verify date format is parseable (YYYY or YYYY-MM-DD)
- Review Node 3 execution output for parsing errors

**Issue: Workflow times out**
- Large number of entries (100+) may take time
- Increase n8n timeout setting
- Or batch processing in smaller chunks

**Issue: Timeline_group not updating**
- Verify Supabase credentials have UPDATE permission
- Check RLS policies allow updates to `timeline_group` field
- Review Node 7 execution log for SQL errors

---

## **PRODUCTION READINESS**

- [ ] Import WF-04 to n8n
- [ ] Configure Supabase credentials
- [ ] Test with manual execution
- [ ] Verify all 17 entries get timeline_group assigned
- [ ] Check distribution matches expectations (1/6/10 split)
- [ ] Activate workflow
- [ ] Optionally set daily schedule
- [ ] Monitor for 48 hours

---

**Status:** Ready for deployment  
**Owner:** Ana Ballesteros Benavent, CSO  
**Last updated:** March 2026

💙🐎🔥
