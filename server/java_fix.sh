#!/usr/bin/env bash
# Zorgt dat er een Java is voor IB Gateway en zet het nieuwe startscript neer.
set -e
GW=/home/rotatiebot/Jts/ibgateway/1050
if [ ! -x "$GW/jre/bin/java" ] && [ ! -x "$GW/.install4j/jre/bin/java" ]; then
  echo ">>> Geen meegeleverde JRE gevonden, systeem-Java installeren"
  apt-get install -y -q openjdk-17-jre-headless >/dev/null
fi
# install4j-config van de gateway: verwijzing naar de verdwenen tijdelijke JRE verwijderen
for f in "$GW/.install4j/pref_jre.cfg" "$GW/.install4j/inst_jre.cfg"; do
  [ -f "$f" ] && grep -q ibinstall "$f" && rm -f "$f" && echo "oude JRE-verwijzing verwijderd: $f"
done
GWV=$(ls /home/rotatiebot/Jts/ibgateway/ | grep -E '^[0-9]+$' | sort -n | tail -1)
sed "s|^TWS_MAJOR_VRSN=.*|TWS_MAJOR_VRSN=$GWV|" /opt/rotatiebot/app/server/start-gateway.sh > /opt/ibc/start-gateway.sh
chmod +x /opt/ibc/start-gateway.sh
echo "Startscript bijgewerkt (gateway $GWV)."
ls -d "$GW/jre" "$GW/.install4j/jre" /usr/lib/jvm/* 2>/dev/null || true
