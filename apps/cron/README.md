# cron

TODO (M1): Scheduled task entrypoints.

Per PRD section 12.2, a Railway cron service fires on a fixed UTC interval (15 min)
and enqueues due per-user jobs (6am briefing, 8pm review, nightly Whoop catch-up)
onto the Procrastinate queue handled by [apps/worker](../worker).

Placeholder only in M0. M0's exit criteria name four deployed services
(web, api, worker, postgres); cron is deployed in M1 when there is work to schedule.
