import streamlit as st

from trading.database import (
    init_db,
    get_account,
    get_open_trades,
    set_auto_pilot
)

st.set_page_config(
    page_title="SAUL AI TRADER V2",
    page_icon="📈"
)

st.title("📈 SAUL AI TRADER V2")
st.subheader("Revisión de operaciones abiertas")

try:
    init_db()

    # Desactivar el piloto automático temporalmente.
    set_auto_pilot(False)

    account = get_account()
    trades = get_open_trades()

    st.success("Piloto automático desactivado.")

    st.metric(
        "Capital disponible",
        f"${account['capital']:,.2f}"
    )

    st.metric(
        "Operaciones abiertas",
        len(trades)
    )

    if trades:
        st.write("### Detalle de operaciones")

        for trade in trades:
            with st.expander(
                f"{trade['ticker']} - {trade['side']}"
            ):
                st.write("ID:", trade["id"])
                st.write("Activo:", trade["ticker"])
                st.write("Tipo:", trade["side"])
                st.write("Precio de entrada:", trade["entry_price"])
                st.write("Capital invertido:", f"${trade['amount']:,.2f}")
                st.write("Fecha de apertura:", trade["opened_at"])
    else:
        st.info("No hay operaciones abiertas.")

    st.warning(
        "Modo de revisión: no se abrirán ni cerrarán operaciones."
    )

except Exception as e:
    st.error("Error al revisar las operaciones.")
    st.exception(e)
