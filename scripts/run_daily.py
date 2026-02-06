#!/usr/bin/env python3
import os
import re
import sys
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://www.o2online.de/netz/netzstoerung/"
ADDRESS = "Egger Straße, 94469 Deggendorf, Deutschland"
MOBILE_NUMBER = "017642930528"
TIMEZONE = ZoneInfo("Europe/Berlin")
LOG_PATH = os.path.join("data", "o2_report.md")
README_PATH = "README.md"
TRIGGER_PHRASE = "Eine Basisstation in der Nähe funktioniert im Moment nicht einwandfrei."

TEMPLATES = [
    "Professional & Technical\nMy mobile number is 017642930528 and I am reporting a persistent speed cap. Despite having a full 5G signal, my downloads never exceed 20 Mbps in any location. I have tested this across multiple cities over several months with the same result. This suggests a profile throttling issue on my SIM card rather than a local mast fault. Please refresh my network provisioning and confirm that my account has no speed limits.",
    "I am writing to follow up on my recent network disturbance report for 017642930528. My device consistently shows a 5G connection, yet speed tests are stalled at 20 Mbps. This performance has been ongoing for many months and occurs regardless of the time. I have already performed a network settings reset on my device with no improvement. I request a manual technical audit of my data plan to ensure 5G access is fully enabled.",
    "Regarding my O2 contract, I am experiencing a severe discrepancy in advertised speeds. My current data throughput is reaching a maximum of 20 Mbps on a 5G network. This issue is not location-specific as it occurs \"everywhere\" according to my tests. Since this has persisted for months, it is no longer a temporary maintenance issue. Please investigate if my internal O2 data profile is restricted to a lower speed tier.",
    "Firm & Demanding\nI am dissatisfied with the 5G data performance on my mobile line 017642930528. For several months, my download speeds have been restricted to a flat 20 Mbps. This is far below the standard 5G capability and the speeds I am paying for monthly. The problem follows me to every location, proving it is an account-level restriction. I expect a response from a technician explaining why my 5G speeds are being throttled.",
    "This is a formal complaint regarding the data speeds for my number 017642930528. Despite my phone indicating a 5G connection, I am only receiving 20 Mbps bandwidth. I have been dealing with this slow connection for months without any improvement. I have filled out the Live Check form, but the automated system does not solve this. Please escalate this ticket to the network department for a manual profile override.",
    "My 5G service has been underperforming for months, capped at exactly 20 Mbps. I am using a 5G-ready device and I am located in areas with excellent O2 coverage. There is no reason for my speeds to be this low unless there is a system error. As a long-term customer, I expect the high-speed data that my contract promises. Please check the bandwidth allocation for 017642930528 and remove any limitations.",
    "Analytical & Evidence-Based\nI have conducted several speed tests on 017642930528 showing a 20 Mbps limit. Even with \"5G\" displayed on my screen, the data rate is identical to an LTE cap. This behavior has been consistent for months across various cell towers in Germany. It appears my SIM card is not being allowed to access the full 5G spectrum bandwidth. I request a technical reset of my HLR (Home Location Register) data on your end.",
    "Current network status for 017642930528: 5G signal is strong, but speeds are weak. I am recording a maximum of 20 Mbps download speed in every environment I visit. This has been an ongoing issue for many months and is now becoming unusable. The \"Live Check\" tool shows no local faults, so the error lies within my account. Please verify my data speed entitlement and update my network profile immediately.",
    "I am reporting a \"Slow Data Connection\" that has persisted for over three months. My 5G speeds are consistently hitting a ceiling of 20 Mbps during all hours. I have cross-referenced this with other O2 users who get much higher speeds nearby. This confirms the issue is specific to my mobile number and not the local towers. Please check for any \"Fair Use\" or technical throttles applied to 017642930528.",
    "Direct & Direct\nPlease look into the 5G data restriction for my mobile number 017642930528. I am only getting 20 Mbps, which is unacceptable for a modern 5G mobile plan. I have been experiencing this slow speed for several months regardless of location. I have already tried all the basic troubleshooting steps like restarting the phone. I need a network engineer to check the speed configuration on my O2 user profile.",
    "My 5G data is currently performing like a throttled 4G connection at 20 Mbps. This issue has been present for months and is consistent across all locations. My number is 017642930528 and I have already submitted the online check form. Since the network shows as \"Fine,\" the problem must be my specific SIM profile. Please remove any speed caps and ensure I have full access to the 5G network.",
    "I am requesting a technical review of the data speeds for line 017642930528. My 5G connection is permanently stuck at 20 Mbps, which is a major bottleneck. This problem has been ongoing for months and I have finally decided to report it. I am paying for high-speed 5G and I am not receiving the service I signed for. Please investigate why my speed is limited and provide a timeline for a fix.",
    "Service-Oriented\nI am contacting O2 support because my 5G speed is capped at 20 Mbps everywhere. I have been a customer for a long time, but this issue has lasted for many months. My phone shows a 5G icon, but the performance does not match the technology. I have checked my number 017642930528 and my hardware is working perfectly. Could you please check if there is a technical error in my contract data settings?",
    "Help is needed for my mobile data connection on the number 017642930528. For months, I have been unable to get speeds higher than 20 Mbps on 5G. This happens in the city, at home, and while traveling across the country. I would like to know if there is a known issue with my specific plan or SIM. Please update my network registration so I can utilize the full 5G bandwidth.",
    "This is my third attempt to resolve the 20 Mbps speed limit on my 5G account. My number is 017642930528 and this slow data has been an issue for many months. It is clear that my 5G access is being restricted by a backend system setting. I am requesting a manual intervention to restore my data speeds to normal. Thank you for looking into this and I look forward to a much faster connection.",
]


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
        page.locator("button[value='30']"),
        page.get_by_role("button", name=re.compile(r"^internet$", re.I)),
        page.get_by_role("button", name=re.compile(r"^empfang$|^sprachtelefonie$|^sms$|^sonstiges$", re.I)),
    ]
    for loc in candidates:
        if click_if_visible(page, loc):
            return


def fill_and_submit_form(iframe, full_result_text):
    # Open the report form
    btn = iframe.get_by_role("button", name=re.compile(r"jetzt melden", re.I))
    try:
        if btn.count() > 0:
            btn.first.scroll_into_view_if_needed()
            btn.first.click(timeout=3000, force=True)
        else:
            raise Exception("no_button")
    except Exception:
        # Sometimes it's a plain div/button without role lookup
        try:
            text_btn = iframe.locator("div[role='button']", has_text=re.compile(r"jetzt melden", re.I)).first
            text_btn.scroll_into_view_if_needed()
            text_btn.click(timeout=3000, force=True)
        except Exception:
            # JS click fallback
            try:
                iframe.evaluate(
                    """() => {
                        const btns = Array.from(document.querySelectorAll("div[role='button'], button"));
                        const target = btns.find(b => (b.innerText || "").toLowerCase().includes("jetzt melden"));
                        if (target) target.click();
                    }"""
                )
            except Exception:
                return False, "form_button_not_found"

    # Wait for form to appear (poll for key fields)
    form_ready = False
    for _ in range(30):
        try:
            if iframe.locator("input[name='category']").count() > 0:
                form_ready = True
                break
        except Exception:
            pass
        try:
            if iframe.locator("textarea").count() > 0:
                form_ready = True
                break
        except Exception:
            pass
        try:
            if iframe.locator("[role='dialog'], .MuiDialog-root, .MuiDialog-container").count() > 0:
                form_ready = True
                break
        except Exception:
            pass
        iframe.page.wait_for_timeout(800)
    if not form_ready:
        return False, "form_not_opened"

    def click_input(name, value):
        try:
            loc = iframe.locator(f"input[name='{name}'][value='{value}']").first
            loc.click(timeout=3000, force=True)
            return True
        except Exception:
            return False

    def click_label(text_regex):
        try:
            loc = iframe.locator("label", has_text=text_regex).first
            loc.click(timeout=3000, force=True)
            return True
        except Exception:
            return False

    # Service: Internet (value 30 per provided HTML)
    if not click_input("category", "30"):
        click_label(re.compile(r"^Internet$", re.I))
    # Problem: Langsame Datenverbindung (value 110 per provided HTML)
    if not click_input("issue", "110"):
        click_label(re.compile(r"Langsame Datenverbindung", re.I))
    # Frequency: Immer (name=frequency value=30)
    if not click_input("frequency", "30"):
        click_label(re.compile(r"^Immer$", re.I))
    # Location: Überall (name=location value=50)
    if not click_input("location", "50"):
        click_label(re.compile(r"Überall|Ueberall", re.I))
    # Since: Schon länger (name=customq1 value=30)
    if not click_input("customq1", "30"):
        click_label(re.compile(r"Schon länger|Schon laenger", re.I))

    # Comment text
    message = random.choice(TEMPLATES)
    comment = f"{message}\n\n{full_result_text}"
    try:
        textarea = iframe.get_by_label(re.compile(r"Bitte geben Sie ein Beispiel an", re.I))
        textarea.fill(comment)
    except Exception:
        try:
            textarea = iframe.get_by_placeholder(re.compile(r"Kommentar|Kommentare", re.I))
            textarea.fill(comment)
        except Exception:
            try:
                iframe.locator("textarea").first.fill(comment)
            except Exception:
                return False, "comment_not_filled"

    # Mobile number
    try:
        phone_input = iframe.get_by_role("textbox", name=re.compile(r"mobilfunknummer", re.I))
        phone_input.fill(MOBILE_NUMBER)
    except Exception:
        try:
            iframe.locator("input[type='tel']").first.fill(MOBILE_NUMBER)
        except Exception:
            return False, "phone_not_filled"

    # Submit
    submit_btn = iframe.get_by_role("button", name=re.compile(r"absenden", re.I))
    try:
        submit_btn.scroll_into_view_if_needed()
    except Exception:
        pass

    if click_if_visible(iframe, submit_btn):
        confirmation = ""
        try:
            iframe.locator("text=Vielen Dank").wait_for(timeout=15000)
            confirmation = iframe.locator("text=Vielen Dank").first.inner_text()
            # Try to include full confirmation block
            try:
                confirmation = iframe.locator("xpath=//*[contains(., 'Vielen Dank')][1]").inner_text()
            except Exception:
                pass
        except Exception:
            confirmation = ""
        return True, confirmation.strip() or "confirmation_not_found"
    # Retry with force click if button might be covered
    try:
        submit_btn.click(force=True, timeout=3000)
        iframe.locator("text=Vielen Dank").wait_for(timeout=15000)
        try:
            confirmation = iframe.locator("xpath=//*[contains(., 'Vielen Dank')][1]").inner_text()
        except Exception:
            confirmation = ""
        return True, confirmation.strip() or "confirmation_not_found"
    except Exception:
        return False, "submit_not_clicked"


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


def run_check():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
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
        search_btn = frame.get_by_role("button", name=re.compile(r"suchen|suche|prüfen|pruefen", re.I))
        if not click_if_visible(page, search_btn):
            # Try the SearchIcon button next to the input
            try:
                icon_btn = frame.locator("button", has=frame.locator("svg[data-testid='SearchIcon']")).first
                icon_btn.click(timeout=3000, force=True)
            except Exception:
                # Fallback: button near input
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

        submitted = False
        confirmation = ""
        submit_reason = ""
        if TRIGGER_PHRASE in full_text:
            try:
                submitted, confirmation = fill_and_submit_form(frame, full_text)
                if not submitted:
                    submit_reason = confirmation
            except Exception:
                submitted = False

        browser.close()
        if submitted:
            if confirmation:
                full_text = f"{full_text}\n\nFORM_SUBMITTED: yes\nCONFIRMATION: {confirmation}"
            else:
                full_text = f"{full_text}\n\nFORM_SUBMITTED: yes"
        else:
            if submit_reason:
                full_text = f"{full_text}\n\nFORM_SUBMITTED: no\nSUBMIT_REASON: {submit_reason}"
            else:
                full_text = f"{full_text}\n\nFORM_SUBMITTED: no"
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
