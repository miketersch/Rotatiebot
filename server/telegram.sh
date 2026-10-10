#!/usr/bin/env bash
# Alleen Telegram instellen en een testbericht sturen.
set -e
ENV=/etc/rotatiebot/env
zet_env() { grep -q "^$1=" "$ENV" && sed -i "s|^$1=.*|$1=$2|" "$ENV" || echo "$1=$2" >> "$ENV"; }
read -r -p "Telegram bot-token: " TGTOKEN
read -r -p "Telegram chat-id: " TGCHAT
[ -n "$TGTOKEN" ] && [ -n "$TGCHAT" ] || { echo "Beide zijn nodig"; exit 1; }
zet_env TELEGRAM_TOKEN "$TGTOKEN"; zet_env TELEGRAM_CHAT_ID "$TGCHAT"
chmod 600 "$ENV"
antw=$(curl -s -X POST "https://api.telegram.org/bot$TGTOKEN/sendMessage" -d chat_id="$TGCHAT" -d text="Rotatiebot is gekoppeld aan deze Telegram-chat.")
echo "$antw" | grep -q '"ok":true' && echo "Gelukt: testbericht verstuurd." || { echo "Mislukt. Antwoord van Telegram:"; echo "$antw"; }
