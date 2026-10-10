"""
Papieren handel op de opgenomen trades: wat was er gebeurd als we hadden gekocht.
Rekent met de echte bonding-curve wiskunde (constant product op de virtuele reserves) zodat
koersimpact van onze eigen koop en verkoop meetelt.
"""
from dataclasses import dataclass
import sqlite3

FEE = 0.0125          # pump.fun handelskosten per kant (1% protocol + ~0.25% creator)
TX_KOSTEN_SOL = 0.002  # prioriteitsfee + netwerkkosten per transactie


@dataclass
class Regels:
    inzet_sol: float = 0.2
    vertraging_sec: float = 3.0      # hoe lang na creatie we "binnen" zijn
    min_kopers: int = 0              # unieke kopers vóór instap (0 = geen filter)
    min_sol_in: float = 0.0          # minimale netto SOL-instroom vóór instap
    geen_maker_verkoop: bool = True  # instappen alleen als de maker nog niet verkocht heeft
    tp_x: float = 2.0                # bij deze vermenigvuldiging de helft verkopen
    trailing: float = 0.30           # daarna: rest verkopen bij 30% onder de piek
    stop: float = 0.50               # alles verkopen bij -50%
    max_min: float = 60.0            # maximale houdtijd in minuten
    uit_bij_maker_verkoop: bool = True


def koop(v_sol, v_tok, sol_in):
    netto = sol_in * (1 - FEE)
    tokens = v_tok - (v_sol * v_tok) / (v_sol + netto)
    return tokens, v_sol + netto, v_tok - tokens


def verkoop_waarde(v_sol, v_tok, tokens):
    if tokens <= 0:
        return 0.0
    sol_out = v_sol - (v_sol * v_tok) / (v_tok + tokens)
    return sol_out * (1 - FEE)


def simuleer(token, trades, regels: Regels):
    """token: dict met ts, maker, v_sol0, v_tok0. trades: lijst van tuples (ts,is_buy,sol,tok,user,v_sol,v_tok).
    Geeft dict met resultaat of None als er niet ingestapt is."""
    t0 = token["ts"]; maker = token["maker"]
    instap_ts = t0 + regels.vertraging_sec
    # toestand op instapmoment = reserves na de laatste trade vóór instap (anders startreserves)
    v_sol, v_tok = token["v_sol0"] / 1e9, token["v_tok0"] / 1e6
    kopers = set(); sol_in = 0.0; maker_verkocht = False; i = 0
    while i < len(trades) and trades[i][0] <= instap_ts:
        ts, is_buy, sol, tok, user, vs, vt = trades[i]
        v_sol, v_tok = vs / 1e9, vt / 1e6
        if is_buy: kopers.add(user); sol_in += sol / 1e9
        else:
            sol_in -= sol / 1e9
            if user == maker: maker_verkocht = True
        i += 1
    if len(kopers) < regels.min_kopers or sol_in < regels.min_sol_in:
        return None
    if regels.geen_maker_verkoop and maker_verkocht:
        return None
    tokens, v_sol, v_tok = koop(v_sol, v_tok, regels.inzet_sol)
    inzet = regels.inzet_sol + TX_KOSTEN_SOL
    piek = regels.inzet_sol; gerealiseerd = 0.0; tp_gedaan = False; reden = "tijd"; laatste_ts = instap_ts
    for ts, is_buy, sol, tok, user, vs, vt in trades[i:]:
        if ts - instap_ts > regels.max_min * 60:
            reden = "tijd"; break
        v_sol, v_tok = vs / 1e9, vt / 1e6
        waarde = verkoop_waarde(v_sol, v_tok, tokens) + gerealiseerd
        piek = max(piek, waarde); laatste_ts = ts
        if user == maker and not is_buy and regels.uit_bij_maker_verkoop:
            reden = "maker verkoopt"; break
        if waarde <= regels.inzet_sol * (1 - regels.stop):
            reden = "stop"; break
        if not tp_gedaan and waarde >= regels.inzet_sol * regels.tp_x:
            half = tokens / 2
            gerealiseerd += verkoop_waarde(v_sol, v_tok, half) - TX_KOSTEN_SOL
            tokens -= half; tp_gedaan = True
            continue
        if tp_gedaan and waarde <= piek * (1 - regels.trailing):
            reden = "trailing"; break
    eind = gerealiseerd + verkoop_waarde(v_sol, v_tok, tokens) - TX_KOSTEN_SOL
    return {"mint": token["mint"], "winst_sol": eind - inzet, "x": eind / inzet, "reden": reden,
            "piek_x": piek / inzet, "duur_min": (laatste_ts - instap_ts) / 60, "tp": tp_gedaan}


def laad(db_pad, van_ts, tot_ts):
    con = sqlite3.connect(db_pad)
    toks = con.execute("SELECT mint,naam,symbool,maker,ts,v_sol0,v_tok0 FROM tokens WHERE ts>=? AND ts<? ORDER BY ts", (van_ts, tot_ts)).fetchall()
    out = []
    for m, naam, sym, maker, ts, vs0, vt0 in toks:
        tr = con.execute("SELECT ts,is_buy,sol,tok,user,v_sol,v_tok FROM trades WHERE mint=? ORDER BY ts", (m,)).fetchall()
        grad = con.execute("SELECT ts FROM completes WHERE mint=?", (m,)).fetchone()
        out.append(({"mint": m, "naam": naam, "symbool": sym, "maker": maker, "ts": ts, "v_sol0": vs0, "v_tok0": vt0, "graduated": bool(grad)}, tr))
    con.close()
    return out
