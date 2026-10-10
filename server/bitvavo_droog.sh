#!/usr/bin/env bash
sed -i "s|^BITVAVO_MODUS=.*|BITVAVO_MODUS=droog|" /etc/rotatiebot/env && echo "Bitvavo-bot staat op droogloop."
