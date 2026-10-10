#!/usr/bin/env bash
# Start IB Gateway headless (Xvfb) met IBC voor automatisch inloggen. Gestart door ibgateway.service.
set -e
TWS_MAJOR_VRSN=1030
IBC_PATH=/opt/ibc
IBC_INI=/etc/rotatiebot/ibc-config.ini
TWS_PATH=/home/rotatiebot/Jts
LOG_PATH=/home/rotatiebot/ibc/logs
export DISPLAY=:1
Xvfb :1 -screen 0 1280x900x24 -nolisten tcp &
XVFB_PID=$!
trap 'kill $XVFB_PID 2>/dev/null' EXIT
sleep 2
exec "${IBC_PATH}/scripts/ibcstart.sh" "${TWS_MAJOR_VRSN}" -g \
  --tws-path="${TWS_PATH}" --ibc-path="${IBC_PATH}" --ibc-ini="${IBC_INI}" \
  --on2fatimeout=restart
