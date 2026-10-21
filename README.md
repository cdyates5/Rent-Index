# Acheron All-Tenant Rent Index (A-ATRI)

A synthetic continuation of the BLS research index **R-CPI-ATR** (all tenant regressed rent), whose publication BLS paused in April 2026. The index is rebuilt from public CPI rent data by inverting the CPI estimator and re-dating rent changes to the month they were set. It is extended with Zillow new-lease rents for the nowcast and forecast. The method is documented in the dashboard's own Method section.

GitHub Actions checks the data sources several times a day. It rebuilds and redeploys only when something has changed: a new CPI print, a new ZORI month, a new or committed BLS workbook, or a code change. A run deploys only if the strict sanity gate and the headless render check both pass.

```
.
├── rebuild.py                      # data fetch + model + single-file HTML (template embedded)
├── probe.py                        # stdlib-only release check: fingerprints each input, decides whether to rebuild
├── requirements.txt                # pinned: numpy, pandas, openpyxl, playwright
├── tests/check_render.py           # headless Chromium: zero console errors, 9 charts, no mobile overflow, no NaN leaks
├── .github/workflows/refresh.yml   # schedule -> probe -> build -> render check -> commit state -> deploy
├── .github/dependabot.yml          # monthly PRs for GitHub Action version bumps
├── data/                           # optional: drop the BLS R-CPI-NTR/ATR workbook here (see data/README.md)
└── state/                          # committed by the bot: input fingerprints, real-time vintages, headline log
```

Each deploy publishes `site/` with `index.html` (the dashboard), `latest.json` (headline readings), `acheron_atri_quarterly.csv` and `.nojekyll`.

---

## 1. Decide who should see it (do this first)

**A GitHub Pages site is public on the internet even when the repository is private.** The one exception is an organisation on GitHub Enterprise Cloud with Pages visibility set to private. Pages from a private repository also needs a paid plan: Pro for a personal account, Team or Enterprise for an organisation.

| Option | Who can see it | Set up |
|---|---|---|
| **A. Private Pages** (Enterprise Cloud org) | Only people with read access to the repo | Private repo; Pages source *GitHub Actions*; Settings → Pages → Visibility: *Private* |
| **B. Artifact only** (any plan) | Only repo members, by downloading the run artifact | Private repo; repository variable `DEPLOY_TARGET` = `artifact`; skip Pages |
| **C. Public Pages** | Anyone with the URL | Any repo; Pages source *GitHub Actions* |

All inputs are public data, but the construction is Acheron research. Pick A or B unless you intend to publish it.

## 2. One-time setup (about 10 minutes)

1. **Create the repository** (private for options A and B) and push these files to `main`:
   ```bash
   git init -b main
   git add .
   git commit -m "A-ATRI dashboard"
   git remote add origin git@github.com:<owner>/<repo>.git
   git push -u origin main
   ```
2. **Secrets.** Settings → Secrets and variables → Actions → *New repository secret*:

   | Secret | Needed? | What it does |
   |---|---|---|
   | `BLS_API_KEY` | Strongly recommended | BLS API v2 key (free: <https://data.bls.gov/registrationEngine/>). Without it, runs share the anonymous daily quota with every other GitHub runner on the same IP and often fail the gate. |
   | `FRED_API_KEY` | Recommended | Fallback CPI source (free: <https://fred.stlouisfed.org/docs/api/api_key.html>). With both keys set, one outage cannot stop a refresh. |
   | `BLS_CONTACT_EMAIL` | Recommended | Your work email, sent in the User-Agent to www.bls.gov, which blocks anonymous clients. It gives the BLS workbook download a chance to work. |

3. **Workflow permissions.** Settings → Actions → General → *Workflow permissions*: **Read and write permissions**. The bot commits `state/` after each rebuild.
4. **Pages (options A and C).** Settings → Pages → *Build and deployment* → Source: **GitHub Actions**.
   **Artifact only (option B).** Settings → Secrets and variables → Actions → *Variables* → `DEPLOY_TARGET` = `artifact`.
5. **First run.** Actions → *Refresh A-ATRI* → **Run workflow** (tick *force*). The first build takes about 4 minutes, including the Chromium install for the render check.
6. **Open it.** The run's *deploy* job shows the Pages URL. The run summary shows the headline nowcast and forecast.

## 3. How "refresh when new data is released" works

GitHub cannot be notified by BLS or Zillow, so the workflow polls on a schedule and decides cheaply whether anything is new.

| Schedule (UTC) | Why |
|---|---|
| 13:17 Mon–Fri | 45 min after the 08:30 ET CPI release during US daylight time |
| 14:17 Mon–Fri | Same, during US standard time |
| 22:43 daily | Catches Zillow's ZORI update (mid-month, no fixed time) and any missed release |

Each run starts with `probe.py`. It fingerprints the latest CPI rent month and value, the latest ZORI month and value, the BLS workbook hash, and the `rebuild.py` hash, then compares them with `state/state.json`.

- **Nothing new:** the run ends in about 15 seconds with nothing installed. That is about 70 short runs a month.
- **Something new:** full rebuild in strict mode, then the render check, a commit of the new fingerprints and vintage to `state/`, and a deploy. A new CPI print usually reaches the live page within one to two hours of release (GitHub sometimes starts scheduled runs late).
- **Unreachable source:** it never triggers a rebuild by itself. Its previous fingerprint is kept, so a flaky source cannot cause flapping.
- **A failed build:** nothing is deployed or committed, so the next scheduled run retries automatically.

You can also trigger a rebuild manually with the *force* box, or by pushing a change to `rebuild.py`, `probe.py`, `data/`, `tests/`, `requirements.txt` or the workflow.

## 4. The strict sanity gate

`rebuild.py --strict` writes nothing and exits with code 2 unless all of these hold:

- CPI rent came from a live API (BLS API v2 or FRED), not the embedded snapshot.
- ZORI came from Zillow's live file.
- The latest CPI month is no older than the embedded snapshot and less than 75 days old.
- All nowcast and forecast values exist and lie between −5% and 15% y/y.
- At least 90 estimated quarters exist.
- The backtest and calibration exist.

The render check then blocks deployment on any console error, a missing chart, horizontal overflow at phone width, or `NaN`/`undefined` in visible text.

## 5. What the bot commits to `state/`

- `state.json`: the input fingerprints and headline of the last good build.
- `vintages/atri_cpiYYYY-MM_zYYYY-MM.csv`: the full quarterly table as it stood after each data release. These are real-time vintages, so you can study how the nowcast revises.
- `headline_log.csv`: one row per build with as-of dates, sources, calibration mode, nowcast, forecast and implied CPI rent.

These monthly commits also count as repository activity, which keeps the schedule alive.

## 6. When BLS resumes R-CPI-ATR, or you have the workbook

The model calibrates to six published BLS prints unless it can read the BLS workbook, in which case it re-estimates the re-dating weight and wedge on every mature quarter.

- **Commit the file:** save `r-cpi-ntr-and-r-cpi-atr.xlsx` into `data/` and push. The push triggers a rebuild, and the Validation section switches to the full series.
- **Automatic:** each probe also tries to download the workbook from bls.gov using `BLS_CONTACT_EMAIL`. If BLS resumes publication and allows the download, a new quarter changes the hash and triggers a rebuild. The KPI tile then switches from *Paused* to the latest BLS print.

The workbook parser looks for a quarter column and an index-level column labelled ATR or "all tenant". If BLS changes the layout and parsing fails, the build logs the reason and falls back to the anchors rather than failing.

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Run fails at *Rebuild*: "SANITY GATE FAILED … not a live API" | No API key, or the anonymous BLS quota was exhausted | Add `BLS_API_KEY` and `FRED_API_KEY` |
| Probe shows `bls_atr unavailable … 403` | www.bls.gov blocks datacenter clients | Expected while BLS is paused; commit the workbook to `data/` instead |
| *Commit* step fails with 403 or "protected branch" | Workflow permissions are read-only, or branch protection blocks the bot | Set *Read and write permissions*; allow `github-actions[bot]` to push to `main` |
| Pages URL returns 404 | Pages source not set to *GitHub Actions* | Settings → Pages → Source: GitHub Actions; re-run with *force* |
| Render check fails with `requestfailed` on cdnjs or Google Fonts | A CDN blip on the runner | Re-run the workflow |
| Schedule stopped running | GitHub disables schedules after 60 days without repo activity (public repos) | Actions → *Refresh A-ATRI* → *Enable workflow*; the monthly state commits normally prevent this |
| CPI released but the page did not change | GitHub cron can start late, or the API had not updated yet | The next scheduled run catches it; or run with *force* |

## 8. Running locally

```bash
pip install -r requirements.txt
export BLS_API_KEY=...          # or FRED_API_KEY=...
python probe.py check           # what's new since the last committed state
python rebuild.py --out site --html-name index.html --standalone --strict
python -m playwright install chromium && python tests/check_render.py site/index.html
```

Without keys, `python rebuild.py` (no `--strict`) still builds from the embedded snapshot and public mirrors, which is useful for working on the page.

## Notes

- The Claude artifact version of this dashboard is a snapshot. The Pages URL is the live one.
- The October 2025 shutdown handling is coded explicitly: October is unobserved and April 2026 uses a twelve-month kernel. The implied-CPI section accounts for the base effect this creates in published prints from November 2026 to March 2027.
- The probe's BLS API path was verified live during development. The full-history BLS and FRED fetch paths could not be exercised from the build sandbox (shared quota, no FRED key), so the first Actions run is their first live test; the gate will stop a bad build there.
