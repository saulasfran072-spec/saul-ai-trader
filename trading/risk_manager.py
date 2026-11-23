class RiskManager:
    def __init__(self, max_risk_per_trade=0.05, max_daily_loss=0.10):
        self.max_risk_per_trade = max_risk_per_trade
        self.max_daily_loss = max_daily_loss
        self.emergency_stop = False

    def trigger_emergency_stop(self):
        self.emergency_stop = True

    def reset_emergency_stop(self):
        self.emergency_stop = False

    def can_trade(self, current_capital, initial_capital):
        if self.emergency_stop:
            return False, "BOTÓN DE EMERGENCIA ACTIVADO."
        drawdown = (initial_capital - current_capital) / initial_capital
        if drawdown >= self.max_daily_loss:
            return False, f"Límite de pérdida alcanzado ({drawdown:.1%})."
        return True, "Operativa habilitada."

    def calculate_position_size(self, available_capital):
        return available_capital * self.max_risk_per_trade
