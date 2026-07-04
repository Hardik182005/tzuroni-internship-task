import logging
import datetime
import numpy as np
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.database.schemas import PortfolioState, Order, Market, Trade
from app.services.trading_service import TradingService

logger = logging.getLogger("portfolio_agent")

class PortfolioAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Portfolio Agent. Your job is to monitor cash balances, calculate total portfolio equity, "
            "track PnL, monitor win rates, and calculate key performance indicators such as Sharpe Ratio, Sortino Ratio, and Drawdowns."
        )
        super().__init__("PortfolioAgent", system_prompt)

    def run(self, db: Session) -> PortfolioState:
        """
        Calculates all portfolio statistics and saves a new snapshot to the database.
        """
        logger.info(f"[{self.name}] Recalculating portfolio statistics...")

        # Get the current cash balance
        last_state = db.query(PortfolioState).order_by(PortfolioState.id.desc()).first()
        if not last_state:
            raise ValueError("Portfolio state not initialized in database.")

        cash = last_state.cash_balance
        
        # Calculate current value of all open positions
        open_val = TradingService.get_portfolio_positions_value(db)
        
        # Total Equity
        equity = round(cash + open_val, 2)

        # Retrieve all historical snapshots to calculate returns volatility
        history = db.query(PortfolioState).order_by(PortfolioState.id.asc()).all()
        equities = [h.equity for h in history] + [equity]

        # Daily Returns Calculation
        daily_ret = 0.0
        if len(equities) >= 2:
            daily_ret = (equities[-1] - equities[-2]) / equities[-2]

        # Calculate Sharpe and Sortino ratios
        sharpe = 0.0
        sortino = 0.0
        if len(equities) >= 5:
            # Convert equities to daily returns array
            rets = np.diff(equities) / equities[:-1]
            avg_ret = np.mean(rets)
            std_ret = np.std(rets)
            
            # Risk free rate assumed to be 0 for paper trading simplicity
            if std_ret > 0:
                sharpe = float((avg_ret / std_ret) * np.sqrt(252)) # Annualized
            
            # Sortino uses downside deviation
            downside_rets = rets[rets < 0]
            if len(downside_rets) > 0:
                downside_std = np.std(downside_rets)
                if downside_std > 0:
                    sortino = float((avg_ret / downside_std) * np.sqrt(252))

        # Win/Loss Rate & Profit Factor based on resolved markets
        resolved_markets = db.query(Market).filter(Market.resolved == True).all()
        wins = 0
        losses = 0
        total_profit = 0.0
        total_loss = 0.0

        for rm in resolved_markets:
            # Get orders for this market
            orders = db.query(Order).filter(Order.market_id == rm.id, Order.status == "FILLED").all()
            for o in orders:
                cost = o.quantity * o.price
                # If resolution matches side, payout is $1 per share, else $0
                payout = o.quantity * 1.0 if rm.resolution_result == o.side else 0.0
                pnl = payout - cost
                
                if pnl > 0:
                    wins += 1
                    total_profit += pnl
                elif pnl < 0:
                    losses += 1
                    total_loss += abs(pnl)

        total_resolved_trades = wins + losses
        win_rate = wins / total_resolved_trades if total_resolved_trades > 0 else 0.0
        loss_rate = losses / total_resolved_trades if total_resolved_trades > 0 else 0.0
        profit_factor = total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 1.0)

        # Max Drawdown
        max_equity = max(equities) if equities else equity
        drawdown = (max_equity - equity) / max_equity if max_equity > 0 else 0.0
        
        # Historical max drawdown
        peak = equities[0]
        max_dd = 0.0
        for eq in equities:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        # Current Exposure Percentage
        exposure_pct = open_val / equity if equity > 0 else 0.0

        # Save new snapshot
        new_state = PortfolioState(
            timestamp=datetime.datetime.utcnow(),
            cash_balance=cash,
            equity=equity,
            open_positions_value=open_val,
            daily_return=round(daily_ret, 4),
            weekly_return=round(daily_ret * 5, 4), # Simple scaling
            win_rate=round(win_rate, 4),
            loss_rate=round(loss_rate, 4),
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            max_drawdown=round(max_dd, 4),
            profit_factor=round(profit_factor, 4),
            exposure_pct=round(exposure_pct, 4)
        )
        db.add(new_state)
        db.commit()

        logger.info(
            f"[{self.name}] Portfolio updated. Total Equity: ${equity:.2f}, "
            f"Cash: ${cash:.2f}, Open Positions: ${open_val:.2f}, Drawdown: {max_dd:.2%}, Sharpe: {sharpe:.2f}"
        )
        return new_state
