#!/usr/bin/env python3
import csv
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://www.o2online.de/netz/netzstoerung/"
ADDRESS = "Egger Straße 2a 94469 Deggendorf"
TIMEZONE = ZoneInfo("Europe/Berlin")
LOG_PATH = os.path.join("data", "o2_report.csv")
README_PATH = "README.md"


def now_iso():
    return datetime.now(TIMEZONE).isoformat(timespec="seconds")


def ensure_log_header():
    if not os.path.exists(LOG_PATH):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp_berlin", "address", "status", "result_text"])


def append_log(status, result_text):
    ensure_log_header()
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now_iso(), ADDRESS, status, result_text])


def append_readme():
    with open(README_PATH, "a", encoding="utf-8") as f:
        f.write("# o2-report\n")


def classify_result(text):
    t = text.lower()
    if "keine störung" in t or "keine stoerung" in t or "keine störungen" in t or "keine stoerungen" in t:
        return "ok"
    if "netzarbeiten" in t or "arbeiten" in t:
        return "maintenance"
    if "störung" in t or "stoerung" in t:
        return "outage"
    return "unknown"


def extract_relevant_line(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    keywords = ["keine störung", "keine stoerung", "keine störungen", "keine stoerungen", "störung", "stoerung", "netzarbeiten"]
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in keywords):
            return ln[:300]
    return ""  # fallback when we cannot find a clear status line


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


def find_address_input(page):
    locators = [
        page.get_by_role("textbox", name=re.compile(r"adresse|straße|strasse|anschrift", re.I)),
        page.locator("input[placeholder*='Adresse' i]"),
        page.locator("input[placeholder*='Straße' i]"),
        page.locator("input[placeholder*='Strasse' i]"),
        page.locator("input[type='text']"),
    ]
    for loc in locators:
        if loc.count() > 0:
            return loc.first
    return None


def run_check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        accept_cookies(page)
        open_live_check(page)

        input_box = find_address_input(page)
        if input_box is None:
            raise RuntimeError("Address input not found")

        input_box.fill(ADDRESS)
        # Try to select the first suggestion if available
        try:
            page.keyboard.press("ArrowDown")
            page.keyboard.press("Enter")
        except PlaywrightTimeout:
            pass

        # Give the page time to render results
        page.wait_for_timeout(5000)

        body_text = page.inner_text("body")
        line = extract_relevant_line(body_text)
        status = classify_result(line or body_text)
        if not line:
            line = (body_text[:300]).replace("\n", " ")

        browser.close()
        return status, line


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
