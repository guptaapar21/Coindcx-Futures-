## Overnight runbook
The collector is independent from processing. Raw Futures artifacts must be followed by a processor run. Five scheduled supervisor checks cover the overnight period. The supervisor records failures in workflow logs rather than allowing a green collector to imply an end-to-end success.
