import streamlit as st

from config import INITIAL_CAPITAL
from trading.database import init_db, get_account, get_open_trades
from trading.simulator import (
    calculate_risk_budget,
    calculate_position_size,
    evaluate_open_trades,
    check_loss_limits,
    run_autopilot_cycle,
)

st.set_page_config(
    page_title="SAUL AI TRADER V2",
    page_icon="📈"
)

st.title("📈 SAUL AI TRADER V2")
st.subheader("Prueba 6: Conexión completa")

try:
    init_db()

    account = get_account()

    risk = calculate_risk_budget(INITIAL_CAPITAL)
    position = calculate_position_size(INITIAL_CAPITAL)

    st.success("¡Conexión con el simulador exitosa!")

    st.metric("Capital inicial", f"${INITIAL_CAPITAL:,.2f}")
    st.metric("Capital disponible", f"${account['capital']:,.2f}")
    st.metric("Riesgo por operación", f"${risk:,.2f}")
    st.metric("Tamaño de posición", f"${position:,.2f}")

    st.write("Operaciones abiertas:", len(get_open_trades()))

    st.write("Estado del piloto automático:",
             "Activado" if account["auto_pilot"] else "Desactivado")

except Exception as e:
    st.error("Error en la conexión")
    st.exception(e)
