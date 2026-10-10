#!/usr/bin/env bash
# Proefrun: start de gateway, wacht op de 2FA-goedkeuring, doet een droogloop en stopt de gateway.
set -a; . /etc/rotatiebot/env; set +a
exec sudo -u rotatiebot --preserve-env=MODUS,IB_PORT,IB_HOST,IB_CLIENT_ID,TELEGRAM_TOKEN,TELEGRAM_CHAT_ID,SMTP_HOST,SMTP_PORT,SMTP_USER,SMTP_PASS,MAIL_TO,DREMPEL_EUR,CASH_BUFFER,WACHT_LOGIN_SEC \
  /opt/rotatiebot/venv/bin/python /opt/rotatiebot/app/run_maandelijks.py --forceer --droog
