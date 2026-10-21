# state/

Written by the refresh workflow after each successful rebuild. Do not edit by hand.

- `state.json`: input fingerprints (CPI, ZORI, BLS workbook, code) and the headline of the last good build. `probe.py` compares against it to decide whether to rebuild. Delete it to force a full rebuild on the next run.
- `vintages/`: the quarterly table after each data release (real-time vintages of A-ATRI).
- `headline_log.csv`: one row per build.
