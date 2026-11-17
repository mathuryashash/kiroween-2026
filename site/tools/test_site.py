#!/usr/bin/env python3
"""
site/tools/test_site.py - open the built site in headless Chromium and check what a judge sees.

    python site/tools/build.py && python site/tools/test_site.py [--no-pyodide]

Checks, at desktop (1440x900) and phone (390x844) sizes:
  - no console errors or failed requests (other than the optional Pyodide CDN when offline)
  - the ledger has one row per routine in data/ledger.json, with the held-out numbers
  - nothing is wider than the screen (no sideways scrolling)
  - every link to a run file points at the commit the site was built from
  - the page still shows every number with the CDN blocked (Pyodide is optional)
  - the in-browser re-run agrees with the build-time spot check (skipped with --no-pyodide)
Screenshots go to site/test-artifacts/ (git-ignored).
"""
from __future__ import annotations

import http.server
import json
import subprocess
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parents[1]
PUBLIC = SITE / "public"
SHOTS = SITE / "test-artifacts"
SIZES = {"desktop": (1440, 900), "phone": (390, 844)}


def serve() -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(PUBLIC))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def check_page(page, url: str, ledger: dict, label: str, fails: list) -> None:
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url, wait_until="load")
    rows = page.locator(".lrow")
    if rows.count() != len(ledger["routines"]):
        fails.append(f"{label}: {rows.count()} ledger rows, expected {len(ledger['routines'])}")
    for r in ledger["routines"]:
        h = r["runs"]["port_heldout"]
        text = page.locator(f"#case-{r['name']}").inner_text()
        if h["file"] not in text:
            fails.append(f"{label}: {r['name']} case does not cite {h['file']}")
        if f"{h['n']:,}" not in text:
            fails.append(f"{label}: {r['name']} case does not show n={h['n']:,}")
    for a in page.locator("a[href*='/blob/']").all():   # each link names a commit that has the file
        href = a.get_attribute("href")
        commit, _, path = href.split("/blob/", 1)[1].partition("/")
        ok = subprocess.run(["git", "-C", str(SITE.parent), "cat-file", "-e", f"{commit}:{path}"],
                            capture_output=True).returncode == 0
        if not ok:
            fails.append(f"{label}: link to a file that is not in that commit: {href}")
    over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    if over > 1:
        wide = page.evaluate("""[...document.querySelectorAll('body *')].filter(e => {
            const r = e.getBoundingClientRect(); return r.right > window.innerWidth + 1 &&
            !e.closest('.scroll, pre') }).slice(0, 5).map(e => e.tagName + '.' + e.className)""")
        fails.append(f"{label}: page is {over}px wider than the screen: {wide}")
    if errors:
        fails.append(f"{label}: console errors: {errors[:3]}")


def main() -> int:
    ledger = json.loads((PUBLIC / "data" / "ledger.json").read_text(encoding="utf-8"))
    SHOTS.mkdir(exist_ok=True)
    srv, url = serve()
    fails: list[str] = []
    with sync_playwright() as p:
        try:                                   # the installed Chrome, else Playwright's own build
            browser = p.chromium.launch(channel="chrome")
        except Exception:
            browser = p.chromium.launch()
        for name, (w, h) in SIZES.items():
            page = browser.new_page(viewport={"width": w, "height": h})
            check_page(page, url, ledger, name, fails)
            page.screenshot(path=str(SHOTS / f"{name}_top.png"))
            page.screenshot(path=str(SHOTS / f"{name}_full.png"), full_page=True)
            page.close()

        # Offline CDN: block every request that is not to our own server.
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(url) else route.abort())
        page = ctx.new_page()
        page.goto(url, wait_until="load")
        if page.locator(".lrow").count() != len(ledger["routines"]):
            fails.append("cdn-blocked: ledger did not render")
        page.click("#lab-run")
        page.wait_for_function("document.querySelector('#lab-status').textContent.includes('could not run')", timeout=70000)
        print("cdn-blocked: re-run button says:", page.locator("#lab-status").inner_text())
        ctx.close()

        if "--no-pyodide" not in sys.argv:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(url, wait_until="load")
            for r in ledger["routines"]:
                s = r["samples"][0]
                page.select_option("#lab-fn", r["name"])
                page.fill("#lab-x", repr(s["x"]))
                page.click("#lab-run")
                page.wait_for_function("document.querySelector('#lab-status').textContent.startsWith('Done')"
                                       " || document.querySelector('#lab-status').textContent.includes('could not')",
                                       timeout=180000)
                status = page.locator("#lab-status").inner_text()
                cells = page.locator("#lab-out tbody td").all_inner_texts()
                print(f"pyodide {r['name']}({s['x']}): {status} | {cells}")
                if not status.startswith("Done"):
                    fails.append(f"pyodide {r['name']}: {status}")
                    continue
                # cells: x, referee, faithful, ulp, healed, ulp, allowed
                if float(cells[1]) != s["referee"]:
                    fails.append(f"pyodide {r['name']}: referee {cells[1]} != build-time {s['referee']!r}")
                if float(cells[4]) != s["healed"] or float(cells[2]) != s["faithful"]:
                    fails.append(f"pyodide {r['name']}: values differ from the build-time spot check")
            page.screenshot(path=str(SHOTS / "pyodide_rerun.png"))
            page.close()
        browser.close()
    srv.shutdown()
    for f in fails:
        print("FAIL", f)
    print("site test:", "PASS" if not fails else f"{len(fails)} failure(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
