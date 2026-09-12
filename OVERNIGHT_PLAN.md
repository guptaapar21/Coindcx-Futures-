# Overnight operating plan

The active Futures acquisition model is continuous, operator-controlled chaining rather than a scheduled GitHub supervisor.

## Default cadence

- Each collector batch runs for **120 minutes (2 hours)** by default.
- After a successful raw upload, the completed batch immediately dispatches its processing workflow.
- At the same point, when chaining is enabled, the next 120-minute collector batch is dispatched.
- Collection and processing therefore proceed independently and may overlap.

## Health responsibility

The repository does not contain a GitHub supervisor/watchdog workflow. GitHub Actions provides the collector, event-driven processor, storage housekeeping, and research-integrity workflows. Any external overnight supervision remains outside the repository.

## Acceptance

A completed collector batch is not considered fully processed until the corresponding `coindcx-process-batch` run has successfully received the exact raw artifact and completed the Futures feature, strategy-research, hypothesis-engine, compact-history, and storage steps.
