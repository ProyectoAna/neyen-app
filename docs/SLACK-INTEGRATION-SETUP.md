# SLACK INTEGRATION SETUP
**Auto-Ingestion from #neyen-core to NEYĒN System**

---

## **OVERVIEW**

This guide documents how to connect Slack channel #neyen-core to the NEYĒN ingestion pipeline (WF-01), enabling automatic classification and insertion of messages into the system metadata.

**Status:** Implemented. App disabled by Slack on March 13 2026 — see **Re-enablement Steps** below.

---

## **ARCHITECTURE**

```
┌─────────────────────────────────────────────────────────┐
│ Slack #neyen-core                                       │
│ • User posts message                                    │
│ • Message.channels event fires                          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Slack Event API                                         │
│ • Webhook configured to n8n endpoint                    │
│ • Sends message payload as JSON                         │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ n8n WF-01 (Ingestion Pipeline)                         │
│ • Receives webhook POST                                 │
│ • Extracts message text + metadata                      │
│ • Calls Claude API for classification                   │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Claude API Classification                               │
│ • Analyzes message content                              │
│ • Extracts: tags, entities, summary, narrative_role     │
│ • Returns structured metadata JSON                      │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ Supabase Metadata Table                                │
│ • Insert new entry with generated metadata              │
│ • Auto-assigns file_name, timestamp, source="slack"    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ WF-02 Cross-Linking Trigger                            │
│ • Executes automatically after insert                   │
│ • Updates related_ids for new entry + affected entries  │
│ • Dashboard updates within 5 minutes (auto-refresh)     │
└─────────────────────────────────────────────────────────┘
```

---

## **WHY THE APP WAS DISABLED (March 13 2026)**

Slack disables apps that repeatedly fail to respond within 3 seconds. Five bugs caused this:

| # | Bug | Impact |
|---|-----|--------|
| 1 | **Missing `url_verification` handler** | Slack periodically re-verifies the endpoint; without a `{"challenge": "..."}` response the app fails verification and gets disabled |
| 2 | **Wrong event payload path** | Code read `body.text` instead of `body.event.text` — no Slack messages were ever actually processed |
| 3 | **Render free-tier cold starts** | n8n on Render sleeps after 15 min of inactivity; cold start takes 30–50 s, far exceeding Slack's 3 s deadline → repeated failures → disable |
| 4 | **No early ACK to Slack** | Workflow only responded after Claude + Supabase completed (5–15 s even when warm), exceeding Slack's timeout |
| 5 | **No bot-message filter** | The bot's own messages would trigger the pipeline, risking infinite ingest loops |

**All five issues are fixed in the updated `WF-01-ingestion-pipeline.json` and the new `keep-alive.yml` GitHub Actions workflow.**

---

## **RE-ENABLEMENT STEPS**

1. **Deploy the updated workflow** — import `workflows/WF-01-ingestion-pipeline.json` into n8n and activate it.
2. **Merge / push to main** — the `keep-alive.yml` GitHub Action will start pinging Render every 10 minutes, preventing cold starts.
3. **Re-enable the Slack app:**
   - Go to https://api.slack.com/apps → select "Asistente TheSpiralWithin"
   - If shown a "disabled" banner, click **"Reactivate app"**
   - Navigate to **Event Subscriptions** → re-enter the Request URL:
     `https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest`
   - Slack will immediately send a `url_verification` challenge — the updated workflow handles this automatically
   - Wait for the green **"Verified ✓"** checkmark
   - Click **"Save Changes"**
4. **Verify end-to-end** — post a test message in #neyen-core and confirm it appears in Supabase.

---

## **SETUP STEPS**

### **1. Create Slack App**
1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name: `NEYĒN Ingestion Bot`
4. Workspace: Select your workspace
5. Click **"Create App"**

### **2. Enable Event Subscriptions**
1. In the Slack App dashboard, navigate to **"Event Subscriptions"**
2. Toggle **"Enable Events"** → ON
3. **Request URL:** Set to n8n WF-01 webhook endpoint (format: `https://n8n-docker-t9sr.onrender.com/webhook/wf01-ingest`)
4. Under **"Subscribe to bot events"**, add:
   - `message.channels` — Listen to messages posted to channels
5. Click **"Save Changes"**

### **3. Configure OAuth & Permissions**
1. Navigate to **"OAuth & Permissions"**
2. Under **"Scopes"** → **"Bot Token Scopes"**, add:
   - `channels:history` — View messages in public channels
   - `channels:read` — View basic channel information
3. Scroll up and click **"Install to Workspace"**
4. Authorize the app
5. Copy the **"Bot User OAuth Token"** (starts with `xoxb-`)

### **4. Add Bot to #neyen-core Channel**
1. In Slack, go to #neyen-core
2. Type: `/invite @NEYĒN Ingestion Bot`
3. Confirm the bot is added

### **5. Configure n8n WF-01 Webhook**

**In WF-01 workflow:**
- **Trigger Node:** Webhook
  - HTTP Method: POST
  - Path: `/wf01-ingest`
  - Authentication: None (Slack will verify via challenge)

- **Check URL Verification Node:** IF
  - Condition: `{{$json.type}}` equals `url_verification`
  - TRUE branch → **Respond Challenge** node: `{"challenge": "{{$json.challenge}}"}`
  - FALSE branch → Extract Content

- **Extract Content Node:** Function — reads from `body.event.*` (not `body.*`):
  - `message_text`: `event.text`
  - `user_id`: `event.user`
  - `channel_id`: `event.channel`
  - `timestamp`: parsed from `event.ts`
  - Skips bot messages (`event.bot_id` or `event.subtype === 'bot_message'`)

- **Respond ACK Node:** RespondToWebhook — placed BEFORE Claude/Supabase so Slack gets its 200 within 3 s; the workflow continues processing after responding.

### **6. Test the Integration**
1. Post a message in #neyen-core: `Test: DINIBA philosophy of no romper`
2. Verify in n8n execution log that WF-01 received the message
3. Check Supabase metadata table for new entry with source="slack"
4. Wait 5 minutes, check dashboard — entry should appear

---

## **MESSAGE CLASSIFICATION LOGIC**

**Claude API Prompt Template:**

```
Analyze this Slack message and extract NEYĒN metadata:

Message: "{message_text}"
User: {user_id}
Channel: #neyen-core
Timestamp: {timestamp}

Extract and return JSON:
{
  "tags": ["tag1", "tag2", "tag3"],
  "entities": ["entity1", "entity2"],
  "summary": "1-2 sentence summary",
  "narrative_role": "symbol|system|pilot|origin|exploration|setup|conflict|realisation|integration",
  "date_estimated": "YYYY-MM-DD or YYYY",
  "timeline_group": "1974-1990|2019-2023|2024-2026"
}

Rules:
- Tags: 3-5 keywords describing the content
- Entities: People, companies, concepts mentioned
- Summary: Concise, factual
- Narrative_role: Best fit from the list above
- Date_estimated: Infer from context or use message timestamp
- Timeline_group: Map to one of the three periods
```

---

## **FILTERING RULES**

**Messages to ingest:**
- ✅ Substantive content about NEYĒN/TSW methodology
- ✅ Pilot updates, case study notes
- ✅ References to symbols, systems, frameworks
- ✅ Historical context (DINIBA, origins)

**Messages to skip:**
- ❌ Purely operational ("meeting at 3pm")
- ❌ Greetings, acknowledgments
- ❌ Bot commands or system messages
- ❌ Messages shorter than 10 words

**Filtering logic in n8n:**
- Add **IF** node after message extraction
- Condition: `{{$json.message_text.length}} > 10 AND NOT {{$json.message_text.startsWith('/')}}`

---

## **EXPECTED BEHAVIOR**

| Action | Result |
|--------|--------|
| Post substantive message in #neyen-core | Message → WF-01 → Claude classification → Supabase insert → WF-02 cross-link → Dashboard update |
| Post short/operational message | Filtered out by WF-01, not ingested |
| Edit existing message | Not tracked (Slack Events API limitation) |
| Delete message | Not tracked |
| Thread reply | Can be configured separately with `message.threads` event |

---

## **TROUBLESHOOTING**

**Webhook not receiving messages:**
- Check Slack App → Event Subscriptions → Request URL is verified (green checkmark)
- Verify bot is in #neyen-core channel
- Check n8n WF-01 is active and webhook endpoint is correct

**Messages ingested but not appearing in dashboard:**
- Check Supabase metadata table — is entry inserted?
- Check WF-02 cross-linking — did it execute?
- Wait 5 minutes for dashboard auto-refresh, or manually refresh

**Duplicate entries:**
- Slack may retry failed webhooks — add deduplication logic in WF-01
- Use Slack `event_id` to check if already processed

---

## **FUTURE ENHANCEMENTS**
- **Thread support:** Track replies to specific entries
- **Reactions as signals:** Use 👍 to mark high-value content
- **@mentions:** Tag entries with specific people/roles
- **Slash commands:** `/neyen-add [content]` for manual ingestion

---

## **SECURITY NOTES**
- Slack webhook verification: Currently not implemented (acceptable for private workspace)
- For public-facing production: implement Slack signature verification using `X-Slack-Signature` header and the app's Signing Secret in WF-01
- Bot token (`xoxb-...`) must be stored securely in n8n credentials
- Webhook endpoint should use HTTPS (already true for Render)

---

## **IMPLEMENTATION CHECKLIST**
- [ ] Create Slack App with Event Subscriptions
- [ ] Configure OAuth scopes (channels:history, channels:read)
- [ ] Install app to workspace and add to #neyen-core
- [ ] Build WF-01 ingestion pipeline (Week 2)
- [ ] Configure Slack webhook → n8n endpoint
- [ ] Test with sample messages
- [ ] Verify end-to-end: Slack → Supabase → Dashboard
- [ ] Monitor for 48 hours, adjust filtering rules as needed

---

**Status:** Ready for implementation once WF-01 is built (Week 2, Day 1-3)
**Owner:** Ana Ballesteros Benavent, CSO
**Last updated:** March 2026
