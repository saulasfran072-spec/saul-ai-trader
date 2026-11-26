import streamlit as st

from config import (
    INITIAL_CAPITAL,
    MAX_RISK_PER_TRADE,
    MAX_DAILY_LOSS,
    MAX_WEEKLY_LOSS,
    MAX_OPEN_TRADES,
    TAKE_PROFIT_PCT,
    STOP_LOSS_PCT,
    WEEKLY_TARGET_PCT,
    MARKETS,)

from trading.database import (
    init_db,
    get_account,
    set_emergency_stop,
    set_auto_pilot,
    reset_account,
    get_open_trades,
    get_closed_trades,
    get_period_summary,
    get_archived_trades,)

from trading.simulator import (
    calculate_risk_budget,
    calculate_position_size,
    evaluate_open_trades,)


def _compute_period_stats(period_type: str, fallback_capital: float):
    snap = get_period_summary(period_type)

    if not snap:
        return {
            "starting_equity": fallback_capital,
            "ending_equity": fallback_capital,
            "realized_pnl": 0.0,
            "pnl_pct": 0.0,
        }

    start_eq = (
        snap["starting_equity"]
        if snap["starting_equity"] and snap["starting_equity"] > 0
        else fallback_capital
    )

    realized = snap["realized_pnl"] or 0.0
    pnl_pct = realized / start_eq if start_eq > 0 else 0.0

    return {
        "starting_equity": start_eq,
        "ending_equity": snap["ending_equity"] or fallback_capital,
        "realized_pnl": realized,
        "pnl_pct": pnl_pct,
    }


def evaluate_risk_traffic_light(
    acc: dict,
    daily_stats: dict,
    weekly_stats: dict,
    open_count: int,
):
    daily_loss_used = max(0.0, -daily_stats["pnl_pct"])
    weekly_loss_used = max(0.0, -weekly_stats["pnl_pct"])

    daily_ratio = (
        daily_loss_used / MAX_DAILY_LOSS
        if MAX_DAILY_LOSS > 0 else 0.0
    )

    weekly_ratio = (
        weekly_loss_used / MAX_WEEKLY_LOSS
        if MAX_WEEKLY_LOSS > 0 else 0.0
    )

    if (
        acc.get("emergency_stop")
        or daily_ratio >= 1.0
        or weekly_ratio >= 1.0
    ):
        return (
            "🔴",
            "Riesgo Crítico / Límite alcanzado",
            "Se alcanzó un límite de pérdida o está activa la parada de emergencia.",
        )

    if (
        daily_ratio >= 0.6
        or weekly_ratio >= 0.6
        or open_count >= MAX_OPEN_TRADES
    ):
        return (
            "🟡",
            "Precaución / Margen ajustado",
            "Acercándose al límite diario/semanal o al cupo máximo de operaciones abiertas.",
        )

    return (
        "🟢",
        "Operativo / Dentro de parámetros",
        "Riesgo diario, semanal y exposición simultánea dentro de los límites V2.",
    )


def render_performance_and_risk_center():
    init_db()

    acc = get_account()
    capital = acc["capital"] if acc else INITIAL_CAPITAL

    open_trades = get_open_trades()
    closed_trades = get_closed_trades()
    archived_trades = get_archived_trades()

    daily = _compute_period_stats("daily", capital)
    weekly = _compute_period_stats("weekly", capital)

    daily_limit_usd = round(
        daily["starting_equity"] * MAX_DAILY_LOSS, 2
    )

    weekly_limit_usd = round(
        weekly["starting_equity"] * MAX_WEEKLY_LOSS, 2
    )

    weekly_target_usd = round(
        weekly["starting_equity"] * WEEKLY_TARGET_PCT, 2
    )

    daily_remaining_usd = round(
        daily_limit_usd + min(0.0, daily["realized_pnl"]), 2
    )

    weekly_remaining_usd = round(
        weekly_limit_usd + min(0.0, weekly["realized_pnl"]), 2
    )

    risk_per_trade_usd = calculate_risk_budget(capital)
    suggested_size_usd = calculate_position_size(capital)

    light_icon, light_title, light_desc = evaluate_risk_traffic_light(
        acc or {},
        daily,
        weekly,
        len(open_trades),
    )

    st.subheader("Centro de Rendimiento y Riesgo")
    st.markdown(f"### {light_icon} {light_title}")
    st.caption(light_desc)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Capital Disponible",
        f"${capital:,.2f}",
    )

    c2.metric(
        "Riesgo por Trade (0.5%)",
        f"${risk_per_trade_usd:,.2f}",
        f"Posición base: ${suggested_size_usd:,.2f}",
    )

    c3.metric(
        "P&L Realizado Hoy",
        f"${daily['realized_pnl']:+,.2f}",
        f"Margen pérdida rest.: ${daily_remaining_usd:,.2f}",
    )

    c4.metric(
        "P&L Realizado Semana",
        f"${weekly['realized_pnl']:+,.2f}",
        f"Objetivo ref. (+2%): ${weekly_target_usd:+,.2f}",
    )

    daily_progress = (
        max(0.0, -daily["realized_pnl"]) / daily_limit_usd
        if daily_limit_usd > 0 else 0.0
    )

    st.progress(min(1.0, daily_progress))

    st.caption(
        f"Límite pérdida diaria: -${daily_limit_usd:,.2f} | "
        f"Margen semanal restante: ${weekly_remaining_usd:,.2f}"
    )

    st.caption(
        f"Operaciones abiertas: {len(open_trades)}/{MAX_OPEN_TRADES} | "
        f"Cerradas: {len(closed_trades)} | "
        f"Archivadas: {len(archived_trades)} | "
        f"SL: -{STOP_LOSS_PCT * 100:.0f}% / "
        f"TP: +{TAKE_PROFIT_PCT * 100:.0f}%"
                         )
