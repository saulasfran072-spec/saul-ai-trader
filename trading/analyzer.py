import yfinance as yf
import pandas as pd

class MarketAnalyzer:
    def fetch_data(self, ticker, period="1mo", interval="1h"):
        data = yf.download(ticker, period=period, interval=interval, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data

    def analyze_ticker(self, ticker):
        df = self.fetch_data(ticker)
        if df.empty or len(df) < 20:
            return {"ticker": ticker, "signal": "SIN DATOS", "price": 0.0, "rsi": 0.0}

        df["SMA_7"] = df["Close"].rolling(window=7).mean()
        df["SMA_20"] = df["Close"].rolling(window=20).mean()

        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        last_row = df.iloc[-1]
        price = float(last_row["Close"])
        sma_7 = float(last_row["SMA_7"])
        sma_20 = float(last_row["SMA_20"])
        rsi = float(last_row["RSI"])

        signal = "MANTENER"
        if sma_7 > sma_20 and rsi < 70:
            signal = "COMPRAR"
        elif sma_7 < sma_20 and rsi > 30:
            signal = "VENDER"

        return {
            "ticker": ticker,
            "price": round(price, 2),
            "sma_7": round(sma_7, 2),
            "sma_20": round(sma_20, 2),
            "rsi": round(rsi, 2),
            "signal": signal
        }
