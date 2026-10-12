"""
Herstelt de boekhouding van de trendbot (output/bitvavo_state.json) uit de echte handelshistorie op Bitvavo.
Telt alle BTC-EUR en ETH-EUR fills vanaf een startmoment (standaard: 12-10-2026 00:00 lokale tijd) op.
Gebruik: herstel_state.py [YYYY-MM-DD]
"""
import os, sys, json, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendbot as tb

start = dt.datetime.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2026-10-12")
start_ms = int(start.timestamp() * 1000)
state = {"posities": {}, "cash": tb.BUDGET, "eur_ingelegd": tb.BUDGET}
regels = []
for c in tb.COINS:
    fills = tb.api("GET", f"/trades?market={c}-EUR&start={start_ms}&limit=500")
    if isinstance(fills, dict) and "error" in fills:
        sys.exit(f"Bitvavo fout: {fills}")
    pos = 0.0
    for f in fills:
        amt, prijs, fee = float(f["amount"]), float(f["price"]), float(f.get("fee", 0))
        quote = amt * prijs
        if f["side"] == "buy":
            pos += amt; state["cash"] -= quote
        else:
            pos -= amt; state["cash"] += quote
        if f.get("feeCurrency") == "EUR":
            state["cash"] -= fee
        regels.append(f"{c} {f['side']} {amt:.6f} @ {prijs:,.2f} (fee {fee} {f.get('feeCurrency')})")
    state["posities"][c] = round(max(pos, 0.0), 8)
state["cash"] = round(state["cash"], 2)
tb.bewaar_state(state)
print("\n".join(regels) or "geen fills gevonden sinds " + start.isoformat())
print("Hersteld:", json.dumps(state))
