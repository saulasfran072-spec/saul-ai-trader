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
    MARKETS,
)

st.set_page_config(page_title="SAUL AI TRADER V2")

st.title("📈 SAUL AI TRADER V2")

st.success("¡Conexión con config.py exitosa!")

st.write("Capital inicial:", INITIAL_CAPITAL)
st.write("Riesgo por operación:", MAX_RISK_PER_TRADE)
st.write("Pérdida diaria máxima:", MAX_DAILY_LOSS)
st.write("Operaciones máximas:", MAX_OPEN_TRADES)

st.write("Mercados disponibles:")
st.json(MARKETS)
