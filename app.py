import streamlit as st
import pandas as pd

from config import (
    INITIAL_CAPITAL,
    MAX_DAILY_LOSS,
    MAX_WEEKLY_LOSS
)

from trading.database import (
    init_db,
    get_account,
    get_open_trades,
    get_closed_trades,
    get_period_summary,
    set_auto_pilot,
    set_emergency_stop
)

from trading.analyzer import get_live_price


st.set_page_config(
    page_title="SAUL AI TRADER V2",
    page_icon="📈",
    layout="wide"
)

init_db()

st.title("📈 SAUL AI TRADER V2")
st.caption("Panel de control y supervisión")

# =====================================
# DATOS DE LA CUENTA
# =====================================

account = get_account()
trades = get_open_trades()
closed = get_closed_trades()

floating_gain = 0.0
floating_loss = 0.0
floating_pnl = 0.0
invested = 0.0

details = []

# =====================================
# EVALUAR OPERACIONES ABIERTAS
# =====================================

for trade in trades:

    invested += trade["amount"]

    price = get_live_price(trade["ticker"])

    if price is None or trade["entry_price"] <= 0:

        details.append({
            "Activo": trade["ticker"],
            "Tipo": trade["side"],
            "Entrada": trade["entry_price"],
            "Actual": "Sin datos",
            "Resultado": "Sin datos"
        })

        continue

    if trade["side"] == "COMPRAR":

        change = (
            price - trade["entry_price"]
        ) / trade["entry_price"]

    else:

        change = (
            trade["entry_price"] - price
        ) / trade["entry_price"]

    pnl = trade["amount"] * change

    if pnl > 0:
        floating_gain += pnl

    elif pnl < 0:
        floating_loss += abs(pnl)

    details.append({
        "Activo": trade["ticker"],
        "Tipo": trade["side"],
        "Entrada": trade["entry_price"],
        "Actual": price,
        "Resultado": round(pnl, 2)
    })

floating_pnl = floating_gain - floating_loss

capital = account["capital"]

equity = capital + invested + floating_pnl

# =====================================
# RESUMEN DE CUENTA
# =====================================

st.subheader("💰 Resumen de cuenta")

st.metric(
    "💵 Capital disponible",
    f"${capital:,.2f}"
)

st.metric(
    "🏦 Patrimonio estimado",
    f"${equity:,.2f}"
)

st.metric(
    "🟢 Ganancia flotante",
    f"+${floating_gain:,.2f}"
)

st.metric(
    "🔴 Pérdida flotante",
    f"-${floating_loss:,.2f}"
)

st.metric(
    "📊 Operaciones abiertas",
    len(trades)
)

st.divider()

# =====================================
# ESTADO DEL SISTEMA
# =====================================

st.subheader("⚙️ Estado del sistema")

s1, s2 = st.columns(2)

with s1:

    if account["auto_pilot"]:
        st.success("Piloto automático ACTIVADO")

    else:
        st.warning("Piloto automático DESACTIVADO")

with s2:

    if account["emergency_stop"]:
        st.error("PARADA DE EMERGENCIA ACTIVADA")

    else:
        st.success("Sistema sin parada de emergencia")

b1, b2, b3 = st.columns(3)

with b1:

    if st.button("⛔ Desactivar piloto"):
        set_auto_pilot(False)
        st.rerun()

with b2:

    if st.button("🚨 PARADA DE EMERGENCIA"):
        set_emergency_stop(True)
        st.rerun()

with b3:

    if st.button("🔓 Quitar parada de emergencia"):
        set_emergency_stop(False)
        st.rerun()

st.caption(
    "Quitar la parada de emergencia no activa el piloto automático."
)

st.divider()

# =====================================
# OPERACIONES ABIERTAS
# =====================================

st.subheader("📊 Operaciones abiertas")

if details:

    st.dataframe(
        pd.DataFrame(details),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("No hay operaciones abiertas.")

st.divider()

# =====================================
# CONTROL DE RIESGO
# =====================================

st.subheader("🛡️ Control de riesgo")

for period, limit, label in [
    ("daily", MAX_DAILY_LOSS, "Diario"),
    ("weekly", MAX_WEEKLY_LOSS, "Semanal")
]:

    summary = get_period_summary(period)

    if summary and summary["starting_equity"] > 0:

        realized = summary["realized_pnl"]

        total = realized + floating_pnl

        max_loss = summary["starting_equity"] * limit

        st.write(f"**Límite {label}:** ${max_loss:,.2f}")

        st.write(
            f"Resultado realizado: ${realized:,.2f}"
        )

        st.write(
            f"Resultado combinado estimado: ${total:,.2f}"
        )

    else:

        st.info(
            f"No hay datos suficientes para el control {label}."
        )

st.divider()

# =====================================
# HISTORIAL
# =====================================

st.subheader("📚 Historial de operaciones")

if closed:

    st.dataframe(
        pd.DataFrame(closed),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("Todavía no hay operaciones cerradas.")

st.divider()

# =====================================
# PIE DE PÁGINA
# =====================================

st.caption(
    f"Capital inicial configurado: ${INITIAL_CAPITAL:,.2f}"
)

st.caption(
    "SAUL AI TRADER V2 | Panel de supervisión"
        )
