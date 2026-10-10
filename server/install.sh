#!/usr/bin/env bash
# Eenmalige installatie van de rotatiebot op een verse Ubuntu 24.04 server (Hetzner).
# Uitvoeren als root:  bash install.sh
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd /

BOT_USER=rotatiebot
BOT_HOME=/opt/rotatiebot
IBC_VERSION=3.20.0
GATEWAY_URL="https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh"

echo ">>> Pakketten"
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3 python3-venv python3-pip xvfb unzip curl ca-certificates \
    libxtst6 libxrender1 libxi6 libgtk-3-0 fonts-dejavu-core tzdata
timedatectl set-timezone Europe/Amsterdam

echo ">>> Gebruiker en mappen"
id -u $BOT_USER >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/$BOT_USER --shell /bin/bash $BOT_USER
mkdir -p $BOT_HOME /etc/rotatiebot
rm -rf $BOT_HOME/app && cp -r "$REPO_DIR" $BOT_HOME/app
chown -R $BOT_USER:$BOT_USER $BOT_HOME

echo ">>> Python-omgeving"
sudo -u $BOT_USER python3 -m venv $BOT_HOME/venv
sudo -u $BOT_USER $BOT_HOME/venv/bin/pip install -q --upgrade pip
sudo -u $BOT_USER $BOT_HOME/venv/bin/pip install -q pandas numpy yfinance ib_async matplotlib

echo ">>> IB Gateway"
GW_HOME=/home/$BOT_USER/ibgateway
if [ ! -d /home/$BOT_USER/Jts/ibgateway ] && [ ! -d $GW_HOME/jars ]; then
  mkdir -p /var/tmp/ibinstall && chown $BOT_USER:$BOT_USER /var/tmp/ibinstall
  curl -sSL "$GATEWAY_URL" -o /var/tmp/ibinstall/ibgateway.sh
  chmod +x /var/tmp/ibinstall/ibgateway.sh
  cd /var/tmp/ibinstall
  sudo -u $BOT_USER HOME=/home/$BOT_USER INSTALL4J_TEMP=/var/tmp/ibinstall ./ibgateway.sh -q -dir $GW_HOME
  cd /
  rm -rf /var/tmp/ibinstall
fi
# IBC verwacht de indeling ~/Jts/ibgateway/<versienummer>/
if [ -d $GW_HOME/jars ]; then
  GW_VERSION=$(ls $GW_HOME/jars | grep -oE 'jts4launch-[0-9]+' | head -1 | sed 's/jts4launch-//')
  [ -n "$GW_VERSION" ] || GW_VERSION=$(grep -oE 'version=[0-9]+' $GW_HOME/.install4j/i4jparams.conf 2>/dev/null | head -1 | cut -d= -f2)
  [ -n "$GW_VERSION" ] || { echo "Kan gateway-versie niet bepalen"; ls $GW_HOME/jars | head; exit 1; }
  mkdir -p /home/$BOT_USER/Jts/ibgateway
  rm -rf /home/$BOT_USER/Jts/ibgateway/$GW_VERSION
  mv $GW_HOME /home/$BOT_USER/Jts/ibgateway/$GW_VERSION
  chown -R $BOT_USER:$BOT_USER /home/$BOT_USER/Jts
fi
# herstel: map hernoemen als de naam niet klopt met de jar-versie
for d in /home/$BOT_USER/Jts/ibgateway/*/; do
  [ -d "$d/jars" ] || continue
  echt=$(ls "$d/jars" | grep -oE 'jts4launch-[0-9]+' | head -1 | sed 's/jts4launch-//')
  naam=$(basename "$d")
  if [ -n "$echt" ] && [ "$echt" != "$naam" ]; then
    rm -rf "/home/$BOT_USER/Jts/ibgateway/$echt"; mv "$d" "/home/$BOT_USER/Jts/ibgateway/$echt"
  fi
done
GW_VERSION=$(ls /home/$BOT_USER/Jts/ibgateway/ | grep -E '^[0-9]+$' | sort -n | tail -1)
[ -n "$GW_VERSION" ] || { echo "IB Gateway niet gevonden onder /home/$BOT_USER/Jts/ibgateway"; exit 1; }
echo "Gateway versie: $GW_VERSION"

echo ">>> IBC (automatisch inloggen)"
if [ ! -d /opt/ibc ]; then
  curl -sSL "https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/IBCLinux-${IBC_VERSION}.zip" -o /var/tmp/ibc.zip
  mkdir -p /opt/ibc && unzip -q -o /var/tmp/ibc.zip -d /opt/ibc && rm /var/tmp/ibc.zip
  chmod +x /opt/ibc/*.sh /opt/ibc/scripts/*.sh
fi
echo ">>> Configuratie"
[ -f /etc/rotatiebot/env ] || cp $BOT_HOME/app/server/env.example /etc/rotatiebot/env
[ -f /etc/rotatiebot/ibc-config.ini ] || cp $BOT_HOME/app/server/ibc-config.ini /etc/rotatiebot/ibc-config.ini
chmod 600 /etc/rotatiebot/env /etc/rotatiebot/ibc-config.ini
chown $BOT_USER:$BOT_USER /etc/rotatiebot/env /etc/rotatiebot/ibc-config.ini
sed -i "s|^TWS_MAJOR_VRSN=.*|TWS_MAJOR_VRSN=$GW_VERSION|" $BOT_HOME/app/server/start-gateway.sh
cp $BOT_HOME/app/server/start-gateway.sh /opt/ibc/start-gateway.sh && chmod +x /opt/ibc/start-gateway.sh
mkdir -p /home/$BOT_USER/ibc/logs /home/$BOT_USER/Jts/ibgateway/stable/jts.ini.d && chown -R $BOT_USER:$BOT_USER /home/$BOT_USER

echo ">>> systemd"
cp $BOT_HOME/app/server/ibgateway.service /etc/systemd/system/
cp $BOT_HOME/app/server/rotatiebot.service /etc/systemd/system/
cp $BOT_HOME/app/server/rotatiebot.timer /etc/systemd/system/
echo "$BOT_USER ALL=(root) NOPASSWD: /usr/bin/systemctl start ibgateway, /usr/bin/systemctl stop ibgateway" > /etc/sudoers.d/rotatiebot
chmod 440 /etc/sudoers.d/rotatiebot
systemctl daemon-reload
systemctl enable rotatiebot.timer
systemctl start rotatiebot.timer

echo ">>> Firewall (alleen SSH open)"
apt-get install -y -q ufw >/dev/null
ufw --force reset >/dev/null; ufw default deny incoming >/dev/null; ufw default allow outgoing >/dev/null
ufw allow OpenSSH >/dev/null; ufw --force enable >/dev/null

cat <<EOF

Klaar. Nog twee dingen invullen:
  nano /etc/rotatiebot/env              (Telegram, modus paper/echt)
  nano /etc/rotatiebot/ibc-config.ini   (IBKR gebruikersnaam en wachtwoord)
Daarna testen:
  sudo -u rotatiebot bash -c 'set -a; . /etc/rotatiebot/env; set +a; /opt/rotatiebot/venv/bin/python /opt/rotatiebot/app/run_maandelijks.py --forceer --droog'
EOF
