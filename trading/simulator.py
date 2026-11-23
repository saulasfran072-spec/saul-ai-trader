from datetime import datetime

class TradingSimulator:
    def __init__(self, initial_capital):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.open_positions = []
        self.history = []

    def open_trade(self, ticker, side, price, amount_usd):
        if amount_usd > self.capital or amount_usd <= 0:
            return False
        qty = amount_usd / price
        self.capital -= amount_usd
        position = {
            "id": len(self.history) + len(self.open_positions) + 1,
            "ticker": ticker,
            "side": side,
            "entry_price": price,
            "qty": qty,
            "invested": amount_usd,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.open_positions.append(position)
        return True

    def close_trade(self, position_id, current_price):
        for pos in self.open_positions:
            if pos["id"] == position_id:
                exit_value = pos["qty"] * current_price
                pnl = exit_value - pos["invested"] if pos["side"] == "COMPRAR" else pos["invested"] - exit_value
                self.capital += (pos["invested"] + pnl)
                self.open_positions.remove(pos)
                record = {
                    **pos,
                    "exit_price": current_price,
                    "pnl": round(pnl, 2),
                    "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.history.append(record)
                return pnl
        return 0.0

    def close_all_positions(self, current_prices):
        for pos in list(self.open_positions):
            price = current_prices.get(pos["ticker"], pos["entry_price"])
            self.close_trade(pos["id"], price)
