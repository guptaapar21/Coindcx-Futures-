# Overnight operations plan

The Futures collector uses 120-minute (2-hour) independent batches by default. When chaining is enabled, each successfully uploaded raw batch immediately dispatches its own processing/research run and starts the next 120-minute collector batch.

Processing remains independent from acquisition, so feature construction, strategy research and the Futures Hypothesis Engine do not block the next collection cycle. There is no GitHub overnight supervisor workflow; storage housekeeping remains an independent scheduled maintenance job, and external supervision is handled outside GitHub.
