"""Draait de volledige backtest, benchmarks, robuustheidstest en maakt de grafieken + rapport."""
import itertools, json, sys
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from strategie import Config, backtest, statistieken, buy_and_hold, vaste_mix

OUT = "output"
prijzen = pd.read_csv("data/assetklassen.csv", index_col=0, parse_dates=True).ffill()

# ---------- hoofdstrategie ----------
cfg = Config()
res = backtest(prijzen, cfg)
eq = res["equity"]
start = eq.index[0]

bench = {
    "Rotatiebot": eq,
    "SPY buy & hold": buy_and_hold(prijzen, "SPY", start),
    "60/40 (SPY/IEF)": vaste_mix(prijzen, {"SPY": 0.6, "IEF": 0.4}, start),
    "Gelijk gewogen 8 assets": vaste_mix(prijzen, {t: 1/8 for t in prijzen.columns}, start),
}
stats = pd.DataFrame([statistieken(v, k) for k, v in bench.items()]).set_index("strategie")
pd.set_option("display.width", 200); pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
print("\n=== HOOFDRESULTAAT", start.date(), "tot", eq.index[-1].date(), "===")
print(stats[["CAGR", "vol", "sharpe", "max_drawdown", "calmar", "slechtste_jaar", "pct_pos_maanden", "eindwaarde_x"]].to_string())
print("Totale transactiekosten over hele periode:", f"{res['kosten_totaal']:.2%}", "| aantal herbalanceringen:", len(res["trades"]))
print("waarvan tussentijdse crash-checks:", int((res["trades"]["type"] == "week-crashcheck").sum()))

# jaarrendementen
jaar = pd.DataFrame({k: v.resample("YE").last().pct_change() for k, v in bench.items()}).dropna()
jaar.index = jaar.index.year
print("\n=== JAARRENDEMENTEN ===")
print((jaar * 100).round(1))

# ---------- varianten ----------
varianten = {
    "basis (top3, invvol, SMA+abs, 3-6-12)": Config(),
    "met wekelijkse crash-check": Config(wekelijkse_check=True),
    "zonder SMA-filter": Config(gebruik_sma_filter=False),
    "zonder absoluut momentum": Config(gebruik_abs_momentum=False, gebruik_sma_filter=False),
    "gelijk gewogen ipv inv-vol": Config(weging="gelijk"),
    "top 1 (geconcentreerd)": Config(top_n=1),
    "top 2": Config(top_n=2),
    "top 4": Config(top_n=4),
    "klassiek 12m lookback": Config(gewichten_1_3_6_12=(0, 0, 0, 1)),
    "13612W lookback (Keller)": Config(gewichten_1_3_6_12=(12, 4, 2, 1)),
    "zonder DBC in universum": Config(risico_assets=["SPY","EFA","EEM","VNQ","GLD","TLT"]),
    "hefboom 1.5x": Config(hefboom=1.5),
    "hefboom 2x": Config(hefboom=2.0),
    "hefboom 1.5x + top 2": Config(hefboom=1.5, top_n=2),
}
rows = []
for naam, c in varianten.items():
    r = backtest(prijzen, c)
    s = statistieken(r["equity"], naam); s["kosten"] = r["kosten_totaal"]; rows.append(s)
var = pd.DataFrame(rows).set_index("strategie")
print("\n=== VARIANTEN ===")
print(var[["CAGR", "vol", "sharpe", "max_drawdown", "calmar", "slechtste_jaar", "eindwaarde_x", "kosten"]].to_string())

# ---------- robuustheid: parametergrid ----------
grid = []
for n, sma_d, k in itertools.product([2, 3, 4], [150, 200, 250], [0.0005, 0.001, 0.002]):
    r = backtest(prijzen, Config(top_n=n, sma_dagen=sma_d, kosten_per_kant=k))
    s = statistieken(r["equity"]); grid.append({"top_n": n, "sma": sma_d, "kosten": k, **s})
grid = pd.DataFrame(grid)
print("\n=== PARAMETERGRID (robuustheid) ===")
print(grid[["top_n", "sma", "kosten", "CAGR", "sharpe", "max_drawdown", "calmar"]].to_string(index=False))
print(f"\nCAGR over alle 27 combinaties: min {grid.CAGR.min():.1%}, mediaan {grid.CAGR.median():.1%}, max {grid.CAGR.max():.1%}")
print(f"MaxDD over alle combinaties: beste {grid.max_drawdown.max():.1%}, slechtste {grid.max_drawdown.min():.1%}")

# ---------- in- en out-of-sample ----------
split = "2016-01-01"
for lbl, c in [("in-sample 2007-2015", Config()), ("out-of-sample 2016-2025", Config(start=split))]:
    r = backtest(prijzen, c)
    e = r["equity"] if lbl.startswith("out") else r["equity"].loc[:split]
    e = e / e.iloc[0]
    s = statistieken(e, lbl)
    spy = buy_and_hold(prijzen, "SPY", e.index[0]).loc[:e.index[-1]]
    ss = statistieken(spy, "SPY")
    print(f"\n{lbl}: bot CAGR {s['CAGR']:.1%} / maxDD {s['max_drawdown']:.1%} / sharpe {s['sharpe']:.2f}   |  SPY CAGR {ss['CAGR']:.1%} / maxDD {ss['max_drawdown']:.1%} / sharpe {ss['sharpe']:.2f}")

# ---------- grafieken ----------
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
kleuren = {"Rotatiebot": "#FF18A7", "SPY buy & hold": "#2C2C2A", "60/40 (SPY/IEF)": "#378ADD", "Gelijk gewogen 8 assets": "#888780"}

fig, ax = plt.subplots(2, 1, figsize=(9, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1.3]})
for k, v in bench.items():
    ax[0].plot(v.index, v * 10_000, label=k, color=kleuren[k], lw=2 if k == "Rotatiebot" else 1.2)
ax[0].set_yscale("log"); ax[0].set_ylabel("Waarde (start 10.000 euro, logschaal)")
ax[0].set_title(f"Rotatiebot vs benchmarks, {start.year} tot {eq.index[-1].year}")
ax[0].legend(frameon=False); ax[0].grid(alpha=.25, which="both")
ax[0].set_yticks([5000, 10000, 20000, 40000, 80000]); ax[0].yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
ax[0].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", ".")))
for k in ["Rotatiebot", "SPY buy & hold"]:
    v = bench[k]; dd = v / v.cummax() - 1
    ax[1].fill_between(dd.index, dd * 100, 0, color=kleuren[k], alpha=.35 if k == "Rotatiebot" else .25, label=k)
ax[1].set_ylabel("Drawdown (%)"); ax[1].legend(frameon=False, loc="lower left"); ax[1].grid(alpha=.25)
fig.tight_layout(); fig.savefig(f"{OUT}/equity_drawdown.png", dpi=150); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.5))
j = jaar[["Rotatiebot", "SPY buy & hold"]] * 100
x = np.arange(len(j)); w = .4
ax.bar(x - w/2, j["Rotatiebot"], w, color=kleuren["Rotatiebot"], label="Rotatiebot")
ax.bar(x + w/2, j["SPY buy & hold"], w, color=kleuren["SPY buy & hold"], label="SPY buy & hold")
ax.set_xticks(x); ax.set_xticklabels(j.index, rotation=45); ax.axhline(0, color="k", lw=.6)
ax.set_ylabel("Jaarrendement (%)"); ax.set_title("Rendement per jaar"); ax.legend(frameon=False); ax.grid(alpha=.25, axis="y")
fig.tight_layout(); fig.savefig(f"{OUT}/jaarrendementen.png", dpi=150); plt.close(fig)

gw = res["gewichten"].resample("ME").last().fillna(0)
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.stackplot(gw.index, [gw[c] for c in gw.columns], labels=gw.columns, alpha=.9)
ax.set_ylim(0, 1); ax.set_ylabel("Allocatie"); ax.set_title("Wat de bot door de jaren heen in bezit had")
ax.legend(ncol=4, frameon=False, fontsize=8, loc="upper left"); fig.tight_layout()
fig.savefig(f"{OUT}/allocatie.png", dpi=150); plt.close(fig)

# ---------- opslaan ----------
stats.to_csv(f"{OUT}/statistieken.csv"); var.to_csv(f"{OUT}/varianten.csv"); grid.to_csv(f"{OUT}/parametergrid.csv", index=False)
(jaar * 100).round(1).to_csv(f"{OUT}/jaarrendementen.csv")
res["trades"].to_csv(f"{OUT}/trades.csv", index=False)
eq.to_csv(f"{OUT}/equity_curve.csv", header=["waarde"])
print("\nKlaar. Bestanden in", OUT)
