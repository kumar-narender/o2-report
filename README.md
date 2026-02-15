# o2-report

Automated O2 Live-Check for **Egger Straße 2a, 94469 Deggendorf**.

**Purpose**
- Check O2 Live-Check for network issues at the address.
- Log results to a Markdown table that is viewable directly on GitHub.
- If a specific outage message appears, attempt to open the “Jetzt melden” form, fill it with predefined options and a detailed complaint message, and submit it automatically.

**What It Does**
- Runs on GitHub Actions every 6 hours.
- Opens the O2 Live-Check page.
- Selects the **Internet** service and searches the address.
- Captures the full “Ergebnis für …” result text.
- Logs every run to `data/o2_report.md`.
- If the result contains: `Eine Basisstation in der Nähe funktioniert im Moment nicht einwandfrei.`, it attempts to:
  - Open “Jetzt melden”.
  - Select options: **Internet → Langsame Datenverbindung → Immer → Überall → Schon länger**.
  - Fill the form with a random template message + the full result text.
  - Submit and log the confirmation text (if successful).

**Tech Stack / Software Used**
- **Python 3.11** (runtime)
- **Playwright** (browser automation)
- **GitHub Actions** (scheduled runs + auto-commit logs)
- **Markdown** (log format stored in repo)

**Key Files**
- `scripts/run_daily.py` – main automation script
- `.github/workflows/daily.yml` – GitHub Actions schedule + runner
- `data/o2_report.md` – log output (viewable on GitHub)
- `requirements.txt` – Python dependency list

**Logging**
- Logs are appended to `data/o2_report.md` as a Markdown table.
- Each entry includes timestamp (Berlin time), address, status, and full result text.
- If the form is submitted, the log includes `FORM_SUBMITTED: yes` and the confirmation text.

**Schedule**
- Every 6 hours (UTC): `0 */6 * * *`

**Notes**
- Scheduled GitHub Actions runs may be delayed by a few minutes by GitHub.
- If the form cannot be opened/submitted, the log will include a `SUBMIT_REASON`.
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
# o2-report
