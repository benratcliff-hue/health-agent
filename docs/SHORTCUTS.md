# Apple Shortcuts Setup

Per-user iPhone setup for logging meals (and quick notes) without a custom app. The
Shortcut POSTs directly to the **api** service using an ingest **API key** (Bearer auth),
not the web app — so it does not use the login cookie.

## Prerequisites

1. **An ingest API key.** In the web app, go to **Settings → Manage ingest API keys**
   (`/settings/keys`), create a key (e.g. label "iPhone Shortcut"), and copy it. The
   plaintext is shown once. The same key works for both HAE and the meal Shortcut.
2. **The api base URL.** This is the api service's public URL, not the web URL. Current
   value: `https://health-agent-production-5a13.up.railway.app`. The meal endpoint is:

   ```
   POST https://health-agent-production-5a13.up.railway.app/v1/ingest/meal
   ```

## What the endpoint expects

`POST /v1/ingest/meal`, `multipart/form-data`:

| Field | Required | Notes |
|---|---|---|
| `file` | yes | The photo. Must be an image (`image/*`). Max 15 MB. |
| `note` | no | Free text, e.g. "chicken & rice". |
| `eaten_at` | no | ISO-8601 timestamp. Defaults to now if omitted. |

Header: `Authorization: Bearer <your api key>`. Returns `201` with the meal JSON.

> M1 is basic acceptance: the photo is stored and a meal row is created. Calorie/macro
> estimates (the `kcal_est` / `protein_g` / ... fields) are filled by the M2 vision job and
> are null until then.

## "Log meal" Shortcut

Build this once in the **Shortcuts** app. It supports both the capture flow (open camera)
and the share-sheet flow (share an existing photo into it).

1. New Shortcut, name it **Log meal**.
2. Turn on **Show in Share Sheet** (Shortcut details / the ⓘ tab) and set **Accept** to
   **Images**. This enables the share-sheet flow from Photos.
3. Add action **If** → condition: **Shortcut Input** **has any value**.
   - **If there is input** (share-sheet flow): use **Shortcut Input** as the photo.
   - **Otherwise** (run directly): add **Take Photo** (set "Show Camera Preview" on), and
     use its result as the photo.
   - Simplest robust pattern: add a **Take Photo** action and a separate share-sheet copy,
     or use the If/Otherwise above to pick the photo into a variable named `Photo`.
4. (Optional) Add **Ask for Input** (Text, prompt "Note?") → variable `Note`. Allow empty.
5. Add **Get Contents of URL**:
   - **URL:** `https://health-agent-production-5a13.up.railway.app/v1/ingest/meal`
   - **Method:** `POST`
   - **Headers:** add `Authorization` = `Bearer <paste your api key>`
   - **Request Body:** **Form**
     - Add field, type **File**, key **`file`**, value = your `Photo` variable.
     - (Optional) Add field, type **Text**, key **`note`**, value = your `Note` variable.
6. (Optional) Add **Show Notification** with the result so you get a confirmation.

### Using it

- **From the camera:** run the Shortcut (Home Screen icon, "Hey Siri, Log meal", or the
  widget). It snaps a photo and uploads.
- **From the share sheet:** in Photos, pick a meal photo → Share → **Log meal**.

Confirm it worked by opening **`/meals`** in the web app; the photo should appear in the
Recent grid within a few seconds.

## "Quick note" Shortcut (optional)

A text-only note has no endpoint yet (notes ride along on a meal via the `note` field).
A dedicated `/v1/ingest/note` endpoint is future scope; for now, attach context to a meal.

## Troubleshooting

- **401 Unauthorized:** the `Authorization` header is missing/wrong, or the key was
  revoked. Re-check the header is exactly `Bearer <key>` and the key is active in
  `/settings/keys`.
- **400 "file must be an image":** the Form field key must be exactly `file` and its type
  **File** (not Text), holding an actual image.
- **413 "photo too large":** the image exceeds 15 MB; rare for phone photos.
- **Nothing in `/meals`:** confirm the URL points at the **api** domain (not the web
  domain) and that the request returned `201`.
