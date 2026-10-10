"""
Bitvavo trendbot: BTC en ETH, dagelijks, long/cash.

Regel: elke ochtend per coin kijken of de slotkoers (in EUR) boven het N-daags voortschrijdend gemiddelde
staat. Zo ja: de helft van het botbudget in die coin. Zo nee: die helft in euro. Alleen handelen als de
positie omslaat of als de afwijking van het doel groter is dan DREMPEL.

Veiligheid:
  - BUDGET_EUR is de harde bovengrens van wat de bot beheert; andere coins en overig saldo blijven onaangeraakt
  - de bot houdt zijn eigen boekhouding (output/bitvavo_state.json); hij verkoopt nooit meer dan hij zelf gekocht heeft
  - MODUS=droog laat alleen zien wat hij zou doen
  - API-sleutel: alleen weergave + handelen, geen opnames, IP-beperkt

Omgevingsvariabelen (in /etc/rotatiebot/env): BITVAVO_KEY, BITVAVO_SECRET, BITVAVO_BUDGET_EUR, BITVAVO_MODUS (droog/echt),
BITVAVO_SMA (dagen, standaard 100), BITVAVO_DREMPEL (fractie, standaard 0.10)
"""
import os, sys, json, time, hmac, hashlib, urllib.request, urllib.parse, urllib.error, datetime as dt, math, socket

# Bitvavo altijd via IPv4 benaderen (IP-whitelist bevat alleen het IPv4-adres van de server)
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(host, port, family=0, *a, **k):
    return _orig_getaddrinfo(host, port, socket.AF_INET, *a, **k)
socket.getaddrinfo = _ipv4_only
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from melding import meld

KEY, SECRET = os.environ.get("BITVAVO_KEY"), os.environ.get("BITVAVO_SECRET")
BUDGET = float(os.environ.get("BITVAVO_BUDGET_EUR", "1000"))
ECHT = os.environ.get("BITVAVO_MODUS", "droog") == "echt" and "--droog" not in sys.argv
SMA = int(os.environ.get("BITVAVO_SMA", "100"))
DREMPEL = float(os.environ.get("BITVAVO_DREMPEL", "0.10"))
COINS = ["BTC", "ETH"]
HIER = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HIER, "..", "output", "bitvavo_state.json")
LOG = os.path.join(HIER, "..", "output", "bitvavo_log.csv")
BASE = "https://api.bitvavo.com/v2"


def api(method, path, body=None):
    ts = str(int(time.time() * 1000))
    payload = json.dumps(body, separators=(",", ":")) if body else ""
    sig = hmac.new(SECRET.encode(), (ts + method + "/v2" + path + payload).encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(BASE + path, data=payload.encode() if body else None, method=method, headers={
        "Bitvavo-Access-Key": KEY, "Bitvavo-Access-Signature": sig, "Bitvavo-Access-Timestamp": ts,
        "Bitvavo-Access-Window": "10000", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Bitvavo {e.code} op {path}: {e.read().decode(errors='replace')[:300]}")


def publiek(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.loads(r.read())


def laad_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"posities": {c: 0.0 for c in COINS}, "eur_ingelegd": BUDGET}


def bewaar_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=1)


def main():
    if not KEY or not SECRET:
        sys.exit("BITVAVO_KEY/SECRET ontbreekt")
    state = laad_state()
    regels, orders = [], []
    bal = {b["symbol"]: float(b["available"]) for b in api("GET", "/balance")}
    eur_vrij = bal.get("EUR", 0.0)

    # waarde van wat de bot beheert
    koersen = {}
    for c in COINS:
        candles = publiek(f"/{c}-EUR/candles?interval=1d&limit={SMA + 5}")
        closes = [float(x[4]) for x in sorted(candles, key=lambda x: x[0])]
        if len(closes) < SMA + 1:
            raise RuntimeError(f"Te weinig candles voor {c}")
        koers = closes[-1]; gem = sum(closes[-SMA - 1:-1]) / SMA     # SMA over de afgesloten dagen
        koersen[c] = (koers, gem)
    bot_waarde = sum(state["posities"][c] * koersen[c][0] for c in COINS)
    bot_cash = state.get("cash", BUDGET)
    totaal = bot_waarde + bot_cash

    regels.append(f"Botvermogen: {totaal:,.2f} EUR (cash {bot_cash:,.2f}, coins {bot_waarde:,.2f}); budget {BUDGET:,.0f}; EUR vrij op rekening {eur_vrij:,.2f}")
    slot = totaal / len(COINS)
    for c in COINS:
        koers, gem = koersen[c]
        boven = koers > gem
        huidig_st = state["posities"][c]; huidig_eur = huidig_st * koers
        doel_eur = slot * 0.995 if boven else 0.0
        delta = doel_eur - huidig_eur
        actie = "-"
        if boven and huidig_eur < slot * (1 - DREMPEL) and delta > 10:
            actie = "KOOP"
        elif not boven and huidig_st > 0:
            actie = "VERKOOP"
        regels.append(f"{c}: koers {koers:,.0f}, SMA{SMA} {gem:,.0f}, {'boven' if boven else 'ONDER'} | positie {huidig_st:.6f} ({huidig_eur:,.0f} EUR) | {actie}")
        if actie == "KOOP":
            bedrag = min(delta, bot_cash, eur_vrij) if ECHT else min(delta, bot_cash)
            if bedrag < 10:
                regels.append(f"   te weinig cash voor {c} ({bedrag:.2f})"); continue
            orders.append((c, "buy", round(bedrag, 2)))
        elif actie == "VERKOOP":
            orders.append((c, "sell", huidig_st))

    for c, side, hoeveel in orders:
        if not ECHT:
            regels.append(f"   DROOGLOOP: zou {side} {c} {'voor ' + str(hoeveel) + ' EUR' if side == 'buy' else str(hoeveel) + ' stuks'}")
            continue
        body = {"market": f"{c}-EUR", "side": side, "orderType": "market"}
        if side == "buy":
            body["amountQuote"] = f"{hoeveel:.2f}"
        else:
            body["amount"] = f"{math.floor(hoeveel * 1e6) / 1e6:.6f}"
        res = api("POST", "/order", body)
        if "error" in res:
            regels.append(f"   FOUT bij {side} {c}: {res['error']}"); continue
        gevuld = float(res.get("filledAmount", 0)); gevuld_eur = float(res.get("filledAmountQuote", 0)); fee = float(res.get("feePaid", 0))
        if side == "buy":
            state["posities"][c] += gevuld; state["cash"] = state.get("cash", BUDGET) - gevuld_eur - (fee if res.get("feeCurrency") == "EUR" else 0)
        else:
            state["posities"][c] = max(0.0, state["posities"][c] - gevuld); state["cash"] = state.get("cash", BUDGET) + gevuld_eur - fee
        regels.append(f"   {side.upper()} {c}: {gevuld:.6f} stuks voor {gevuld_eur:,.2f} EUR (fee {fee:.2f})")
        bewaar_state(state)

    if "cash" not in state:
        state["cash"] = BUDGET; bewaar_state(state)
    kop = f"Bitvavo trendbot {'ECHT' if ECHT else 'DROOGLOOP'} {dt.date.today()}"
    tekst = "\n".join(regels)
    if orders or "--altijd-melden" in sys.argv or dt.date.today().weekday() == 6:
        meld(kop, tekst)
    else:
        print(kop + "\n" + tekst)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')},{totaal:.2f}," + ";".join(f"{c}={state['posities'][c]:.6f}" for c in COINS) + f",orders={len(orders)},echt={ECHT}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        meld("Bitvavo trendbot FOUT", f"{type(e).__name__}: {e}")
        raise
