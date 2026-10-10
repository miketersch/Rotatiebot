"""
Adaptieve Dual Momentum rotatiestrategie
=========================================
Gebaseerd op de best onderbouwde ideeen uit de literatuur:
  - Dual momentum (Antonacci): relatief EN absoluut momentum
  - Momentumscore = gemiddelde van 3/6/12-maands rendement (Faber GTAA); in de backtest
    robuuster dan 12m alleen of de snellere 13612W-score van Keller
  - 200-daags trendfilter (Faber, GTAA): tweede onafhankelijke rem
  - Inverse-volatiliteit weging: elke positie draagt even veel risico bij
  - Wekelijkse crash-check tussen de maandelijkse herbalanceringen door

Alles is parametriseerbaar zodat de robuustheid getest kan worden.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

TRADING_DAYS = 252


@dataclass
class Config:
    risico_assets: list = field(default_factory=lambda: ["SPY", "EFA", "EEM", "VNQ", "DBC", "GLD", "TLT"])
    veilig_asset: str = "IEF"           # waar niet-gevulde slots naartoe gaan
    top_n: int = 3                      # aantal posities
    gewichten_1_3_6_12: tuple = (0, 1, 1, 1)   # gemiddelde van 3/6/12 mnd (Faber); 13612W=(12,4,2,1) testte slechter
    sma_dagen: int = 200                # trendfilter
    gebruik_sma_filter: bool = True
    gebruik_abs_momentum: bool = True
    weging: str = "invvol"              # "invvol" of "gelijk"
    vol_dagen: int = 60
    wekelijkse_check: bool = False      # tussentijdse crash-check; kostte rendement (whipsaws), optioneel
    kosten_per_kant: float = 0.001      # 0.1% per transactie (spread + slippage)
    hefboom: float = 1.0                # 1.0 = geen hefboom
    hefboom_rente_pj: float = 0.05      # rente op geleend deel bij hefboom > 1
    start: str | None = None


def momentum_score(prijzen: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """13612W score op dagbasis: gewogen gemiddelde van 1,3,6,12-maands rendement,
    elk geannualiseerd zodat ze vergelijkbaar zijn. Positief = opwaartse trend."""
    w1, w3, w6, w12 = cfg.gewichten_1_3_6_12
    r1 = prijzen.pct_change(21)
    r3 = prijzen.pct_change(63)
    r6 = prijzen.pct_change(126)
    r12 = prijzen.pct_change(252)
    return (w1 * r1 + w3 * r3 + w6 * r6 + w12 * r12) / (w1 + w3 + w6 + w12)


def doelgewichten_op(dag: pd.Timestamp, prijzen: pd.DataFrame, score: pd.DataFrame,
                     sma: pd.DataFrame, vol: pd.DataFrame, cfg: Config) -> pd.Series:
    """Bepaal de doelportefeuille op een herbalanceerdag. Gebruikt alleen data t/m die dag."""
    s = score.loc[dag, cfg.risico_assets].dropna()
    ok = s.copy()
    if cfg.gebruik_abs_momentum:
        ok = ok[ok > 0]
    if cfg.gebruik_sma_filter:
        boven = prijzen.loc[dag, ok.index] > sma.loc[dag, ok.index]
        ok = ok[boven]
    gekozen = ok.sort_values(ascending=False).head(cfg.top_n).index.tolist()

    gew = pd.Series(0.0, index=prijzen.columns)
    slot = 1.0 / cfg.top_n
    if gekozen:
        if cfg.weging == "invvol":
            iv = 1.0 / vol.loc[dag, gekozen].replace(0, np.nan)
            iv = iv.fillna(iv.mean())
            w = iv / iv.sum() * (slot * len(gekozen))
        else:
            w = pd.Series(slot, index=gekozen)
        gew[gekozen] = w
    # lege slots naar het veilige asset, mits dat zelf in opwaartse trend is; anders cash (0%)
    leeg = 1.0 - gew.sum()
    if leeg > 1e-9 and cfg.veilig_asset in prijzen.columns:
        v_ok = score.loc[dag, cfg.veilig_asset] > 0 if cfg.gebruik_abs_momentum else True
        if v_ok:
            gew[cfg.veilig_asset] += leeg
    return gew * cfg.hefboom


def backtest(prijzen: pd.DataFrame, cfg: Config) -> dict:
    prijzen = prijzen.sort_index().ffill()
    if cfg.start:
        pass  # start wordt hieronder toegepast na warm-up
    rend = prijzen.pct_change().fillna(0.0)
    score = momentum_score(prijzen, cfg)
    sma = prijzen.rolling(cfg.sma_dagen).mean()
    vol = rend.rolling(cfg.vol_dagen).std() * np.sqrt(TRADING_DAYS)

    # warm-up: pas starten als 12 maanden data beschikbaar is
    eerste = score.dropna(how="all").index[0]
    if cfg.start:
        eerste = max(eerste, pd.Timestamp(cfg.start))
    dagen = prijzen.index[prijzen.index >= eerste]

    # maandelijkse herbalanceerdagen: laatste handelsdag van de maand
    maand_eind = prijzen.loc[dagen].groupby(prijzen.loc[dagen].index.to_period("M")).tail(1).index
    week_eind = prijzen.loc[dagen].groupby(prijzen.loc[dagen].index.to_period("W")).tail(1).index

    gew = pd.Series(0.0, index=prijzen.columns)
    equity = pd.Series(index=dagen, dtype=float)
    waarde = 1.0
    gewichten_log = {}
    trades = []
    kosten_totaal = 0.0
    dagrente = (1 + cfg.hefboom_rente_pj) ** (1 / TRADING_DAYS) - 1

    for i, dag in enumerate(dagen):
        if i > 0:
            # rendement van de dag op de gewichten van gisteren
            r_dag = float((gew * rend.loc[dag]).sum())
            if cfg.hefboom > 1.0:
                r_dag -= (cfg.hefboom - 1.0) * dagrente
            waarde *= (1 + r_dag)
            # gewichten driften mee met de koersen (als fractie van de portefeuillewaarde)
            gew = gew * (1 + rend.loc[dag]) / (1 + r_dag)
        equity[dag] = waarde

        herbalanceer = dag in maand_eind
        tussentijds = False
        if not herbalanceer and cfg.wekelijkse_check and dag in week_eind:
            # crash-check: een gehouden risico-asset dat onder zijn SMA zakt EN negatief momentum
            # heeft, gaat eruit. Alleen afbouwen, niet bijkopen (dat gebeurt maandelijks).
            gehouden = [a for a in cfg.risico_assets if gew.get(a, 0) > 0]
            breuk = [a for a in gehouden
                     if prijzen.loc[dag, a] < sma.loc[dag, a] and score.loc[dag, a] < 0]
            if breuk:
                tussentijds = True

        if herbalanceer or tussentijds:
            if herbalanceer:
                nieuw = doelgewichten_op(dag, prijzen, score, sma, vol, cfg)
            else:
                nieuw = gew.copy()
                vrij = 0.0
                for a in breuk:
                    vrij += nieuw[a]; nieuw[a] = 0.0
                v_ok = score.loc[dag, cfg.veilig_asset] > 0
                if v_ok:
                    nieuw[cfg.veilig_asset] += vrij
            omzet = float((nieuw - gew).abs().sum())
            kosten = omzet * cfg.kosten_per_kant
            waarde *= (1 - kosten)
            kosten_totaal += kosten
            equity[dag] = waarde
            if omzet > 1e-6:
                trades.append({"datum": dag, "omzet": omzet, "type": "maand" if herbalanceer else "week-crashcheck",
                               **{a: round(nieuw[a], 3) for a in nieuw.index if nieuw[a] > 0}})
            gew = nieuw
            gewichten_log[dag] = gew.copy()

    equity = equity.dropna()
    return {
        "equity": equity,
        "gewichten": pd.DataFrame(gewichten_log).T.fillna(0.0),
        "trades": pd.DataFrame(trades),
        "kosten_totaal": kosten_totaal,
        "cfg": cfg,
    }


def statistieken(equity: pd.Series, naam: str = "") -> dict:
    r = equity.pct_change().dropna()
    jaren = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = equity.iloc[-1] ** (1 / jaren) - 1
    vol = r.std() * np.sqrt(TRADING_DAYS)
    dd = equity / equity.cummax() - 1
    maxdd = dd.min()
    # langste herstelperiode
    onder = dd < 0
    langste = 0; huidig = 0
    for x in onder:
        huidig = huidig + 1 if x else 0
        langste = max(langste, huidig)
    jaarr = equity.resample("YE").last().pct_change().dropna()
    maand = equity.resample("ME").last().pct_change().dropna()
    return {
        "strategie": naam,
        "CAGR": cagr,
        "vol": vol,
        "sharpe": (r.mean() * TRADING_DAYS) / vol if vol > 0 else np.nan,
        "max_drawdown": maxdd,
        "calmar": cagr / abs(maxdd) if maxdd < 0 else np.nan,
        "langste_dd_dagen": langste,
        "slechtste_jaar": jaarr.min(),
        "beste_jaar": jaarr.max(),
        "pct_pos_maanden": (maand > 0).mean(),
        "eindwaarde_x": equity.iloc[-1],
        "jaren": jaren,
    }


def buy_and_hold(prijzen: pd.DataFrame, ticker: str, start) -> pd.Series:
    p = prijzen[ticker].loc[start:].dropna()
    return p / p.iloc[0]


def vaste_mix(prijzen: pd.DataFrame, gewichten: dict, start) -> pd.Series:
    """Maandelijks geherbalanceerde vaste mix, bv 60/40."""
    r = prijzen.pct_change().fillna(0).loc[start:]
    w = pd.Series(gewichten)
    out = []; waarde = 1.0; cur = w.copy()
    maand_eind = r.groupby(r.index.to_period("M")).tail(1).index
    for dag in r.index:
        waarde *= 1 + float((cur * r.loc[dag, cur.index]).sum())
        cur = cur * (1 + r.loc[dag, cur.index]); cur = cur / cur.sum()
        if dag in maand_eind:
            cur = w.copy()
        out.append(waarde)
    return pd.Series(out, index=r.index)
