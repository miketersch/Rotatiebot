"""
Haalt actuele dividend-gecorrigeerde slotkoersen op via Yahoo Finance (yfinance) en schrijft data/assetklassen.csv.
Draai dit op een machine met internet (VPS, laptop) voor elke maandelijkse herbalancering.
"""
import pandas as pd
import yfinance as yf

TICKERS = ["SPY", "EFA", "EEM", "VNQ", "DBC", "GLD", "TLT", "IEF"]

d = yf.download(TICKERS, start="2005-01-01", auto_adjust=True, progress=False)["Close"]
d = d[TICKERS].dropna(how="all")
d.index.name = "Date"
d.to_csv("data/assetklassen.csv")
print("Opgeslagen:", d.shape, d.index.min().date(), "tot", d.index.max().date())
