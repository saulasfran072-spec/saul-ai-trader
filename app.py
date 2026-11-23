import time
import streamlit as st
import pandas as pd
from config import MARKETS, INITIAL_CAPITAL, MAX_DAILY_LOSS
from trading.database import (
    init_db, get_account, set_emergency_stop, set_auto_pilot,
    reset_account, open_trade_db, close_trade_db, get_closed_trades
)
from trading.analyzer import analyze_asset, get_live_price
from trading.simulator import (
    calculate_position_size, evaluate_open_trades, run_autopilot_cycle
)

st.set_page_config(page_title="SAUL AI TRADER v2", page_icon="🤖", layout="wide")
init_db()

acc = get_account()

st.title("🤖 SAUL AI TRADER v2 — Piloto Automático")

# Botonera superior de seguridad y modo automático
c_btn1, c_btn2 = st.columns(2)
with c_btn1:
    if not acc["emergency_stop"]:
        if st.button("🚨 PARADA DE EMERGENCIA", type="primary", use_container_width=True):
            set_emergency_stop(True)
            st.rerun()
    else:
        if st.button("✅ REACTIVAR SISTEMA", use_container_width=True):
            set_emergency_stop(False)
            st.rerun()

with c_btn2:
    if not acc["emergency_stop"]:
        auto_label = "🟢 PILOTO AUTOMÁTICO: ENCENDIDO" if acc["auto_pilot"] else "⚪ ACTIVAR PILOTO AUTOMÁTICO"
        if st.button(auto_label, use_container_width=True):
            set_auto_pilot(not bool(acc["auto_pilot"]))
            st.rerun()

acc = get_account()

if acc["emergency_stop"]:
    st.error("SISTEMA DETENIDO POR EMERGENCIA — Todas las operaciones automáticas están bloqueadas.")
else:
    if acc["auto_pilot"]:
        st.info("🤖 Piloto Automático ACTIVO: Escaneando mercados y gestionando Take Profit (+4%) / Stop Loss (-2%) cada 60 segundos.")
        run_autopilot_cycle(MARKETS)
    else:
        st.success("ESTADO DEL SISTEMA: ACTIVO — Modo manual habilitado.")

# Evaluar posiciones abiertas en vivo
open_trades = evaluate_open_trades()
closed_trades = get_closed_trades()
acc = get_account()

realized_pnl = sum(t["pnl"] for t in closed_trades)
floating_pnl = sum(t["floating_pnl"] for t in open_trades)
invested_capital = sum(t["amount"] for t in open_trades)
total_equity = round(acc["capital"] + invested_capital + floating_pnl, 2)
net_pnl = round(total_equity - INITIAL_CAPITAL, 2)

# Control de pérdida diaria máxima (10%)
if net_pnl <= -(INITIAL_CAPITAL * MAX_DAILY_LOSS) and not acc["emergency_stop"]:
    set_emergency_stop(True)
    st.error("🛑 Límite de pérdida diaria del 10% alcanzado. Parada de emergencia activada automáticamente.")
    st.rerun()

# Métricas principales
m1, m2, m3, m4 = st.columns(4)
m1.metric("Patrimonio Total", f"${total_equity:,.2f}", f"{net_pnl:+.2f} $")
m2.metric("Capital Libre", f"${acc['capital']:,.2f}")
m3.metric("Ganancia Flotante (En vivo)", f"${floating_pnl:+.2f}")
m4.metric("Operaciones Abiertas", len(open_trades))

st.divider()

# Escáner de mercados
st.subheader("📊 Escáner de Mercados en Tiempo Real")
market_choice = st.selectbox("Selecciona un mercado:", list(MARKETS.keys()))

if st.button("🔍 Analizar Mercado Ahora"):
    with st.spinner("Descargando precios en vivo y calculando indicadores..."):
        results = [analyze_asset(t) for t in MARKETS[market_choice]]
        results = [r for r in results if r is not None]
        st.session_state.scan_results = results

if "scan_results" in st.session_state and st.session_state.scan_results:
    df_res = pd.DataFrame(st.session_state.scan_results)
    st.dataframe(df_res, use_container_width=True)

    if not acc["emergency_stop"]:
        st.subheader("Ejecutar Orden Manual")
        col_a, col_b, col_c = st.columns([2, 2, 1])
        with col_a:
            selected_ticker = st.selectbox("Activo", [r["ticker"] for r in st.session_state.scan_results])
        with col_b:
            direction = st.selectbox("Dirección", ["COMPRAR", "VENDER"])
        with col_c:
            st.write("")
            st.write("")
            pos_size = calculate_position_size(acc["capital"])
            if st.button(f"Abrir (${pos_size:.2f})"):
                asset_data = next(r for r in st.session_state.scan_results if r["ticker"] == selected_ticker)
                if open_trade_db(selected_ticker, direction, asset_data["price"], pos_size):
                    st.success(f"Orden abierta en {selected_ticker} por ${pos_size:.2f}")
                    st.rerun()
                else:
                    st.warning("Ya tienes una operación abierta en ese activo o capital insuficiente.")

st.divider()

# Operaciones abiertas e historial
tab1, tab2, tab3 = st.tabs(["⚡ Operaciones Abiertas (En Vivo)", "📜 Historial Cerrado", "⚙️ Reiniciar Simulador"])

with tab1:
    if not open_trades:
        st.info("No hay operaciones abiertas actualmente.")
    else:
        for t in open_trades:
            color = "🟢" if t["floating_pnl"] >= 0 else "🔴"
            c1, c2 = st.columns([4, 1])
            c1.write(
                f"{color} **#{t['id']} | {t['ticker']}** ({t['side']}) — "
                f"Entrada: `${t['entry_price']}` | Actual: `${t['live_price']}` | "
                f"Flotante: **`${t['floating_pnl']:+.2f} ({t['floating_pct']:+.2f}%)`**"
            )
            if c2.button("Cerrar", key=f"close_{t['id']}"):
                pnl = close_trade_db(t["id"], t["live_price"], reason="Manual")
                st.toast(f"Operación cerrada. Resultado: ${pnl:+.2f}")
                st.rerun()

with tab2:
    if not closed_trades:
        st.info("Aún no hay operaciones cerradas.")
    else:
        st.dataframe(pd.DataFrame(closed_trades), use_container_width=True)

with tab3:
    st.warning("Esto borrará todo el historial y devolverá el capital a $10,000.00.")
    if st.button("🔄 Reiniciar Cuenta Simulada a $10,000"):
        reset_account()
        st.rerun()

# Refresco automático cada 60 segundos si el Piloto Automático está encendido
if acc["auto_pilot"] and not acc["emergency_stop"]:
    time.sleep(60)
    st.rerun()
