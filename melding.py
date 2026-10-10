"""Meldingen naar Telegram (en optioneel e-mail). Instellen via omgevingsvariabelen in /etc/rotatiebot/env."""
import os, json, urllib.request, urllib.parse, smtplib
from email.mime.text import MIMEText


def telegram(tekst: str) -> bool:
    token, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": tekst[:4000]}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20)
        return True
    except Exception as e:
        print("Telegram mislukt:", e)
        return False


def email(onderwerp: str, tekst: str) -> bool:
    host, user, pw, naar = (os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "MAIL_TO"))
    if not all([host, user, pw, naar]):
        return False
    try:
        msg = MIMEText(tekst)
        msg["Subject"], msg["From"], msg["To"] = onderwerp, user, naar
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=30) as s:
            s.starttls(); s.login(user, pw); s.send_message(msg)
        return True
    except Exception as e:
        print("E-mail mislukt:", e)
        return False


def meld(onderwerp: str, tekst: str):
    """Stuurt naar alle ingestelde kanalen en print altijd naar de log."""
    print(f"\n=== {onderwerp} ===\n{tekst}\n")
    telegram(f"{onderwerp}\n\n{tekst}")
    email(onderwerp, tekst)
