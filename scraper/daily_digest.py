"""
TenderRadar — Daily Digest
Sends a morning summary of all active tenders in your pipeline.
Runs every day at 8 AM IST via GitHub Actions.
"""
import json
import logging
import sys
from datetime import datetime, date
from alerts import _send_email, _send_telegram, load_alert_log
from config import (
    TENDERS_FILE, EMAIL_ENABLED, SMTP_USER, ALERT_EMAIL_TO,
    TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    MIN_RELEVANCE_SCORE
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DailyDigest")


def load_pipeline_tenders() -> dict:
    if not TENDERS_FILE.exists():
        return {}
    with open(TENDERS_FILE) as f:
        data = json.load(f)

    tenders = data.get("tenders", [])
    today = date.today()

    pipeline   = [t for t in tenders if t.get("status") in ("Watching","Bid Submitted")]
    high_score = [t for t in tenders if float(t.get("score",0)) >= 8 and t.get("status") == "New"]
    closing    = []
    for t in tenders:
        try:
            d = datetime.strptime(t["deadline"], "%Y-%m-%d").date()
            days = (d - today).days
            if 0 <= days <= 7 and t.get("status") not in ("Won","Lost"):
                t["_days_left"] = days
                closing.append(t)
        except Exception:
            pass

    closing.sort(key=lambda t: t.get("_days_left", 99))
    return {"pipeline": pipeline, "high_score": high_score[:5], "closing": closing[:5]}


def _build_digest_email(groups: dict) -> str:
    def section(title: str, tenders: list, color: str) -> str:
        if not tenders:
            return ""
        rows = ""
        for t in tenders:
            days = t.get("_days_left")
            deadline_str = f"{t.get('deadline','')} ({days}d left)" if days is not None else t.get("deadline","N/A")
            rows += f"""
            <tr style="border-bottom:1px solid #f1f5f9">
              <td style="padding:10px 8px">
                <div style="font-weight:600;color:#1e293b;font-size:13px">{t.get('title','')[:90]}</div>
                <div style="color:#94a3b8;font-size:11px;margin-top:2px">{t.get('portal','')} · {t.get('ref_no','')}</div>
              </td>
              <td style="padding:10px 8px;color:#64748b;font-size:12px;white-space:nowrap">{t.get('value_str','N/A')}</td>
              <td style="padding:10px 8px;color:#ef4444;font-size:12px;white-space:nowrap">{deadline_str}</td>
              <td style="padding:10px 8px">
                <span style="background:{color}22;color:{color};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">{t.get('status','New')}</span>
              </td>
            </tr>"""
        return f"""
        <div style="margin-bottom:24px">
          <h2 style="font-size:14px;font-weight:600;color:{color};text-transform:uppercase;letter-spacing:.5px;margin:0 0 12px;padding-bottom:8px;border-bottom:2px solid {color}22">{title}</h2>
          <table style="width:100%;border-collapse:collapse;font-size:13px">{rows}</table>
        </div>"""

    body = section("⏰ Closing This Week", groups["closing"], "#ef4444")
    body += section("📌 In Pipeline", groups["pipeline"], "#8b5cf6")
    body += section("⭐ High Score New Tenders", groups["high_score"], "#10b981")

    total = sum(len(v) for v in groups.values())

    return f"""<!DOCTYPE html><html><body style="font-family:-apple-system,sans-serif;background:#f8fafc;padding:20px;margin:0">
  <div style="max-width:750px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)">
    <div style="background:#0a0f1e;padding:20px 28px">
      <h1 style="color:white;margin:0;font-size:18px">📋 TenderRadar — Daily Digest</h1>
      <p style="color:#64748b;margin:4px 0 0;font-size:13px">{datetime.now().strftime('%A, %d %B %Y')} · {total} items requiring attention</p>
    </div>
    <div style="padding:24px 28px">{body if body else '<p style="color:#94a3b8;text-align:center;padding:24px 0">No active tenders today.</p>'}</div>
    <div style="background:#f8fafc;padding:14px 28px;border-top:1px solid #e2e8f0">
      <p style="color:#94a3b8;font-size:11px;margin:0">TenderRadar daily digest · Scores are AI estimates</p>
    </div>
  </div>
</body></html>"""


def run():
    logger.info("Generating daily digest…")
    groups = load_pipeline_tenders()

    total = sum(len(v) for v in groups.values())
    if total == 0:
        logger.info("Nothing to digest today.")
        return

    if EMAIL_ENABLED and SMTP_USER and ALERT_EMAIL_TO:
        from alerts import _send_email as _orig
        # Repurpose _send_email with digest content
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from config import SMTP_HOST, SMTP_PORT, SMTP_PASS

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"TenderRadar Daily Digest — {datetime.now().strftime('%d %b %Y')}"
        msg["From"]    = f"TenderRadar <{SMTP_USER}>"
        msg["To"]      = ALERT_EMAIL_TO
        msg.attach(MIMEText(_build_digest_email(groups), "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())
        logger.info("Digest email sent.")

    if TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        closing = groups.get("closing", [])
        pipeline = groups.get("pipeline", [])
        lines = [f"*📋 TenderRadar — Daily Digest ({datetime.now().strftime('%d %b')})*\n"]
        if closing:
            lines.append("*⏰ Closing this week:*")
            for t in closing[:5]:
                lines.append(f"• {t['title'][:60]} — {t['deadline']} ({t.get('_days_left','?')}d)")
        if pipeline:
            lines.append(f"\n*📌 In pipeline: {len(pipeline)} tender(s)*")

        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": "\n".join(lines),
            "parse_mode": "Markdown"
        }).encode()
        urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data=data),
            timeout=10
        )
        logger.info("Digest Telegram sent.")


if __name__ == "__main__":
    run()
