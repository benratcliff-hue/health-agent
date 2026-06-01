# Health Auto Export (HAE) Setup

How to push iPhone HealthKit data to the backend via Health Auto Export's REST API
automation. One-time, per user. UI labels in HAE change between versions; treat steps as
guidance and adapt.

## Endpoints

- **Ingest URL:** `https://health-agent-production-5a13.up.railway.app/v1/ingest/healthkit`
  (HAE posts directly to the api with a Bearer key — no browser, no proxy.)
- **Auth header:** `Authorization: Bearer <your-ingest-key>`

## 1. Create an ingest API key

1. Sign in to the web app and open **Settings → Ingest API keys** (`/settings/keys`).
2. Create a key labeled e.g. `iPhone HAE`. **Copy it immediately** — it is shown once.

## 2. Install and grant permissions

1. Install **Health Auto Export - JSON+CSV** from the App Store.
2. Open it and grant HealthKit **read** access for the data types below (it may prompt on
   first export, or via the iOS Health app → Sharing → Apps).

## 3. Create a REST API automation

In HAE's **Automations** tab, add an automation:

- **Format:** JSON
- **Destination / type:** REST API
- **URL:** the ingest URL above
- **Method:** `POST`
- **Headers:** `Authorization: Bearer <your-ingest-key>`
- **Schedule:** hourly (the backend is idempotent, so overlapping/retried windows are
  safe — duplicates are skipped).

## 4. Select data types (MVP, per PRD 8.1)

Steps, active energy, basal energy, heart rate, resting heart rate, HRV, VO2 max, sleep
analysis, body mass (weight), workouts.

## 5. Test

1. Run a manual export. A success looks like HTTP `200` with a body like
   `{"accepted": <n>, "skipped": <m>}`.
2. `accepted` counts new samples stored; `skipped` counts duplicates already present
   (expected on repeated/overlapping exports).
3. Enable the schedule.

## Notes

- iOS may delay or skip background tasks, so gaps of up to ~24h are normal; the schedule
  catches up and ingestion is idempotent (PRD 8.1 risks).
- The backend keeps the raw sample JSON in `metric_sample.value_json` and a representative
  number in `value_numeric`, so unfamiliar HAE shapes are stored rather than rejected.
- If a step does not match HAE's current UI, screenshot it and we will update this guide.
