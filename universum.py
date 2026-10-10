"""
Koppeling tussen het signaal-universum (Amerikaanse ETF's met 20 jaar historie, alleen voor de berekening)
en de UCITS-ETF's die daadwerkelijk gekocht worden bij IBKR (Europese noteringen, wel koopbaar voor
Nederlandse beleggers). Elk paar volgt dezelfde index of hetzelfde activum.

De ISIN is leidend: de bot zoekt via de IBKR-API het contract op ISIN en kiest een notering in EUR
(Xetra of Euronext Amsterdam). Tickers verschillen per beurs en zijn alleen ter herkenning.
"""

UCITS = {
    # signaal : {ISIN, naam, voorkeurs-ticker, gewenste valuta}
    "SPY": {"isin": "IE000XZSV718", "naam": "SPDR S&P 500 UCITS ETF (acc)",              "ticker": "SPYL", "valuta": "EUR"},
    "EFA": {"isin": "IE0006WW1TQ4", "naam": "Xtrackers MSCI World ex USA UCITS ETF",      "ticker": "EXUS", "valuta": "EUR"},
    "EEM": {"isin": "IE00BKM4GZ66", "naam": "iShares Core MSCI EM IMI UCITS ETF",         "ticker": "EIMI", "valuta": "EUR"},
    "VNQ": {"isin": "IE00B1FZSF77", "naam": "iShares US Property Yield UCITS ETF",        "ticker": "IUSP", "valuta": "EUR"},
    "DBC": {"isin": "IE00BD6FTQ80", "naam": "Invesco Bloomberg Commodity UCITS ETF",      "ticker": "CMOD", "valuta": "EUR"},
    "GLD": {"isin": "IE00B4ND3602", "naam": "iShares Physical Gold ETC",                  "ticker": "IGLN", "valuta": "EUR"},
    "TLT": {"isin": "IE00BSKRJZ44", "naam": "iShares $ Treasury Bond 20+yr UCITS ETF",    "ticker": "DTLA", "valuta": "EUR"},
    "IEF": {"isin": "IE00B1FZS798", "naam": "iShares $ Treasury Bond 7-10yr UCITS ETF",   "ticker": "IBTM", "valuta": "EUR"},
}

# beurzen in volgorde van voorkeur voor EUR-noteringen bij IBKR
BEURS_VOORKEUR = ["IBIS", "IBIS2", "AEB", "SBF", "BVME.ETF", "LSEETF", "SMART"]
