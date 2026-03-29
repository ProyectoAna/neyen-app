# CHANGELOG
All notable changes to the NEYĒN system will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---
## [Unreleased]

### Planned for Week 2 (Ingestion Pipeline)

**WF-01 Auto-Classification:**
- Accept raw content from Slack, Telegram, manual input
- Claude API classification (tags, entities, summary, narrative_role)
- Auto-insert to Supabase metadata table
- Trigger WF-02 cross-linking on insert

**Integration Testing:**
- Slack #neyen-core → WF-01 → Supabase → Dashboard
- Telegram voice notes → transcription → WF-01 → Supabase
- End-to-end verification (message → dashboard update <5min)

### Planned for Week 3 (Timeline Engine)

**WF-04 Temporal Clustering:**
- Analyze date_estimated field across all entries
- Create temporal clusters: 1974-1990, 2019-2023, 2024-2026
- Assign timeline_group automatically
- Dashboard timeline view visualization

**Narrative Arc Detection:**
- Identify progression patterns (setup → exploration → conflict → realisation → integration)
- Auto-tag narrative phases
- Highlight evolution from DINIBA origin → current execution

### Backlog

**API Query Interface (Implementation):**
- GET /api/query?category=pilot
- GET /api/query?tag=E'A
- GET /api/entry/{uuid} (expanded relations)
- Pagination support (limit, offset)
- Authentication for write endpoints

**Monitoring & Analytics:**
- UptimeRobot integration (keep endpoint warm)
- Supabase performance metrics
- Dashboard usage analytics
- Cross-link quality scoring

**Additional Integrations:**
- Google Drive → WF-01 (new files auto-ingest)
- Telegram bot enhancements (inline commands)
- Webhook for external system notifications

---

## Version History

**[1.0.0]** - 2026-03-29 — Phase 4 complete, Phase 5 Week 1 delivered  
**[0.4.0]** - 2026-03-28 — Cross-linking engine operational  
**[0.3.0]** - 2026-03-27 — Dashboard deployed, endpoint live  
**[0.2.0]** - 2026-03-26 — Supabase backend established  
**[0.1.0]** - 2026-03-25 — Initial system architecture defined

---

**Maintained by:** Ana Ballesteros Benavent, CSO, The Spiral Within SLU  
**Repository:** https://github.com/ProyectoAna/neyen-app  
**Live System:** https://neyen.thespiralwithin.ai/system.html

💙🐎🔥

---
## [1.0.0] - 2026-03-29

### Added

**Phase 4 Complete — System Externalized:**
- 17 metadata entries spanning 1974-present timeline
- 16/17 entries cross-linked via automated scoring algorithm
- Live dashboard at https://neyen.thespiralwithin.ai/system.html
- About page at https://neyen.thespiralwithin.ai/about.html
- Public JSON endpoint at https://n8n-docker-t9sr.onrender.com/webhook/system

**Infrastructure:**
- Supabase PostgreSQL backend with 5 core tables
- n8n workflow automation (WF-00, WF-02, WF-03)
- Row-Level Security (RLS) policies on all tables
- Real-time subscriptions enabled
- Automated cross-linking engine (tags×3 + entities×2 + role×1 scoring)

**Verified Entries:**
- TSW_origin_diniba (DINIBA founding 1974, "no romper" philosophy)
- TSW_pilot_helios (Colegio Elios, 4-year education plan, 2022-2026)
- TSW_pilot_xmas (Spiral Xmas v0.3, Nov 2024)
- TSW_pilot_paterna (Case Study 0004)
- TSW_libro_0 (Amazon Kindle, ISBN 9798251590173)
- TSW_trademark (EUIPO 019288972)
- TSW_company (TSW SLU, Valencia/Sedaví)
- Plus 10 foundational entries (symbols, systems, frameworks)

**Documentation:**
- docs/FRONTEND.md — Vue 3 PWA architecture
- docs/DATABASE-SCHEMA.md — PostgreSQL schema + RLS policies
- docs/API-ENDPOINTS.md — Query interface specification
- docs/DEMO-SCRIPT.md — 5-minute client presentation
- docs/SLACK-INTEGRATION-SETUP.md — Auto-ingestion architecture
- docs/DEPLOYMENT.md — CI/CD pipeline guide
- README.md — System overview and quick start