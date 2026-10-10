#!/usr/bin/env bash
systemctl start sniper-rapport.service && journalctl -u sniper-rapport -n 40 --no-pager
