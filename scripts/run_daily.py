#!/usr/bin/env python3
import csv
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://www.o2online.de/netz/netzstoerung/"
ADDRESS = "Egger Straße, 94469 Deggendorf, Deutschland"
TIMEZONE = ZoneInfo("Europe/Berlin")
LOG_PATH = os.path.join("data", "o2_report.md")
README_PATH = "README.md"


def now_iso():
    return datetime.now(TIMEZONE).isoformat(timespec="seconds")


def ensure_log_header():
    if not os.path.exists(LOG_PATH):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("# O2 Live-Check Log\n\n")
            f.write("| Timestamp (Berlin) | Address | Status | Result |\n")
            f.write("| --- | --- | --- | --- |\n")


def md_escape(text):
    return text.replace("|", "\\|").replace("\n", "<br>").strip()


def append_log(status, result_text):
    ensure_log_header()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"| {now_iso()} | {md_escape(ADDRESS)} | {md_escape(status)} | {md_escape(result_text)} |\n")


def append_readme():
    with open(README_PATH, "a", encoding="utf-8") as f:
        f.write("# o2-report\n")


def classify_result(text):
    t = text.lower()
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


def accept_cookies(page):
    # Try common consent buttons
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
        page.get_by_role("button", name=re.compile(r"^internet$", re.I)),
        page.get_by_role("button", name=re.compile(r"^empfang$|^sprachtelefonie$|^sms$|^sonstiges$", re.I)),
    ]
    for loc in candidates:
        if click_if_visible(page, loc):
            return


def find_address_input(ctx):
    locators = [
        ctx.get_by_role("textbox", name=re.compile(r"adresse|straße|strasse|anschrift", re.I)),
        ctx.locator("input[placeholder*='Adresse' i]"),
        ctx.locator("input[placeholder*='Straße' i]"),
        ctx.locator("input[placeholder*='Strasse' i]"),
        ctx.locator("input[type='text']"),
    ]
    for loc in locators:
        try:
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue
    return None


def run_check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        accept_cookies(page)
        open_live_check(page)

        # Live-Check UI is inside an iframe (spatialbuzz)
        iframe = page.frame_locator("iframe[src*='spatialbuzz']")
        try:
            iframe.locator("body").wait_for(timeout=15000)
        except PlaywrightTimeout:
            pass

        select_service(iframe)

        input_box = find_address_input(iframe)
        if input_box is None:
            raise RuntimeError("Address input not found")

        input_box.fill(ADDRESS)
        # Try to select the first suggestion if available
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
        search_btn = iframe.get_by_role("button", name=re.compile(r"suchen|suche|prüfen|pruefen", re.I))
        if not click_if_visible(page, search_btn):
            # Try the button closest to the address input (magnifier icon)
            try:
                near_btn = input_box.locator("xpath=ancestor::div[1]//button").first
                near_btn.click(timeout=3000)
            except Exception:
                pass

        # Wait for result section
        page.wait_for_timeout(2000)
        result_text = ""
        try:
            iframe.get_by_text(re.compile(r"Ergebnis für", re.I)).first.wait_for(timeout=20000)
            result_heading = iframe.get_by_text(re.compile(r"Ergebnis für", re.I)).first
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
    status = "error"
    result_text = ""
    try:
        status, result_text = run_check()
    except Exception as exc:
        result_text = f"error: {exc.__class__.__name__}: {exc}"

    append_log(status, result_text)
    append_readme()
    print(f"[{now_iso()}] status={status} result={result_text}")


if __name__ == "__main__":
    main()
