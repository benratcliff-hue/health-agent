"""Background task name constants.

Shared so the api can enqueue a job by name (`App.configure_task`) without importing the
worker's task code, and the worker registers tasks under the same names.
"""

WHOOP_BACKFILL = "whoop_backfill"
WHOOP_SYNC = "whoop_sync"
BRIEFING_GENERATE = "generate_briefing"
