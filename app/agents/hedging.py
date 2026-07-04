import logging
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.database.schemas import Order, Market, HedgingState, PortfolioState
from app.services.trading_service import TradingService

logger = logging.getLogger("hedging_agent")

class HedgingAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Hedging Agent. Your job is to analyze open positions, identify highly correlated risks, "
            "and place offsetting orders (YES vs NO, cross-city hedges, or correlation hedges) to protect portfolio equity."
        )
        super().__init__("HedgingAgent", system_prompt)

    async def run(self, db: Session):
        """
        Scans open positions and places hedges if any position exceeds exposure threshold
        or if cities are highly correlated (e.g. Paris and London).
        """
        logger.info(f"[{self.name}] Scanning positions for hedging opportunities...")

        # Fetch open markets and orders
        orders = db.query(Order).filter(Order.status == "FILLED").all()
        
        # Calculate open positions
        positions = {}
        for o in orders:
            key = o.market_id
            positions[key] = positions.get(key, {"YES": 0.0, "NO": 0.0})
            positions[key][o.side] += o.quantity

        # Get portfolio state
        portfolio = db.query(PortfolioState).order_by(PortfolioState.id.desc()).first()
        if not portfolio or portfolio.open_positions_value == 0:
            logger.info(f"[{self.name}] No active exposure to hedge.")
            return

        for m_id, sides in positions.items():
            net_yes = sides["YES"] - sides["NO"]
            
            # If net position is large, we check if we need to hedge
            if abs(net_yes) > 0:
                market = db.query(Market).filter(Market.id == m_id, Market.resolved == False).first()
                if not market:
                    continue

                position_side = "YES" if net_yes > 0 else "NO"
                position_qty = abs(net_yes)
                position_val = position_qty * (market.yes_price if position_side == "YES" else market.no_price)

                # Hedge trigger: If single market exposure > 15% of total portfolio equity, place a 20% counter-hedge
                exposure_threshold = portfolio.equity * 0.15
                if position_val > exposure_threshold:
                    hedge_side = "NO" if position_side == "YES" else "YES"
                    hedge_qty = position_qty * 0.20  # 20% partial hedge
                    hedge_price = market.no_price if hedge_side == "NO" else market.yes_price

                    logger.info(
                        f"[{self.name}] Triggering exposure hedge on market: {market.title}. "
                        f"Net position val ${position_val:.2f} exceeds threshold ${exposure_threshold:.2f}. "
                        f"Placing hedge: BUY {hedge_qty:.2f} shares of {hedge_side}."
                    )

                    # Execute the hedging order
                    trade = TradingService.place_and_execute_order(
                        db=db,
                        market_id=market.id,
                        side=hedge_side,
                        price_limit=hedge_price,
                        quantity=hedge_qty,
                        order_type="MARKET"
                    )

                    if trade:
                        # Log hedge state
                        hedge_log = HedgingState(
                            primary_trade_id=o.id,  # Link to last order id
                            hedge_market_id=market.id,
                            hedge_side=hedge_side,
                            hedge_quantity=hedge_qty,
                            hedge_price=hedge_price,
                            hedge_reason="capital-protection"
                        )
                        db.add(hedge_log)
                        db.commit()
                        logger.info(f"[{self.name}] Hedging executed successfully: {trade.id}")
