import logging
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.database.schemas import Prediction, Market
from app.services.trading_service import TradingService
from app.services.telegram_service import TelegramService

logger = logging.getLogger("execution_agent")

class ExecutionAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Execution Agent. Your job is to interact with the Paper Trading engine, "
            "place buy/sell/hedge orders against order books, calculate slippage, and maintain transaction logs."
        )
        super().__init__("ExecutionAgent", system_prompt)

    async def run(self, db: Session, prediction: Prediction, market: Market, shares_to_buy: float):
        """
        Submits trade requests to the paper trader engine and logs execution.
        """
        if prediction.decision == "NO TRADE" or shares_to_buy <= 0:
            logger.info(f"[{self.name}] No trade to execute for market: {market.title}")
            return None

        logger.info(f"[{self.name}] Executing trade for market '{market.title}': {prediction.decision} - {shares_to_buy} shares")
        
        # Decide side
        side = "YES" if prediction.decision == "BUY YES" else "NO"
        price_limit = market.yes_price if side == "YES" else market.no_price

        # Call TradingService to match orders and deduct cash
        trade = TradingService.place_and_execute_order(
            db=db,
            market_id=market.id,
            side=side,
            price_limit=price_limit,
            quantity=shares_to_buy,
            order_type="MARKET"
        )

        if trade:
            logger.info(f"[{self.name}] Trade successfully completed: {trade.id}")
            
            # Send Telegram Alert
            msg = (
                f"🔔 *New Trade Executed*\n\n"
                f"*Market*: {market.title}\n"
                f"*Side*: {trade.side}\n"
                f"*Avg Price*: ${trade.execution_price:.2f}\n"
                f"*Quantity*: {trade.quantity:.2f} shares\n"
                f"*Slippage*: {trade.slippage_bps:.1f} bps"
            )
            TelegramService.send_message(msg)
            
            # Send LLM verification
            prompt = (
                f"Verify the trade execution log:\n"
                f"Trade ID: {trade.id}\n"
                f"Market: {market.title}\n"
                f"Side: {trade.side}\n"
                f"Price: ${trade.execution_price:.2f}\n"
                f"Shares: {trade.quantity:.2f}\n"
                f"Slippage: {trade.slippage_bps} bps\n"
                f"Analyze if fill execution was clean or had excessive slippage."
            )
            analysis = await self.call_llm(prompt)
            logger.info(f"[{self.name}] Execution post-trade analysis: {analysis[:100]}...")
            return trade
        else:
            logger.error(f"[{self.name}] Trade execution failed.")
            return None
