from config import MAX_RISK_PER_TRADE, TAKE_PROFIT_PCT, STOP_LOSS_PCT
from trading.database import (
    get_account, open_trade_db, close_trade_db, get_open_trades
)
from trading.analyzer import get_live_price, analyze_asset

def calculate_position_size(capital: float) -> float:
    return round(capital * MAX_RISK_PER_TRADE, 2)

def evaluate_open_trades():
    open_trades = get_open_trades()
    results = []
    for t in open_trades:
        live = get_live_price(t["ticker"])
        if live is None:
            live = t["entry_price"]
        if t["side"] == "COMPRAR":
            pct = (live - t["entry_price"]) / t["entry_price"]
        else:
            pct = (t["entry_price"] - live) / t["entry_price"]
        floating_pnl = round(t["amount"] * pct, 2)

        if pct >= TAKE_PROFIT_PCT:
            close_trade_db(t["id"], live, reason="Take Profit (+4%)")
        elif pct <= -STOP_LOSS_PCT:
            close_trade_db(t["id"], live, reason="Stop Loss (-2%)")
        else:
            t["live_price"] = live
            t["floating_pnl"] = floating_pnl
            t["floating_pct"] = round(pct * 100, 2)
            results.append(t)
    return results

def run_autopilot_cycle(markets: dict):
    acc = get_account()
    if acc["emergency_stop"] or not acc["auto_pilot"]:
        return
    evaluate_open_trades()
    for market_name, tickers in markets.items():
        for ticker in tickers:
            acc = get_account()
            open_list = get_open_trades()
            if len(open_list) >= 5:
                return
            res = analyze_asset(ticker)
            if res and res["signal"] in ("COMPRAR", "VENDER"):
                size = calculate_position_size(acc["capital"])
                if size >= 10:
                    open_trade_db(ticker, res["signal"], res["price"], size)
