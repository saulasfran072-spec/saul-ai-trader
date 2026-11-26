import streamlit as st
import pandas as pd
import requests

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
    get_protected_funds_summary,
    get_protected_funds_history,
    release_protected_funds,
    protect_eligible_profits
)

from trading.analyzer import get_live_price


# ==========================================
# CONFIGURACIÓN GENERAL
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

# Comprobar ganancias y proteger bloques de USD 20.
protect_eligible_profits()


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
    "Sistema de supervisión y análisis de mercados"
)

st.caption(
    f"Actualización automática N.º {refresh_count} | "
    "Intervalo: 60 segundos"
)

st.divider()


# ==========================================
# DATOS DE CUENTA
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

# El dinero protegido también forma parte del patrimonio.
equity = (
    capital
    + invested
    + floating_pnl
    + protected_balance
)


# ==========================================
# COTIZACIONES DEL DÓLAR
# ==========================================

rates = get_dollar_rates()


# ==========================================
# RESUMEN DE CUENTA
# ==========================================

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


# ==========================================
# FONDOS PROTEGIDOS
# ==========================================

st.divider()

st.subheader("🔒 FONDOS PROTEGIDOS")

st.info(
    "Las ganancias realizadas se separan automáticamente "
    "en bloques de USD 20. El dinero protegido no forma "
    "parte del capital operativo."
)

p1, p2, p3 = st.columns(3)

with p1:
    st.metric(
        "🔐 Dinero bloqueado",
        money_usd(protected_balance)
    )

with p2:
    st.metric(
        "💵 Capital operativo",
        money_usd(capital)
    )

with p3:
    st.metric(
        "🎯 Objetivo de bloqueo",
        money_usd(20)
    )

st.warning(
    "El piloto automático no debe utilizar los fondos protegidos. "
    "La liberación requiere una acción manual."
)

st.markdown("### 🔓 Autorizar liberación de fondos")

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
        "Confirmo que autorizo liberar esta cantidad "
        "y devolverla al capital operativo.",
        key="release_confirmation"
    )

    if st.button(
        "🔓 AUTORIZAR LIBERACIÓN",
        disabled=not confirmation
    ):

        success = release_protected_funds(
            amount_to_release,
            user_authorized=True
        )

        if success:
            st.success(
                f"Se liberaron {money_usd(amount_to_release)} "
                "hacia el capital operativo."
            )
            st.rerun()
        else:
            st.error(
                "No se pudo liberar el dinero. "
                "Verificá el saldo protegido."
            )

else:

    st.success(
        "No hay fondos protegidos pendientes de autorización."
    )


st.markdown("### 📋 Historial de fondos protegidos")

protected_history = get_protected_funds_history()

if protected_history:

    history_df = pd.DataFrame(protected_history)

    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "Todavía no hay movimientos de fondos protegidos."
    )


# ==========================================
# CONVERSOR USD / ARS
# ==========================================

st.divider()

st.subheader("💱 Conversor de divisas")

if "show_currency" not in st.session_state:
    st.session_state.show_currency = False

if st.button("💱 VER CONVERSIONES"):

    st.session_state.show_currency = (
        not st.session_state.show_currency
    )

if st.session_state.show_currency:

    if rates:

        st.write("### Valor de 1 dólar")

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

        st.write("### Tu capital convertido")

        for name, rate in rates.items():

            ars_capital = capital * rate["compra"]
            ars_equity = equity * rate["compra"]
            ars_protected = protected_balance * rate["compra"]

            st.markdown(f"**Dólar {name}**")

            a, b = st.columns(2)

            with a:
                st.metric(
                    "Capital disponible",
                    money_ars(ars_capital)
                )

            with b:
                st.metric(
                    "Patrimonio estimado",
                    money_ars(ars_equity)
                )

            st.metric(
                "Fondos protegidos",
                money_ars(ars_protected)
            )

            st.caption(
                "Conversión estimada usando la cotización de compra."
            )

            st.caption(
                f"Última confirmación: {rate['actualizacion']}"
            )

            st.divider()

    else:

        st.warning(
            "No se pudieron obtener las cotizaciones. "
            "Se intentará nuevamente en la próxima actualización."
        )


# ==========================================
# MERCADOS
# ==========================================

st.divider()

st.subheader("🌎 Mercados")

st.caption(
    "Últimos precios disponibles. "
    "Los datos dependen del proveedor y pueden tener demoras."
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


# ==========================================
# ESTADO DEL SISTEMA
# ==========================================

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
# OPERACIONES ABIERTAS
# ==========================================

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


# ==========================================
# CONTROL DE RIESGO
# ==========================================

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


# ==========================================
# HISTORIAL DE OPERACIONES
# ==========================================

st.divider()

st.subheader("📚 Historial de operaciones")

if closed:

    st.dataframe(
        pd.DataFrame(closed),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "Todavía no hay operaciones cerradas."
    )


# ==========================================
# PIE DE PÁGINA
# ==========================================

st.divider()

st.caption(
    f"Capital inicial configurado: {money_usd(INITIAL_CAPITAL)}"
)

st.caption(
    "SAUL AI TRADER V2 | Sistema de supervisión"
)

st.caption(
    "Los resultados son simulados y no representan ganancias reales."
)
