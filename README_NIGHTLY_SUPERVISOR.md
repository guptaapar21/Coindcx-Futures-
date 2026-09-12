# Nightly health supervision note

This file is retained as an operational note, but the repository does **not** contain a GitHub supervisor or watchdog workflow.

The current Futures pipeline uses a 120-minute (2-hour) default collector batch, event-driven processing, and independent scheduled storage housekeeping. After each successful raw upload, the completed batch is dispatched for processing while the next collector cycle is started when chaining is enabled.

`tools/nightly_health.py` is a manual health-check utility; it is not an always-on supervisor and does not schedule collection or research.
