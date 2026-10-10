#!/usr/bin/env bash
# Helius-key opslaan, observer installeren en starten.
set -e
ENV=/etc/rotatiebot/env
zet_env() { grep -q "^$1=" "$ENV" && sed -i "s|^$1=.*|$1=$2|" "$ENV" || echo "$1=$2" >> "$ENV"; }
read -r -p "Helius API-key: " KEY
[ -n "$KEY" ] || { echo "Key is verplicht"; exit 1; }
zet_env HELIUS_API_KEY "$KEY"; chmod 600 "$ENV"
/opt/rotatiebot/venv/bin/pip install -q websockets base58
cp /opt/rotatiebot/app/server/sniper-observer.service /opt/rotatiebot/app/server/sniper-rapport.service /opt/rotatiebot/app/server/sniper-rapport.timer /etc/systemd/system/
mkdir -p /opt/rotatiebot/app/output && chown rotatiebot:rotatiebot /opt/rotatiebot/app/output
systemctl daemon-reload
systemctl enable --now sniper-observer sniper-rapport.timer
sleep 8
echo; echo "=== status ==="; systemctl --no-pager status sniper-observer | head -12
echo; echo "Laatste logregels:"; journalctl -u sniper-observer -n 5 --no-pager
echo; echo "Rapport op aanvraag: bash /opt/rotatiebot/app/server/sniper_rapport.sh"
