#!/usr/bin/env bash
# Start IB Gateway headless (Xvfb) met IBC voor automatisch inloggen. Gestart door ibgateway.service.
set -e
TWS_MAJOR_VRSN=1050
IBC_PATH=/opt/ibc
IBC_INI=/etc/rotatiebot/ibc-config.ini
TWS_PATH=/home/rotatiebot/Jts
LOG_PATH=/home/rotatiebot/ibc/logs
GW_DIR="${TWS_PATH}/ibgateway/${TWS_MAJOR_VRSN}"

# Java: de meegeleverde JRE van de gateway, anders de systeem-Java
JAVA_PATH=""
for d in "${GW_DIR}/jre" "${GW_DIR}/.install4j/jre" /home/rotatiebot/.install4j/jre* /usr/lib/jvm/java-17-openjdk-amd64 /usr/lib/jvm/default-java; do
  if [ -x "$d/bin/java" ]; then JAVA_PATH="$d/bin"; break; fi
done
[ -n "$JAVA_PATH" ] || { echo "Geen Java gevonden"; exit 1; }
echo "Java: $JAVA_PATH"

export DISPLAY=:1
Xvfb :1 -screen 0 1280x900x24 -nolisten tcp &
XVFB_PID=$!
trap 'kill $XVFB_PID 2>/dev/null' EXIT
sleep 2
exec "${IBC_PATH}/scripts/ibcstart.sh" "${TWS_MAJOR_VRSN}" -g \
  --tws-path="${TWS_PATH}" --ibc-path="${IBC_PATH}" --ibc-ini="${IBC_INI}" \
  --java-path="${JAVA_PATH}" --on2fatimeout=restart
