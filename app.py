"""Analyse boursière : technique + fondamentale + portefeuille. Données : Yahoo Finance (yfinance)."""
from functools import lru_cache
import math
import time
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Bourse")
app.mount("/static", StaticFiles(directory="static"), name="static")

def cached(ttl=300):
    """Cache mémoire simple pour limiter les appels à l'API."""
    def deco(fn):
        store = {}
        def wrapper(*a):
            now = time.time()
            if a in store and now - store[a][0] < ttl:
                return store[a][1]
            val = fn(*a)
            store[a] = (now, val)
            return val
        return wrapper
    return deco

@cached(300)
def history(symbol: str, period: str):
    df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    if df.empty:
        raise HTTPException(404, f"Aucune donnée pour « {symbol} ». Vérifie le symbole (ex. AIR.PA, AAPL).")
    return df

def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)

def clean(s):
    return [None if pd.isna(v) else round(float(v), 4) for v in s]

@app.get("/")
def index():
    return FileResponse("static/index.html")

@app.get("/api/technical/{symbol}")
def technical(symbol: str, period: str = "1y"):
    df = history(symbol.upper(), period)
    c = df["Close"]
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    signal = macd.ewm(span=9, adjust=False).mean()
    r = rsi(c)
    last_rsi = float(r.iloc[-1])
    sma20, sma50 = c.rolling(20).mean(), c.rolling(50).mean()
    signals = []
    signals.append("RSI > 70 : suracheté" if last_rsi > 70 else
                   "RSI < 30 : survendu" if last_rsi < 30 else "RSI neutre")
    if not pd.isna(sma50.iloc[-1]):
        signals.append("Tendance haussière (SMA20 > SMA50)" if sma20.iloc[-1] > sma50.iloc[-1]
                       else "Tendance baissière (SMA20 < SMA50)")
    signals.append("MACD au-dessus du signal" if macd.iloc[-1] > signal.iloc[-1] else "MACD sous le signal")
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in df.index],
        "close": clean(c), "volume": clean(df["Volume"]),
        "sma20": clean(sma20), "sma50": clean(sma50),
        "rsi": clean(r), "macd": clean(macd), "signal": clean(signal),
        "signals": signals,
    }

@app.get("/api/fundamentals/{symbol}")
def fundamentals(symbol: str):
    try:
        i = yf.Ticker(symbol.upper()).info
    except Exception:
        raise HTTPException(502, "Données fondamentales indisponibles pour le moment.")
    if not i or "shortName" not in i:
        raise HTTPException(404, "Symbole introuvable.")
    keys = {
        "name": "shortName", "sector": "sector", "currency": "currency",
        "market_cap": "marketCap", "per": "trailingPE", "per_forward": "forwardPE",
        "pb": "priceToBook", "dividend_yield": "dividendYield", "roe": "returnOnEquity",
        "profit_margin": "profitMargins", "debt_to_equity": "debtToEquity",
        "revenue_growth": "revenueGrowth", "beta": "beta",
        "high_52w": "fiftyTwoWeekHigh", "low_52w": "fiftyTwoWeekLow",
    }
    if i.get("quoteType") == "ETF":
        return etf_fundamentals(symbol.upper(), i)
    return {"type": "equity", **{k: i.get(v) for k, v in keys.items()}}

def etf_fundamentals(symbol: str, i: dict):
    out = {
        "type": "etf", "name": i.get("longName") or i.get("shortName"),
        "currency": i.get("currency"), "family": i.get("fundFamily"), "category": i.get("category"),
        "expense_ratio": i.get("netExpenseRatio") or i.get("annualReportExpenseRatio"),  # en %
        "total_assets": i.get("totalAssets"), "ytd_return": i.get("ytdReturn"),          # en %
        "yield": i.get("yield"), "return_3y": i.get("threeYearAverageReturn"),             # fractions
        "return_5y": i.get("fiveYearAverageReturn"), "beta": i.get("beta3Year"),
        "high_52w": i.get("fiftyTwoWeekHigh"), "low_52w": i.get("fiftyTwoWeekLow"),
        "sectors": {}, "holdings": [],
    }
    try:
        fd = yf.Ticker(symbol).funds_data
        out["sectors"] = {k: round(float(v) * 100, 1) for k, v in fd.sector_weightings.items() if v}
        out["holdings"] = [{"symbol": s, "name": r["Name"], "pct": round(float(r["Holding Percent"]) * 100, 2)}
                           for s, r in fd.top_holdings.head(10).iterrows()]
    except Exception:
        pass  # composition non publiée pour certains ETF européens
    return out

# Catalogue d'ETF courants. pea=True : éligible au PEA.
ETFS = [
    ("CW8.PA", "Amundi MSCI World", "Actions Monde", True),
    ("EWLD.PA", "Amundi PEA MSCI World", "Actions Monde", True),
    ("WPEA.PA", "iShares MSCI World Swap PEA", "Actions Monde", True),
    ("IWDA.AS", "iShares Core MSCI World", "Actions Monde", False),
    ("VWCE.DE", "Vanguard FTSE All-World", "Actions Monde", False),
    ("IUSN.DE", "iShares MSCI World Small Cap", "Actions Monde", False),
    ("ESE.PA", "BNP Paribas Easy S&P 500", "Actions USA", True),
    ("PUST.PA", "Amundi PEA Nasdaq-100", "Actions USA", True),
    ("RS2K.PA", "Amundi Russell 2000", "Actions USA", True),
    ("CSPX.AS", "iShares Core S&P 500", "Actions USA", False),
    ("SPY", "SPDR S&P 500", "Actions USA", False),
    ("QQQ", "Invesco QQQ (Nasdaq-100)", "Actions USA", False),
    ("VTI", "Vanguard Total Stock Market", "Actions USA", False),
    ("C40.PA", "Amundi CAC 40", "Actions Europe", True),
    ("MEUD.PA", "Amundi Stoxx Europe 600", "Actions Europe", True),
    ("PCEU.PA", "Amundi PEA MSCI Europe", "Actions Europe", True),
    ("EXSA.DE", "iShares Stoxx Europe 600", "Actions Europe", False),
    ("PAEEM.PA", "Amundi PEA MSCI Emerging Markets", "Actions Émergents", True),
    ("AASI.PA", "Amundi PEA MSCI EM Asia", "Actions Émergents", True),
    ("IEMG", "iShares Core MSCI Emerging Markets", "Actions Émergents", False),
    ("AGGH.AS", "iShares Core Global Aggregate Bond", "Obligations", False),
    ("BND", "Vanguard Total Bond Market", "Obligations", False),
    ("GLD", "SPDR Gold Shares", "Matières premières", False),
]

@app.get("/api/etfs")
def etf_list():
    return [{"symbol": s, "name": n, "category": c, "pea": p} for s, n, c, p in ETFS]

@cached(600)
def closes(symbols: tuple, period: str):
    df = yf.download(list(symbols), period=period, auto_adjust=True, progress=False, threads=True)
    if df.empty:
        raise HTTPException(502, "Données indisponibles pour le moment.")
    return df["Close"]

def risk_metrics(s: pd.Series):
    s = s.dropna()
    years = (s.index[-1] - s.index[0]).days / 365.25
    perf = s.iloc[-1] / s.iloc[0] - 1
    vol = s.pct_change().std() * math.sqrt(252)
    cagr = (1 + perf) ** (1 / years) - 1 if years >= 0.95 else None
    return {
        "price": round(float(s.iloc[-1]), 2), "perf": round(perf * 100, 2),
        "cagr": None if cagr is None else round(cagr * 100, 2),
        "vol": round(vol * 100, 2), "max_dd": round(float((s / s.cummax() - 1).min()) * 100, 2),
        "ratio": round((cagr if cagr is not None else perf) / vol, 2) if vol else None,
    }

@app.get("/api/etfs/compare")
def etf_compare(symbols: str, period: str = "1y"):
    syms = tuple(sorted({x.strip().upper() for x in symbols.split(",") if x.strip()}))
    if not syms or len(syms) > 40:
        raise HTTPException(400, "Indique entre 1 et 40 symboles.")
    df = closes(syms, period)
    rows, series, missing = [], {}, []
    for sym in syms:
        s = df[sym].dropna() if sym in df else pd.Series(dtype=float)
        if len(s) < 2:
            missing.append(sym)
            continue
        rows.append({"symbol": sym, **risk_metrics(s)})
        # base 100 ; ffill pour aligner les calendriers de bourses différentes
        series[sym] = clean(df[sym].ffill() / s.iloc[0] * 100)
    return {"dates": [d.strftime("%Y-%m-%d") for d in df.index], "rows": rows,
            "series": series, "missing": missing}

class Position(BaseModel):
    symbol: str
    qty: float
    buy_price: float

@app.post("/api/portfolio")
def portfolio(positions: list[Position]):
    rows, total, cost = [], 0.0, 0.0
    for p in positions:
        df = history(p.symbol.upper(), "5d")
        px = float(df["Close"].iloc[-1])
        val, paid = px * p.qty, p.buy_price * p.qty
        total += val; cost += paid
        rows.append({"symbol": p.symbol.upper(), "qty": p.qty, "buy_price": p.buy_price,
                     "price": round(px, 2), "value": round(val, 2),
                     "pnl": round(val - paid, 2), "pnl_pct": round((val / paid - 1) * 100, 2)})
    for r in rows:
        r["weight_pct"] = round(r["value"] / total * 100, 1) if total else 0
    return {"rows": rows, "total": round(total, 2), "pnl": round(total - cost, 2),
            "pnl_pct": round((total / cost - 1) * 100, 2) if cost else 0}
