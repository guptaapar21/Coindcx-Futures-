## Overnight operating note

The active Futures pipeline is operator-controlled and event-driven. With the default configuration, collection runs in independent **120-minute (2-hour) batches** when chaining is enabled.

At the successful end of each raw batch:

1. the completed raw Futures artifact is handed immediately to the batch-processing workflow;
2. processing builds the Futures 1s/1m/3m research data and runs strategy research plus the Futures Hypothesis Engine;
3. the next 120-minute collector batch is started independently when chaining remains enabled.

There is no GitHub Actions cron collector and no GitHub supervisor/watchdog workflow. Any external monitoring remains outside this repository. A collector success is therefore not, by itself, an end-to-end processing acceptance; the corresponding processor run must also succeed.
