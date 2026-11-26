import sqlite3
from datetime import datetime, timedelta

try:
    from config import INITIAL_CAPITAL, MAX_OPEN_TRADES
except ImportError:
    from ..config import INITIAL_CAPITAL, MAX_OPEN_TRADES

DB_PATH = "saul_trader.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _sync_snapshots(conn, current_capital: float, realized_pnl_delta: float = 0.0):
    now = datetime.now()
    day_key = now.strftime("%Y-%m-%d")
    monday = now - timedelta(days=now.weekday())
    week_key = monday.strftime("%Y-W%W")

    # El dinero invertido en operaciones abiertas sigue siendo
    # parte del patrimonio de la cuenta.
    invested = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM trades
        WHERE status = 'ABIERTA'
    """).fetchone()[0]

    total_equity = round(current_capital + invested, 2)

    for p_type, p_key in [("daily", day_key), ("weekly", week_key)]:
        row = conn.execute(
            """
            SELECT starting_equity, realized_pnl
            FROM snapshots
            WHERE period_type = ? AND period_key = ?
            """,
            (p_type, p_key),
        ).fetchone()

        if row is None:
            _record_snapshot(
                conn,
                p_type,
                p_key,
                total_equity,
                total_equity,
                realized_pnl_delta,
            )
        else:
            new_pnl = round(
                row["realized_pnl"] + realized_pnl_delta, 2
            )

            _record_snapshot(
                conn,
                p_type,
                p_key,
                row["starting_equity"],
                total_equity,
                new_pnl,
    )



def _sync_snapshots(conn, current_capital: float, realized_pnl_delta: float = 0.0):
    now = datetime.now()
    day_key = now.strftime("%Y-%m-%d")
    monday = now - timedelta(days=now.weekday())
    week_key = monday.strftime("%Y-W%W")

    for p_type, p_key in [("daily", day_key), ("weekly", week_key)]:
        row = conn.execute(
            "SELECT starting_equity, realized_pnl FROM snapshots WHERE period_type = ? AND period_key = ?",
            (p_type, p_key),
        ).fetchone()
        if row is None:
            _record_snapshot(conn, p_type, p_key, current_capital, current_capital, realized_pnl_delta)
        else:
            new_pnl = round(row["realized_pnl"] + realized_pnl_delta, 2)
            _record_snapshot(conn, p_type, p_key, row["starting_equity"], current_capital, new_pnl)


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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period_type TEXT,
            period_key TEXT,
            starting_equity REAL,
            ending_equity REAL,
            realized_pnl REAL,
            updated_at TEXT,
            UNIQUE(period_type, period_key)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trade_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            ticker TEXT,
            side TEXT,
            entry_price REAL,
            exit_price REAL,
            amount REAL,
            pnl REAL,
            status TEXT,
            reason TEXT,
            opened_at TEXT,
            closed_at TEXT,
            archived_at TEXT
        )
    """)
    cur.execute("SELECT COUNT(*) FROM account")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO account (id, capital, emergency_stop, auto_pilot) VALUES (1, ?, 0, 0)",
            (INITIAL_CAPITAL,),
        )
        _sync_snapshots(conn, INITIAL_CAPITAL, 0.0)
    else:
        acc = conn.execute("SELECT capital FROM account WHERE id = 1").fetchone()
        if acc is not None:
            _sync_snapshots(conn, acc["capital"], 0.0)
    conn.commit()
    conn.close()


def get_account():
    conn = get_conn()
    row = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
    conn.close()
    return dict(row)


def set_emergency_stop(active: bool):
    conn = get_conn()
    conn.execute(
        "UPDATE account SET emergency_stop = ?, auto_pilot = CASE WHEN ? = 1 THEN 0 ELSE auto_pilot END WHERE id = 1",
        (1 if active else 0, 1 if active else 0),
    )
    conn.commit()
    conn.close()


def set_auto_pilot(active: bool):
    conn = get_conn()
    conn.execute("UPDATE account SET auto_pilot = ? WHERE id = 1", (1 if active else 0,))
    conn.commit()
    conn.close()


def reset_account(archive_history: bool = True):
    conn = get_conn()
    if archive_history:
        run_id = datetime.now().strftime("RUN-%Y%m%d-%H%M%S")
        archived_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO trade_archive (
                run_id, ticker, side, entry_price, exit_price, amount, pnl,
                status, reason, opened_at, closed_at, archived_at
            )
            SELECT
                ?, ticker, side, entry_price, exit_price, amount, pnl,
                status, reason, opened_at, closed_at, ?
            FROM trades
        """, (run_id, archived_at))

    conn.execute("UPDATE account SET capital = ?, emergency_stop = 0, auto_pilot = 0 WHERE id = 1", (INITIAL_CAPITAL,))
    conn.execute("DELETE FROM trades")
    conn.execute("DELETE FROM snapshots")
    _sync_snapshots(conn, INITIAL_CAPITAL, 0.0)
    conn.commit()
    conn.close()


def open_trade_db(ticker: str, side: str, price: float, amount: float):
    conn = get_conn()
    acc = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
    if not acc or acc["emergency_stop"] or amount <= 0 or acc["capital"] < amount:
        conn.close()
        return False

    open_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'ABIERTA'").fetchone()[0]
    if open_count >= MAX_OPEN_TRADES:
        conn.close()
        return False

    exists = conn.execute(
        "SELECT COUNT(*) FROM trades WHERE ticker = ? AND status = 'ABIERTA'",
        (ticker,),
    ).fetchone()[0]
    if exists > 0:
        conn.close()
        return False

    new_cap = round(acc["capital"] - amount, 2)
    conn.execute("UPDATE account SET capital = ? WHERE id = 1", (new_cap,))
    conn.execute("""
        INSERT INTO trades (ticker, side, entry_price, amount, pnl, status, opened_at)
        VALUES (?, ?, ?, ?, 0.0, 'ABIERTA', ?)
    """, (ticker, side, price, amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    _sync_snapshots(conn, new_cap, 0.0)
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
    acc = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
    new_cap = round(acc["capital"] + returned, 2)

    conn.execute("UPDATE account SET capital = ? WHERE id = 1", (new_cap,))
    conn.execute("""
        UPDATE trades
        SET exit_price = ?, pnl = ?, status = 'CERRADA', reason = ?, closed_at = ?
        WHERE id = ?
    """, (current_price, pnl, reason, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), trade_id))
    _sync_snapshots(conn, new_cap, pnl)
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


def get_period_summary(period_type: str):
    now = datetime.now()
    if period_type == "daily":
        period_key = now.strftime("%Y-%m-%d")
    else:
        monday = now - timedelta(days=now.weekday())
        period_key = monday.strftime("%Y-W%W")

    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM snapshots WHERE period_type = ? AND period_key = ?",
        (period_type, period_key),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_archived_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trade_archive ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
    
