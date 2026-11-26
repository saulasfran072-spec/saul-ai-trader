import streamlit as st

from config import INITIAL_CAPITAL
from trading.database import init_db, get_account

st.set_page_config(page_title="SAUL AI TRADER V2")

st.title("📈 SAUL AI TRADER V2")

try:
    init_db()
    account = get_account()

    st.success("¡Base de datos conectada correctamente!")

    st.write("Capital inicial:", INITIAL_CAPITAL)

    if account:
        st.write("Datos de la cuenta:")
        st.write(dict(account))
    else:
        st.warning("Base conectada, pero todavía no hay una cuenta creada.")

except Exception as e:
    st.error("Error al conectar la base de datos")
    st.exception(e)
