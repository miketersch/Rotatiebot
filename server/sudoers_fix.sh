#!/usr/bin/env bash
# Sudo-regels voor de bot-gebruiker (gateway en observer starten/stoppen) opnieuw schrijven en controleren.
set -e
cat > /etc/sudoers.d/rotatiebot <<'SUDO'
rotatiebot ALL=(root) NOPASSWD: /usr/bin/systemctl start ibgateway, /usr/bin/systemctl stop ibgateway, /usr/bin/systemctl start sniper-observer, /usr/bin/systemctl stop sniper-observer
SUDO
chmod 440 /etc/sudoers.d/rotatiebot
visudo -cf /etc/sudoers.d/rotatiebot
sudo -u rotatiebot sudo -n systemctl stop sniper-observer && echo "sudo-test OK"
sudo -u rotatiebot sudo -n systemctl start sniper-observer
