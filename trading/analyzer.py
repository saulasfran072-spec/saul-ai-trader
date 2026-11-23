import yfinance as yf
import pandas as pd

def get_decimals(ticker: str) -> int:
    return 4 if "=X" in ticker and "JPY" not in ticker else 2

def get_live_price(ticker: str):
    try:
        df = yf.download(ticker, period="2d", interval="15m", progress=False)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        price = float(df["Close"].iloc[-1])
        return round(price, get_decimals(ticker))
    except Exception:
        return None

def analyze_asset(ticker: str):
    try:
        df = yf.download(ticker, period="5d", interval="1h", progress=False)
        if df.empty or len(df) < 20:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        sma_fast = close.rolling(window=7).mean().iloc[-1]
        sma_slow = close.rolling(window=20).mean().iloc[-1]

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean().iloc[-1]
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean().iloc[-1]
        rs = gain / loss if loss != 0 else 0
        rsi = 100 - (100 / (1 + rs))

        price = float(close.iloc[-1])
        dec = get_decimals(ticker)

        if sma_fast > sma_slow and rsi < 68:
            signal = "COMPRAR"
        elif sma_fast < sma_slow and rsi > 32:
            signal = "VENDER"
        else:
            signal = "MANTENER"

        return {
            "ticker": ticker,
            "price": round(price, dec),
            "sma_7": round(float(sma_fast), dec),
            "sma_20": round(float(sma_slow), dec),
            "rsi": round(float(rsi), 2),
            "signal": signal
        }
    except Exception:
        return None
