#!/usr/bin/env bash
# Eenmalig: herbalancering NU uitvoeren met echte orders (vereist MODUS=echt in /etc/rotatiebot/env).
set -a; . /etc/rotatiebot/env; set +a
[ "$MODUS" = "echt" ] || { echo "MODUS staat op droog; eerst instellen.sh met 'ja' bij echte orders."; exit 1; }
exec sudo -u rotatiebot --preserve-env=MODUS,IB_PORT,IB_HOST,IB_CLIENT_ID,TELEGRAM_TOKEN,TELEGRAM_CHAT_ID,SMTP_HOST,SMTP_PORT,SMTP_USER,SMTP_PASS,MAIL_TO,DREMPEL_EUR,CASH_BUFFER,WACHT_LOGIN_SEC \
  /opt/rotatiebot/venv/bin/python /opt/rotatiebot/app/run_maandelijks.py --forceer
