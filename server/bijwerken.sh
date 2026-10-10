#!/usr/bin/env bash
# Haalt de nieuwste versie van GitHub en zet hem in /opt/rotatiebot/app (instellingen blijven staan).
set -e
cd /root/rotatiebot && git pull
rm -rf /opt/rotatiebot/app && cp -r /root/rotatiebot /opt/rotatiebot/app
chown -R rotatiebot:rotatiebot /opt/rotatiebot/app
chmod +x /opt/rotatiebot/app/server/*.sh
cp /opt/rotatiebot/app/server/rotatiebot.service /opt/rotatiebot/app/server/rotatiebot.timer /opt/rotatiebot/app/server/ibgateway.service /etc/systemd/system/
systemctl daemon-reload
echo "Bijgewerkt naar $(git -C /root/rotatiebot log --oneline | head -1)"
