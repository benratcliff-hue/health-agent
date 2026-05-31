# Personal Health Agent

**Product Requirements Document**

Owner: Ben Ratcliff
Audience: Builder + AI coding agents
Status: Draft v0.2

## Revision History

**v0.1** — initial draft. Assumed a native Swift iOS companion app to access HealthKit, push notifications for briefings, and 6 to 10 weeks for MVP.

**v0.2** — this revision. Removed the custom iOS app from MVP scope in favor of Health Auto Export plus Apple Shortcuts. Locked FastAPI as the API language. Locked Procrastinate as the Postgres-backed job queue. Switched morning and evening briefings from push notifications to email. Revised M1 timeline to 3 to 5 weeks. Updated data flow, components, repo structure, and acceptance criteria accordingly.

> Note: the em dashes in the revision history above are the only ones intentionally kept in this document. Source of truth is the Google Doc / docx; this file is for in-repo reference.

---

## 1. Overview

Personal Health Agent is a two-person (initially: me and my wife) longitudinal health system. It ingests structured health data from wearables and apps, unstructured medical records, and daily user inputs like meal photos, and exposes a conversational coach plus scheduled briefings that help each user move toward their stated health goals.

The product is built for two specific users at the outset, but the architecture is multi-tenant from day one so additional users (children, parents, friends) can be added without a rewrite. The system runs on Railway, with a Postgres database, a FastAPI backend, a Next.js web app, and no custom mobile app. Apple HealthKit data is captured on iPhone via Health Auto Export (a third-party iOS app) and Apple Shortcuts, then pushed to the backend over HTTPS.

> **Honesty note:** This PRD is a starting point, not a contract. Cost estimates, third-party app capabilities (including Health Auto Export), and timeline numbers are best-effort and flagged where uncertain. Verify before committing to architecture.

## 2. Problem & Motivation

Health data today is fragmented. Apple Health holds rich sensor data but exposes it only on-device. Whoop holds strain and recovery in its own silo. Lab results sit in patient portals. Meals are tracked, if at all, in a third app with poor adherence. No tool ties these together for an individual, and even fewer support a household.

The result: I cannot easily answer questions like "how did my sleep last week correlate with my training load and what I ate?" or "is my fasting glucose trending in the right direction since I changed my breakfast?" A general-purpose LLM cannot answer these either, because it does not have the data.

This product solves three things:

- A single, queryable Postgres store of every relevant health signal for each member of the household.
- A conversational coach that has continuous context on goals, history, and recent data, and is cheap enough to chat with daily.
- A scheduled briefing loop (morning and evening) that pulls insights forward without requiring the user to ask.

## 3. Users & Personas

### 3.1 Primary users

Two adults sharing a household. Both own iPhones and Apple Watches. One (Ben) wears a Whoop. Both want to be healthier but have different goals, schedules, and preferences.

### 3.2 Persona A: Ben

- Goals: maintain body weight, improve VO2 max, hit consistent sleep, monitor a small set of biomarkers from annual labs.
- Devices: iPhone, Apple Watch, Whoop, smart scale (future).
- Daily inputs: meal photos (via Shortcut), occasional notes ("feeling fatigued", "long meeting day").
- Coaching style: data-forward, terse, willing to be challenged.

### 3.3 Persona B: Wife

- Goals: TBD. Likely a mix of fitness, energy, and longevity-oriented metrics. To be defined during onboarding flow.
- Devices: iPhone, Apple Watch.
- Daily inputs: meal photos, mood and energy notes.
- Coaching style: warmer, less data-heavy, more habit-oriented. Tone configurable per user.

> **Open question:** Wife should review this PRD and either confirm or override her persona, goals, and tone. Treat the current Persona B as a placeholder.

## 4. Goals & Non-Goals

### 4.1 Goals (what success looks like)

- Both users open the app or read a briefing at least once a day for 30 consecutive days post-launch.
- All Apple Health and Whoop data lands in Postgres within 2 hours of being recorded on device.
- Coach can answer a question grounded in the last 7 days of data with no manual prompting in under 5 seconds.
- Daily LLM cost per active user stays under approximately $1/day on average. Verify with actual usage.
- Each user can configure goals, coach tone, and notification cadence without touching code.

### 4.2 Non-goals (explicitly out of scope for MVP)

- Custom native iOS app for MVP. We use Health Auto Export plus Apple Shortcuts instead. A native app may be reconsidered post-V2.
- Replacing a doctor. The system surfaces patterns and prompts conversation, it does not diagnose.
- FDA-regulated medical claims or HIPAA-covered-entity status. Personal-use software, not a covered offering.
- Public sign-ups, marketing site, billing. Family-only deployment for at least the first year.
- Android support.
- Real-time CGM ingestion.
- Real-time push notifications. Briefings are delivered by email; chat is pull, not push.
- Social features, leaderboards, sharing outside the household.

## 5. Scope by Milestone

### 5.1 MVP (M1): Ingest + ask

Goal: one user (Ben) can log in, sync Apple Health and Whoop data, ask the coach questions in chat, and get morning and evening briefings via email.

- Auth (single user, email magic link).
- Per-user API key generated in the web app for HAE and Shortcuts to authenticate ingest calls.
- Health Auto Export configured on iPhone to push selected HealthKit data types to the backend on a schedule (default: hourly).
- Apple Shortcuts: at minimum a "Log meal" shortcut for photo upload; optionally a "Quick note" shortcut.
- Whoop OAuth, initial backfill (30 days), and webhooks for new data.
- Postgres schema for users, time-series metrics, daily summaries.
- Chat interface (web app, mobile-friendly Safari view) backed by Claude Haiku.
- Scheduled jobs: 6am briefing email, 8pm evening review email.

### 5.2 V1 (M2): Two users + meals

- Multi-user / household model; wife onboarded.
- Meal photo upload via Apple Shortcut from share sheet (or directly from the web app on iPhone); vision model estimates calories and macros.
- Shared household dashboard (combined view, not coach mixing).
- Per-user coach tone configuration.
- Goal definition flow in onboarding.

### 5.3 V2 (M3): Medical records + smart scale

- PDF lab report ingestion with extraction to structured biomarkers.
- Smart scale integration. Withings has an official API; verify before choosing the device.
- Weekly review email with trends and recommended adjustments.
- Annotated trend graphs in the chat surface.

### 5.4 Future (not committed)

- CGM (Dexcom or Libre) integration.
- Strength training program generation.
- Allowing the coach to schedule things into the user's calendar.
- Voice interface (Whisper transcription and TTS).
- Custom native iOS app if HAE or Shortcuts becomes a bottleneck.

## 6. System Architecture

High-level: an iPhone (running Health Auto Export and Apple Shortcuts) and a Next.js web app talk to a single backend API, which writes to Postgres and enqueues background jobs for ingestion and LLM calls. All compute and data live on Railway.

### 6.1 Components

- **iPhone setup (no custom code):** Health Auto Export configured to POST HealthKit data on a schedule; one or more Apple Shortcuts for meal photos and quick notes. Setup is documented per user in `docs/HAE-SETUP.md` and `docs/SHORTCUTS.md`.
- **Web App** (Next.js, deployed on Railway). Primary surface for dashboards, configuration, goal editing, history, and chat. Mobile-friendly so iPhone Safari is a fine daily driver. Optionally installed as a PWA.
- **Backend API** (single service, FastAPI / Python). Handles auth, ingest endpoints, chat (SSE streaming), briefings, API key management.
- **Worker service** (Python). Background jobs: nightly Whoop sync, HealthKit batch processing, meal-photo vision calls, briefing generation, email delivery.
- **Job queue:** Procrastinate (Postgres-backed) so we do not run a separate Redis. Verify it is actively maintained at build time.
- **Cron service.** Schedules briefings and periodic syncs. Railway cron jobs run as scheduled services with a 5-minute minimum interval.
- **Postgres** (Railway-managed).
- **Object storage** for meal photos and PDF labs. Cloudflare R2 preferred for cheaper egress; S3 is the fallback. Verify pricing before choosing.
- **Email delivery:** Resend or Postmark (pick one in M0). Used for magic links and morning/evening briefings.

### 6.2 Data flow

1. iPhone, hourly via Health Auto Export: HAE collects new HealthKit samples since its last successful sync and POSTs JSON to `/v1/ingest/healthkit` with the user's API key.
2. Whoop webhook hits `/v1/ingest/whoop/webhook`; worker fetches the new record via Whoop API and stores in DB.
3. User taps a "Log meal" Shortcut: photo is uploaded to `/v1/ingest/meal`; worker calls vision model; structured macros stored.
4. Cron 6:00 AM local time per user: worker pulls last 24h of data, generates briefing, sends email via Resend/Postmark.
5. User opens chat in web app: backend pulls last 7 days summary plus relevant history plus user goals, calls Claude Haiku with system prompt, streams response over SSE.

## 7. Data Model

All times stored as UTC. All measurements stored in metric SI units; presentation layer converts. Multi-tenant from day one via `household_id` and `user_id` on every row that holds personal data.

### 7.1 Core tables

| Table | Purpose | Notes |
|---|---|---|
| `household` | A shared unit of two or more users | id, name, timezone, created_at |
| `user` | An individual member | id, household_id, name, email, dob, sex, role, coach_tone, created_at |
| `api_key` | Per-user token for ingest endpoints (HAE, Shortcuts) | id, user_id, key_hash, label, scopes, last_used_at, created_at, revoked_at |
| `goal` | A user's stated health objective | id, user_id, type (weight/sleep/hr/biomarker/custom), target_value, target_date, active |
| `device` | A connected source | id, user_id, kind (apple_health_hae/whoop/scale/cgm), external_id, oauth_tokens (encrypted), last_sync_at |
| `metric_sample` | Time-series raw signal | id, user_id, source, metric_type, value_numeric, value_json, unit, recorded_at, ingested_at |
| `daily_summary` | Per-user-per-day rollup | user_id, date, sleep_score, strain, hrv, rhr, steps, kcal_in, kcal_out, weight, notes |
| `meal` | A logged meal | id, user_id, photo_url, eaten_at, kcal_est, protein_g, carbs_g, fat_g, items_json, source |
| `lab_report` | An ingested PDF | id, user_id, pdf_url, report_date, lab_name, status |
| `biomarker` | Extracted lab value | id, lab_report_id, user_id, name, value, unit, reference_low, reference_high, drawn_at |
| `conversation` | Chat thread | id, user_id, started_at, summary, last_message_at |
| `message` | Single chat message | id, conversation_id, role, content, tokens_in, tokens_out, model, created_at |
| `briefing` | Generated morning/evening report | id, user_id, kind, generated_at, content_md, delivered_at, delivery_channel (email) |
| `audit_log` | Mutations and LLM calls | id, user_id, action, payload_json, created_at |

### 7.2 Indexing notes

- `metric_sample`: composite index on `(user_id, metric_type, recorded_at desc)`. This is the hot path for the coach.
- `daily_summary`: primary key `(user_id, date)`. Cheap source of truth for last-N-days queries.
- `api_key`: index on `key_hash` for O(1) lookup at ingest time.
- Partition `metric_sample` by month if it gets large. Probably unnecessary for two users in year one.

### 7.3 Retention

- Raw `metric_sample`: keep forever. Cheap in Postgres at this volume.
- Meal photo originals: keep 90 days, then thumbnail-only.
- Chat messages: keep forever, with daily summaries written into `conversation.summary` for cheap recall.
- Briefing emails: keep the rendered markdown forever in DB; do not depend on the email provider for archive.

## 8. Integrations

### 8.1 Apple HealthKit via Health Auto Export

Health Auto Export (HAE) is a third-party iOS app that reads HealthKit on-device and exports selected data types to a destination of choice (REST endpoint, Dropbox, iCloud) on a schedule. We use the REST automation to push JSON to our backend. This replaces the custom Swift app that v0.1 of this PRD assumed.

**REST automation support confirmed by builder (2026-05-30).**

**Setup (per user, one-time):**

1. User installs Health Auto Export on iPhone and grants HealthKit permissions for the data types we care about.
2. In the web app settings, user generates a personal API key.
3. In HAE, user creates an automation: REST API destination, our `/v1/ingest/healthkit` URL, header `Authorization: Bearer <api_key>`, JSON format, frequency hourly (or as supported), data types per the list below.
4. User runs a test export to confirm the first batch lands.

**Data types in scope for MVP** (verify HAE supports each at current version):

- Steps, active energy, basal energy.
- Heart rate, resting heart rate, HRV.
- VO2 max.
- Sleep analysis (stages if available).
- Body mass (weight).
- Workouts.

**Backend handling:**

- Validate API key, identify user.
- Normalize HAE's JSON shape to our `metric_sample` schema.
- Idempotency: derive a stable key from `(user_id, metric_type, source_uuid_if_present, recorded_at)`. HAE's payload format varies by data type; verify the exact fields available and pick a deduplication strategy that survives reprocessing.
- On success, return 200 with a count of accepted samples; on partial failure, return 207 with per-sample status.

> **Verify before building:** Health Auto Export pricing (one-time purchase vs subscription for REST automations), supported data types at the current version, retry behavior on failed POSTs, and any rate limits.

**Risks specific to HAE:**

- Reliability of background scheduling on iOS. iOS can delay or skip background tasks. Mitigation: nightly catch-up sync expectation (assume gaps up to 24h are normal), and make ingestion idempotent.
- Vendor risk: HAE is one developer. If the app stops being maintained, we move to a different export tool or revisit a custom app. The ingest API is the abstraction boundary.
- Data shape changes between HAE versions. Mitigation: version the ingest payload schema and log unknown fields rather than rejecting.

### 8.2 Whoop

Whoop has an official developer API (v2 as of 2026) with OAuth 2.0 and webhooks. Free dev access; users must have an active Whoop membership.

- OAuth 2.0 flow on first connect; store refresh token encrypted at rest.
- On connect: fetch trailing 30 days of cycles, recoveries, sleeps, workouts.
- Subscribe to webhooks for new records; backend endpoint `/v1/ingest/whoop/webhook` validates signature, enqueues sync job.
- Nightly catch-up sync as a safety net in case webhooks miss anything.

### 8.3 Meal photo logging (vision)

User taps an Apple Shortcut on iPhone to log a meal. Two flows supported:

- **Capture flow:** Shortcut opens the camera, user snaps a photo, Shortcut POSTs to `/v1/ingest/meal` with API key.
- **Share flow:** from the Photos app share sheet, user picks the "Log meal" Shortcut to upload an existing photo.

**Backend:**

- Downscale image to ~1024px max edge.
- Call Claude vision model with a strict JSON schema (items, portion_estimates, kcal, protein, carbs, fat, confidence).
- Persist meal row; user sees estimate within seconds in the web app and can tap any field to correct.
- Corrections feed back into the user's profile to improve future estimates.

> **Cost note:** Vision calls are noticeably more expensive than text-only. Budget approximately $0.05 to $0.15 per meal photo as a rough estimate; verify with actual usage. Three meals/day times 2 users times 30 days is up to roughly $27/month worst case before any caching or batching.

### 8.4 Medical records (V2)

Users upload lab PDFs. A worker extracts biomarkers using a combination of PDF text extraction and an LLM pass to normalize names and units.

- Upload via web app drag-and-drop or iOS share extension via a Shortcut.
- Worker: pdfminer or similar for text, then Claude pass with structured output schema. Validate against a curated list of common biomarkers.
- Store both the PDF and the extracted structured rows in `biomarker` table.
- Coach can reference: "your last LDL was X on date Y, compared to Z a year ago".

## 9. AI / Coach Design

### 9.1 Coaching modes

Two complementary surfaces, both backed by the same prompt and context-building pipeline:

- **Chat:** user-initiated, in-the-moment Q&A. Streaming via SSE. Available on web (including iPhone Safari).
- **Scheduled briefings:** morning summary (6am local) and evening review (8pm local). Delivered by email with a markdown-friendly HTML template; the email links back into the web app for follow-up chat.

### 9.2 Model routing (lean on Haiku)

| Job | Default model | Reasoning |
|---|---|---|
| Daily chat coach | Claude Haiku | High call volume, mostly grounded in summaries already in DB. Haiku is fast and cheap. |
| Morning and evening briefings | Claude Haiku | Templated structure, low reasoning bar. Escalate to Sonnet only for weekly review. |
| Meal photo to macros | Claude Haiku (vision) | Verify Haiku vision quality on real meals during M1; escalate to Sonnet if accuracy is poor. |
| Weekly review | Claude Sonnet | Higher reasoning load, runs once/week per user, cost impact small. |
| Lab report extraction (V2) | Claude Sonnet | Accuracy matters; runs rarely (a few times/year per user). |

> **Cost estimate:** Rough estimate, verify with real usage: with Haiku for daily coach and briefings, two heavy users running ~30 chat turns/day each plus 2 briefings, the LLM bill should land somewhere in the $15 to $30/month range for text. Vision adds approximately $20 to $30/month if 3 meals/day times 2 users. Treat as a range, not a guarantee.

### 9.3 Context-building pipeline

Every coach call assembles its context the same way:

1. Load user profile (name, dob, goals, tone).
2. Load last 7 `daily_summary` rows.
3. Load any new `metric_sample` anomalies (z-score > 2 vs trailing 30 days).
4. Load conversation summary plus last 10 messages.
5. If the user message mentions a topic (sleep, weight, training), fetch the relevant slice (last 30 days of that metric).
6. Compose into a system prompt with explicit instructions on tone, refusals, and what to do when uncertain.

### 9.4 Coach safety rules

- Never diagnose. If the user describes symptoms suggesting something acute, redirect to a clinician.
- Never recommend a specific medication change.
- Always cite the data: if the coach says "your sleep is down", it shows the numbers.
- Flag uncertainty: when an inference is low-confidence, say so.

## 10. Multi-User & Household Model

Two-user system from day one, designed to expand. Each user has fully separate data, goals, and coach. A shared "household view" surfaces overlapping items (shared meals, joint workouts), but the coach never mixes voices across users.

### 10.1 Rules

- Every personal-data row has a `user_id`.
- Every user belongs to exactly one household at a time.
- Auth tokens are per-user. There is no shared login.
- Each user has their own API key for HAE and Shortcuts ingestion. Keys are revocable in web app settings.
- The shared dashboard reads from both users' summaries but only when both have opted in.
- A user can leave a household; their data goes with them.

### 10.2 Shared household view (V1)

- Combined weekly calendar (workouts, meal times).
- Shared meals: when both users log the same meal within 30 min, link them so corrections propagate.
- Household streaks (e.g., 5 nights in a row both sleeping more than 7h).

## 11. Auth, Privacy & Security

### 11.1 Auth

- Email magic-link login for humans (Resend or Postmark for delivery).
- Sessions backed by signed JWT in httpOnly cookie (web).
- Per-user API keys for machine ingest (HAE, Shortcuts). Generated in settings, displayed once, stored as a hash. Scoped to ingest endpoints only; cannot read data, cannot change settings.
- No passwords. No social login in MVP.

### 11.2 Encryption

- Postgres encrypted at rest (Railway default).
- OAuth refresh tokens and API key hashes use a pepper from Railway secrets. Rotate annually.
- Object storage with signed URLs only; no public buckets.

### 11.3 Privacy posture

- This is personal-use software for one household. Not a covered entity under HIPAA.
- No third-party analytics on health data screens.
- LLM calls go to the Anthropic API. Verify and document Anthropic's data retention and zero-retention options before sending PHI-equivalent data.
- Email briefings include summary data. Treat email provider as a data processor; choose one with reasonable security posture (Resend and Postmark both publish SOC 2 attestations at the time of writing; verify currency).

> **Verify:** Confirm Anthropic's current API data handling terms (retention, training opt-out, ZDR availability) and reflect the choice in the system. This is a build-time decision before the first ingest endpoint is live.

### 11.4 Backups

- Daily Postgres backup via Railway.
- Weekly logical dump to a separate cloud (e.g., B2 or R2) for off-platform redundancy.
- Annual restore test.

## 12. Infrastructure

### 12.1 Hosting

- Railway project with separate services: web, api, worker, cron, postgres.
- Environments: dev (laptop), staging (Railway), prod (Railway).
- Approximate Railway cost for a household-scale deployment: ~$25/mo plan fee plus compute. Total likely under $50/mo at MVP scale. Verify with usage.
- Alternatives considered: Render (similar PaaS), Fly.io (usage-based, cheap at our scale), Hetzner + Coolify (cheapest, most DIY), Vercel for the Next.js web only (not a fit for workers/cron). Decision: stay on Railway for MVP simplicity. Revisit if monthly cost crosses $75.

### 12.2 Background jobs

- Cron service runs scheduled jobs via Railway cron (5-minute minimum granularity, evaluated in UTC).
- Per-user briefings need timezone-aware scheduling: compute target UTC time per user, dispatch from a UTC cron that fires every 15 min and picks up due users.
- Worker uses Procrastinate (Postgres-backed queue). No Redis. Verify active maintenance before locking in.

### 12.3 Observability

- Structured JSON logs to stdout (Railway captures).
- Error tracking via Sentry.
- LLM call telemetry: log model, tokens in/out, latency, cost, prompt hash. Surface in an internal `/admin/llm-usage` page.
- Ingest telemetry: per-user counts of HAE batches received, samples accepted, samples rejected, last-seen-at. Surface in `/admin/ingest`.

## 13. Repository Structure

Monorepo on GitHub. Single repo simplifies cross-service refactors at this scale.

```
health-agent/
  apps/
    web/             # Next.js
    api/             # FastAPI
    worker/          # Procrastinate jobs
    cron/            # Scheduled task entrypoints
  packages/
    shared/          # Shared types, constants, prompt templates
    db/              # Migrations, SQLAlchemy models
  infra/
    railway/         # Railway service configs
    scripts/         # One-off ops scripts
  docs/
    PRD.md
    ARCHITECTURE.md
    PROMPTS.md
    HAE-SETUP.md     # Health Auto Export per-user setup guide
    SHORTCUTS.md     # Apple Shortcuts setup + sample shortcut links
  .github/
    workflows/       # CI: lint, test, deploy
  README.md
```

No `apps/ios/` directory. If we revisit a custom iOS app post-V2, add it then.

## 14. Milestones & Timeline

Timeline assumes part-time work (nights and weekends). Treat the week counts as planning estimates, not commitments. Numbers below are revised downward from v0.1 due to removing the custom iOS app.

| Milestone | Scope | Approx duration | Exit criteria |
|---|---|---|---|
| M0 | Repo, CI, Railway, hello-world web + api + Postgres | 1 to 2 weeks | Web app on Railway hits API hits DB end-to-end. |
| M1 (MVP) | Single-user. HAE + Shortcuts setup, Whoop, chat coach, email briefings. | 3 to 5 weeks | Ben uses the app daily for 14 consecutive days without intervention. |
| M2 (V1) | Two-user household, meal photos via Shortcut, shared dashboard. | 3 to 5 weeks | Wife onboarded; both users log meals daily for 14 days. |
| M3 (V2) | Lab PDF ingestion, smart scale, weekly review. | 3 to 4 weeks | One real lab PDF parsed correctly; weekly review delivered every Sunday. |

## 15. Acceptance Criteria (per milestone)

### 15.1 M0

- GitHub repo exists with the structure in section 13.
- CI runs lint and unit tests on PR.
- Railway has 4 services deployed: web, api, worker, postgres.
- A test endpoint `/healthz` returns 200 from production.
- A test write/read against Postgres succeeds from api.

### 15.2 M1 (MVP)

- User can generate, view (once), and revoke an API key in web app settings.
- Health Auto Export is configured on Ben's iPhone and is successfully POSTing batched HealthKit data to `/v1/ingest/healthkit` at least every 2 hours during the day. Verify with `/admin/ingest` dashboard.
- Apple Shortcut "Log meal" is installed on Ben's iPhone and successfully posts photos to `/v1/ingest/meal` (basic acceptance only; macros estimate in M2).
- Whoop OAuth completes; trailing 30 days backfilled within 10 min of connect.
- Whoop webhooks deliver new records to DB within 5 min of being available on Whoop.
- Chat in web returns a streamed response within 5s for a typical 7-day question.
- Morning briefing email arrives within 5 min of user's 6:00 AM local.
- Evening review email arrives within 5 min of user's 8:00 PM local.
- All metrics persisted: steps, HR, RHR, HRV, sleep, workouts, weight (if recorded), Whoop strain/recovery/sleep.

### 15.3 M2 (V1)

- Wife can sign in via magic link and complete onboarding (goals, tone).
- Wife's HAE and Shortcuts are set up and pushing data.
- Meal photo upload via Shortcut returns structured macros visible in the web app within 30s.
- Shared household dashboard shows both users' last 7 days side-by-side.
- Each user's coach uses that user's configured tone.

### 15.4 M3 (V2)

- Lab PDF upload extracts at least 80% of biomarkers correctly on a test set of at least 3 real lab reports.
- Smart scale weight ingestion lands in `metric_sample` within 1 hour of stepping on scale.
- Weekly review email lands Sunday morning.

## 16. Open Questions & Risks

### 16.1 Open questions

- Email provider: Resend or Postmark. Both fine; pick one in M0 based on free-tier limits at the time.
- Should we also support Web Push (PWA on iOS 16.4+) for chat-style nudges, on top of email briefings? Behavior on iOS is reportedly improving but still less reliable than native push. Verify before committing.
- Smart scale brand for M3. Withings is the default candidate; verify API access and reliability.
- Wife's actual goals and coach tone preference.
- Where do we store and rotate OAuth keys? Railway secrets is fine for MVP; revisit for V2.
- Should email briefings include the actual numbers or only the narrative summary? Numbers are more useful, but also more sensitive if forwarded.

### 16.2 Locked decisions (no longer open)

- No custom native iOS app in MVP. Health Auto Export + Apple Shortcuts.
- API language: FastAPI (Python).
- Background job queue: Procrastinate (Postgres-backed).
- Briefing delivery: email.
- Hosting: Railway.

### 16.3 Risks

- Health Auto Export reliability and vendor risk. Mitigation: idempotent ingest design, log gaps, treat HAE as replaceable behind a stable API.
- iOS background scheduling delays HAE syncs. Mitigation: tolerate gaps; do not promise real-time freshness; verify daily that something arrived.
- Coach feels generic. Mitigation: invest in tone configuration and in data-grounded responses (always cite numbers).
- LLM cost overshoot. Mitigation: cost telemetry from day one; alert if a user's monthly cost exceeds $40.
- Whoop API rate limits. Mitigation: webhook-first design; only poll as a nightly safety net.
- Email deliverability (inbox vs spam) hurts briefing engagement. Mitigation: SPF/DKIM/DMARC set up on day one; send from a real domain not a shared one.
- Single-developer bus factor. Mitigation: comments and docs in repo; PRD kept current.

## 17. Glossary

- **HAE:** Health Auto Export, the third-party iOS app we use to push HealthKit data to our backend.
- **HRV:** Heart Rate Variability. Measure of variation in time between heartbeats; proxy for autonomic balance and recovery.
- **RHR:** Resting Heart Rate.
- **VO2 max:** Maximal oxygen uptake during exercise; proxy for cardio fitness.
- **Strain (Whoop):** Whoop's daily cardiovascular load metric, scale 0 to 21.
- **Recovery (Whoop):** Whoop's daily readiness score, scale 0 to 100%.
- **Daily summary:** Per-user, per-day pre-aggregated row used to keep coach calls cheap.
- **Household:** A unit of one or more users who share a coach surface and a dashboard.

## 18. Appendix A: Starter System Prompt

Used as the base for the daily chat coach. Treat as a starting point; iterate weekly.

```
You are {USER_NAME}'s personal health coach.

Your job:
- Help {USER_NAME} make progress on their stated goals.
- Be specific. Always cite the numbers when you reference data.
- Be honest about uncertainty. If you don't have data for something, say so.
- Keep responses short by default. Expand only when asked.

Tone: {USER_TONE}.

Hard rules:
- Never diagnose a medical condition.
- Never recommend a specific medication change.
- If {USER_NAME} describes symptoms suggesting something acute (chest pain, severe shortness of breath, sudden neuro symptoms), tell them to seek medical care.
- If asked something outside health/fitness/nutrition, politely redirect.

Available context:
- Goals: {GOALS_JSON}
- Last 7 days daily_summary: {DAILY_SUMMARIES_JSON}
- Recent anomalies: {ANOMALIES_JSON}
- Conversation so far: {CONVERSATION_SUMMARY}

Respond to the user's message below.
```

## 19. Appendix B: API Endpoint Sketch (MVP)

| Method + Path | Purpose |
|---|---|
| `POST /auth/magic-link` | Send magic link email |
| `GET /auth/callback` | Complete magic-link login |
| `POST /v1/api-keys` | Create a new ingest API key (returns plaintext once) |
| `GET /v1/api-keys` | List existing keys (metadata only) |
| `DELETE /v1/api-keys/{id}` | Revoke an API key |
| `POST /v1/ingest/healthkit` | Receive batched HealthKit samples from Health Auto Export |
| `POST /v1/ingest/whoop/webhook` | Receive Whoop webhook |
| `POST /v1/ingest/meal` | Upload a meal photo (from Shortcut or web) |
| `GET /v1/me` | Current user profile and goals |
| `PATCH /v1/me/goals` | Update goals |
| `GET /v1/summary?days=7` | Daily summaries |
| `POST /v1/chat` | Send chat message; returns SSE stream |
| `GET /v1/briefings?date=...` | Retrieve a generated briefing |
| `GET /healthz` | Service liveness |

## 20. Appendix C: Health Auto Export Setup (one-time)

This appendix is the canonical setup checklist that will be expanded into `docs/HAE-SETUP.md` in the repo. The exact UI labels in Health Auto Export may change; treat steps as guidance, not verbatim.

1. Install Health Auto Export from the App Store on the user's iPhone.
2. Open the app and grant HealthKit read permissions for all data types listed in section 8.1.
3. In our web app, go to Settings, Ingest API Keys, create a new key labeled "iPhone HAE". Copy the key (shown only once).
4. In Health Auto Export, create a new automation: destination = REST API, URL = `https://<api-domain>/v1/ingest/healthkit`, method = POST, headers include `Authorization: Bearer <key>`, format = JSON, frequency = hourly.
5. Select data types matching section 8.1.
6. Run one manual export and confirm a 200 response and a non-zero count in `/admin/ingest`.
7. Enable the schedule.

If a step does not match the current Health Auto Export UI, take screenshots and update `docs/HAE-SETUP.md`.

---

*End of document. Draft v0.2. Update freely.*
