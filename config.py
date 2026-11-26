# CONFIGURACIÓN SAUL AI TRADER V2

INITIAL_CAPITAL = 10000.0

# Gestión de riesgo
MAX_RISK_PER_TRADE = 0.005
MAX_DAILY_LOSS = 0.01
MAX_WEEKLY_LOSS = 0.02

# Límites operativos
MAX_OPEN_TRADES = 3
LEVERAGE = 1

# Objetivos y protección
TAKE_PROFIT_PCT = 0.04
STOP_LOSS_PCT = 0.02
WEEKLY_TARGET_PCT = 0.02

# Mercados
MARKETS = {
    "Criptomonedas": ["BTC-USD", "ETH-USD", "SOL-USD"],
    "Acciones": ["AAPL", "MSFT", "NVDA", "TSLA"],
    "Materias Primas": ["GC=F", "CL=F", "SI=F"],
    "Forex": ["EURUSD=X", "JPY=X", "GBPUSD=X"]
}
