import streamlit as st

from trading.analyzer import get_live_price, analyze_asset

st.set_page_config(page_title="SAUL AI TRADER V2")

st.title("📈 SAUL AI TRADER V2")
st.subheader("Prueba 5: Análisis de mercado")

ticker = st.selectbox(
    "Seleccionar activo",
    ["BTC-USD", "ETH-USD", "SOL-USD", "AAPL", "NVDA"]
)

if st.button("Analizar mercado"):
    with st.spinner("Consultando mercado..."):

        price = get_live_price(ticker)
        analysis = analyze_asset(ticker)

        if price is not None:
            st.metric("Precio actual", f"${price:,.2f}")
        else:
            st.warning("No se pudo obtener el precio.")

        if analysis:
            st.success("¡Análisis completado!")

            st.write("Señal:", analysis["signal"])
            st.write("RSI:", analysis["rsi"])
            st.write("SMA 7:", analysis["sma_7"])
            st.write("SMA 20:", analysis["sma_20"])

            st.json(analysis)
        else:
            st.error("No se pudo completar el análisis.")
