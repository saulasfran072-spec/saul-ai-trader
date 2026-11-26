import streamlit as st

from trading.database import init_db, get_open_trades
from trading.analyzer import get_live_price

st.set_page_config(page_title="SAUL AI TRADER V2")

st.title("📈 SAUL AI TRADER V2")
st.subheader("Análisis de operaciones abiertas")

init_db()

trades = get_open_trades()

for trade in trades:

    ticker = trade["ticker"]
    entry = trade["entry_price"]
    amount = trade["amount"]

    price = get_live_price(ticker)

    st.markdown(f"### {ticker}")

    st.write("Operación:", trade["side"])
    st.write("Precio de entrada:", entry)

    if price is None:
        st.warning("No se pudo obtener el precio actual.")
        continue

    if trade["side"] == "COMPRAR":
        change = (price - entry) / entry
    else:
        change = (entry - price) / entry

    pnl = amount * change

    st.metric("Precio actual", price)
    st.metric("Ganancia / Pérdida flotante", f"${pnl:.2f}")
    st.metric("Variación", f"{change * 100:.2f}%")

    st.divider()

st.info("Consulta únicamente informativa. No modifica operaciones.")
