#!/usr/bin/env python3
import argparse
import os
import re
import sys
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

URL = "https://www.o2online.de/netz/netzstoerung/"
ADDRESS = "Egger Straße, 94469 Deggendorf, Deutschland"
MOBILE_NUMBER = "01797568645"
TIMEZONE = ZoneInfo("Europe/Berlin")
LOG_PATH = os.path.join("data", "o2_report.md")
README_PATH = "README.md"
LAST_SUBMIT_PATH = os.path.join("data", ".last_submit_date")
TRIGGER_PHRASE = "Eine Basisstation in der Nähe funktioniert im Moment nicht einwandfrei."

TEMPLATES = [
    "I am reporting slow internet speeds and weak signal at my home address. The data connection is very slow and the signal strength has dropped noticeably. I suspect the nearby base station has a problem. When I go out to other parts of the city or travel to places like Munich, the speed and signal are completely normal. This issue is specific to my home location and points to a local base station fault. Please check and repair the tower serving this area.",
    "At my home I am experiencing both poor signal strength and very slow mobile internet. This was not the case before and the problem started recently. When I leave and go into the city or to other cities like Munich, everything works perfectly with strong signal and fast data. The issue is clearly with the base station near my home. Please investigate the local tower and restore normal service.",
    "I am affected by weak signal and slow data speeds at home. The internet is barely usable and the signal keeps dropping. However, when I travel to the city center or other cities such as Munich, the O2 network works without any issues. This confirms the problem is not with my device but with the local base station near my home. I request that the technical team inspect and fix the tower.",
    "My mobile signal at home has become weak and internet speeds are extremely slow. It used to work well at this location before. I have tested at other places in the city and in Munich where the network is fast and the signal is strong. This tells me the nearby base station is not functioning properly. Please send a technician to check the base station and restore the coverage at my home address.",
    "I want to report poor signal and slow internet at my home. Both the signal strength and data speed have degraded significantly at this address. The problem does not occur when I am in other areas of the city or when I visit other cities like Munich where O2 works perfectly. I believe the base station serving my home area has a fault. Please prioritize repairing the local tower so the service returns to normal.",
]


def now_iso():
    return datetime.now(TIMEZONE).isoformat(timespec="seconds")


def now_readable():
    """Human-friendly timestamp like 'Date: 7 Feb 2026 Time: 01:06 TZ: Berlin'."""
    dt = datetime.now(TIMEZONE)
    return dt.strftime("Date: %-d %b %Y Time: %H:%M TZ: Berlin")


def ensure_log_header():
    if not os.path.exists(LOG_PATH):
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("# O2 Live-Check Log\n\n")
            f.write("| Date | Time | TZ | Address | Status | Result | Form Submitted | Reason | Message Sent |\n")
            f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")


def md_escape(text):
    return text.replace("|", "\\|").replace("\n", "<br>").strip()


def append_log(status, result_text, form_submitted, reason, message_sent):
    ensure_log_header()
    dt = datetime.now(TIMEZONE)
    date_str = dt.strftime("%-d %b %Y")
    time_str = dt.strftime("%H:%M")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(
            f"| {date_str} | {time_str} | Berlin"
            f" | {md_escape(ADDRESS)} | {md_escape(status)} | {md_escape(result_text)}"
            f" | {md_escape(form_submitted)} | {md_escape(reason)} | {md_escape(message_sent)} |\n"
        )


def append_readme():
    with open(README_PATH, "a", encoding="utf-8") as f:
        f.write("# o2-report\n")


def was_submitted_today():
    """Check if a form was already submitted today."""
    if not os.path.exists(LAST_SUBMIT_PATH):
        return False
    try:
        with open(LAST_SUBMIT_PATH, "r", encoding="utf-8") as f:
            last_date = f.read().strip()
        today = datetime.now(TIMEZONE).date().isoformat()
        return last_date == today
    except Exception as e:
        print(f"Warning: Failed to read last submit date: {e}", file=sys.stderr)
        return False


def mark_submitted_today():
    """Mark that a form was submitted today."""
    try:
        os.makedirs(os.path.dirname(LAST_SUBMIT_PATH), exist_ok=True)
        today = datetime.now(TIMEZONE).date().isoformat()
        with open(LAST_SUBMIT_PATH, "w", encoding="utf-8") as f:
            f.write(today)
    except Exception as e:
        print(f"Warning: Failed to write last submit date: {e}", file=sys.stderr)


NO_OUTAGE_PHRASE = "Unser Netz funktioniert störungsfrei"


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


def fill_and_submit_form(iframe, full_result_text, dry_run=False, phone_override=None):
    # Open the report form — use JS click because the site's sticky nav bar
    # (<tef-navigation>) overlays the button and intercepts pointer events.
    clicked = iframe.evaluate("""() => {
        const els = Array.from(document.querySelectorAll("div[role='button'], button, a, span"));
        const target = els.find(el => (el.innerText || "").trim().toLowerCase() === "jetzt melden");
        if (target) { target.click(); return true; }
        return false;
    }""")
    if not clicked:
        return False, "form_button_not_found", ""

    # Wait for form to appear (poll for key fields)
    form_ready = False
    for _ in range(30):
        try:
            if iframe.locator("input[name='category']").count() > 0:
                form_ready = True
                break
        except Exception:
            pass
        iframe.page.wait_for_timeout(800)
    if not form_ready:
        return False, "form_not_opened", ""

    # Re-remove overlays in case they reappeared
    remove_overlays(iframe.page)
    iframe.page.wait_for_timeout(500)

    def click_radio(name, value):
        """Click a radio's parent label via JS to trigger React state updates."""
        return iframe.evaluate(
            """([name, value]) => {
                const el = document.querySelector(`input[name='${name}'][value='${value}']`);
                if (!el) return false;
                // Click the label wrapping this radio to trigger React/MUI properly
                const label = el.closest('label') || el.parentElement?.querySelector('label');
                if (label) { label.click(); return true; }
                el.click();
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""",
            [name, value],
        )

    def click_label(text_regex):
        try:
            loc = iframe.locator("label", has_text=text_regex).first
            loc.click(timeout=3000, force=True)
            return True
        except Exception:
            return False

    # Category: Internet (value=30)
    if not click_radio("category", "30"):
        click_label(re.compile(r"^Internet$", re.I))
    # Wait for issue options to load (they appear after selecting category)
    iframe.page.wait_for_timeout(1000)
    # Issue: Langsame Datenverbindung (appears dynamically after category)
    if not click_radio("issue", "110"):
        click_label(re.compile(r"Langsame Datenverbindung", re.I))
    # Frequency: Immer (value=30)
    if not click_radio("frequency", "30"):
        click_label(re.compile(r"^Immer$", re.I))
    # Location: Im Gebäude (value=10)
    if not click_radio("location", "10"):
        click_label(re.compile(r"Im Gebäude|Im Gebaeude", re.I))
    # Since: Schon länger (value=30)
    if not click_radio("customq1", "30"):
        click_label(re.compile(r"Schon länger|Schon laenger", re.I))

    # Comment text — sanitize special chars the form rejects
    def sanitize(text):
        """Replace special Unicode chars with ASCII equivalents."""
        text = text.replace("\u201E", '"').replace("\u201C", '"')   # „ "
        text = text.replace("\u201A", "'").replace("\u2018", "'")   # ‚ '
        text = text.replace("\u201D", '"').replace("\u201F", '"')
        text = text.replace("\u2019", "'").replace("\u2013", "-")   # ' –
        text = text.replace("\u2014", "-").replace("\u2026", "...") # — …
        return text

    message = random.choice(TEMPLATES)
    comment = sanitize(f"{message}\n\n{full_result_text}")
    try:
        textarea = iframe.locator("textarea#comments").first
        textarea.click(force=True, timeout=3000)
        textarea.fill(comment)
    except Exception:
        try:
            textarea = iframe.locator("textarea").first
            textarea.click(force=True, timeout=3000)
            textarea.fill(comment)
        except Exception:
            return False, "comment_not_filled", ""

    # Mobile number — use JS focus + keyboard typing to trigger React state
    number = phone_override or MOBILE_NUMBER
    try:
        # Focus the input via JS inside the iframe to bypass any overlay
        iframe.evaluate("""() => {
            const inp = document.querySelector("input[name='customer_mobile']");
            if (inp) { inp.focus(); inp.value = ''; }
        }""")
        iframe.page.wait_for_timeout(300)
        # Type each digit via keyboard to trigger React onChange events
        iframe.page.keyboard.type(number, delay=50)
        iframe.page.wait_for_timeout(300)
    except Exception:
        return False, "phone_not_filled", message

    # --- dry-run: stop here so user can inspect the filled form ---
    if dry_run:
        return False, "dry_run_stopped_before_submit", message

    # Check for validation errors before submitting
    iframe.page.wait_for_timeout(500)
    has_errors = iframe.evaluate("""() => {
        const errs = document.querySelectorAll('.MuiFormHelperText-root.Mui-error');
        const visible = Array.from(errs).filter(e => e.offsetParent !== null && e.innerText.trim());
        return visible.map(e => e.innerText.trim());
    }""")
    if has_errors:
        return False, f"validation_errors: {'; '.join(has_errors)}", message

    # Submit
    submit_clicked = iframe.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll("button, div[role='button']"));
        const target = btns.find(b => /absenden/i.test(b.innerText || ""));
        if (target) { target.click(); return true; }
        return false;
    }""")
    if not submit_clicked:
        submit_btn = iframe.get_by_role("button", name=re.compile(r"absenden", re.I))
        try:
            submit_btn.click(force=True, timeout=5000)
            submit_clicked = True
        except Exception:
            return False, "submit_not_clicked", message

    # Wait for confirmation dialog (MuiDialog with "Vielen Dank")
    iframe.page.wait_for_timeout(3000)

    # Check if validation errors appeared after submit
    post_errors = iframe.evaluate("""() => {
        const errs = document.querySelectorAll('.MuiFormHelperText-root.Mui-error');
        const visible = Array.from(errs).filter(e => e.offsetParent !== null && e.innerText.trim());
        return visible.map(e => e.innerText.trim());
    }""")
    if post_errors:
        return False, f"validation_errors: {'; '.join(post_errors)}", message

    confirmation = ""
    try:
        iframe.locator(".MuiDialogContent-root").wait_for(timeout=15000)
        confirmation = iframe.locator(".MuiDialogContent-root").first.inner_text()
    except Exception:
        try:
            iframe.locator("text=Vielen Dank").wait_for(timeout=5000)
            confirmation = iframe.locator("text=Vielen Dank").first.inner_text()
        except Exception:
            confirmation = ""
    return True, confirmation.strip() or "confirmation_not_found", message


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


def run_check(dry_run=False, headed=False, phone=None, force_submit=False):
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
        message_sent = ""
        is_monday = datetime.now(TIMEZONE).weekday() == 0  # 0 = Monday
        if TRIGGER_PHRASE in full_text:
            if is_monday or dry_run or force_submit:
                # Check if already submitted today (only for Monday submissions, not for force_submit)
                if is_monday and not dry_run and not force_submit and was_submitted_today():
                    submit_reason = "already_submitted_today"
                else:
                    try:
                        submitted, confirmation, message_sent = fill_and_submit_form(frame, full_text, dry_run=dry_run, phone_override=phone)
                        if not submitted:
                            submit_reason = confirmation
                        elif not dry_run:
                            # Mark as submitted only if actually submitted (not dry-run)
                            mark_submitted_today()
                    except Exception as exc:
                        submitted = False
                        submit_reason = f"exception: {exc.__class__.__name__}: {exc}"
            else:
                submit_reason = "outage_detected_but_form_only_on_mondays"

        if dry_run:
            # Take focused screenshots of the filled form for inspection
            try:
                frame.locator("input[name='category']").first.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
            except Exception:
                pass
            top_path = os.path.join(os.path.dirname(LOG_PATH), "dry_run_form_top.png")
            page.screenshot(path=top_path)
            print(f"Screenshot (top) saved to {top_path}")
            try:
                frame.locator("input[name='customer_mobile']").first.scroll_into_view_if_needed()
                page.wait_for_timeout(300)
            except Exception:
                pass
            bottom_path = os.path.join(os.path.dirname(LOG_PATH), "dry_run_form_bottom.png")
            page.screenshot(path=bottom_path)
            print(f"Screenshot (bottom) saved to {bottom_path}")
            if headed:
                print("\n=== DRY RUN: Form filled. Inspect the browser. Press Enter to close. ===")
                try:
                    input()
                except EOFError:
                    pass

        browser.close()

        form_submitted = "yes" if submitted else "no"
        reason = confirmation if submitted else submit_reason
        return status, full_text, form_submitted, reason, message_sent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fill form but do not submit")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed (visible) mode")
    parser.add_argument("--no-log", action="store_true", help="Skip writing to log file")
    parser.add_argument("--phone", type=str, default=None, help="Override phone number for testing")
    parser.add_argument("--force-submit", action="store_true", help="Force form submission even if not Monday")
    args = parser.parse_args()

    status = "error"
    result_text = ""
    form_submitted = "no"
    reason = ""
    message_sent = ""
    try:
        status, result_text, form_submitted, reason, message_sent = run_check(dry_run=args.dry_run, headed=args.headed, phone=args.phone, force_submit=args.force_submit)
    except Exception as exc:
        reason = f"error: {exc.__class__.__name__}: {exc}"

    if not args.no_log:
        append_log(status, result_text, form_submitted, reason, message_sent)
        append_readme()
    print(f"[{now_iso()}] status={status} form_submitted={form_submitted} reason={reason}")


if __name__ == "__main__":
    main()
