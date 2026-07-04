import logging
import os
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.database.schemas import Prediction, PortfolioState, Market, Trade

logger = logging.getLogger("risk_management_agent")

class RiskManagementAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Risk Management Agent. Your job is to implement the Kelly Criterion, fractional Kelly sizing, "
            "enforce portfolio concentration limits, maximum drawdowns, and Value at Risk (VaR) constraints."
        )
        super().__init__("RiskManagementAgent", system_prompt)

    def run(self, db: Session, prediction: Prediction, market: Market) -> float:
        """
        Calculates the optimal trade size using Fractional Kelly and checks portfolio risk limits.
        Returns the allocation size in shares.
        """
        logger.info(f"[{self.name}] Assessing risk for market: {market.title} (Decision: {prediction.decision})")

        if prediction.decision == "NO TRADE":
            return 0.0

        # Load portfolio configuration
        fractional_kelly = float(os.getenv("FRACTIONAL_KELLY", "0.5"))
        max_exposure_pct = float(os.getenv("MAX_EXPOSURE_PCT", "0.20"))
        max_daily_loss_pct = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.05"))
        max_total_exposure_pct = float(os.getenv("MAX_TOTAL_EXPOSURE_PCT", "0.80"))

        # Fetch latest portfolio state
        portfolio = db.query(PortfolioState).order_by(PortfolioState.id.desc()).first()
        if not portfolio:
            logger.error("Portfolio state not found. Sizing set to 0.")
            return 0.0

        # Check daily loss limit
        if portfolio.daily_return < -max_daily_loss_pct:
            logger.warning(f"[{self.name}] Daily return ({portfolio.daily_return:.2%}) has breached limit (-{max_daily_loss_pct:.2%}). Stop Trading active.")
            return 0.0

        # Check max drawdown (stop trading if equity drawdown is > 20% from initial balance)
        initial_balance = float(os.getenv("INITIAL_BALANCE", "10000.0"))
        drawdown = (initial_balance - portfolio.equity) / initial_balance
        if drawdown > 0.20:
            logger.warning(f"[{self.name}] Cumulative drawdown ({drawdown:.2%}) has breached 20%. Stop Trading active.")
            return 0.0

        # Calculate Kelly Criterion position size percentage
        p = prediction.model_probability
        p_market = market.yes_price

        if prediction.decision == "BUY YES":
            # For buying YES, the contract price is p_market
            if p > p_market:
                f_star = (p - p_market) / (1.0 - p_market)
            else:
                f_star = 0.0
        elif prediction.decision == "BUY NO":
            # For buying NO, the contract price is 1.0 - p_market, and winning probability is 1.0 - p
            p_no_market = 1.0 - p_market
            p_no_model = 1.0 - p
            if p_no_model > p_no_market:
                f_star = (p_no_model - p_no_market) / (1.0 - p_no_market)
            else:
                f_star = 0.0
        else:
            f_star = 0.0

        # Apply fractional Kelly multiplier
        allocation_pct = f_star * fractional_kelly

        # Enforce maximum single trade exposure cap
        allocation_pct = min(allocation_pct, max_exposure_pct)
        allocation_pct = max(0.0, allocation_pct)

        # Convert allocation percentage to trade size in dollars, then to shares
        trade_capital = portfolio.equity * allocation_pct
        price_per_share = p_market if prediction.decision == "BUY YES" else (1.0 - p_market)

        if price_per_share <= 0:
            return 0.0

        # Enforce aggregate portfolio exposure cap: sum the dollar cost basis of
        # all trades on currently-unresolved markets and ensure this new trade
        # doesn't push total exposure past max_total_exposure_pct of equity.
        # Without this, per-trade caps alone allow N trades to each take up to
        # max_exposure_pct and collectively exhaust all cash.
        open_exposure = (
            db.query(Trade)
            .join(Market, Trade.market_id == Market.id)
            .filter(Market.resolved == False)
            .all()
        )
        current_exposure_value = sum(t.execution_price * t.quantity for t in open_exposure)
        max_total_exposure_value = portfolio.equity * max_total_exposure_pct
        remaining_capacity = max(0.0, max_total_exposure_value - current_exposure_value)

        if trade_capital > remaining_capacity:
            logger.warning(
                f"[{self.name}] Trade capital ${trade_capital:.2f} exceeds remaining portfolio "
                f"exposure capacity ${remaining_capacity:.2f} (cap {max_total_exposure_pct:.0%} of equity). Reducing size."
            )
            trade_capital = remaining_capacity

        if trade_capital <= 0:
            logger.warning(f"[{self.name}] Portfolio exposure cap reached. No capacity for new trade.")
            return 0.0

        shares_to_buy = trade_capital / price_per_share
        
        # Log risk metrics
        logger.info(
            f"[{self.name}] Risk evaluation complete. Kelly: {f_star:.2%}, "
            f"Fractional Sizing: {allocation_pct:.2%}, Sized Capital: ${trade_capital:.2f} ({shares_to_buy:.1f} shares)"
        )
        
        return round(shares_to_buy, 2)
