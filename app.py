import streamlit as st
import pandas as pd
import config
from trading.analyzer import MarketAnalyzer
from trading.simulator import TradingSimulator
from trading.risk_manager import RiskManager

st.set_page_config(page_title="SAUL AI TRADER", page_icon="🤖", layout="wide")

if "sim" not in st.session_state:
    st.session_state.sim = TradingSimulator(config.INITIAL_CAPITAL)
if "risk" not in st.session_state:
    st.session_state.risk = RiskManager(config.MAX_RISK_PER_TRADE, config.MAX_DAILY_LOSS)
if "analyzer" not in st.session_state:
    st.session_state.analyzer = MarketAnalyzer()

sim = st.session_state.sim
risk = st.session_state.risk
analyzer = st.session_state.analyzer

col_title, col_emerg = st.columns([3, 1])
with col_title:
    st.title("🤖 SAUL AI TRADER — Panel de Control")
with col_emerg:
    if not risk.emergency_stop:
        if st.button("🚨 PARADA DE EMERGENCIA", type="primary", use_container_width=True):
            risk.trigger_emergency_stop()
            sim.close_all_positions({})
            st.rerun()
    else:
        if st.button("🔄 Reactivar Sistema", use_container_width=True):
            risk.reset_emergency_stop()
            st.rerun()

can_trade, status_msg = risk.can_trade(sim.capital, sim.initial_capital)
if not can_trade:
    st.error(f"ESTADO DEL SISTEMA: DETENIDO — {status_msg}")
else:
    st.success(f"ESTADO DEL SISTEMA: ACTIVO — {status_msg}")

total_pnl = sum(item["pnl"] for item in sim.history)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Capital Disponible", f"${sim.capital:,.2f}")
m2.metric("Ganancia / Pérdida Neta", f"${total_pnl:,.2f}", delta=f"{(total_pnl/sim.initial_capital)*100:.2f}%")
m3.metric("Operaciones Abiertas", len(sim.open_positions))
m4.metric("Operaciones Cerradas", len(sim.history))

st.divider()

st.subheader("📊 Escáner de Mercados en Tiempo Real")
selected_category = st.selectbox("Selecciona un mercado:", list(config.MARKETS.keys()))

if st.button("🔍 Analizar Mercado Ahora"):
    results = [analyzer.analyze_ticker(t) for t in config.MARKETS[selected_category]]
    st.session_state.last_scan = results

if "last_scan" in st.session_state:
    df_scan = pd.DataFrame(st.session_state.last_scan)
    st.dataframe(df_scan, use_container_width=True, hide_index=True)

    if can_trade:
        st.markdown("#### Ejecutar Orden Simulada")
        c1, c2, c3 = st.columns(3)
        chosen_ticker = c1.selectbox("Activo", [r["ticker"] for r in st.session_state.last_scan])
        chosen_side = c2.selectbox("Dirección", ["COMPRAR", "VENDER"])
        ticker_info = next(r for r in st.session_state.last_scan if r["ticker"] == chosen_ticker)
        trade_amount = risk.calculate_position_size(sim.capital)
        if c3.button(f"Abrir Orden (${trade_amount:,.2f})", use_container_width=True):
            if sim.open_trade(chosen_ticker, chosen_side, ticker_info["price"], trade_amount):
                st.toast(f"Orden abierta en {chosen_ticker} a ${ticker_info['price']}")
                st.rerun()

st.divider()

tab1, tab2 = st.tabs(["⚡ Operaciones Abiertas", "📜 Historial de Movimientos"])
with tab1:
    if sim.open_positions:
        for pos in sim.open_positions:
            col_a, col_b = st.columns([4, 1])
            col_a.write(f"**#{pos['id']} | {pos['ticker']}** ({pos['side']}) — Entrada: `${pos['entry_price']}` | Invertido: `${pos['invested']:.2f}`")
            if col_b.button("Cerrar", key=f"close_{pos['id']}"):
                current_data = analyzer.analyze_ticker(pos["ticker"])
                sim.close_trade(pos["id"], current_data["price"])
                st.rerun()
    else:
        st.info("No hay operaciones abiertas actualmente.")

with tab2:
    if sim.history:
        st.dataframe(pd.DataFrame(sim.history), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no se han cerrado operaciones.")
