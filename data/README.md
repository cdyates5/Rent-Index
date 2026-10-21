# data/

Optional. Save the BLS research workbook here as `r-cpi-ntr-and-r-cpi-atr.xlsx` and push.

Source: <https://www.bls.gov/cpi/research-series/r-cpi-ntr.htm> (download it in a browser; BLS blocks automated clients).

When present, `rebuild.py` calibrates the re-dating weight and the formula wedge on every mature published quarter instead of the six anchor prints, plots the full BLS series in the dashboard, and uses the workbook's new-tenant index in the lead-indicator panels. The push triggers a rebuild automatically.
