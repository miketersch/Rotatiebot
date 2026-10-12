#!/usr/bin/env bash
# Herstelt de boekhouding van de Bitvavo-bot uit de handelshistorie (na verlies van output/bitvavo_state.json).
sudo -u rotatiebot bash -c "set -a; . /etc/rotatiebot/env; set +a; cd /opt/rotatiebot/app && /opt/rotatiebot/venv/bin/python bitvavo/herstel_state.py ${1:-2026-10-12}"
