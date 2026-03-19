#!/usr/bin/env python3
import argparse
import os
import re
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://www.o2online.de/netz/netzstoerung/"
ADDRESS = "Egger Straße, 94469 Deggendorf, Deutschland"
TIMEZONE = ZoneInfo("Europe/Berlin")
LOG_PATH = os.path.join("data", "o2_report.md")


def now_iso():
    return datetime.now(TIMEZONE).isoformat(timespec="seconds")



def ensure_log_header():
    if not os.path.exists(LOG_PATH):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("# O2 Live-Check Log\n\n")
            f.write("| Date | Time | TZ | Address | Status | Result |\n")
            f.write("| --- | --- | --- | --- | --- | --- |\n")


def md_escape(text):
    return text.replace("|", "\\|").replace("\n", "<br>").strip()


MONTH_PARSE = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

CHART_PATH = os.path.join("data", "monthly_chart.png")


def parse_rows(content):
    """Parse log table rows into list of (date_str, status) tuples."""
    rows = []
    for line in content.split("\n"):
        if not line.startswith("|"):
            continue
        if line.startswith("| ---") or line.startswith("| Date |"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) > 5:
            rows.append((cols[1], cols[5].lower()))  # date_str, status
    return rows


def parse_month_key(date_str):
    """Turn '7 Feb 2026' into '2026-02'."""
    parts = date_str.strip().split()
    if len(parts) == 3:
        mon = MONTH_PARSE.get(parts[1].lower()[:3])
        if mon:
            return f"{parts[2]}-{mon:02d}"
    return None


def generate_chart(monthly):
    """Generate a monthly bar chart: works vs not-works, saved as PNG."""
    months = sorted(monthly.keys())
    works = [monthly[m]["ok"] for m in months]
    not_works = [monthly[m]["not_ok"] for m in months]
    labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months]

    x = range(len(months))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(6, len(months) * 1.2), 4))
    bars_ok = ax.bar([i - width / 2 for i in x], works, width, label="Works (ok)", color="#4caf50")
    bars_bad = ax.bar([i + width / 2 for i in x], not_works, width, label="Not working", color="#f44336")

    # Add count labels on bars
    for bar in bars_ok:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3, str(int(h)),
                    ha="center", va="bottom", fontsize=9)
    for bar in bars_bad:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.3, str(int(h)),
                    ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("Checks")
    ax.set_title("O2 Network Status — Monthly")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.legend()
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=120)
    plt.close(fig)


def append_log(status, result_text):
    ensure_log_header()
    dt = datetime.now(TIMEZONE)
    date_str = dt.strftime("%-d %b %Y")
    time_str = dt.strftime("%H:%M")

    # Read existing content and strip any old summary
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    summary_marker = "\n## Summary\n"
    if summary_marker in content:
        content = content[: content.index(summary_marker)]

    # Append new row
    row = (
        f"| {date_str} | {time_str} | Berlin"
        f" | {md_escape(ADDRESS)} | {md_escape(status)} | {md_escape(result_text)} |\n"
    )
    content += row

    # Parse all rows for counts
    rows = parse_rows(content)

    # Overall counts
    counts = {"ok": 0, "outage": 0, "maintenance": 0, "unknown": 0, "error": 0}
    # Monthly counts
    monthly = defaultdict(lambda: {"ok": 0, "not_ok": 0})
    for date_s, s in rows:
        if s in counts:
            counts[s] += 1
        mk = parse_month_key(date_s)
        if mk:
            if s == "ok":
                monthly[mk]["ok"] += 1
            else:
                monthly[mk]["not_ok"] += 1

    total = sum(counts.values())

    # Build summary section
    summary = summary_marker
    summary += f"\n**Total checks:** {total}\n\n"
    summary += "| Status | Count |\n| --- | --- |\n"
    for s, c in counts.items():
        if c > 0:
            summary += f"| {s} | {c} |\n"

    # Monthly breakdown table
    summary += "\n### Monthly Breakdown\n\n"
    summary += "| Month | Works (ok) | Not Working | Total |\n"
    summary += "| --- | --- | --- | --- |\n"
    for mk in sorted(monthly.keys()):
        label = datetime.strptime(mk, "%Y-%m").strftime("%b %Y")
        ok = monthly[mk]["ok"]
        nok = monthly[mk]["not_ok"]
        summary += f"| {label} | {ok} | {nok} | {ok + nok} |\n"

    # Chart image reference
    summary += f"\n### Monthly Chart\n\n![Monthly Chart](monthly_chart.png)\n"

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(content + summary)

    # Generate chart image
    if monthly:
        generate_chart(monthly)



def classify_result(text):
    t = text.lower()
    if "störungsfrei" in t:
        return "ok"
    if "keine störung" in t or "keine stoerung" in t or "keine störungen" in t or "keine stoerungen" in t:
        return "ok"
    if "wartungsarbeiten" in t or "netzarbeiten" in t or "arbeiten" in t or "beeinträchtigungen" in t:
        return "maintenance"
    if "störung" in t or "stoerung" in t:
        return "outage"
    return "unknown"


def extract_relevant_text(text):
    # Keep full result text; it's already scoped to the result container when available.
    return "\n".join([ln.strip() for ln in text.splitlines() if ln.strip()]).strip()


def click_if_visible(page, locator):
    if locator.count() > 0:
        try:
            if locator.first.is_visible():
                locator.first.click(timeout=3000)
                return True
        except PlaywrightTimeout:
            return False
    return False


def remove_overlays(page):
    """Remove Usercentrics cookie banner and sticky nav that block interactions."""
    try:
        page.evaluate("""() => {
            const uc = document.querySelector('#usercentrics-root');
            if (uc) uc.remove();
            const nav = document.querySelector('tef-navigation');
            if (nav) nav.style.display = 'none';
        }""")
    except Exception:
        pass


def accept_cookies(page):
    """Dismiss Usercentrics cookie consent by removing the overlay from the DOM."""
    remove_overlays(page)
    # Fallback: standard buttons on the page
    candidates = [
        page.get_by_role("button", name=re.compile(r"(alle|akzeptieren|zustimmen|einverstanden)", re.I)),
        page.get_by_role("button", name=re.compile(r"(accept|agree)", re.I)),
    ]
    for loc in candidates:
        if click_if_visible(page, loc):
            return


def open_live_check(page):
    # Try obvious link/button labels first
    candidates = [
        page.get_by_role("link", name=re.compile(r"netzstörung prüfen|live-?check", re.I)),
        page.get_by_role("button", name=re.compile(r"netzstörung prüfen|live-?check", re.I)),
        page.locator("a", has_text=re.compile(r"netzstörung prüfen|live-?check", re.I)),
    ]
    for loc in candidates:
        if click_if_visible(page, loc):
            return


def select_service(page):
    # Prefer "Internet" as in the UI options
    candidates = [
        page.locator("button[value='30']"),
        page.get_by_role("button", name=re.compile(r"^internet$", re.I)),
        page.get_by_role("button", name=re.compile(r"^empfang$|^sprachtelefonie$|^sms$|^sonstiges$", re.I)),
    ]
    for loc in candidates:
        if click_if_visible(page, loc):
            return



def find_address_input(ctx):
    locators = [
        ctx.locator("#sbuzz_search_input"),
        ctx.get_by_role("textbox", name=re.compile(r"adresse|straße|strasse|anschrift", re.I)),
        ctx.locator("input[placeholder*='Straße' i]"),
        ctx.locator("input[placeholder*='Strasse' i]"),
        ctx.locator("input[placeholder*='Adresse' i]"),
        ctx.locator("input[type='text']"),
    ]
    for loc in locators:
        try:
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue
    return None


def run_check(headed=False):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        accept_cookies(page)
        open_live_check(page)

        # Live-Check UI is inside an iframe (spatialbuzz)
        frame = None
        for _ in range(20):
            for f in page.frames:
                if "spatialbuzz" in f.url:
                    frame = f
                    break
            if frame is not None:
                break
            page.wait_for_timeout(500)
        if frame is None:
            raise RuntimeError("Live-Check iframe not found")

        try:
            frame.locator("body").wait_for(timeout=15000)
        except PlaywrightTimeout:
            pass

        select_service(frame)

        input_box = find_address_input(frame)
        if input_box is None:
            raise RuntimeError("Address input not found")

        input_box.fill(ADDRESS)
        try:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        except PlaywrightTimeout:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass

        # Trigger search if there is a search button
        search_btn = frame.get_by_role("button", name=re.compile(r"suchen|suche|prüfen|pruefen", re.I))
        if not click_if_visible(page, search_btn):
            try:
                icon_btn = frame.locator("button", has=frame.locator("svg[data-testid='SearchIcon']")).first
                icon_btn.click(timeout=3000, force=True)
            except Exception:
                try:
                    near_btn = input_box.locator("xpath=ancestor::div[1]//button").first
                    near_btn.click(timeout=3000, force=True)
                except Exception:
                    pass

        # Wait for result section
        page.wait_for_timeout(2000)
        result_text = ""
        try:
            frame.get_by_text(re.compile(r"Ergebnis für", re.I)).first.wait_for(timeout=20000)
            result_heading = frame.get_by_text(re.compile(r"Ergebnis für", re.I)).first
            container = result_heading.locator(
                "xpath=ancestor::*[self::section or self::div][1]"
            )
            result_text = container.inner_text()
        except Exception:
            result_text = ""

        body_text = page.inner_text("body")
        full_text = extract_relevant_text(result_text or body_text)
        status = classify_result(full_text)
        if not full_text:
            full_text = ((result_text or body_text)[:2000]).replace("\n", " ").strip()

        browser.close()
        return status, full_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Run browser in headed (visible) mode")
    parser.add_argument("--no-log", action="store_true", help="Skip writing to log file")
    args = parser.parse_args()

    status = "error"
    result_text = ""
    try:
        status, result_text = run_check(headed=args.headed)
    except Exception as exc:
        result_text = f"error: {exc.__class__.__name__}: {exc}"

    if not args.no_log:
        append_log(status, result_text)
    print(f"[{now_iso()}] status={status} result={result_text[:200]}")


if __name__ == "__main__":
    main()
