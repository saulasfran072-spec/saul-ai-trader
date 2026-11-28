import streamlit as st
import pandas as pd
import requests
import altair as alt
from streamlit_autorefresh import st_autorefresh

from config import (
    INITIAL_CAPITAL,
    MAX_DAILY_LOSS,
    MAX_WEEKLY_LOSS,
    MARKETS
)

from trading.database import (
    init_db,
    get_account,
    get_open_trades,
    get_closed_trades,
    get_period_summary,
    set_auto_pilot,
    set_emergency_stop,
    reset_account,
    get_protected_funds_summary,
    get_protected_funds_history,
    release_protected_funds,
    protect_eligible_profits,
    record_equity_point,
    get_equity_history
)

from trading.analyzer import get_live_price


# ==========================================
# CONFIGURACIÓN
# ==========================================

st.set_page_config(
    page_title="SAUL AI TRADER V2",
    page_icon="📈",
    layout="wide"
)

refresh_count = st_autorefresh(
    interval=60000,
    key="saul_refresh"
)

init_db()
protect_eligible_profits()


# ==========================================
# ESTILO VISUAL
# ==========================================

st.markdown("""
<style>

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

div[data-testid="stMetric"] {
    background-color: rgba(128,128,128,0.08);
    padding: 15px;
    border-radius: 12px;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 10px;
}

.stTabs [data-baseweb="tab"] {
    height: 55px;
    border-radius: 10px;
    padding: 10px 20px;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# FUNCIONES DE DATOS
# ==========================================

@st.cache_data(ttl=45)
def get_market_price(ticker):
    try:
        return get_live_price(ticker)
    except Exception:
        return None


@st.cache_data(ttl=60)
def get_dollar_rates():

    endpoints = {
        "Oficial": "https://monedapi.ar/api/v2/usd/oficial",
        "MEP": "https://monedapi.ar/api/v2/usd/bolsa",
        "Blue": "https://monedapi.ar/api/v2/usd/blue"
    }

    rates = {}

    for name, url in endpoints.items():

        try:
            response = requests.get(url, timeout=8)
            response.raise_for_status()

            data = response.json()

            buy = float(data["buy"])
            sell = float(data["sell"])

            if buy <= 0 or sell <= 0:
                continue

            rates[name] = {
                "compra": buy,
                "venta": sell,
                "actualizacion": data.get(
                    "lastScrapedAt",
                    data.get("updatedAt", "Sin información")
                )
            }

        except Exception:
            continue

    return rates


def money_usd(value):
    return f"USD ${value:,.2f}"


def money_ars(value):
    return f"ARS ${value:,.2f}"


# ==========================================
# ENCABEZADO
# ==========================================

st.title("📈 SAUL AI TRADER V2")

st.caption(
    "Sistema de supervisión, análisis y administración de capital"
)

st.caption(
    f"Actualización automática N.º {refresh_count} | "
    "Intervalo: 60 segundos"
)

st.divider()


# ==========================================
# CARGAR INFORMACIÓN
# ==========================================

account = get_account()

trades = get_open_trades()
closed = get_closed_trades()

protected = get_protected_funds_summary()

capital = float(account["capital"])
protected_balance = float(protected["locked"])

invested = 0.0
floating_gain = 0.0
floating_loss = 0.0

details = []


# ==========================================
# EVALUAR OPERACIONES
# ==========================================

for trade in trades:

    amount = float(trade["amount"])
    entry = float(trade["entry_price"])

    invested += amount

    price = get_market_price(trade["ticker"])

    if price is None or entry <= 0:

        details.append({
            "Activo": trade["ticker"],
            "Tipo": trade["side"],
            "Entrada": entry,
            "Actual": "Sin datos",
            "Resultado": "Sin datos"
        })

        continue

    if trade["side"] == "COMPRAR":
        change = (price - entry) / entry
    else:
        change = (entry - price) / entry

    pnl = amount * change

    if pnl > 0:
        floating_gain += pnl
    elif pnl < 0:
        floating_loss += abs(pnl)

    details.append({
        "Activo": trade["ticker"],
        "Tipo": trade["side"],
        "Entrada": entry,
        "Actual": price,
        "Resultado": round(pnl, 2)
    })


floating_pnl = floating_gain - floating_loss

equity = (
    capital
    + invested
    + floating_pnl
    + protected_balance
)

rates = get_dollar_rates()


# ==========================================
# REGISTRO DEL HISTORIAL DE PATRIMONIO
# ==========================================

usd_ars_rate = None

for currency in ["Blue", "MEP", "Oficial"]:

    if currency in rates:
        usd_ars_rate = rates[currency]["compra"]
        break


record_equity_point(
    capital=capital,
    invested=invested,
    floating_pnl=floating_pnl,
    protected=protected_balance,
    usd_ars_rate=usd_ars_rate
)


# ==========================================
# GRÁFICOS COMPACTOS DE EVOLUCIÓN
# ==========================================

st.subheader("📊 Evolución del patrimonio")

history = get_equity_history(limit=1000)

if history:

    history_df = pd.DataFrame(history)

    history_df["timestamp"] = pd.to_datetime(
        history_df["timestamp"],
        errors="coerce"
    )

    history_df["equity"] = pd.to_numeric(
        history_df["equity"],
        errors="coerce"
    )

    history_df = history_df.dropna(
        subset=["timestamp", "equity"]
    ).sort_values("timestamp")

    if not history_df.empty:

        st.markdown("#### 💵 Patrimonio en USD")

        usd_chart = alt.Chart(history_df).mark_bar(
            size=10,
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3
        ).encode(
            x=alt.X("timestamp:T", title=None),
            y=alt.Y(
                "equity:Q",
                title="Patrimonio USD",
                scale=alt.Scale(zero=True)
            ),
            tooltip=[
                alt.Tooltip("timestamp:T", title="Fecha"),
                alt.Tooltip(
                    "equity:Q",
                    title="Patrimonio USD",
                    format=",.2f"
                )
            ]
        ).properties(
            height=180
        )

        st.altair_chart(
            usd_chart,
            use_container_width=True
        )

        st.metric(
            "Patrimonio actual",
            money_usd(equity)
        )

        st.divider()

        st.markdown("#### 💱 Patrimonio en ARS")

        if (
            "equity_ars" in history_df.columns
            and history_df["equity_ars"].notna().any()
        ):

            history_ars = history_df.copy()

            history_ars["equity_ars"] = pd.to_numeric(
                history_ars["equity_ars"],
                errors="coerce"
            )

            history_ars = history_ars.dropna(
                subset=["equity_ars"]
            )

            ars_chart = alt.Chart(history_ars).mark_bar(
                size=10,
                cornerRadiusTopLeft=3,
                cornerRadiusTopRight=3
            ).encode(
                x=alt.X("timestamp:T", title=None),
                y=alt.Y(
                    "equity_ars:Q",
                    title="Patrimonio ARS",
                    scale=alt.Scale(zero=True)
                ),
                tooltip=[
                    alt.Tooltip("timestamp:T", title="Fecha"),
                    alt.Tooltip(
                        "equity_ars:Q",
                        title="Patrimonio ARS",
                        format=",.2f"
                    )
                ]
            ).properties(
                height=180
            )

            st.altair_chart(
                ars_chart,
                use_container_width=True
            )

            if usd_ars_rate:
                st.metric(
                    "Patrimonio actual",
                    money_ars(equity * usd_ars_rate)
                )

        else:

            st.info(
                "El historial en pesos aparecerá "
                "cuando se registre una cotización válida."
            )

        st.caption(
            "Historial registrado por SAUL AI TRADER. "
            "La conversión a ARS es estimativa."
        )

    else:

        st.info("Todavía no hay datos válidos para mostrar.")

else:

    st.info(
        "El gráfico aparecerá cuando se registre "
        "el primer punto de patrimonio."
    )

st.divider()


# ==========================================
# NAVEGACIÓN PRINCIPAL
# ==========================================

tab_usd, tab_ars, tab_withdraw = st.tabs([
    "💵 USD",
    "💱 CONVERSOR A ARS",
    "🏦 LISTO PARA RETIRAR"
])


# ==========================================
# ESPACIO 1: USD
# ==========================================

with tab_usd:

    st.subheader("💰 Resumen de cuenta")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Capital disponible",
            money_usd(capital)
        )

    with c2:
        st.metric(
            "Patrimonio estimado",
            money_usd(equity)
        )

    with c3:
        st.metric(
            "Operaciones abiertas",
            len(trades)
        )

    c4, c5 = st.columns(2)

    with c4:
        st.metric(
            "🟢 Ganancia flotante",
            money_usd(floating_gain)
        )

    with c5:
        st.metric(
            "🔴 Pérdida flotante",
            money_usd(floating_loss)
        )

    st.divider()

    st.subheader("🔒 Fondos protegidos")

    st.info(
        "Las ganancias realizadas se separan automáticamente "
        "en bloques de USD 20. El dinero protegido no forma "
        "parte del capital operativo."
    )

    p1, p2, p3 = st.columns(3)

    with p1:
        st.metric(
            "Dinero bloqueado",
            money_usd(protected_balance)
        )

    with p2:
        st.metric(
            "Capital operativo",
            money_usd(capital)
        )

    with p3:
        st.metric(
            "Objetivo de bloqueo",
            money_usd(20)
        )

    st.warning(
        "Los fondos protegidos no deben utilizarse para operar."
    )

    with st.expander("🔓 Autorizar liberación de fondos"):

        if protected_balance > 0:

            amount_to_release = st.number_input(
                "Cantidad que autorizás liberar (USD)",
                min_value=0.01,
                max_value=float(protected_balance),
                value=float(protected_balance),
                step=1.00,
                key="release_amount"
            )

            confirmation = st.checkbox(
                "Confirmo que autorizo liberar esta cantidad.",
                key="release_confirmation"
            )

            if st.button(
                "AUTORIZAR LIBERACIÓN",
                disabled=not confirmation
            ):

                success = release_protected_funds(
                    amount_to_release,
                    user_authorized=True
                )

                if success:
                    st.success("Liberación realizada.")
                    st.rerun()
                else:
                    st.error("No se pudo liberar el dinero.")

        else:

            st.success("No hay fondos protegidos pendientes.")

    with st.expander("📋 Historial de fondos protegidos"):

        protected_history = get_protected_funds_history()

        if protected_history:

            st.dataframe(
                pd.DataFrame(protected_history),
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("Todavía no hay movimientos.")

    st.divider()

    st.subheader("🌎 Mercados")

    st.caption(
        "Últimos precios disponibles. "
        "Los datos pueden presentar demoras."
    )

    market_rows = []

    for category, tickers in MARKETS.items():

        for ticker in tickers:

            price = get_market_price(ticker)

            market_rows.append({
                "Categoría": category,
                "Activo": ticker,
                "Precio USD": (
                    price if price is not None else "Sin datos"
                )
            })

    if market_rows:

        st.dataframe(
            pd.DataFrame(market_rows),
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    st.subheader("📊 Operaciones abiertas")

    if details:

        st.dataframe(
            pd.DataFrame(details),
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No hay operaciones abiertas.")

    with st.expander("📚 Historial de operaciones"):

        if closed:

            st.dataframe(
                pd.DataFrame(closed),
                use_container_width=True,
                hide_index=True
            )

        else:
            st.info("Todavía no hay operaciones cerradas.")

    st.divider()

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

            st.write(
                f"**Límite {label}:** {money_usd(max_loss)}"
            )

            st.write(
                f"Resultado realizado: {money_usd(realized)}"
            )

            st.write(
                f"Resultado combinado estimado: {money_usd(total)}"
            )

        else:

            st.info(
                f"No hay datos suficientes para el control {label}."
            )

    st.divider()

    st.subheader("⚙️ Estado del sistema")

    s1, s2 = st.columns(2)

    with s1:

        if account["auto_pilot"]:
            st.success("🟢 Piloto automático ACTIVADO")
        else:
            st.warning("Piloto automático DESACTIVADO")

    with s2:

        if account["emergency_stop"]:
            st.error("🚨 PARADA DE EMERGENCIA ACTIVADA")
        else:
            st.success("Sistema sin parada de emergencia")

    b1, b2, b3 = st.columns(3)

    with b1:

        if st.button("⛔ Desactivar piloto"):
            set_auto_pilot(False)
            st.rerun()

    with b2:

        if st.button("🟢 Activar piloto"):
            set_auto_pilot(True)
            st.rerun()

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

    # ==========================================
    # REINICIO TOTAL Y PROTEGIDO DE LA CUENTA
    # ==========================================

    st.divider()
    st.subheader("♻️ Reinicio de cuenta")

    st.warning(
        "Esta acción es irreversible. Elimina todas las operaciones, "
        "el historial de operaciones, los fondos protegidos y el historial "
        "de patrimonio. Restablece el capital simulado a USD 10.000 y "
        "desactiva el piloto automático y la parada de emergencia. "
        "No elimina ni modifica el código de SAUL AI TRADER."
    )

    with st.expander("Abrir opciones de reinicio"):

        st.write(
            "Para evitar un reinicio accidental, escribí exactamente "
            "**REINICIAR SAUL** en el campo de confirmación."
        )

        reset_phrase = st.text_input(
            "Confirmación de seguridad",
            key="reset_saul_confirmation",
            placeholder="REINICIAR SAUL"
        )

        reset_button = st.button(
            "♻️ REINICIAR TODA LA CUENTA",
            type="primary",
            disabled=(reset_phrase != "REINICIAR SAUL"),
            key="reset_saul_button"
        )

        if reset_button:

            try:
                # Apaga primero los controles y luego limpia los registros.
                set_auto_pilot(False)
                set_emergency_stop(False)

                success = reset_account(archive_history=False)

                if success:
                    # Evita que precios/cotizaciones cacheados confundan
                    # la primera visualización después del reinicio.
                    get_market_price.clear()
                    get_dollar_rates.clear()

                    st.session_state["reset_saul_confirmation"] = ""
                    st.success(
                        "Cuenta reiniciada. Capital simulado: USD 10.000. "
                        "Operaciones, fondos protegidos e historiales en cero."
                    )
                    st.rerun()
                else:
                    st.error("No se pudo completar el reinicio.")

            except Exception as exc:
                st.error(f"Error durante el reinicio: {exc}")


# ==========================================
# ESPACIO 2: CONVERSOR ARS
# ==========================================

with tab_ars:

    st.subheader("💱 Conversor de divisas")

    st.write(
        "Consultá las cotizaciones y calculá el valor "
        "estimado de tu capital en pesos argentinos."
    )

    if rates:

        rows = []

        for name, rate in rates.items():

            rows.append({
                "Cotización": name,
                "Compra": money_ars(rate["compra"]),
                "Venta": money_ars(rate["venta"])
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("Tu capital convertido")

        for name, rate in rates.items():

            st.markdown(f"### Dólar {name}")

            a, b = st.columns(2)

            with a:
                st.metric(
                    "Capital disponible",
                    money_ars(capital * rate["compra"])
                )

            with b:
                st.metric(
                    "Patrimonio estimado",
                    money_ars(equity * rate["compra"])
                )

            st.metric(
                "Fondos protegidos",
                money_ars(protected_balance * rate["compra"])
            )

            st.caption(
                f"Última actualización: {rate['actualizacion']}"
            )

            st.divider()

        st.subheader("Conversor personalizado")

        amount_usd = st.number_input(
            "Cantidad de dólares a convertir",
            min_value=0.0,
            value=100.0,
            step=10.0
        )

        selected_rate = st.selectbox(
            "Seleccioná cotización",
            list(rates.keys())
        )

        result = amount_usd * rates[selected_rate]["compra"]

        st.metric(
            "Resultado estimado",
            money_ars(result)
        )

        st.caption(
            "Conversión calculada con la cotización de compra."
        )

    else:

        st.warning(
            "No se pudieron obtener cotizaciones. "
            "Se intentará nuevamente en la próxima actualización."
        )
# ==========================================
# ESPACIO 3: LISTO PARA RETIRAR
# ==========================================
with tab_withdraw:

    st.subheader("🏦 Administración de brokers")

        st.info(
        "Este espacio permitirá supervisar los saldos, "
        "las ganancias y el dinero disponible para retirar "
        "en cada broker conectado."
    )

    st.warning(
        "Los brokers todavía no están conectados. "
        "No se muestran saldos reales ni disponibilidad confirmada."
    )

    brokers = [
        "BROKER 1",
        "BROKER 2",
        "BROKER 3"
    ]

    for broker in brokers:

        with st.container(border=True):

            st.markdown(f"### 🏦 {broker}")

            a, b, c = st.columns(3)

            with a:
                st.metric("Saldo total", "Pendiente")

            with b:
                st.metric("Disponible para retirar", "Pendiente")

            with c:
                st.metric("Ganancias realizadas", "Pendiente")

            st.warning("⚪ Broker sin conectar")

            st.markdown("**🧠 Recomendación de SAUL AI:**")

            st.info(
                "Pendiente de conexión. "
                "Se analizarán el saldo, las comisiones, "
                "las operaciones abiertas y las condiciones "
                "de retiro cuando se conecte la cuenta."
            )
