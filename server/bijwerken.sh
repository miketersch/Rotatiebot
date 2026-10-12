#!/usr/bin/env bash
# Haalt de nieuwste versie van GitHub en zet hem in /opt/rotatiebot/app (instellingen blijven staan).
set -e
cd /root/rotatiebot && git pull
rm -rf /opt/rotatiebot/app && cp -r /root/rotatiebot /opt/rotatiebot/app
chown -R rotatiebot:rotatiebot /opt/rotatiebot/app
chmod +x /opt/rotatiebot/app/server/*.sh
cp /opt/rotatiebot/app/server/*.service /opt/rotatiebot/app/server/*.timer /etc/systemd/system/
/opt/rotatiebot/venv/bin/pip install -q websockets base58
mkdir -p /opt/rotatiebot/app/output && chown -R rotatiebot:rotatiebot /opt/rotatiebot/app/output
bash /opt/rotatiebot/app/server/sudoers_fix.sh >/dev/null
systemctl daemon-reload
systemctl is-active --quiet sniper-observer && systemctl restart sniper-observer || true
echo "Bijgewerkt naar $(git -C /root/rotatiebot log --oneline | head -1)"
