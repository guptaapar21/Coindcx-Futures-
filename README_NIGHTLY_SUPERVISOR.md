# Nightly supervisor

This repository uses an independent scheduled collector, an event-driven processor, and a five-slot overnight supervisor. The supervisor checks workflow registration, recent collector/processor/housekeeping health, and raw-batch-to-processing continuity. It can directly dispatch processing for a successful raw batch that lacks a processor run.
