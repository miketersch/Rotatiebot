"""
Live/paper trading via Alpaca (alpaca.markets). Commissievrij, gratis paper-account, Amerikaanse ETF's.

Setup (eenmalig):
  pip install alpaca-py yfinance pandas numpy
  export ALPACA_KEY=...        # API-key uit het Alpaca dashboard
  export ALPACA_SECRET=...
  export ALPACA_PAPER=1       # 1 = paper trading (nepgeld), 0 = echt geld

Gebruik (elke laatste handelsdag van de maand, na sluiting of de ochtend erna):
  python data_ophalen.py && python live_alpaca.py

Wat het doet:
  1. leest de laatste koersen en berekent de doelgewichten (zelfde code als de backtest)
  2. haalt de huidige posities op bij Alpaca
  3. plaatst marktorders voor het verschil (fractional shares), met een drempel zodat
     minieme verschillen niet steeds worden bijgehandeld
  4. schrijft een logregel naar output/live_log.csv

Veiligheid: de API-key hoort ALLEEN handelsrechten te hebben, geen opnames. Zet de key nooit in de code.
"""
import os, sys, datetime as dt
import pandas as pd, numpy as np
from strategie import Config, momentum_score, doelgewichten_op, TRADING_DAYS

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
except ImportError:
    sys.exit("alpaca-py ontbreekt: pip install alpaca-py")

KEY, SECRET = os.environ.get("ALPACA_KEY"), os.environ.get("ALPACA_SECRET")
PAPER = os.environ.get("ALPACA_PAPER", "1") == "1"
DREMPEL = 0.02          # alleen handelen als het gewichtsverschil > 2 procentpunt is
DROOGLOOP = "--echt" not in sys.argv   # zonder --echt worden orders alleen geprint

if not KEY or not SECRET:
    sys.exit("Zet ALPACA_KEY en ALPACA_SECRET als omgevingsvariabelen.")

cfg = Config()
prijzen = pd.read_csv("data/assetklassen.csv", index_col=0, parse_dates=True).sort_index().ffill()
rend = prijzen.pct_change()
score = momentum_score(prijzen, cfg)
sma = prijzen.rolling(cfg.sma_dagen).mean()
vol = rend.rolling(cfg.vol_dagen).std() * np.sqrt(TRADING_DAYS)
dag = prijzen.index[-1]
doel = doelgewichten_op(dag, prijzen, score, sma, vol, cfg)

client = TradingClient(KEY, SECRET, paper=PAPER)
acct = client.get_account()
equity = float(acct.equity)
posities = {p.symbol: float(p.market_value) for p in client.get_all_positions()}
huidig = pd.Series({t: posities.get(t, 0.0) / equity for t in prijzen.columns})

print(f"{'PAPER' if PAPER else 'ECHT GELD'} | portefeuillewaarde {equity:,.2f} USD | signalen per {dag.date()} | {'DROOGLOOP' if DROOGLOOP else 'ORDERS WORDEN GEPLAATST'}")
print(pd.DataFrame({"huidig": huidig, "doel": doel, "verschil": doel - huidig}).round(3).to_string())

orders = []
for t in prijzen.columns:
    delta = doel[t] - huidig[t]
    if abs(delta) < DREMPEL:
        continue
    bedrag = round(abs(delta) * equity, 2)
    side = OrderSide.BUY if delta > 0 else OrderSide.SELL
    # verkopen gaat in aandelen (notional sell is niet overal toegestaan): bereken aantal uit laatste koers
    req = MarketOrderRequest(symbol=t, notional=bedrag, side=side, time_in_force=TimeInForce.DAY)
    orders.append((t, side.value, bedrag))
    if not DROOGLOOP:
        client.submit_order(req)

print("\nOrders:" if orders else "\nGeen orders nodig.")
for o in orders:
    print(f"  {o[1]:4s} {o[0]:4s} {o[2]:>10,.2f} USD")

os.makedirs("output", exist_ok=True)
with open("output/live_log.csv", "a") as f:
    f.write(f"{dt.datetime.now().isoformat(timespec='seconds')},{'paper' if PAPER else 'live'},{equity:.2f},"
            + ";".join(f"{t}={doel[t]:.3f}" for t in doel.index if doel[t] > 0)
            + f",orders={len(orders)},droogloop={DROOGLOOP}\n")
