import logging
import os
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.services.market_service import MarketService
from app.database.schemas import Market

logger = logging.getLogger("market_agent")

class MarketAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Market Agent. Your job is to collect active prediction markets, YES/NO contract prices, "
            "liquidity depth, historical odds, and calculate market-implied probabilities."
        )
        super().__init__("MarketAgent", system_prompt)

    async def run(self, db: Session, target_cities: list) -> list:
        """
        Fetches live Polymarket weather prediction markets. If none are found,
        it generates simulated weather markets for the target cities.
        Saves all discovered/simulated markets to the database.
        """
        logger.info(f"[{self.name}] Scanning prediction markets...")
        
        # Try fetching live markets first
        markets = await MarketService.fetch_live_weather_markets()
        
        # Fallback to simulated markets if live is empty and config permits
        simulate_empty = os.getenv("SIMULATE_MARKETS_IF_EMPTY", "True") == "True"
        if not markets and simulate_empty:
            logger.info(f"[{self.name}] No live weather markets found. Generating high-fidelity simulated markets.")
            markets = MarketService.generate_simulated_markets(target_cities)

        # Sync markets with database
        synced_markets = []
        for m in markets:
            existing = db.query(Market).filter(Market.id == m["id"]).first()
            if existing:
                # Update prices, volume, and liquidity
                existing.yes_price = m["yes_price"]
                existing.no_price = m["no_price"]
                existing.volume_24h = m["volume_24h"]
                existing.liquidity = m["liquidity"]
                existing.resolved = m.get("resolved", existing.resolved)
                synced_markets.append(existing)
            else:
                db_market = Market(**m)
                db.add(db_market)
                synced_markets.append(db_market)

        db.commit()
        
        logger.info(f"[{self.name}] Sync completed. {len(synced_markets)} prediction markets recorded in DB.")
        return synced_markets
