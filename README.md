# Rotatiebot: adaptieve dual momentum op 8 assetklassen

Maandelijkse rotatiestrategie die belegt in de 3 sterkst trendende assetklassen uit
SPY (VS aandelen), EFA (ontwikkelde markten), EEM (opkomende markten), VNQ (vastgoed),
DBC (grondstoffen), GLD (goud) en TLT (lange staatsobligaties). Lege plekken gaan naar IEF
(middellange staatsobligaties) of cash.

## Regels
1. Momentumscore = gemiddelde van het 3-, 6- en 12-maands rendement.
2. Een asset komt alleen in aanmerking als de score > 0 is EN de koers boven het 200-daags gemiddelde staat.
3. Kies de top 3. Weeg ze naar omgekeerde volatiliteit (60 dagen), zodat elke positie evenveel risico bijdraagt.
4. Slots die niet gevuld kunnen worden gaan naar IEF als die in opwaartse trend is, anders cash.
5. Herbalanceer op de laatste handelsdag van de maand. Kosten: 0,1% per transactie ingerekend.

## Backtest 2007 tot 2025 (19 jaar, 10.000 euro start)
| | Rotatiebot | SPY buy & hold | 60/40 |
|---|---|---|---|
| Rendement per jaar | 11,5% | 10,7% | 8,1% |
| Volatiliteit | 12,8% | 19,8% | 11,1% |
| Sharpe | 0,92 | 0,61 | 0,76 |
| Grootste daling | -14,7% | -55,2% | -32,6% |
| Slechtste jaar | -7,6% | -36,8% | -18,0% |
| Eindwaarde | 79.590 | 68.460 | 43.750 |

In-sample (2007-2015) 11,0% per jaar, out-of-sample (2016-2025) 11,9% per jaar: de strategie
houdt stand op data die niet gebruikt is om hem te kiezen. Over 27 parametercombinaties ligt het
rendement tussen 7,9% en 11,8% met een grootste daling tussen -11% en -24%: geen enkele instelling
maakt of breekt het resultaat.

Met hefboom (via margin of hefboom-ETF's): 1,5x geeft 14,5% per jaar bij -24% maximale daling,
2x geeft 17,1% per jaar bij -33%. Hefboom is een keuze die je bewust later maakt, niet de standaard.

## Bestanden
- `strategie.py`: de strategie en backtest-engine (de enige plek waar logica staat)
- `backtest_run.py`: draait backtest, benchmarks, varianten, robuustheidsgrid en maakt grafieken
- `verkenning.py`: de verkenning van universum en lookback waarmee de standaardinstelling is gekozen
- `signalen.py`: wat de bot NU zou aanhouden, met bedragen voor jouw kapitaal
- `data_ophalen.py`: haalt verse koersen op (vereist internet, yfinance)
- `live_alpaca.py`: plaatst de orders bij Alpaca (paper of echt), met droogloop-modus
- `data/`: historische koersen (dividend-gecorrigeerd)
- `output/`: grafieken, statistieken, trades, logboek

## Maandelijkse routine (5 minuten)
```
python data_ophalen.py          # verse koersen
python signalen.py data/assetklassen.csv 10000
python live_alpaca.py           # droogloop: laat zien wat hij zou doen
python live_alpaca.py --echt    # plaatst de orders
```

## Eerlijke kanttekeningen
- Backtest is geen garantie. Momentum heeft periodes van jaren waarin het achterblijft op de index (2012-2014, 2019, 2023).
- Resultaten zijn in USD; als euro-belegger komt daar wisselkoersbeweging bij.
- Belasting (box 3 of vennootschapsbelasting bij beleggen via de holding) is niet meegenomen.
- Dit is geen beleggingsadvies.
