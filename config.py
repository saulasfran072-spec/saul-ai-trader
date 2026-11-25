# Configu# Configuración de seguridad y reglas de SAUL AI TRADER (V2)
# Configuración de seguridad y reglas de SAUL AI TRADER (V2)
INITIAL_CAPITAL = 10000.0
MAX_RISK_PER_TRADE = 0.005    # 0.5% de riesgo real por operación
MAX_DAILY_LOSS = 0.01         # 1% límite de pérdida diaria máxima
MAX_WEEKLY_LOSS = 0.02        # 2% límite de pérdida semanal máxima
MAX_OPEN_TRADES = 3           # Máximo de operaciones simultáneas
LEVERAGE = 1                  # Sin apalancamiento (1x)
TAKE_PROFIT_PCT = 0.04        # +4% toma de ganancia
STOP_LOSS_PCT = 0.02          # -2% corte de pérdida
WEEKLY_TARGET_PCT = 0.02      # +2% objetivo semanal orientativo

MARKETS = {
    "Criptomonedas": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "Acciones": ["AAPL", "MSFT", "NVDA", "TSLA"],
    "Materias Primas": ["GC=F", "CL=F", "SI=F"],
    "Forex": ["EURUSD=X", "JPY=X", "GBPUSD=X"]
}
