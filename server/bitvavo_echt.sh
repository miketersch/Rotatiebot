#!/usr/bin/env bash
sed -i "s|^BITVAVO_MODUS=.*|BITVAVO_MODUS=echt|" /etc/rotatiebot/env && echo "Bitvavo-bot staat nu op ECHT. Eerstvolgende run: morgen 08:20. Terug naar droogloop: bash /opt/rotatiebot/app/server/bitvavo_droog.sh"
