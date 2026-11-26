import sqlite3
from datetime import datetime, timedelta

try:
    from config import INITIAL_CAPITAL, MAX_OPEN_TRADES
except ImportError:
    from ..config import INITIAL_CAPITAL, MAX_OPEN_TRADES


DB_PATH = "saul_trader.db"
PROFIT_LOCK_THRESHOLD = 20.00


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ==========================================
# FONDOS PROTEGIDOS
# ==========================================

def init_protected_funds_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS protected_funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
    """)


def _get_protected_balance(conn):
    init_protected_funds_db(conn)

    locked = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM protected_funds
        WHERE event_type = 'LOCK'
    """).fetchone()[0]

    released = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM protected_funds
        WHERE event_type = 'RELEASE'
    """).fetchone()[0]

    return round(locked - released, 2)


def _get_current_run_locked(conn):
    init_protected_funds_db(conn)

    last_reset = conn.execute("""
        SELECT id
        FROM protected_funds
        WHERE event_type = 'RESET'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    if last_reset:
        reset_id = last_reset["id"]
        condition = "AND id > ?"
        params = (reset_id,)
    else:
        condition = ""
        params = ()

    result = conn.execute(f"""
        SELECT COALESCE(SUM(amount), 0)
        FROM protected_funds
        WHERE event_type = 'LOCK'
        {condition}
    """, params).fetchone()[0]

    return round(result, 2)


def _get_eligible_profit(conn):
    realized = conn.execute("""
        SELECT COALESCE(SUM(pnl), 0)
        FROM trades
        WHERE status = 'CERRADA'
    """).fetchone()[0]

    already_locked = _get_current_run_locked(conn)

    return round(max(0, realized - already_locked), 2)


def _lock_eligible_profits(conn):
    """
    Protege automáticamente bloques de USD 20
    de ganancias netas realizadas.
    """

    eligible = _get_eligible_profit(conn)

    amount_to_lock = (
        int((eligible + 0.000001) / PROFIT_LOCK_THRESHOLD)
        * PROFIT_LOCK_THRESHOLD
    )

    if amount_to_lock < PROFIT_LOCK_THRESHOLD:
        return 0.0

    account = conn.execute("""
        SELECT capital
        FROM account
        WHERE id = 1
    """).fetchone()

    if not account or account["capital"] < amount_to_lock:
        return 0.0

    new_capital = round(
        account["capital"] - amount_to_lock,
        2
    )

    conn.execute("""
        UPDATE account
        SET capital = ?
        WHERE id = 1
    """, (new_capital,))

    conn.execute("""
        INSERT INTO protected_funds (
            event_type,
            amount,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        "LOCK",
        amount_to_lock,
        "Ganancias protegidas automáticamente",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    return amount_to_lock


def protect_eligible_profits():
    """
    Comprueba y protege ganancias realizadas
    cuando se alcanza el umbral configurado.
    """

    conn = get_conn()

    try:
        amount = _lock_eligible_profits(conn)

        if amount > 0:
            account = conn.execute("""
                SELECT capital
                FROM account
                WHERE id = 1
            """).fetchone()

            if account:
                _sync_snapshots(conn, account["capital"], 0.0)

        conn.commit()
        return amount

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_protected_funds_summary():
    conn = get_conn()

    locked = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM protected_funds
        WHERE event_type = 'LOCK'
    """).fetchone()[0]

    released = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM protected_funds
        WHERE event_type = 'RELEASE'
    """).fetchone()[0]

    conn.close()

    return {
        "locked": round(locked - released, 2),
        "total_protected": round(locked, 2),
        "total_released": round(released, 2),
        "threshold": PROFIT_LOCK_THRESHOLD
    }


def release_protected_funds(amount, user_authorized=False):
    """
    Libera fondos únicamente si existe
    autorización explícita del usuario.
    """

    if user_authorized is not True:
        return False

    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        return False

    if amount <= 0:
        return False

    conn = get_conn()

    balance = _get_protected_balance(conn)

    if amount > balance:
        conn.close()
        return False

    account = conn.execute("""
        SELECT capital
        FROM account
        WHERE id = 1
    """).fetchone()

    if not account:
        conn.close()
        return False

    new_capital = round(account["capital"] + amount, 2)

    conn.execute("""
        UPDATE account
        SET capital = ?
        WHERE id = 1
    """, (new_capital,))

    conn.execute("""
        INSERT INTO protected_funds (
            event_type,
            amount,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        "RELEASE",
        amount,
        "Liberación autorizada por el usuario",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return True


def get_protected_funds_history():
    conn = get_conn()

    rows = conn.execute("""
        SELECT *
        FROM protected_funds
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ==========================================
# SNAPSHOTS
# ==========================================

def _record_snapshot(
    conn,
    period_type,
    period_key,
    starting_equity,
    ending_equity,
    realized_pnl
):
    conn.execute("""
        INSERT INTO snapshots (
            period_type,
            period_key,
            starting_equity,
            ending_equity,
            realized_pnl,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(period_type, period_key) DO UPDATE SET
            ending_equity = excluded.ending_equity,
            realized_pnl = excluded.realized_pnl,
            updated_at = excluded.updated_at
    """, (
        period_type,
        period_key,
        round(starting_equity, 2),
        round(ending_equity, 2),
        round(realized_pnl, 2),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))


def _sync_snapshots(
    conn,
    current_capital,
    realized_pnl_delta=0.0
):
    now = datetime.now()

    day_key = now.strftime("%Y-%m-%d")

    monday = now - timedelta(days=now.weekday())
    week_key = monday.strftime("%Y-W%W")

    invested = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM trades
        WHERE status = 'ABIERTA'
    """).fetchone()[0]

    protected = _get_protected_balance(conn)

    total_equity = round(
        current_capital + invested + protected,
        2
    )

    periods = [
        ("daily", day_key),
        ("weekly", week_key)
    ]

    for period_type, period_key in periods:

        row = conn.execute("""
            SELECT starting_equity, realized_pnl
            FROM snapshots
            WHERE period_type = ? AND period_key = ?
        """, (period_type, period_key)).fetchone()

        if row is None:
            _record_snapshot(
                conn,
                period_type,
                period_key,
                total_equity,
                total_equity,
                realized_pnl_delta
            )
        else:
            new_pnl = round(
                row["realized_pnl"] + realized_pnl_delta,
                2
            )

            _record_snapshot(
                conn,
                period_type,
                period_key,
                row["starting_equity"],
                total_equity,
                new_pnl
            )


# ==========================================
# INICIALIZAR BASE DE DATOS
# ==========================================

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

    init_protected_funds_db(conn)

    cur.execute("SELECT COUNT(*) FROM account")

    if cur.fetchone()[0] == 0:

        cur.execute("""
            INSERT INTO account (
                id,
                capital,
                emergency_stop,
                auto_pilot
            )
            VALUES (1, ?, 0, 0)
        """, (INITIAL_CAPITAL,))

        _sync_snapshots(conn, INITIAL_CAPITAL, 0.0)

    else:

        acc = conn.execute("""
            SELECT capital
            FROM account
            WHERE id = 1
        """).fetchone()

        if acc is not None:
            _sync_snapshots(conn, acc["capital"], 0.0)

    conn.commit()
    conn.close()


# ==========================================
# CUENTA
# ==========================================

def get_account():

    conn = get_conn()

    row = conn.execute("""
        SELECT *
        FROM account
        WHERE id = 1
    """).fetchone()

    conn.close()

    return dict(row) if row else None


def set_emergency_stop(active):

    conn = get_conn()

    conn.execute("""
        UPDATE account
        SET emergency_stop = ?,
            auto_pilot = CASE
                WHEN ? = 1 THEN 0
                ELSE auto_pilot
            END
        WHERE id = 1
    """, (
        1 if active else 0,
        1 if active else 0
    ))

    conn.commit()
    conn.close()


def set_auto_pilot(active):

    conn = get_conn()

    conn.execute("""
        UPDATE account
        SET auto_pilot = ?
        WHERE id = 1
    """, (1 if active else 0,))

    conn.commit()
    conn.close()


# ==========================================
# REINICIAR CUENTA
# ==========================================

def reset_account(archive_history=True):

    conn = get_conn()

    # No permitir borrar una cuenta con fondos protegidos.
    if _get_protected_balance(conn) > 0:
        conn.close()
        return False

    if archive_history:

        run_id = datetime.now().strftime(
            "RUN-%Y%m%d-%H%M%S"
        )

        archived_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        conn.execute("""
            INSERT INTO trade_archive (
                run_id,
                ticker,
                side,
                entry_price,
                exit_price,
                amount,
                pnl,
                status,
                reason,
                opened_at,
                closed_at,
                archived_at
            )
            SELECT
                ?, ticker, side, entry_price,
                exit_price, amount, pnl, status,
                reason, opened_at, closed_at, ?
            FROM trades
        """, (run_id, archived_at))

    conn.execute("""
        UPDATE account
        SET capital = ?,
            emergency_stop = 0,
            auto_pilot = 0
        WHERE id = 1
    """, (INITIAL_CAPITAL,))

    conn.execute("DELETE FROM trades")
    conn.execute("DELETE FROM snapshots")

    conn.execute("""
        INSERT INTO protected_funds (
            event_type,
            amount,
            description,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        "RESET",
        0,
        "Inicio de una nueva simulación",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    _sync_snapshots(conn, INITIAL_CAPITAL, 0.0)

    conn.commit()
    conn.close()

    return True


# ==========================================
# ABRIR OPERACIONES
# ==========================================

def open_trade_db(
    ticker,
    side,
    price,
    amount
):

    conn = get_conn()

    # Intentar proteger ganancias antes de operar.
    _lock_eligible_profits(conn)

    # Si hay ganancias que deberían protegerse pero
    # no se pudieron separar, bloquear nuevas operaciones.
    if _get_eligible_profit(conn) >= PROFIT_LOCK_THRESHOLD:

        conn.commit()
        conn.close()
        return False

    acc = conn.execute("""
        SELECT *
        FROM account
        WHERE id = 1
    """).fetchone()

    if (
        not acc
        or acc["emergency_stop"]
        or amount <= 0
        or acc["capital"] < amount
    ):
        conn.close()
        return False

    open_count = conn.execute("""
        SELECT COUNT(*)
        FROM trades
        WHERE status = 'ABIERTA'
    """).fetchone()[0]

    if open_count >= MAX_OPEN_TRADES:
        conn.close()
        return False

    exists = conn.execute("""
        SELECT COUNT(*)
        FROM trades
        WHERE ticker = ?
        AND status = 'ABIERTA'
    """, (ticker,)).fetchone()[0]

    if exists > 0:
        conn.close()
        return False

    new_cap = round(acc["capital"] - amount, 2)

    conn.execute("""
        UPDATE account
        SET capital = ?
        WHERE id = 1
    """, (new_cap,))

    conn.execute("""
        INSERT INTO trades (
            ticker,
            side,
            entry_price,
            amount,
            pnl,
            status,
            opened_at
        )
        VALUES (?, ?, ?, ?, 0.0, 'ABIERTA', ?)
    """, (
        ticker,
        side,
        price,
        amount,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    _sync_snapshots(conn, new_cap, 0.0)

    conn.commit()
    conn.close()

    return True


# ==========================================
# CERRAR OPERACIONES
# ==========================================

def close_trade_db(
    trade_id,
    current_price,
    reason="Manual"
):

    conn = get_conn()

    trade = conn.execute("""
        SELECT *
        FROM trades
        WHERE id = ?
        AND status = 'ABIERTA'
    """, (trade_id,)).fetchone()

    if not trade:
        conn.close()
        return 0.0

    if trade["entry_price"] <= 0:
        conn.close()
        return 0.0

    if trade["side"] == "COMPRAR":

        pct = (
            current_price - trade["entry_price"]
        ) / trade["entry_price"]

    else:

        pct = (
            trade["entry_price"] - current_price
        ) / trade["entry_price"]

    pnl = round(trade["amount"] * pct, 2)

    returned = round(trade["amount"] + pnl, 2)

    acc = conn.execute("""
        SELECT *
        FROM account
        WHERE id = 1
    """).fetchone()

    if not acc:
        conn.close()
        return 0.0

    new_cap = round(acc["capital"] + returned, 2)

    conn.execute("""
        UPDATE account
        SET capital = ?
        WHERE id = 1
    """, (new_cap,))

    conn.execute("""
        UPDATE trades
        SET exit_price = ?,
            pnl = ?,
            status = 'CERRADA',
            reason = ?,
            closed_at = ?
        WHERE id = ?
    """, (
        current_price,
        pnl,
        reason,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        trade_id
    ))

    # Proteger ganancias netas acumuladas.
    _lock_eligible_profits(conn)

    final_account = conn.execute("""
        SELECT capital
        FROM account
        WHERE id = 1
    """).fetchone()

    _sync_snapshots(conn, final_account["capital"], pnl)

    conn.commit()
    conn.close()

    return pnl


# ==========================================
# CONSULTAS DE OPERACIONES
# ==========================================

def get_open_trades():

    conn = get_conn()

    rows = conn.execute("""
        SELECT *
        FROM trades
        WHERE status = 'ABIERTA'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def get_closed_trades():

    conn = get_conn()

    rows = conn.execute("""
        SELECT *
        FROM trades
        WHERE status = 'CERRADA'
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# ==========================================
# RESUMEN DIARIO Y SEMANAL
# ==========================================

def get_period_summary(period_type):

    now = datetime.now()

    if period_type == "daily":

        period_key = now.strftime("%Y-%m-%d")

    else:

        monday = now - timedelta(days=now.weekday())
        period_key = monday.strftime("%Y-W%W")

    conn = get_conn()

    row = conn.execute("""
        SELECT *
        FROM snapshots
        WHERE period_type = ?
        AND period_key = ?
    """, (period_type, period_key)).fetchone()

    conn.close()

    return dict(row) if row else None


# ==========================================
# HISTORIAL ARCHIVADO
# ==========================================

def get_archived_trades():

    conn = get_conn()

    rows = conn.execute("""
        SELECT *
        FROM trade_archive
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return [dict(row) for row in rows]
