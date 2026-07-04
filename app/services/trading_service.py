import uuid
import datetime
import logging
from typing import Dict, List
from sqlalchemy.orm import Session
from app.database.schemas import Order, Trade, Market, PortfolioState
from app.services.market_service import MarketService

logger = logging.getLogger("trading_service")

class TradingService:
    @staticmethod
    def place_and_execute_order(
        db: Session,
        market_id: str,
        side: str,  # "YES" or "NO"
        price_limit: float,  # Max price willing to pay (YES or NO price)
        quantity: float,  # Number of shares to buy
        order_type: str = "MARKET"
    ) -> Trade:
        """
        Executes a paper trade on a Polymarket weather market.
        Replicates walking the order book level-by-level to calculate fill price and slippage.
        """
        # Fetch the market
        market = db.query(Market).filter(Market.id == market_id).first()
        if not market:
            raise ValueError(f"Market '{market_id}' does not exist.")

        # Get latest portfolio state
        portfolio = db.query(PortfolioState).order_by(PortfolioState.id.desc()).first()
        if not portfolio:
            raise ValueError("Portfolio state not initialized.")

        # Determine target price for order book generation
        # YES price is market.yes_price. NO price is 1.0 - market.yes_price
        mid_price = market.yes_price if side == "YES" else market.no_price
        
        # Generate the order book for this contract side
        order_book = MarketService.get_order_book(market_id, mid_price)
        asks = order_book["asks"]  # Sellers of this contract. We buy from them.

        # Walk the ask book
        remaining_qty = quantity
        total_cost = 0.0
        filled_qty = 0.0
        fill_prices_weighted = 0.0

        for level in asks:
            if remaining_qty <= 0:
                break
            
            level_price = level["price"]
            # For LIMIT orders, we cannot buy above price_limit
            if order_type == "LIMIT" and level_price > price_limit:
                break
                
            level_qty = level["size"]
            fill_amount = min(remaining_qty, level_qty)
            
            total_cost += fill_amount * level_price
            fill_prices_weighted += fill_amount * level_price
            filled_qty += fill_amount
            remaining_qty -= fill_amount

        if filled_qty == 0:
            logger.warning(f"No execution possible for {quantity} shares of {side} in market {market_id}")
            return None

        avg_execution_price = fill_prices_weighted / filled_qty
        
        # Polymarket fee: 0.2% of fill value
        fee = total_cost * 0.002
        total_deduction = total_cost + fee

        if portfolio.cash_balance < total_deduction:
            logger.warning(f"Insufficient cash balance. Need ${total_deduction:.2f}, have ${portfolio.cash_balance:.2f}. Reducing order quantity.")
            # Reduce quantity to fit cash
            max_value = portfolio.cash_balance / 1.002
            filled_qty = max_value / avg_execution_price
            total_cost = max_value
            fee = total_cost * 0.002
            total_deduction = total_cost + fee
            if filled_qty < 1.0:
                logger.error("Drawn down to negligible cash. Cannot place order.")
                return None

        # Slippage calculation compared to the top ask
        top_ask_price = asks[0]["price"] if len(asks) > 0 else avg_execution_price
        slippage_bps = max(0.0, (avg_execution_price - top_ask_price) / top_ask_price * 10000.0)

        # Create Order record
        order_id = str(uuid.uuid4())
        new_order = Order(
            id=order_id,
            market_id=market_id,
            side=side,
            type=order_type,
            price=avg_execution_price,
            quantity=filled_qty,
            filled_quantity=filled_qty,
            status="FILLED",
            created_at=datetime.datetime.utcnow()
        )
        db.add(new_order)

        # Create Trade record
        trade_id = f"tr-{uuid.uuid4().hex[:12]}"
        new_trade = Trade(
            id=trade_id,
            order_id=order_id,
            market_id=market_id,
            side=side,
            execution_price=avg_execution_price,
            quantity=filled_qty,
            slippage_bps=round(slippage_bps, 2),
            executed_at=datetime.datetime.utcnow()
        )
        db.add(new_trade)

        # Update portfolio cash balance
        portfolio.cash_balance = round(portfolio.cash_balance - total_deduction, 2)
        portfolio.timestamp = datetime.datetime.utcnow()
        
        # Commit to db
        db.commit()

        logger.info(f"Order filled: Bought {filled_qty:.2f} shares of {side} in market {market_id} @ ${avg_execution_price:.2f}. Cash deduction: ${total_deduction:.2f}. Slippage: {slippage_bps:.1f} bps.")
        return new_trade

    @staticmethod
    def get_portfolio_positions_value(db: Session) -> float:
        """
        Calculates the current market value of all open contracts based on current market prices.
        """
        positions_value = 0.0
        
        # Get all filled orders
        orders = db.query(Order).filter(Order.status == "FILLED").all()
        
        # Aggregate positions
        positions = {}
        for o in orders:
            key = (o.market_id, o.side)
            positions[key] = positions.get(key, 0.0) + o.quantity

        for (m_id, side), qty in positions.items():
            market = db.query(Market).filter(Market.id == m_id).first()
            if market and not market.resolved:
                # Value position at current market price
                price = market.yes_price if side == "YES" else market.no_price
                positions_value += qty * price

        return round(positions_value, 2)

    @staticmethod
    def resolve_markets(db: Session, outcomes: Dict[str, str]):
        """
        Resolves active markets and updates the portfolio cash balance.
        If YES contract resolutions match the outcomes, the user receives $1.00 per share.
        Otherwise, they receive $0.00.
        """
        portfolio = db.query(PortfolioState).order_by(PortfolioState.id.desc()).first()
        if not portfolio:
            return

        for m_id, outcome in outcomes.items():
            market = db.query(Market).filter(Market.id == m_id, Market.resolved == False).first()
            if not market:
                continue

            logger.info(f"Resolving market {m_id} to '{outcome}'")
            
            # Find all filled orders for this market
            orders = db.query(Order).filter(Order.market_id == m_id, Order.status == "FILLED").all()
            
            # Aggregate what we hold
            yes_qty = sum(o.quantity for o in orders if o.side == "YES")
            no_qty = sum(o.quantity for o in orders if o.side == "NO")

            payout = 0.0
            if outcome == "YES":
                payout = yes_qty * 1.0
            elif outcome == "NO":
                payout = no_qty * 1.0

            # Update market resolution status
            market.resolved = True
            market.resolution_result = outcome

            # Credit payout to portfolio
            if payout > 0:
                portfolio.cash_balance = round(portfolio.cash_balance + payout, 2)
                logger.info(f"Market {m_id} payout received: ${payout:.2f}")

        portfolio.timestamp = datetime.datetime.utcnow()
        db.commit()
