from config import MARKETS, INITIAL_CAPITAL, MAX_DAILY_LOSS
from trading.database import (
    init_db, get_account, set_emergency_stop, get_open_trades, get_closed_trades
)
from trading.simulator import evaluate_open_trades, run_autopilot_cycle

def main():
    init_db()
    acc = get_account()
    print("=== SAUL AI TRADER v3 — Ciclo Autónomo ===")

    if acc["emergency_stop"]:
        print("🚨 Parada de emergencia activa. Sin operaciones.")
        return

    open_trades = evaluate_open_trades()
    closed_trades = get_closed_trades()
    acc = get_account()

    floating_pnl = sum(t["floating_pnl"] for t in open_trades)
    invested_capital = sum(t["amount"] for t in open_trades)
    total_equity = round(acc["capital"] + invested_capital + floating_pnl, 2)
    net_pnl = round(total_equity - INITIAL_CAPITAL, 2)

    if net_pnl <= -(INITIAL_CAPITAL * MAX_DAILY_LOSS):
        set_emergency_stop(True)
        print("🛑 Límite de pérdida diaria (-10%) alcanzado. Parada de emergencia activada.")
        return

    if acc["auto_pilot"]:
        print("🤖 Piloto Automático ENCENDIDO: Escaneando mercados...")
        run_autopilot_cycle(MARKETS)
    else:
        print("⏸️ Piloto Automático APAGADO: Solo se vigilaron posiciones abiertas.")

    open_after = get_open_trades()
    acc_after = get_account()
    print(f"Patrimonio estimado: ${total_equity:,.2f} | Libre: ${acc_after['capital']:,.2f} | Abiertas: {len(open_after)}")

if __name__ == "__main__":
    main()
