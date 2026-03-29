
# WF-01 TESTING PROTOCOL
**Integration Testing & Quality Assurance**

---

## **OVERVIEW**

This protocol validates the complete WF-01 ingestion pipeline from input to dashboard visibility.

**Test Scope:**
- Manual API calls → Supabase insert
- Classification quality (Claude API)
- Cross-linking trigger (WF-02)
- Dashboard visibility (5min refresh)
- Error handling & edge cases

**Duration:** 2-3 hours initial testing + 24hr monitoring

---

## **PRE-TESTING CHECKLIST**

Before running tests, verify:

- [ ] WF-01 imported to n8n and **Active**
- [ ] Anthropic API credentials configured
- [ ] Supabase credentials configured
- [ ] WF-02 is **Active** (cross-linking)
- [ ] Dashboard accessible at https://neyen.thespiralwithin.ai/system.html
- [ ] Baseline: Current entry count in Supabase (should be 17)

---

## **TEST SUITE**

### **TEST 1: BASIC MANUAL INGESTION**

**Objective:** Verify WF-01 accepts manual POST and creates entry

**Execution:**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "text": "Testing WF-01 ingestion pipeline with DINIBA philosophy of no romper",
        "source": "manual",
        "user": "ana_test"
    }'
```

**Expected Response:**
```json
{
    "status": "success",
    "message": "Entry created and cross-linking triggered",
    "file_name": "auto_manual_[timestamp]"
}
```

**Verification:**

1. Check n8n execution log (WF-01 → Executions → Latest)
2. All 8 nodes should show green checkmarks
3. Query Supabase:
```sql
SELECT * FROM metadata 
WHERE source = 'manual' 
ORDER BY created_at DESC 
LIMIT 1;
```

4. Wait 5 minutes, refresh dashboard
5. Search for "DINIBA philosophy" in dashboard
6. Verify entry appears with auto-generated tags/entities

**Pass Criteria:**
- ✅ 200 response with success status
- ✅ Entry in Supabase with file_name matching response
- ✅ Tags include "DINIBA", "philosophy", "no romper"
- ✅ Entities include "DINIBA"
- ✅ narrative_role is "origin" or "system"
- ✅ Entry visible in dashboard within 5 minutes

---

### **TEST 2: CLASSIFICATION QUALITY**

**Objective:** Verify Claude API extracts accurate metadata

**Test Cases:**

**2A: Pilot Entry**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "text": "HELIOS pilot at Colegio Elios is a 4-year education transformation plan starting 2022",
        "source": "manual",
        "user": "ana_test"
    }'
```

**Expected Classification:**
- Tags: `["HELIOS", "education", "pilot", "4-year"]`
- Entities: `["Colegio Elios", "HELIOS"]`
- narrative_role: `"exploration"` or `"pilot"`
- timeline_group: `"2024-2026"` or `"2019-2023"`

**2B: Symbol Entry**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "text": "Water consciousness represents recursive observation and the mirror principle in NEYĒN",
        "source": "manual",
        "user": "ana_test"
    }'
```

**Expected Classification:**
- Tags: `["water", "consciousness", "recursion", "mirror"]`
- Entities: `["NEYĒN"]`
- narrative_role: `"symbol"`
- summary: Should mention "recursive observation" or "mirror principle"

**Pass Criteria:**
- ✅ At least 3/5 tags are relevant
- ✅ All entities are correctly identified
- ✅ narrative_role is appropriate
- ✅ Summary is factual and concise (1-2 sentences)
- ✅ timeline_group matches content or defaults to current period

---

### **TEST 3: FILTERING RULES**

**Objective:** Verify short/command messages are filtered out

**3A: Short Message (Should Skip)**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "text": "ok thanks",
        "source": "manual",
        "user": "ana_test"
    }'
```

**Expected:** No entry created (filtered at Node 3)

**3B: Command Message (Should Skip)**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "text": "/help system",
        "source": "manual",
        "user": "ana_test"
    }'
```

**Expected:** No entry created (filtered at Node 3)

**Verification:**
- Check n8n execution log
- Node 3 (Filter Messages) should show "false" branch taken
- No Supabase insert should occur
- Entry count in metadata table unchanged

**Pass Criteria:**
- ✅ No new entries in Supabase
- ✅ WF-01 execution log shows filter triggered
- ✅ No error messages

---

### **TEST 4: CROSS-LINKING TRIGGER**

**Objective:** Verify WF-02 executes after WF-01 insert

**Execution:**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "text": "E'A geometric framework connects to serpent star symbolism and water consciousness",
        "source": "manual",
        "user": "ana_test"
    }'
```

**Verification:**

1. Note the `file_name` from response
2. Check WF-02 execution log (should show new execution within seconds)
3. Query Supabase for the new entry:
```sql
SELECT file_name, related_ids 
FROM metadata 
WHERE file_name = 'auto_manual_[timestamp]';
```

4. `related_ids` should be populated (not empty array)
5. Related entries should include `TSW_ea_geometry`, `TSW_serpent_star_symbol`, `TSW_mirror_water_symbol`

**Pass Criteria:**
- ✅ WF-02 execution log shows trigger after WF-01
- ✅ `related_ids` array has at least 3 UUIDs
- ✅ Related entries share tags (E'A, geometry, symbolism)
- ✅ Cross-link scoring worked (tags×3 + entities×2 + role×1)

---

### **TEST 5: END-TO-END LATENCY**

**Objective:** Measure time from webhook → dashboard visibility

**Execution:**
```bash
# Note current time
date

# Send request
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "text": "Latency test entry for WF-01 integration testing protocol verification",
        "source": "manual",
        "user": "ana_test"
    }'

# Note response time
# Wait and refresh dashboard every 30 seconds
# Note when entry becomes visible
```

**Target Latency:**
- Webhook → Supabase insert: < 5 seconds
- Supabase insert → Dashboard visibility: < 5 minutes (auto-refresh)
- Total: < 5 minutes 5 seconds

**Pass Criteria:**
- ✅ Entry in Supabase within 10 seconds
- ✅ Entry visible in dashboard within 6 minutes
- ✅ No errors in n8n execution log

---

### **TEST 6: ERROR HANDLING**

**6A: Invalid JSON**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d 'invalid json here'
```

**Expected:** Error response, workflow handles gracefully

**6B: Missing Required Fields**
```bash
curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
    -H "Content-Type: application/json" \
    -d '{
        "source": "manual"
    }'
```

**Expected:** Workflow continues with empty message_text (filtered at Node 3)

**6C: Claude API Timeout Simulation**

Temporarily disable Anthropic API credentials in n8n, send valid request.

**Expected:** Error at Node 4, workflow stops, error logged

**Pass Criteria:**
- ✅ Errors are logged in n8n
- ✅ No partial entries in Supabase
- ✅ Workflow doesn't crash completely
- ✅ Re-enabling credentials allows recovery

---

### **TEST 7: BULK INGESTION**

**Objective:** Verify WF-01 handles multiple requests

**Execution:**
```bash
# Send 5 requests in quick succession
for i in {1..5}; do
    curl -X POST https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest \
        -H "Content-Type: application/json" \
        -d "{
            \"text\": \"Bulk test entry number $i for WF-01 load testing\",
            \"source\": \"manual\",
            \"user\": \"ana_test\"
        }"
    echo ""
done
```

**Verification:**
- All 5 requests should succeed
- 5 new entries in Supabase
- Each has unique `file_name` (timestamp differentiation)
- All trigger WF-02 successfully

**Pass Criteria:**
- ✅ 5/5 success responses
- ✅ 5 entries in Supabase
- ✅ No duplicate file_names
- ✅ All cross-linked within 1 minute

---

## **POST-TESTING VALIDATION**

### **Dashboard Review**

After all tests complete:

1. Open https://neyen.thespiralwithin.ai/system.html
2. Total entry count should be: **17 (baseline) + [successful test entries]**
3. Filter by source: "manual"
4. Review test entries:
     - Tags look accurate
     - Entities extracted correctly
     - Summaries are coherent
     - narrative_role assignments make sense

### **Supabase Quality Check**
```sql
-- Count new test entries
SELECT COUNT(*) 
FROM metadata 
WHERE source = 'manual' 
AND created_at > NOW() - INTERVAL '1 hour';

-- Review classification quality
SELECT file_name, tags, entities, narrative_role, summary
FROM metadata 
WHERE source = 'manual' 
ORDER BY created_at DESC 
LIMIT 10;

-- Verify cross-linking worked
SELECT file_name, array_length(related_ids, 1) as num_links
FROM metadata 
WHERE source = 'manual' 
ORDER BY created_at DESC;
```

### **Clean Up Test Entries (Optional)**
```sql
-- Delete test entries after validation
DELETE FROM metadata 
WHERE source = 'manual' 
AND user_id = 'ana_test';
```

---

## **24-HOUR MONITORING**

After initial tests pass, monitor for 24 hours:

**Metrics to track:**
- Total WF-01 executions
- Success rate (should be > 95%)
- Average latency (webhook → Supabase)
- Classification quality (manual spot-check 5 entries)
- Cross-linking accuracy (% with related_ids populated)

**Red flags:**
- ❌ Success rate < 90%
- ❌ Any Claude API errors
- ❌ Supabase insert failures
- ❌ WF-02 not triggering
- ❌ Latency > 10 seconds

---

## **PRODUCTION READINESS CHECKLIST**

Before connecting Slack/Telegram:

- [ ] All 7 tests passed
- [ ] 24-hour monitoring complete
- [ ] No critical errors in logs
- [ ] Classification quality acceptable (manual review)
- [ ] Cross-linking working (> 90% entries have related_ids)
- [ ] Dashboard updating correctly
- [ ] Latency < 10 seconds consistently
- [ ] Error handling verified
- [ ] Bulk ingestion stable

---

## **ROLLBACK PLAN**

If WF-01 fails in production:

1. **Immediate:** Deactivate WF-01 workflow in n8n
2. **Stop input:** Disconnect Slack/Telegram webhooks
3. **Review logs:** Check last 10 executions for error patterns
4. **Fix identified issue:** Update workflow, credentials, or configuration
5. **Re-test:** Run TEST 1-3 again
6. **Re-activate:** Only after passing tests

---

**Status:** Ready for execution  
**Estimated Time:** 2-3 hours + 24hr monitoring  
**Owner:** Ana Ballesteros Benavent, CSO  
**Last updated:** March 2026

💙🐎🔥
