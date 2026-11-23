import sqlite3
from datetime import datetime
from config import INITIAL_CAPITAL

DB_PATH = "saul_trader.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY,
            capital REAL,
            emergency_stop INTEGER,
            auto_pilot INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            side TEXT,
            entry_price REAL,
            exit_price REAL,
            amount REAL,
            pnl REAL,
            status TEXT,
            reason TEXT,
            opened_at TEXT,
            closed_at TEXT
        )
    """)
    cur.execute("SELECT COUNT(*) FROM account")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO account (id, capital, emergency_stop, auto_pilot) VALUES (1, ?, 0, 0)", (INITIAL_CAPITAL,))
    conn.commit()
    conn.close()

def get_account():
    conn = get_conn()
    row = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
    conn.close()
    return dict(row)

def set_emergency_stop(active: bool):
    conn = get_conn()
    conn.execute("UPDATE account SET emergency_stop = ?, auto_pilot = CASE WHEN ? = 1 THEN 0 ELSE auto_pilot END WHERE id = 1", (1 if active else 0, 1 if active else 0))
    conn.commit()
    conn.close()

def set_auto_pilot(active: bool):
    conn = get_conn()
    conn.execute("UPDATE account SET auto_pilot = ? WHERE id = 1", (1 if active else 0,))
    conn.commit()
    conn.close()

def reset_account():
    conn = get_conn()
    conn.execute("UPDATE account SET capital = ?, emergency_stop = 0, auto_pilot = 0 WHERE id = 1", (INITIAL_CAPITAL,))
    conn.execute("DELETE FROM trades")
    conn.commit()
    conn.close()

def open_trade_db(ticker: str, side: str, price: float, amount: float):
    conn = get_conn()
    acc = get_account()
    if acc["emergency_stop"] or amount <= 0 or acc["capital"] < amount:
        conn.close()
        return False
    exists = conn.execute("SELECT COUNT(*) FROM trades WHERE ticker = ? AND status = 'ABIERTA'", (ticker,)).fetchone()[0]
    if exists > 0:
        conn.close()
        return False
    new_cap = round(acc["capital"] - amount, 2)
    conn.execute("UPDATE account SET capital = ? WHERE id = 1", (new_cap,))
    conn.execute("""
        INSERT INTO trades (ticker, side, entry_price, amount, pnl, status, opened_at)
        VALUES (?, ?, ?, ?, 0.0, 'ABIERTA', ?)
    """, (ticker, side, price, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return True

def close_trade_db(trade_id: int, current_price: float, reason: str = "Manual"):
    conn = get_conn()
    trade = conn.execute("SELECT * FROM trades WHERE id = ? AND status = 'ABIERTA'", (trade_id,)).fetchone()
    if not trade:
        conn.close()
        return 0.0
    if trade["side"] == "COMPRAR":
        pct = (current_price - trade["entry_price"]) / trade["entry_price"]
    else:
        pct = (trade["entry_price"] - current_price) / trade["entry_price"]
    pnl = round(trade["amount"] * pct, 2)
    returned = round(trade["amount"] + pnl, 2)
    acc = get_account()
    new_cap = round(acc["capital"] + returned, 2)
    conn.execute("UPDATE account SET capital = ? WHERE id = 1", (new_cap,))
    conn.execute("""
        UPDATE trades
        SET exit_price = ?, pnl = ?, status = 'CERRADA', reason = ?, closed_at = ?
        WHERE id = ?
    """, (current_price, pnl, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), trade_id))
    conn.commit()
    conn.close()
    return pnl

def get_open_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades WHERE status = 'ABIERTA' ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_closed_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades WHERE status = 'CERRADA' ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
