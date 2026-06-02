# Architecture

TODO (M1+): Expand this into the canonical architecture reference.

For now, the source of truth for system design is [PRD.md](PRD.md), specifically:

- Section 6: System Architecture and data flow.
- Section 7: Data Model.
- Section 12: Infrastructure (Railway services, background jobs, observability).
- Section 13: Repository Structure.

This file exists so the layout matches PRD section 13. It will be filled in as
the design solidifies past M0.

## LLM data handling (PRD 11.3)

The coach uses the **Anthropic Claude API** (Haiku 4.5 for daily chat/briefings; Sonnet
reserved for the weekly review in M3).

- **No training on our data.** Anthropic does not use API inputs/outputs to train models
  by default.
- **Retention:** the standard API retains inputs/outputs for a limited window (historically
  up to ~30 days) for trust-and-safety, then deletes them. **Zero-data-retention (ZDR) is
  NOT enabled** — it is a separate enterprise arrangement. The owner accepted the standard
  posture for this personal, two-person, non-HIPAA-covered deployment (2026-06).
- **What we send:** the coach context is the user's goals, an **aggregated** 7-day summary
  of `metric_sample` (counts/averages, not raw record dumps), and recent chat turns — not
  raw medical records.
- **Verify on change:** confirm Anthropic's current data-usage/retention terms before any
  change that widens what is sent (e.g. raw lab values, meal photos) or before onboarding
  additional users. Revisit ZDR if the data sensitivity increases.

Configured via `ANTHROPIC_API_KEY` (absent → a local stub coach, no network). The context
builder lives in `apps/api/src/health_api/coach/`.
