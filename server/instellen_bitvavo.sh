#!/usr/bin/env bash
set -e
ENV=/etc/rotatiebot/env
zet_env() { grep -q "^$1=" "$ENV" && sed -i "s|^$1=.*|$1=$2|" "$ENV" || echo "$1=$2" >> "$ENV"; }
read -r -p "Bitvavo API Key: " K
read -r -p "Bitvavo API Secret: " S
read -r -p "Budget voor de bot in euro [1000]: " B; B=${B:-1000}
[ -n "$K" ] && [ -n "$S" ] || { echo "Key en secret zijn verplicht"; exit 1; }
zet_env BITVAVO_KEY "$K"; zet_env BITVAVO_SECRET "$S"; zet_env BITVAVO_BUDGET_EUR "$B"; zet_env BITVAVO_MODUS droog
chmod 600 "$ENV"
cp /opt/rotatiebot/app/server/bitvavo.service /opt/rotatiebot/app/server/bitvavo.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now bitvavo.timer
echo; echo "=== proefrun (droogloop) ==="
sudo -u rotatiebot bash -c "set -a; . $ENV; set +a; /opt/rotatiebot/venv/bin/python /opt/rotatiebot/app/bitvavo/trendbot.py --droog --altijd-melden"
echo; echo "Staat in droogloop. Echt aanzetten: bash /opt/rotatiebot/app/server/bitvavo_echt.sh"
