"""
Geeft de huidige doelallocatie: wat de bot NU zou aanhouden op basis van de laatste koersen.
Gebruik:  python signalen.py [pad/naar/prijzen.csv] [kapitaal_in_euro]

Prijzenbestand: CSV met kolom Date en per ticker een kolom met dividend-gecorrigeerde slotkoersen.
Met een werkende internetverbinding haalt data_ophalen.py dit bestand automatisch op.
"""
import sys
import pandas as pd, numpy as np
from strategie import Config, momentum_score, doelgewichten_op, TRADING_DAYS

pad = sys.argv[1] if len(sys.argv) > 1 else "data/assetklassen.csv"
kapitaal = float(sys.argv[2]) if len(sys.argv) > 2 else 10_000.0
cfg = Config()

prijzen = pd.read_csv(pad, index_col=0, parse_dates=True).sort_index().ffill()
rend = prijzen.pct_change()
score = momentum_score(prijzen, cfg)
sma = prijzen.rolling(cfg.sma_dagen).mean()
vol = rend.rolling(cfg.vol_dagen).std() * np.sqrt(TRADING_DAYS)
dag = prijzen.index[-1]

gew = doelgewichten_op(dag, prijzen, score, sma, vol, cfg)

print(f"\nSignalen per {dag.date()}  (kapitaal {kapitaal:,.0f} euro)\n")
tabel = pd.DataFrame({
    "koers": prijzen.loc[dag],
    "momentum 3/6/12": score.loc[dag],
    "boven SMA200": prijzen.loc[dag] > sma.loc[dag],
    "vol 60d": vol.loc[dag],
    "doelgewicht": gew,
    "bedrag": gew * kapitaal,
}).sort_values("momentum 3/6/12", ascending=False)
pd.set_option("display.width", 160)
print(tabel.to_string(float_format=lambda x: f"{x:,.3f}"))
cash = 1 - gew.sum()
print(f"\nCash: {cash:.1%}  ({cash * kapitaal:,.0f} euro)")
print("\nUitleg: een risico-asset komt alleen in aanmerking als momentum > 0 EN koers > SMA200.")
print("De top 3 wordt gekozen, gewogen naar omgekeerde volatiliteit. Lege plekken gaan naar IEF (mits in opwaartse trend), anders cash.")
