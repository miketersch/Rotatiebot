"""Verkenning: universum, lookback, canary (Keller DAA) en hefboom."""
import itertools, pandas as pd, numpy as np
from strategie import Config, backtest, statistieken, momentum_score

prijzen = pd.read_csv("data/assetklassen.csv", index_col=0, parse_dates=True).ffill()
pd.set_option("display.width", 220); pd.set_option("display.float_format", lambda x: f"{x:,.3f}")

def run(naam, cfg):
    r = backtest(prijzen, cfg); s = statistieken(r["equity"], naam); s["kosten"] = r["kosten_totaal"]; return s

U_ALL = ["SPY", "EFA", "EEM", "VNQ", "DBC", "GLD", "TLT"]
U_NO_DBC = ["SPY", "EFA", "EEM", "VNQ", "GLD", "TLT"]
U_GEM = ["SPY", "EFA", "EEM"]            # Antonacci-stijl aandelen only, veilig=IEF/TLT
U_CORE = ["SPY", "EFA", "EEM", "GLD", "TLT"]

rows = []
for (un, ul), (lb, lbl), wk, n in itertools.product(
        [("alle7", U_ALL), ("zonderDBC", U_NO_DBC), ("GEM3", U_GEM), ("core5", U_CORE)],
        [("13612W", (12, 4, 2, 1)), ("12m", (0, 0, 0, 1)), ("6m", (0, 0, 1, 0)), ("3-6-12", (0, 1, 1, 1))],
        [False], [1, 2, 3]):
    if n > len(ul): continue
    s = run(f"{un}|{lb}|top{n}", Config(risico_assets=ul, gewichten_1_3_6_12=lbl, top_n=n, wekelijkse_check=wk))
    s.update(universum=un, lookback=lb, top_n=n); rows.append(s)
df = pd.DataFrame(rows)
print(df.sort_values("calmar", ascending=False)[["strategie", "CAGR", "vol", "sharpe", "max_drawdown", "calmar", "slechtste_jaar", "eindwaarde_x"]].to_string(index=False))
print("\nGemiddeld per universum:"); print(df.groupby("universum")[["CAGR", "sharpe", "max_drawdown"]].mean())
print("\nGemiddeld per lookback:"); print(df.groupby("lookback")[["CAGR", "sharpe", "max_drawdown"]].mean())
print("\nGemiddeld per top_n:"); print(df.groupby("top_n")[["CAGR", "sharpe", "max_drawdown"]].mean())
