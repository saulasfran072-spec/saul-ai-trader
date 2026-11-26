from config import (
    MAX_RISK_PER_TRADE,
    MAX_OPEN_TRADES,
    MAX_DAILY_LOSS,
    MAX_WEEKLY_LOSS,
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT,
)

from trading.database import (
    get_account,
    open_trade_db,
    close_trade_db,
    get_open_trades,
    get_period_summary,
    set_auto_pilot,
)

from trading.analyzer import (
    get_live_price,
    analyze_asset,
)


def calculate_risk_budget(capital: float) -> float:
    return round(capital * MAX_RISK_PER_TRADE, 2)


def calculate_position_size(capital: float) -> float:

    risk_amount = calculate_risk_budget(capital)

    if STOP_LOSS_PCT <= 0:
        return risk_amount

    return round(risk_amount / STOP_LOSS_PCT, 2)


def evaluate_open_trades():

    open_trades = get_open_trades()
    results = []

    for trade in open_trades:

        live = get_live_price(trade["ticker"])

        if live is None or live <= 0:
            continue

        if trade["entry_price"] <= 0:
            continue

        if trade["side"] == "COMPRAR":

            pct = (
                live - trade["entry_price"]
            ) / trade["entry_price"]

        else:

            pct = (
                trade["entry_price"] - live
            ) / trade["entry_price"]

        floating_pnl = round(
            trade["amount"] * pct, 2
        )

        if pct >= TAKE_PROFIT_PCT:

            close_trade_db(
                trade["id"],
                live,
                reason="Take Profit"
            )

        elif pct <= -STOP_LOSS_PCT:

            close_trade_db(
                trade["id"],
                live,
                reason="Stop Loss"
            )

        else:

            trade["live_price"] = live
            trade["floating_pnl"] = floating_pnl
            trade["floating_pct"] = round(pct * 100, 2)

            results.append(trade)

    return results


def check_loss_limits(open_trades):

    floating_pnl = sum(
        trade.get("floating_pnl", 0)
        for trade in open_trades
    )

    limits = [
        ("daily", MAX_DAILY_LOSS, "DIARIO"),
        ("weekly", MAX_WEEKLY_LOSS, "SEMANAL"),
    ]

    for period_type, limit_pct, label in limits:

        summary = get_period_summary(period_type)

        if not summary:
            continue

        starting_equity = summary["starting_equity"]

        if starting_equity <= 0:
            continue

        realized_pnl = summary["realized_pnl"]

        total_pnl = realized_pnl + floating_pnl

        max_loss = starting_equity * limit_pct

        if total_pnl <= -max_loss:

            set_auto_pilot(False)

            return (
                True,
                f"LÍMITE DE PÉRDIDA {label} ALCANZADO"
            )

    return False, "Límites de pérdida respetados"


def run_autopilot_cycle(markets: dict):

    acc = get_account()

    if not acc:
        return "No existe una cuenta."

    if acc["emergency_stop"]:
        return "Sistema detenido por emergencia."

    if not acc["auto_pilot"]:
        return "Piloto automático desactivado."

    # Primero evaluar operaciones existentes.
    open_trades = evaluate_open_trades()

    # Comprobar límites diarios y semanales.
    stopped, message = check_loss_limits(open_trades)

    if stopped:
        return message

    # Buscar nuevas oportunidades.
    for market_name, tickers in markets.items():

        acc = get_account()

        if (
            not acc
            or acc["emergency_stop"]
            or not acc["auto_pilot"]
        ):
            return "Piloto automático detenido."

        open_list = get_open_trades()

        if len(open_list) >= MAX_OPEN_TRADES:
            return "Máximo de operaciones alcanzado."

        for ticker in tickers:

            acc = get_account()

            if (
                not acc
                or acc["emergency_stop"]
                or not acc["auto_pilot"]
            ):
                return "Piloto automático detenido."

            open_list = get_open_trades()

            if len(open_list) >= MAX_OPEN_TRADES:
                return "Máximo de operaciones alcanzado."

            # Evitar activos duplicados.
            if any(
                trade["ticker"] == ticker
                for trade in open_list
            ):
                continue

            analysis = analyze_asset(ticker)

            if not analysis:
                continue

            signal = analysis.get("signal")

            if signal not in ("COMPRAR", "VENDER"):
                continue

            price = analysis.get("price")

            if price is None or price <= 0:
                continue

            size = calculate_position_size(
                acc["capital"]
            )

            if size < 10 or acc["capital"] < size:
                continue

            opened = open_trade_db(
                ticker,
                signal,
                price,
                size
            )

            if opened:
                pass

    return "Ciclo de análisis completado."
