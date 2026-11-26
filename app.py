import streamlit as st
import inspect

from config import INITIAL_CAPITAL
from trading.simulator import (
    calculate_risk_budget,
    calculate_position_size,
    evaluate_open_trades,
)

st.set_page_config(page_title="SAUL AI TRADER V2")

st.title("📈 SAUL AI TRADER V2")
st.subheader("Prueba 4: Simulador de operaciones")

try:
    risk = calculate_risk_budget(INITIAL_CAPITAL)
    position = calculate_position_size(INITIAL_CAPITAL)

    st.success("¡Simulador conectado correctamente!")

    st.metric("Capital de referencia", f"${INITIAL_CAPITAL:,.2f}")
    st.metric("Riesgo por operación", f"${risk:,.2f}")
    st.metric("Tamaño de posición", f"${position:,.2f}")

    st.write("Función de evaluación:")
    st.code(str(inspect.signature(evaluate_open_trades)))

except Exception as e:
    st.error("Error al conectar el simulador")
    st.exception(e)
