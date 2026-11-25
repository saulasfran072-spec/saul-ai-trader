import streamlit as st
st.set_page_config(
    page_title="SAUL AI TRADER",
    page_icon="📈",
    layout="wide"
)

st.title("SAUL AI TRADER")
st.subheader("Sistema de Trading V2")

st.success("¡La aplicación está funcionando correctamente!")

st.metric("Capital inicial", "$10,000")
st.metric("Riesgo por operación", "0.5%")
st.metric("Pérdida diaria máxima", "1%")

st.info("Modo de prueba: sin operaciones reales.")
