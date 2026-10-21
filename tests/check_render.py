#!/usr/bin/env python3
"""Headless render gate for the A-ATRI dashboard.

Fails (exit 1) unless, in both desktop/light and phone/dark:
  - there are no console errors, page errors or failed requests,
  - all 9 charts are created,
  - the page does not scroll sideways at phone width,
  - no 'NaN' or 'undefined' leaks into visible text.

Usage: python tests/check_render.py site/index.html
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

EXPECTED_CHARTS = 9


def main(path):
    p = pathlib.Path(path).resolve()
    html = p.read_text(encoding="utf-8")
    if not html.lstrip().lower().startswith("<!doctype"):
        wrapped = p.with_name("_render_check.html")
        wrapped.write_text("<!doctype html><html><head><meta charset='utf-8'>"
                           "<meta name='viewport' content='width=device-width,initial-scale=1'></head><body>"
                           + html + "</body></html>", encoding="utf-8")
        p = wrapped
    failures = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, vp, scheme in [("desktop-light", {"width": 1280, "height": 900}, "light"),
                                 ("phone-dark", {"width": 400, "height": 860}, "dark")]:
            ctx = browser.new_context(viewport=vp, color_scheme=scheme)
            page = ctx.new_page()
            errs = []
            page.on("console", lambda m: errs.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
            page.on("requestfailed", lambda r: errs.append(f"requestfailed: {r.url[:100]}"))
            page.goto(p.as_uri(), wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(1500)
            charts = page.evaluate("typeof Chart !== 'undefined' ? Object.keys(Chart.instances).length : -1")
            sw = page.evaluate("document.documentElement.scrollWidth")
            cw = page.evaluate("document.documentElement.clientWidth")
            text = page.inner_text("body")
            leaks = [w for w in ("NaN", "undefined") if w in text]
            ok = not errs and charts == EXPECTED_CHARTS and sw <= cw and not leaks
            print(f"{name:14s} charts={charts} scrollW={sw} clientW={cw} errors={len(errs)} leaks={leaks or '-'} "
                  f"{'OK' if ok else 'FAIL'}")
            for e in errs:
                print("   ", e)
            if not ok:
                failures.append(name)
            ctx.close()
        browser.close()
    if p.name == "_render_check.html":
        p.unlink()
    if failures:
        sys.exit(f"render check failed: {', '.join(failures)}")
    print("render check passed")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "site/index.html")
