# o2-report

Automated O2 Live-Check for **Egger Straße 2a, 94469 Deggendorf**.

What it does:
- Runs on GitHub Actions every 6 hours.
- Checks the O2 Live-Check page for outages at the address.
- Writes a running Markdown log to `data/o2_report.md` (viewable directly on GitHub).
- If the result contains: "Eine Basisstation in der Nähe funktioniert im Moment nicht einwandfrei.", it attempts to open the "Jetzt melden" form, select the options shown (Internet → Langsame Datenverbindung → Immer → Überall → Schon länger), fill the form with a random template plus the full result text, and submit.
- If submission succeeds, the confirmation message is appended to the log entry.
- If there is no outage message, it only logs the result (no form submission).

Log file:
- `data/o2_report.md`
