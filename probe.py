#!/usr/bin/env python3
"""
probe.py - cheap release check for the A-ATRI refresh workflow (standard library only).

Fingerprints each input without downloading full histories:
  cpi        latest month and value of CPI rent of primary residence (CUUR0000SEHA)
             via BLS API v2 (latest=true), falling back to the FRED API
  zori       latest month and value of Zillow's national ZORI
  bls_atr    hash of the BLS R-CPI-NTR/ATR workbook: a committed copy in data/ wins,
             otherwise a download attempt (www.bls.gov blocks clients without a contact UA)
  code       hash of rebuild.py, so a code change forces a rebuild

  python probe.py check    compare with state/state.json, write state/pending.json,
                           emit changed=true|false and reason=... to $GITHUB_OUTPUT
  python probe.py commit   promote state/pending.json to state/state.json after a good build

A source that cannot be reached is reported as unavailable and never triggers a rebuild on its
own; its previous fingerprint is carried forward so it does not flap. FORCE=true forces a rebuild.
"""
import csv
import datetime as dt
import glob
import hashlib
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state", "state.json")
PENDING = os.path.join(HERE, "state", "pending.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
UNAVAILABLE = "unavailable"


def get(url, data=None, headers=None, timeout=40):
    ua = UA
    if "bls.gov" in url and os.environ.get("BLS_CONTACT_EMAIL"):
        ua = f"Acheron-ATRI-rebuild/1.0 ({os.environ['BLS_CONTACT_EMAIL']})"
    h = {"User-Agent": ua}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=timeout) as r:
        return r.read()


def fp_cpi():
    errs = []
    try:
        body = {"seriesid": ["CUUR0000SEHA"], "latest": True}
        if os.environ.get("BLS_API_KEY"):
            body["registrationkey"] = os.environ["BLS_API_KEY"]
        d = json.loads(get("https://api.bls.gov/publicAPI/v2/timeseries/data/", json.dumps(body).encode(),
                           {"Content-Type": "application/json"}))
        if d.get("status") != "REQUEST_SUCCEEDED":
            raise RuntimeError(str(d.get("message"))[:80])
        o = d["Results"]["series"][0]["data"][0]
        float(o["value"])
        return f'{o["year"]}-{o["period"][1:]}={o["value"]}', "BLS API"
    except Exception as e:
        errs.append(f"BLS API: {e}")
    try:
        key = os.environ.get("FRED_API_KEY")
        if not key:
            raise RuntimeError("no FRED_API_KEY")
        d = json.loads(get("https://api.stlouisfed.org/fred/series/observations?series_id=CUUR0000SEHA"
                           f"&sort_order=desc&limit=3&file_type=json&api_key={key}"))
        o = next(x for x in d["observations"] if x["value"] not in (".", ""))
        return f'{o["date"][:7]}={o["value"]}', "FRED API"
    except Exception as e:
        errs.append(f"FRED: {e}")
    return UNAVAILABLE, " | ".join(errs)[:200]


def fp_zori():
    try:
        raw = get("https://files.zillowstatic.com/research/public_csvs/zori/National_zori_uc_sfrcondomfr_sm_month.csv").decode()
        rows = list(csv.reader(io.StringIO(raw)))
        hdr = rows[0]
        us = next(r for r in rows[1:] if len(r) > 2 and r[2] == "United States")
        k = max(i for i in range(4, len(us)) if us[i] != "")
        return f"{hdr[k][:7]}={float(us[k]):.4f}", "Zillow"
    except Exception as e:
        return UNAVAILABLE, f"Zillow: {e}"[:200]


def fp_bls_atr():
    local = [p for p in [os.path.join(HERE, "data", "r-cpi-ntr-and-r-cpi-atr.xlsx")] +
             sorted(glob.glob(os.path.join(HERE, "data", "*.xlsx"))) if os.path.isfile(p)]
    if local:
        return "local:" + hashlib.sha256(open(local[0], "rb").read()).hexdigest()[:16], f"committed file {os.path.basename(local[0])}"
    try:
        blob = get("https://www.bls.gov/cpi/research-series/r-cpi-ntr-and-r-cpi-atr.xlsx",
                   headers={"Accept": "*/*", "Referer": "https://www.bls.gov/cpi/research-series/r-cpi-ntr.htm"})
        if not blob.startswith(b"PK"):
            raise RuntimeError("blocked (not an xlsx)")
        return "bls:" + hashlib.sha256(blob).hexdigest()[:16], "downloaded from bls.gov"
    except Exception as e:
        return UNAVAILABLE, f"bls.gov workbook: {e}"[:200]


def fp_code():
    p = os.path.join(HERE, "rebuild.py")
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:16], "rebuild.py"


def emit(**kv):
    out = os.environ.get("GITHUB_OUTPUT")
    for k, v in kv.items():
        print(f"{k}={v}")
        if out:
            with open(out, "a") as f:
                f.write(f"{k}={v}\n")


def check():
    old = {}
    if os.path.exists(STATE):
        old = json.load(open(STATE)).get("inputs", {})
    new, notes = {}, {}
    for name, fn in [("cpi", fp_cpi), ("zori", fp_zori), ("bls_atr", fp_bls_atr), ("code", fp_code)]:
        val, note = fn()
        notes[name] = note
        new[name] = old.get(name, UNAVAILABLE) if val == UNAVAILABLE else val
        flag = "  (unavailable, kept previous)" if val == UNAVAILABLE else ""
        print(f"  {name:8s} {val:40s} {note}{flag}")
    changed = [k for k in new if new[k] != UNAVAILABLE and new[k] != old.get(k)]
    force = os.environ.get("FORCE", "").lower() == "true"
    if not old:
        reason = "first run"
    elif force:
        reason = "forced"
    else:
        reason = ", ".join(f"new {k}" for k in changed) if changed else "no new data"
    do_build = bool(force or not old or changed)
    os.makedirs(os.path.dirname(PENDING), exist_ok=True)
    json.dump({"inputs": new, "notes": notes, "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")},
              open(PENDING, "w"), indent=2)
    emit(changed=str(do_build).lower(), reason=reason.replace("\n", " "))


def commit():
    if not os.path.exists(PENDING):
        sys.exit("no state/pending.json - run 'probe.py check' first")
    st = json.load(open(PENDING))
    st["built_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    latest = os.path.join(HERE, "site", "latest.json")
    if os.path.exists(latest):
        st["headline"] = json.load(open(latest))
    json.dump(st, open(STATE, "w"), indent=2)
    os.remove(PENDING)
    print("state/state.json updated")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"check": check, "commit": commit}.get(cmd, lambda: sys.exit(f"unknown command {cmd}"))()
