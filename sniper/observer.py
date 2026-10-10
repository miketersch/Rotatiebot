"""
Observatiebot voor pump.fun (fase 1, geen geld).

Luistert via Helius (logsSubscribe) naar het pump.fun-programma en slaat op:
  - elke nieuwe token (CreateEvent): naam, symbool, maker, startreserves
  - elke trade (TradeEvent) in de eerste uren van die token: tijd, koop/verkoop, SOL, koers, wallet
  - graduaties (CompleteEvent)
Alles gaat in een SQLite-database. rapport.py en analyse.py rekenen daar strategieën op door,
alsof we gekocht hadden, inclusief de echte koersimpact van de bonding curve.

Draait als systemd-service (altijd aan). Omgevingsvariabele: HELIUS_API_KEY.
"""
import asyncio, base64, json, os, sqlite3, struct, time, sys, logging
import websockets, base58

API_KEY = os.environ.get("HELIUS_API_KEY")
WSS = os.environ.get("SOLANA_WSS") or (f"wss://mainnet.helius-rpc.com/?api-key={API_KEY}" if API_KEY else None)
HIER = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("SNIPER_DB", os.path.join(HIER, "..", "output", "sniper.db"))
VOLG_SECONDEN = int(os.environ.get("SNIPER_VOLG_SEC", "14400"))     # trades per token bijhouden gedurende 4 uur
MAX_TRADES_PER_TOKEN = int(os.environ.get("SNIPER_MAX_TRADES", "3000"))

PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
D_CREATE = bytes([27, 114, 169, 77, 222, 235, 99, 118])
D_TRADE = bytes([189, 219, 127, 211, 78, 230, 97, 238])
D_COMPLETE = bytes([95, 114, 97, 156, 212, 46, 152, 8])

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("observer")


def db_init():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS tokens(
        mint TEXT PRIMARY KEY, naam TEXT, symbool TEXT, uri TEXT, maker TEXT, user TEXT,
        ts REAL, sig TEXT, token_standard TEXT, mayhem INTEGER, cashback INTEGER,
        v_sol0 INTEGER, v_tok0 INTEGER, prijs0 REAL, n_trades INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS trades(
        mint TEXT, ts REAL, is_buy INTEGER, sol INTEGER, tok INTEGER, user TEXT,
        v_sol INTEGER, v_tok INTEGER, prijs REAL, sig TEXT);
    CREATE INDEX IF NOT EXISTS ix_trades_mint ON trades(mint, ts);
    CREATE TABLE IF NOT EXISTS completes(mint TEXT PRIMARY KEY, ts REAL, user TEXT);
    CREATE TABLE IF NOT EXISTS heartbeat(ts REAL, tokens INTEGER, trades INTEGER);
    """)
    con.commit()
    return con


def pk(b): return base58.b58encode(b).decode()
def u64(b, o): return struct.unpack_from("<Q", b, o)[0]
def i64(b, o): return struct.unpack_from("<q", b, o)[0]


def parse_create(d):
    o = 8; out = {}
    for naam in ("naam", "symbool", "uri"):
        n = struct.unpack_from("<I", d, o)[0]; o += 4
        out[naam] = d[o:o + n].decode("utf-8", "replace"); o += n
    out["mint"] = pk(d[o:o + 32]); o += 32
    out["bonding_curve"] = pk(d[o:o + 32]); o += 32
    out["user"] = pk(d[o:o + 32]); o += 32
    out["maker"] = pk(d[o:o + 32]); o += 32
    out["ts_chain"] = i64(d, o); o += 8
    out["v_tok0"] = u64(d, o); o += 8
    out["v_sol0"] = u64(d, o); o += 8
    o += 16  # real_token_reserves, token_total_supply
    tp = pk(d[o:o + 32]) if len(d) >= o + 32 else ""; o += 32
    out["token_standard"] = "token2022" if tp.startswith("TokenzQd") else "legacy"
    out["mayhem"] = int(d[o]) if len(d) > o else 0; o += 1
    out["cashback"] = int(d[o]) if len(d) > o else 0
    return out


def parse_trade(d):
    o = 8
    mint = pk(d[o:o + 32]); o += 32
    sol = u64(d, o); o += 8
    tok = u64(d, o); o += 8
    is_buy = int(d[o]); o += 1
    user = pk(d[o:o + 32]); o += 32
    ts_chain = i64(d, o); o += 8
    v_sol = u64(d, o); o += 8
    v_tok = u64(d, o); o += 8
    return dict(mint=mint, sol=sol, tok=tok, is_buy=is_buy, user=user, ts_chain=ts_chain, v_sol=v_sol, v_tok=v_tok)


def parse_complete(d):
    o = 8
    user = pk(d[o:o + 32]); o += 32
    mint = pk(d[o:o + 32])
    return dict(user=user, mint=mint)


def prijs(v_sol, v_tok):
    return (v_sol / 1e9) / (v_tok / 1e6) if v_tok else 0.0


class Observer:
    def __init__(self):
        self.con = db_init()
        self.volgen = {}          # mint -> (aangemaakt_ts, n_trades)
        self.buf_trades = []
        self.n_tokens = 0; self.n_trades = 0
        self.laatste_flush = time.time(); self.laatste_hb = time.time()

    def verwerk(self, msg):
        try:
            v = msg["params"]["result"]["value"]
        except KeyError:
            return
        logs = v.get("logs") or []
        if v.get("err"):
            return
        sig = v.get("signature", ""); nu = time.time()
        for line in logs:
            if not line.startswith("Program data: "):
                continue
            try:
                d = base64.b64decode(line[14:])
            except Exception:
                continue
            if len(d) < 8:
                continue
            disc = d[:8]
            try:
                if disc == D_TRADE:
                    t = parse_trade(d)
                    info = self.volgen.get(t["mint"])
                    if not info:
                        continue
                    t0, n = info
                    if nu - t0 > VOLG_SECONDEN or n >= MAX_TRADES_PER_TOKEN:
                        self.volgen.pop(t["mint"], None); continue
                    self.volgen[t["mint"]] = (t0, n + 1)
                    self.buf_trades.append((t["mint"], nu, t["is_buy"], t["sol"], t["tok"], t["user"], t["v_sol"], t["v_tok"], prijs(t["v_sol"], t["v_tok"]), sig))
                    self.n_trades += 1
                elif disc == D_CREATE:
                    c = parse_create(d)
                    self.con.execute("INSERT OR IGNORE INTO tokens VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                        (c["mint"], c["naam"][:64], c["symbool"][:16], c["uri"][:200], c["maker"], c["user"], nu, sig, c["token_standard"],
                         c["mayhem"], c["cashback"], c["v_sol0"], c["v_tok0"], prijs(c["v_sol0"], c["v_tok0"])))
                    self.volgen[c["mint"]] = (nu, 0); self.n_tokens += 1
                elif disc == D_COMPLETE:
                    c = parse_complete(d)
                    self.con.execute("INSERT OR IGNORE INTO completes VALUES(?,?,?)", (c["mint"], nu, c["user"]))
            except Exception as e:
                log.warning("parse-fout %s: %s", disc.hex(), e)
        if nu - self.laatste_flush > 2:
            self.flush(nu)

    def flush(self, nu):
        if self.buf_trades:
            self.con.executemany("INSERT INTO trades VALUES(?,?,?,?,?,?,?,?,?,?)", self.buf_trades)
            self.buf_trades.clear()
        self.con.commit(); self.laatste_flush = nu
        # opruimen van oude volg-items
        for m, (t0, n) in list(self.volgen.items()):
            if nu - t0 > VOLG_SECONDEN:
                self.con.execute("UPDATE tokens SET n_trades=? WHERE mint=?", (n, m)); self.volgen.pop(m)
        if nu - self.laatste_hb > 300:
            self.con.execute("INSERT INTO heartbeat VALUES(?,?,?)", (nu, self.n_tokens, self.n_trades)); self.con.commit()
            log.info("tokens %d, trades %d, volgend %d", self.n_tokens, self.n_trades, len(self.volgen))
            self.laatste_hb = nu

    async def run(self):
        if not WSS:
            sys.exit("HELIUS_API_KEY ontbreekt")
        while True:
            try:
                async with websockets.connect(WSS, max_size=32 * 1024 * 1024, ping_interval=20, ping_timeout=20) as ws:
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                                              "params": [{"mentions": [PUMP]}, {"commitment": "processed"}]}))
                    log.info("verbonden, abonnement: %s", await ws.recv())
                    async for raw in ws:
                        msg = json.loads(raw)
                        if msg.get("method") == "logsNotification":
                            self.verwerk(msg)
            except Exception as e:
                log.error("verbinding weg: %s, opnieuw over 5 s", e)
                self.flush(time.time())
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(Observer().run())
