#!/usr/bin/env bash
# Werkt IBC bij naar een versie die de huidige IB Gateway (10.48+) ondersteunt.
set -e
V=${1:-3.24.2}
systemctl stop ibgateway 2>/dev/null || true
curl -sSL "https://github.com/IbcAlpha/IBC/releases/download/${V}/IBCLinux-${V}.zip" -o /var/tmp/ibc.zip
unzip -q -o /var/tmp/ibc.zip -d /opt/ibc && rm -f /var/tmp/ibc.zip
chmod +x /opt/ibc/*.sh /opt/ibc/scripts/*.sh
cp /opt/rotatiebot/app/server/start-gateway.sh /opt/ibc/start-gateway.sh && chmod +x /opt/ibc/start-gateway.sh
echo "IBC ${V} geïnstalleerd: $(cat /opt/ibc/version 2>/dev/null)"
