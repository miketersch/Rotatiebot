"""
Herbalancering via Interactive Brokers (IB Gateway + ib_async).

Werkwijze:
  1. Signalen berekenen op de Amerikaanse ETF-reeksen (data/assetklassen.csv, vers via data_ophalen.py)
  2. Doelgewichten vertalen naar UCITS-ETF's (universum.py), contracten opzoeken op ISIN in EUR
  3. Huidige portefeuille ophalen, verschil bepalen, orders in hele stukken plaatsen
  4. Rapport sturen (Telegram/e-mail) en loggen

Gebruik:
  python ibkr_live.py            droogloop: laat zien wat hij zou doen, plaatst niets
  python ibkr_live.py --echt     plaatst de orders
Omgevingsvariabelen: IB_HOST (127.0.0.1), IB_PORT (4002 paper / 4001 live), IB_CLIENT_ID (7)
"""
import os, sys, math, time, datetime as dt
import pandas as pd, numpy as np
from strategie import Config, momentum_score, doelgewichten_op, TRADING_DAYS
from universum import UCITS, BEURS_VOORKEUR
from melding import meld

try:
    from ib_async import IB, Contract, MarketOrder, LimitOrder, util
except ImportError:
    sys.exit("ib_async ontbreekt: pip install ib_async")

ECHT = "--echt" in sys.argv
HOST = os.environ.get("IB_HOST", "127.0.0.1")
PORT = int(os.environ.get("IB_PORT", "4002"))
CLIENT_ID = int(os.environ.get("IB_CLIENT_ID", "7"))
DREMPEL_EUR = float(os.environ.get("DREMPEL_EUR", "25"))    # verschillen kleiner dan dit niet bijhandelen
CASH_BUFFER = float(os.environ.get("CASH_BUFFER", "0.01"))   # 1% cash aanhouden voor kosten/afronding
HIER = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HIER, "output", "live_log.csv")


def signalen():
    cfg = Config()
    prijzen = pd.read_csv(os.path.join(HIER, "data", "assetklassen.csv"), index_col=0, parse_dates=True).sort_index().ffill()
    rend = prijzen.pct_change()
    score = momentum_score(prijzen, cfg)
    sma = prijzen.rolling(cfg.sma_dagen).mean()
    vol = rend.rolling(cfg.vol_dagen).std() * np.sqrt(TRADING_DAYS)
    dag = prijzen.index[-1]
    if (pd.Timestamp.today() - dag).days > 7:
        raise RuntimeError(f"Koersdata is oud (laatste dag {dag.date()}). data_ophalen.py mislukt?")
    gew = doelgewichten_op(dag, prijzen, score, sma, vol, cfg)
    return dag, gew, score.loc[dag], prijzen.loc[dag] > sma.loc[dag]


def zoek_contract(ib: IB, isin: str, valuta: str) -> Contract:
    c = Contract(secType="STK", secIdType="ISIN", secId=isin)
    details = ib.reqContractDetails(c)
    if not details:
        raise RuntimeError(f"Geen contract gevonden voor ISIN {isin}")
    kandidaten = [d.contract for d in details if d.contract.currency == valuta]
    if not kandidaten:
        kandidaten = [d.contract for d in details]
    def rang(ct):
        return BEURS_VOORKEUR.index(ct.exchange) if ct.exchange in BEURS_VOORKEUR else 99
    best = sorted(kandidaten, key=rang)[0]
    ib.qualifyContracts(best)
    return best


def laatste_koers(ib: IB, c: Contract) -> float:
    t = ib.reqMktData(c, "", snapshot=True)
    ib.sleep(2.5)
    p = t.last if t.last and t.last > 0 else (t.close if t.close and t.close > 0 else None)
    if p is None and t.bid and t.ask:
        p = (t.bid + t.ask) / 2
    ib.cancelMktData(c)
    if p is None or math.isnan(p):
        bars = ib.reqHistoricalData(c, "", "2 D", "1 day", "TRADES", useRTH=True)
        p = bars[-1].close if bars else None
    if not p:
        raise RuntimeError(f"Geen koers voor {c.symbol} ({c.secId})")
    return float(p)


def main():
    dag, gew, score, boven_sma = signalen()
    ib = IB()
    ib.connect(HOST, PORT, clientId=CLIENT_ID, timeout=60)
    acct = ib.managedAccounts()[0]
    paper = acct.startswith("DU")

    # vermogen in EUR
    nlv = {v.currency: float(v.value) for v in ib.accountValues(acct) if v.tag == "NetLiquidationByCurrency"}
    vermogen = nlv.get("BASE", nlv.get("EUR"))
    if not vermogen:
        raise RuntimeError("Kon portefeuillewaarde niet lezen")

    # contracten + koersen voor alle assets in het universum
    contracten, koersen = {}, {}
    for sig, info in UCITS.items():
        c = zoek_contract(ib, info["isin"], info["valuta"])
        contracten[sig] = c
        koersen[sig] = laatste_koers(ib, c)

    # huidige posities (op ISIN herkennen)
    posities = {}
    for p in ib.positions(acct):
        for sig, c in contracten.items():
            if p.contract.conId == c.conId:
                posities[sig] = float(p.position)

    doel_eur = (gew * vermogen * (1 - CASH_BUFFER)).round(2)
    regels, orders = [], []
    for sig in UCITS:
        huidig_st = posities.get(sig, 0.0)
        huidig_eur = huidig_st * koersen[sig]
        doel_st = math.floor(doel_eur.get(sig, 0.0) / koersen[sig])
        delta = doel_st - huidig_st
        if abs(delta * koersen[sig]) < DREMPEL_EUR:
            delta = 0
        regels.append(f"{sig:4s} {UCITS[sig]['ticker']:5s} koers {koersen[sig]:8.2f}  nu {huidig_st:6.0f} st ({huidig_eur:8.0f})  doel {doel_st:6.0f} st  {'KOOP' if delta>0 else 'VERKOOP' if delta<0 else '-':8s} {abs(delta):.0f}")
        if delta != 0:
            orders.append((sig, delta))

    kop = f"{'PAPER' if paper else 'ECHT GELD'} | rekening {acct} | vermogen {vermogen:,.0f} EUR | signalen per {dag.date()} | {'DROOGLOOP' if not ECHT else 'ORDERS GEPLAATST'}"
    tekst = kop + "\n\n" + "\n".join(regels)
    tekst += "\n\nMomentum: " + ", ".join(f"{k} {v:+.1%}{'' if boven_sma[k] else ' (onder SMA)'}" for k, v in score.sort_values(ascending=False).items())

    # verkopen eerst (maakt geld vrij), dan kopen
    resultaten = []
    if ECHT and orders:
        for sig, delta in sorted(orders, key=lambda o: o[1]):
            c = contracten[sig]
            order = MarketOrder("BUY" if delta > 0 else "SELL", abs(delta))
            order.tif = "DAY"
            trade = ib.placeOrder(c, order)
            for _ in range(60):
                ib.sleep(2)
                if trade.isDone():
                    break
            st = trade.orderStatus
            resultaten.append(f"{sig}: {order.action} {abs(delta)} -> {st.status}, gevuld {st.filled:.0f} @ {st.avgFillPrice:.2f}")
        tekst += "\n\nUitvoering:\n" + "\n".join(resultaten)
    elif not orders:
        tekst += "\n\nGeen orders nodig."

    ib.disconnect()
    meld("Rotatiebot maandrapport", tekst)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')},{acct},{vermogen:.2f},"
                + ";".join(f"{k}={v:.3f}" for k, v in gew.items() if v > 0)
                + f",orders={len(orders)},echt={ECHT}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        meld("Rotatiebot FOUT", f"{type(e).__name__}: {e}")
        raise
