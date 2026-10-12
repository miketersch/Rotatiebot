"""Dagrapport van de observatiefase: wat gebeurde er, en wat hadden een paar strategieën opgeleverd."""
import os, sys, time, statistics as st
HIER = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HIER); sys.path.insert(0, os.path.join(HIER, ".."))
from simulatie import Regels, simuleer, laad
from melding import meld

DB = os.environ.get("SNIPER_DB", os.path.join(HIER, "..", "output", "sniper.db"))
UREN = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0
nu = time.time()
tot = nu - 1 * 3600                      # tokens moeten 1 uur gevolgd zijn
van = tot - UREN * 3600
data = laad(DB, van, tot)
n = len(data)
if n == 0:
    meld("Sniper observatie", "Geen tokens in het venster. Draait de observer? (systemctl status sniper-observer)")
    sys.exit(0)

met_trades = [d for d in data if len(d[1]) > 0]
graduated = sum(1 for t, _ in data if t["graduated"])
maker_dump_5m = 0; dood_5m = 0
for t, tr in met_trades:
    if any((not b) and u == t["maker"] and ts - t["ts"] < 300 for ts, b, s, k, u, vs, vt in tr): maker_dump_5m += 1
    if not any(ts - t["ts"] > 300 for ts, *_ in tr): dood_5m += 1

regels = {
    "A: blind, 3s, geen filter": Regels(min_kopers=0, geen_maker_verkoop=False),
    "B: 3s, maker niet verkocht": Regels(min_kopers=0, geen_maker_verkoop=True),
    "C: 20s, >=5 kopers, >=1 SOL in": Regels(vertraging_sec=20, min_kopers=5, min_sol_in=1.0),
    "D: 45s, >=10 kopers, >=2 SOL in": Regels(vertraging_sec=45, min_kopers=10, min_sol_in=2.0),
    "E: 45s, >=10 kopers, tp 3x, stop 40%": Regels(vertraging_sec=45, min_kopers=10, min_sol_in=2.0, tp_x=3.0, stop=0.4),
}
regels_uit = []
for naam, r in regels.items():
    res = [x for x in (simuleer(t, tr, r) for t, tr in data) if x]
    if not res:
        regels_uit.append(f"{naam}: geen instap"); continue
    w = [x["winst_sol"] for x in res]; tot_w = sum(w); hit = sum(1 for x in w if x > 0) / len(w)
    ingezet = len(res) * r.inzet_sol
    regels_uit.append(f"{naam}\n   {len(res)} trades, hit {hit:.0%}, netto {tot_w:+.2f} SOL op {ingezet:.1f} ingezet ({tot_w/ingezet:+.0%}), "
                      f"beste {max(w):+.2f}, mediaan {st.median(w):+.3f}, >=2x gehaald {sum(1 for x in res if x['piek_x']>=2)/len(res):.0%}")

tekst = (f"Venster: {UREN:.0f} uur (tokens van {time.strftime('%d-%m %H:%M', time.localtime(van))} tot {time.strftime('%d-%m %H:%M', time.localtime(tot))})\n"
         f"Nieuwe tokens: {n}\nMet minstens 1 trade: {len(met_trades)} ({len(met_trades)/n:.0%})\n"
         f"Maker verkoopt binnen 5 min: {maker_dump_5m} ({maker_dump_5m/max(1,len(met_trades)):.0%} van verhandelde)\n"
         f"Dood binnen 5 min (geen trades meer): {dood_5m} ({dood_5m/max(1,len(met_trades)):.0%})\n"
         f"Gegradueerd naar PumpSwap: {graduated} ({graduated/n:.1%})\n\nPapieren strategieën (0,2 SOL per trade, kosten meegerekend):\n" + "\n".join(regels_uit))
meld("Sniper observatie, dagrapport", tekst)
