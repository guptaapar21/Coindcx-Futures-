# Legacy supervisor note

This file is retained only as historical documentation of an earlier operating concept. It is **not part of the active Futures pipeline**.

The active repository uses:

- an operator-controlled Futures collector;
- 120-minute (2-hour) default batches when chaining is enabled;
- event-driven processing immediately after each successful raw batch;
- the Futures strategy-research and Hypothesis Engine stages inside batch processing;
- repository-local storage housekeeping; and
- research-integrity checks.

There is no `nightly-supervisor.yml` workflow, no GitHub supervisor/watchdog, and no scheduled collector. External monitoring, if used, is outside this repository.

The historical supervisor design must not be used to infer the current collection or processing cadence.
