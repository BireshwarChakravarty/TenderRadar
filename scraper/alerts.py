"""
TenderRadar — Alert Engine
Sends email + Telegram notifications for new high-score tenders.
Tracks which tenders have already been alerted to avoid duplicates.
"""
import json
import logging
import smtplib
import urllib.request
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from config import (
    EMAIL_ENABLED, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO,
    TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    ALERT_LOG_FILE, TENDERS_FILE, MIN_RELEVANCE_SCORE
)

logger = logging.getLogger("Alerts")


def load_alert_log() -> set[str]:
    if not ALERT_LOG_FILE.exists():
        return set()
    try:
        with open(ALERT_LOG_FILE) as f:
            return set(json.load(f).get("alerted_ids", []))
    except Exception:
        return set()


def save_alert_log(alerted_ids: set[str]) -> None:
    with open(ALERT_LOG_FILE, "w") as f:
        json.dump({"alerted_ids": list(alerted_ids), "updated_at": datetime.utcnow().isoformat()}, f, indent=2)


def load_new_tenders() -> list[dict]:
    """Load tenders that haven't been alerted yet and score >= threshold."""
    if not TENDERS_FILE.exists():
        return []
    try:
        with open(TENDERS_FILE) as f:
            data = json.load(f)
        alerted = load_alert_log()
        return [
            t for t in data.get("tenders", [])
            if t.get("id") not in alerted
            and float(t.get("score", 0)) >= MIN_RELEVANCE_SCORE
        ]
    except Exception as e:
        logger.error(f"Failed to load tenders: {e}")
        return []


def run_alerts():
    new_tenders = load_new_tenders()
    if not new_tenders:
        logger.info("No new tenders to alert.")
        return

    logger.info(f"Alerting on {len(new_tenders)} new tenders…")
    alerted = load_alert_log()

    if EMAIL_ENABLED and SMTP_USER and ALERT_EMAIL_TO:
        try:
            _send_email(new_tenders)
            logger.info("Email alert sent.")
        except Exception as e:
            logger.error(f"Email failed: {e}")

    if TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        for t in new_tenders:
            try:
                _send_telegram(t)
            except Exception as e:
                logger.error(f"Telegram failed for {t.get('id')}: {e}")

    # Mark all as alerted
    for t in new_tenders:
        alerted.add(t["id"])
    save_alert_log(alerted)
    logger.info(f"Marked {len(new_tenders)} tenders as alerted.")


# ── Email ──────────────────────────────────────────────────────────────

def _send_email(tenders: list[dict]) -> None:
    subject = f"TenderRadar — {len(tenders)} new relevant tender(s) found"
    body_html = _build_email_html(tenders)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"TenderRadar <{SMTP_USER}>"
    msg["To"]      = ALERT_EMAIL_TO
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, ALERT_EMAIL_TO, msg.as_string())


def _build_email_html(tenders: list[dict]) -> str:
    rows = ""
    for t in tenders:
        score_color = "#10b981" if t.get("score",0) >= 8 else "#f59e0b" if t.get("score",0) >= 6 else "#ef4444"
        deadline = t.get("deadline","N/A")
        rows += f"""
        <tr style="border-bottom:1px solid #e2e8f0">
          <td style="padding:12px 8px">
            <div style="font-weight:600;color:#1e293b">{t.get('title','')[:100]}</div>
            <div style="font-size:12px;color:#64748b;margin-top:2px">{t.get('ref_no','')} · {t.get('portal','')}</div>
          </td>
          <td style="padding:12px 8px;font-size:13px;color:#475569">{t.get('category','')}</td>
          <td style="padding:12px 8px;font-size:13px;font-weight:600;color:#1e293b;white-space:nowrap">{t.get('value_str','N/A')}</td>
          <td style="padding:12px 8px;font-size:13px;color:#ef4444;white-space:nowrap">{deadline}</td>
          <td style="padding:12px 8px;text-align:center">
            <span style="background:{score_color}22;color:{score_color};padding:3px 10px;border-radius:12px;font-weight:700;font-size:13px">{t.get('score',0)}</span>
          </td>
          <td style="padding:12px 8px">
            <a href="{t.get('url','#')}" style="background:#0ea5e9;color:white;padding:5px 12px;border-radius:6px;text-decoration:none;font-size:12px">View →</a>
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:20px">
  <div style="max-width:800px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1)">
    <div style="background:#0a0f1e;padding:24px 28px;display:flex;align-items:center;gap:10px">
      <div style="width:10px;height:10px;background:#f59e0b;border-radius:50%"></div>
      <h1 style="color:white;margin:0;font-size:20px;font-weight:700">TenderRadar</h1>
      <span style="color:#64748b;font-size:13px;margin-left:auto">{datetime.now().strftime('%d %b %Y, %I:%M %p')}</span>
    </div>
    <div style="padding:24px 28px">
      <p style="color:#475569;font-size:15px;margin:0 0 20px">
        Found <strong style="color:#0f172a">{len(tenders)} new tender(s)</strong> matching your profile (score ≥ {MIN_RELEVANCE_SCORE}).
      </p>
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <thead>
          <tr style="background:#f8fafc">
            <th style="padding:10px 8px;text-align:left;color:#64748b;font-weight:500;font-size:12px;text-transform:uppercase;border-bottom:2px solid #e2e8f0">Tender</th>
            <th style="padding:10px 8px;text-align:left;color:#64748b;font-weight:500;font-size:12px;text-transform:uppercase;border-bottom:2px solid #e2e8f0">Category</th>
            <th style="padding:10px 8px;text-align:left;color:#64748b;font-weight:500;font-size:12px;text-transform:uppercase;border-bottom:2px solid #e2e8f0">Value</th>
            <th style="padding:10px 8px;text-align:left;color:#64748b;font-weight:500;font-size:12px;text-transform:uppercase;border-bottom:2px solid #e2e8f0">Deadline</th>
            <th style="padding:10px 8px;text-align:center;color:#64748b;font-weight:500;font-size:12px;text-transform:uppercase;border-bottom:2px solid #e2e8f0">Score</th>
            <th style="padding:10px 8px;border-bottom:2px solid #e2e8f0"></th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <div style="background:#f8fafc;padding:16px 28px;border-top:1px solid #e2e8f0">
      <p style="color:#94a3b8;font-size:12px;margin:0">TenderRadar — automated tender monitoring. Scores are AI-generated estimates.</p>
    </div>
  </div>
</body>
</html>"""


# ── Telegram ───────────────────────────────────────────────────────────

def _send_telegram(tender: dict) -> None:
    score = tender.get("score", 0)
    score_emoji = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"

    text = (
        f"*📋 New Tender — TenderRadar*\n\n"
        f"*{tender.get('title','')[:120]}*\n\n"
        f"🏛 Portal: `{tender.get('portal','')}`\n"
        f"📁 Category: {tender.get('category','')}\n"
        f"💰 Value: {tender.get('value_str', 'N/A')}\n"
        f"⏰ Deadline: {tender.get('deadline', 'N/A')}\n"
        f"📎 Ref: `{tender.get('ref_no','')}`\n"
        f"{score_emoji} Score: *{score}/10*\n\n"
        f"[View Tender]({tender.get('url','#')})"
    )

    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": "true"
    }).encode()

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        data=data
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
        if not result.get("ok"):
            raise Exception(f"Telegram API error: {result}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_alerts()
