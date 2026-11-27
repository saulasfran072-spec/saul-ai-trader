import sqlite3
from datetime import datetime, timedelta
from config import INITIAL_CAPITAL, MAX_OPEN_TRADES

DB_PATH = "saul_trader.db"
PROFIT_LOCK_THRESHOLD = 20.0


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _table_columns(conn, table):
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column_if_missing(conn, table, column, definition):
    if column not in _table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    """
    Crea las tablas y conserva los datos existentes.
    No reinicia la cuenta ni crea snapshots en cada carga de Streamlit.
    """
    conn = get_conn()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            capital REAL NOT NULL DEFAULT 10000,
            auto_pilot INTEGER NOT NULL DEFAULT 0,
            emergency_stop INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            exit_price REAL,
            pnl REAL DEFAULT 0,
            reason TEXT,
            opened_at TEXT,
            closed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT NOT NULL,
            period_type TEXT NOT NULL,
            starting_equity REAL NOT NULL DEFAULT 0,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS trade_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_trade_id INTEGER,
            ticker TEXT,
            side TEXT,
            entry_price REAL,
            amount REAL,
            status TEXT,
            exit_price REAL,
            pnl REAL,
            reason TEXT,
            opened_at TEXT,
            closed_at TEXT,
            archived_at TEXT
        );

        CREATE TABLE IF NOT EXISTS protected_funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL DEFAULT 0,
            event_type TEXT NOT NULL,
            note TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS equity_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            capital REAL NOT NULL DEFAULT 0,
            invested REAL NOT NULL DEFAULT 0,
            floating_pnl REAL NOT NULL DEFAULT 0,
            protected REAL NOT NULL DEFAULT 0,
            equity REAL NOT NULL DEFAULT 0,
            usd_ars_rate REAL,
            equity_ars REAL,
            created_at TEXT
        );
        """)

        # Compatibilidad con bases creadas por versiones anteriores.
        for col, definition in {
            "capital": "REAL NOT NULL DEFAULT 10000",
            "auto_pilot": "INTEGER NOT NULL DEFAULT 0",
            "emergency_stop": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }.items():
            _add_column_if_missing(conn, "account", col, definition)

        for col, definition in {
            "status": "TEXT NOT NULL DEFAULT 'OPEN'",
            "exit_price": "REAL",
            "pnl": "REAL DEFAULT 0",
            "reason": "TEXT",
            "opened_at": "TEXT",
            "closed_at": "TEXT",
        }.items():
            _add_column_if_missing(conn, "trades", col, definition)

        for col, definition in {
            "snapshot_date": "TEXT",
            "period_type": "TEXT",
            "starting_equity": "REAL NOT NULL DEFAULT 0",
            "created_at": "TEXT",
        }.items():
            _add_column_if_missing(conn, "snapshots", col, definition)

        for col, definition in {
            "original_trade_id": "INTEGER",
            "ticker": "TEXT",
            "side": "TEXT",
            "entry_price": "REAL",
            "amount": "REAL",
            "status": "TEXT",
            "exit_price": "REAL",
            "pnl": "REAL",
            "reason": "TEXT",
            "opened_at": "TEXT",
            "closed_at": "TEXT",
            "archived_at": "TEXT",
        }.items():
            _add_column_if_missing(conn, "trade_archive", col, definition)

        for col, definition in {
            "amount": "REAL NOT NULL DEFAULT 0",
            "event_type": "TEXT",
            "note": "TEXT",
            "created_at": "TEXT",
        }.items():
            _add_column_if_missing(conn, "protected_funds", col, definition)

        for col, definition in {
            "capital": "REAL NOT NULL DEFAULT 0",
            "invested": "REAL NOT NULL DEFAULT 0",
            "floating_pnl": "REAL NOT NULL DEFAULT 0",
            "protected": "REAL NOT NULL DEFAULT 0",
            "equity": "REAL NOT NULL DEFAULT 0",
            "usd_ars_rate": "REAL",
            "equity_ars": "REAL",
            "created_at": "TEXT",
        }.items():
            _add_column_if_missing(conn, "equity_history", col, definition)

        row = conn.execute("SELECT id FROM account WHERE id = 1").fetchone()
        if row is None:
            now = _now()
            conn.execute("""
                INSERT INTO account
                (id, capital, auto_pilot, emergency_stop, created_at, updated_at)
                VALUES (1, ?, 0, 0, ?, ?)
            """, (INITIAL_CAPITAL, now, now))
            conn.commit()
            # Snapshots iniciales solamente al crear una cuenta nueva.
            _create_initial_snapshots()
        else:
            conn.commit()
    finally:
        conn.close()


def _create_initial_snapshots():
    conn = get_conn()
    try:
        row = conn.execute("SELECT capital FROM account WHERE id = 1").fetchone()
        starting = float(row["capital"]) if row else float(INITIAL_CAPITAL)
        now = datetime.now()
        for period_type in ("daily", "weekly"):
            start, _ = _period_bounds(period_type)
            conn.execute("""
                INSERT INTO snapshots
                (snapshot_date, period_type, starting_equity, created_at)
                VALUES (?, ?, ?, ?)
            """, (start.date().isoformat(), period_type, starting, now.isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()


def get_account():
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
        if row is None:
            now = _now()
            conn.execute("""
                INSERT INTO account
                (id, capital, auto_pilot, emergency_stop, created_at, updated_at)
                VALUES (1, ?, 0, 0, ?, ?)
            """, (INITIAL_CAPITAL, now, now))
            conn.commit()
            row = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_auto_pilot(enabled):
    conn = get_conn()
    try:
        # No permite activar el piloto si la parada de emergencia está activa.
        row = conn.execute(
            "SELECT emergency_stop FROM account WHERE id = 1"
        ).fetchone()
        if row is None:
            return False
        if enabled and row["emergency_stop"]:
            return False
        conn.execute(
            "UPDATE account SET auto_pilot = ?, updated_at = ? WHERE id = 1",
            (1 if enabled else 0, _now())
        )
        conn.commit()
        return True
    finally:
        conn.close()


def set_emergency_stop(enabled):
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE account SET emergency_stop = ?, updated_at = ? WHERE id = 1",
            (1 if enabled else 0, _now())
        )
        if enabled:
            conn.execute("UPDATE account SET auto_pilot = 0 WHERE id = 1")
        conn.commit()
    finally:
        conn.close()


def reset_account(archive_history=False):
    """
    Reinicio total y destructivo de la cuenta simulada.
    Borra operaciones, archivos, fondos protegidos, snapshots e historial
    de patrimonio. El argumento archive_history se conserva por compatibilidad,
    pero no se archiva nada porque el reinicio solicitado es total.
    No se ejecuta automáticamente al iniciar la aplicación.
    """
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT id FROM account WHERE id = 1").fetchone()
        if row is None:
            now = _now()
            conn.execute("""
                INSERT INTO account
                (id, capital, auto_pilot, emergency_stop, created_at, updated_at)
                VALUES (1, ?, 0, 0, ?, ?)
            """, (INITIAL_CAPITAL, now, now))
        else:
            conn.execute("""
                UPDATE account
                SET capital = ?, auto_pilot = 0, emergency_stop = 0, updated_at = ?
                WHERE id = 1
            """, (INITIAL_CAPITAL, _now()))

        for table in (
            "trades",
            "trade_archive",
            "protected_funds",
            "equity_history",
            "snapshots",
        ):
            conn.execute(f"DELETE FROM {table}")

        # Reinicia los contadores AUTOINCREMENT para que la cuenta quede limpia.
        conn.execute("""
            DELETE FROM sqlite_sequence
            WHERE name IN ('trades', 'trade_archive', 'protected_funds',
                           'equity_history', 'snapshots')
        """)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def open_trade_db(ticker, side, entry_price, amount):
    if not ticker or side not in ("COMPRAR", "VENDER"):
        return False
    try:
        entry_price = float(entry_price)
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        return False
    if entry_price <= 0 or amount <= 0:
        return False

    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        account = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
        if account is None or account["emergency_stop"] or not account["auto_pilot"]:
            conn.rollback()
            return False

        open_count = conn.execute("""
            SELECT COUNT(*) AS n FROM trades WHERE status = 'OPEN'
        """).fetchone()["n"]
        if open_count >= MAX_OPEN_TRADES:
            conn.rollback()
            return False

        duplicate = conn.execute("""
            SELECT id FROM trades WHERE ticker = ? AND status = 'OPEN' LIMIT 1
        """, (ticker,)).fetchone()
        if duplicate:
            conn.rollback()
            return False

        if amount > float(account["capital"]):
            conn.rollback()
            return False

        # El capital representa dinero libre; el importe pasa a estar invertido.
        new_capital = round(float(account["capital"]) - amount, 2)
        conn.execute("""
            UPDATE account SET capital = ?, updated_at = ? WHERE id = 1
        """, (new_capital, _now()))

        cur = conn.execute("""
            INSERT INTO trades
            (ticker, side, entry_price, amount, status, pnl, opened_at)
            VALUES (?, ?, ?, ?, 'OPEN', 0, ?)
        """, (ticker, side, entry_price, amount, _now()))
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_trade_db(trade_id, exit_price, reason="Cierre manual"):
    try:
        exit_price = float(exit_price)
    except (TypeError, ValueError):
        return False
    if exit_price <= 0:
        return False

    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        trade = conn.execute("""
            SELECT * FROM trades WHERE id = ? AND status = 'OPEN'
        """, (trade_id,)).fetchone()
        if trade is None or float(trade["entry_price"]) <= 0:
            conn.rollback()
            return False

        entry = float(trade["entry_price"])
        amount = float(trade["amount"])
        if trade["side"] == "COMPRAR":
            pct = (exit_price - entry) / entry
        else:
            pct = (entry - exit_price) / entry
        pnl = round(amount * pct, 2)

        # Devuelve el importe invertido más/menos el resultado a capital libre.
        account = conn.execute("SELECT capital FROM account WHERE id = 1").fetchone()
        current_capital = float(account["capital"]) if account else 0.0
        conn.execute("""
            UPDATE account SET capital = ?, updated_at = ? WHERE id = 1
        """, (round(current_capital + amount + pnl, 2), _now()))

        conn.execute("""
            UPDATE trades
            SET status = 'CLOSED', exit_price = ?, pnl = ?, reason = ?, closed_at = ?
            WHERE id = ?
        """, (exit_price, pnl, reason, _now(), trade_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_open_trades():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM trades WHERE status = 'OPEN' ORDER BY id ASC
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_closed_trades():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM trades
            WHERE status = 'CLOSED'
            ORDER BY closed_at DESC, id DESC
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_archived_trades():
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM trade_archive
            ORDER BY archived_at DESC, id DESC
        """).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _period_bounds(period_type):
    now = datetime.now()
    if period_type == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period_type == "weekly":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        raise ValueError("period_type debe ser 'daily' o 'weekly'")
    return start, now


def get_period_summary(period_type):
    start, _ = _period_bounds(period_type)
    conn = get_conn()
    try:
        snap = conn.execute("""
            SELECT starting_equity FROM snapshots
            WHERE period_type = ? AND snapshot_date = ?
            ORDER BY id DESC LIMIT 1
        """, (period_type, start.date().isoformat())).fetchone()

        if snap is None:
            account = conn.execute(
                "SELECT capital FROM account WHERE id = 1"
            ).fetchone()
            starting_equity = float(account["capital"]) if account else float(INITIAL_CAPITAL)
        else:
            starting_equity = float(snap["starting_equity"])

        realized = conn.execute("""
            SELECT COALESCE(SUM(pnl), 0) AS total
            FROM trades
            WHERE status = 'CLOSED' AND closed_at >= ?
        """, (start.isoformat(timespec="seconds"),)).fetchone()["total"]

        return {
            "starting_equity": starting_equity,
            "realized_pnl": float(realized or 0),
            "period_type": period_type,
        }
    finally:
        conn.close()


def _protected_balance_from_conn(conn):
    row = conn.execute("""
        SELECT COALESCE(SUM(
            CASE
                WHEN event_type IN ('PROTECT', 'LOCK', 'DEPOSIT') THEN amount
                WHEN event_type IN ('RELEASE', 'WITHDRAW') THEN -amount
                ELSE 0
            END
        ), 0) AS balance
        FROM protected_funds
    """).fetchone()
    return max(0.0, round(float(row["balance"] or 0), 2))


def get_protected_funds_summary():
    conn = get_conn()
    try:
        return {"balance": _protected_balance_from_conn(conn)}
    finally:
        conn.close()


def get_protected_funds_history(limit=100):
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT * FROM protected_funds
            ORDER BY id DESC LIMIT ?
        """, (max(1, int(limit)),)).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def release_protected_funds(amount, user_authorized=False):
    if not user_authorized:
        return False
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        return False
    if amount <= 0:
        return False

    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        balance = _protected_balance_from_conn(conn)
        if amount > balance:
            conn.rollback()
            return False

        account = conn.execute(
            "SELECT capital FROM account WHERE id = 1"
        ).fetchone()
        if account is None:
            conn.rollback()
            return False

        conn.execute("""
            INSERT INTO protected_funds (amount, event_type, note, created_at)
            VALUES (?, 'RELEASE', 'Liberación autorizada por el usuario', ?)
        """, (amount, _now()))
        conn.execute("""
            UPDATE account SET capital = ?, updated_at = ? WHERE id = 1
        """, (round(float(account["capital"]) + amount, 2), _now()))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def protect_eligible_profits():
    """
    Protege ganancias realizadas que superen el umbral.
    Descuenta el importe del capital libre para no contar el mismo dinero dos veces.
    La base de cálculo usa todo lo protegido históricamente, incluso si luego se libera,
    para no volver a bloquear automáticamente la misma ganancia.
    """
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")

        realized_row = conn.execute("""
            SELECT COALESCE(SUM(pnl), 0) AS total
            FROM trades
            WHERE status = 'CLOSED' AND pnl > 0
        """).fetchone()
        realized_profit = float(realized_row["total"] or 0)

        protected_ever_row = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM protected_funds
            WHERE event_type IN ('PROTECT', 'LOCK', 'DEPOSIT')
        """).fetchone()
        protected_ever = float(protected_ever_row["total"] or 0)

        eligible = round(max(
            0.0,
            realized_profit - PROFIT_LOCK_THRESHOLD - protected_ever
        ), 2)

        if eligible < 0.01:
            conn.commit()
            return 0.0

        account = conn.execute(
            "SELECT capital FROM account WHERE id = 1"
        ).fetchone()
        if account is None or float(account["capital"]) < eligible:
            conn.commit()
            return 0.0

        conn.execute("""
            UPDATE account SET capital = ?, updated_at = ? WHERE id = 1
        """, (round(float(account["capital"]) - eligible, 2), _now()))
        conn.execute("""
            INSERT INTO protected_funds (amount, event_type, note, created_at)
            VALUES (?, 'PROTECT', 'Ganancia realizada protegida automáticamente', ?)
        """, (eligible, _now()))
        conn.commit()
        return eligible
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def record_equity_point(capital, invested, floating_pnl, protected,
                        usd_ars_rate=None, equity=None, equity_ars=None):
    capital = float(capital or 0)
    invested = float(invested or 0)
    floating_pnl
