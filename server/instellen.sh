#!/usr/bin/env bash
# Vraagt de inloggegevens en schrijft ze in /etc/rotatiebot (alleen leesbaar voor de bot).
set -e
ENV=/etc/rotatiebot/env
INI=/etc/rotatiebot/ibc-config.ini
[ -f "$ENV" ] && [ -f "$INI" ] || { echo "Eerst install.sh draaien"; exit 1; }

zet_env() { grep -q "^$1=" "$ENV" && sed -i "s|^$1=.*|$1=$2|" "$ENV" || echo "$1=$2" >> "$ENV"; }
zet_ini() { grep -q "^$1=" "$INI" && sed -i "s|^$1=.*|$1=$2|" "$INI" || echo "$1=$2" >> "$INI"; }

echo "=== IBKR ==="
read -r -p "Modus (paper/live) [paper]: " MODE; MODE=${MODE:-paper}
read -r -p "IBKR gebruikersnaam ($MODE): " IBUSER
read -r -s -p "IBKR wachtwoord ($MODE), typen blijft onzichtbaar: " IBPASS; echo
[ -n "$IBUSER" ] && [ -n "$IBPASS" ] || { echo "Gebruikersnaam en wachtwoord zijn verplicht"; exit 1; }
zet_ini IbLoginId "$IBUSER"
zet_ini IbPassword "$IBPASS"
zet_ini TradingMode "$MODE"
if [ "$MODE" = "live" ]; then zet_ini OverrideTwsApiPort 4001; zet_env IB_PORT 4001; else zet_ini OverrideTwsApiPort 4002; zet_env IB_PORT 4002; fi

echo
echo "=== Telegram (leeg laten = overslaan) ==="
read -r -p "Bot-token: " TGTOKEN
read -r -p "Chat-id: " TGCHAT
[ -n "$TGTOKEN" ] && zet_env TELEGRAM_TOKEN "$TGTOKEN"
[ -n "$TGCHAT" ] && zet_env TELEGRAM_CHAT_ID "$TGCHAT"

echo
read -r -p "Orders echt plaatsen? (ja/nee) [nee]: " ECHT
if [ "$ECHT" = "ja" ]; then zet_env MODUS echt; else zet_env MODUS droog; fi

chmod 600 "$ENV" "$INI"; chown rotatiebot:rotatiebot "$ENV" "$INI"
echo
echo "Opgeslagen. Modus: $MODE, orders: $( [ "$ECHT" = "ja" ] && echo echt || echo droogloop )."
if [ -n "$TGTOKEN" ] && [ -n "$TGCHAT" ]; then
  curl -s -X POST "https://api.telegram.org/bot$TGTOKEN/sendMessage" -d chat_id="$TGCHAT" -d text="Rotatiebot is gekoppeld." >/dev/null && echo "Testbericht naar Telegram gestuurd." || echo "Telegram-test mislukt, controleer token en chat-id."
fi
echo
echo "Testen (gateway start, keur de IBKR-melding op je telefoon goed):"
echo "  bash /opt/rotatiebot/app/server/test.sh"
