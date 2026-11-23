# Configuración de seguridad y reglas de SAUL AI TRADER v2
INITIAL_CAPITAL = 10000.0
MAX_RISK_PER_TRADE = 0.05      # 5% máximo por operación
MAX_DAILY_LOSS = 0.10          # 10% límite de pérdida diaria
LEVERAGE = 1                   # Sin apalancamiento (1x)
TAKE_PROFIT_PCT = 0.04         # +4% toma de ganancias automática
STOP_LOSS_PCT = 0.02           # -2% corte de pérdidas automático

MARKETS = {
    "Criptomonedas": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "Acciones": ["AAPL", "MSFT", "NVDA", "TSLA"],
    "Materias Primas": ["GC=F", "CL=F", "SI=F"],
    "Forex": ["EURUSD=X", "JPY=X", "GBPUSD=X"]
}
