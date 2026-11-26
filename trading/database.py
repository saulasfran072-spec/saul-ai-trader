# ==========================================
# SAUL AI TRADER V2 - FONDOS PROTEGIDOS
# ==========================================

PROFIT_LOCK_THRESHOLD = 20.00


def init_protected_funds_db(conn=None):
    own_connection = conn is None

    if own_connection:
        conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS protected_funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
    """)

    if own_connection:
        conn.commit()
        conn.close()


def protect_realized_profits(conn):
    """
    Bloquea automáticamente cada USD 20
    de ganancias realizadas acumuladas.
    Debe ejecutarse dentro de la transacción
    que cierra una operación.
    """

    init_protected_funds_db(conn)

    realized = conn.execute("""
        SELECT COALESCE(SUM(pnl), 0)
        FROM trades
        WHERE status = 'CERRADA'
    """).fetchone()[0]

    already_locked = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM protected_funds
        WHERE event_type = 'LOCK'
    """).fetchone()[0]

    eligible = max(0, realized - already_locked)

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

    conn.execute("""
        UPDATE account
        SET capital = capital - ?
        WHERE id = 1
    """, (amount_to_lock,))

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


def get_protected_funds_summary():
    conn = get_conn()
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

    conn.close()

    return {
        "locked": round(locked - released, 2),
        "total_protected": round(locked, 2),
        "total_released": round(released, 2)
    }
