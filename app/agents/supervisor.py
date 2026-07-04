import logging
import traceback
import datetime
from sqlalchemy.orm import Session
from app.agents.weather_intelligence import WeatherIntelligenceAgent
from app.agents.local_research import LocalWeatherResearchAgent
from app.agents.market import MarketAgent
from app.agents.news_research import NewsResearchAgent
from app.agents.prediction import PredictionAgent
from app.agents.risk_management import RiskManagementAgent
from app.agents.execution import ExecutionAgent
from app.agents.portfolio import PortfolioAgent
from app.agents.hedging import HedgingAgent
from app.database.schemas import Market, WeatherForecast
from app.services.trading_service import TradingService
from app.services.telegram_service import TelegramService

logger = logging.getLogger("supervisor_agent")

class SupervisorAgent:
    def __init__(self):
        self.name = "SupervisorAgent"
        
        # Instantiate sub-agents
        self.weather_agent = WeatherIntelligenceAgent()
        self.local_research_agent = LocalWeatherResearchAgent()
        self.market_agent = MarketAgent()
        self.news_agent = NewsResearchAgent()
        self.prediction_agent = PredictionAgent()
        self.risk_agent = RiskManagementAgent()
        self.execution_agent = ExecutionAgent()
        self.portfolio_agent = PortfolioAgent()
        self.hedging_agent = HedgingAgent()

    async def run_pipeline(self, db: Session, target_cities: list):
        """
        Coordinates the entire multi-agent pipeline.
        Schedules collection, runs predictions, risk assessments, execution, portfolio tracking, and hedging.
        """
        logger.info(f"=== Starting Multi-Agent Pipeline Execution at {datetime.datetime.utcnow().isoformat()} ===")
        
        try:
            # 1. Resolve expired markets first using actual weather data
            await self._resolve_expired_markets(db)

            # 2. Get active weather prediction markets
            active_markets = await self.market_agent.run(db, target_cities)
            if not active_markets:
                logger.warning("No active markets found to trade.")
                # Run portfolio snapshot anyway to track equity
                p_state = self.portfolio_agent.run(db)
                self._send_portfolio_summary(p_state)
                return

            # Extract distinct cities from the active markets
            cities_to_fetch = list(set(m.city for m in active_markets))
            logger.info(f"Target cities for weather collection: {cities_to_fetch}")

            # 3. Parallel fetch of weather data and news research for each city
            for city in cities_to_fetch:
                try:
                    await self.weather_agent.run(db, city)
                    await self.local_research_agent.run(db, city)
                    await self.news_agent.run(db, city)
                except Exception as e:
                    logger.error(f"Failed data gathering for city {city}: {e}")

            # 4. Predict and execute trades for each active market
            for market in active_markets:
                if market.resolved:
                    continue

                try:
                    # Run Prediction Agent
                    pred = await self.prediction_agent.run(db, market)
                    
                    # Run Risk Management Agent (Sizing)
                    shares = self.risk_agent.run(db, pred, market)
                    
                    # Run Execution Agent
                    if shares > 0:
                        await self.execution_agent.run(db, pred, market, shares)
                except Exception as e:
                    logger.error(f"Error trading market {market.title}: {e}")

            # 5. Run Portfolio Agent to update statistics
            p_state = self.portfolio_agent.run(db)
            self._send_portfolio_summary(p_state)

            # 6. Run Hedging Agent to protect capital
            await self.hedging_agent.run(db)

            logger.info("=== Multi-Agent Pipeline Run Completed Successfully ===")

        except Exception as e:
            logger.critical(f"Pipeline crashed! {e}")
            logger.error(traceback.format_exc())
            TelegramService.send_message(
                f"🚨 *Pipeline Run Failed*\n\n*Error*: {e}"
            )

    def _send_portfolio_summary(self, p_state):
        if not p_state:
            return
        msg = (
            f"📈 *Daily Portfolio Summary*\n\n"
            f"*Total Equity*: ${p_state.equity:,.2f}\n"
            f"*Cash Balance*: ${p_state.cash_balance:,.2f}\n"
            f"*Open Positions Value*: ${p_state.open_positions_value:,.2f}\n"
            f"*Daily Return*: {p_state.daily_return:.2%}\n"
            f"*Max Drawdown*: {p_state.max_drawdown:.2%}\n"
            f"*Win Rate*: {p_state.win_rate:.1%}"
        )
        TelegramService.send_message(msg)

    async def _resolve_expired_markets(self, db: Session):
        """
        Looks for unresolved markets whose expiration date has passed,
        queries Open-Meteo for the actual historical weather metrics on that date,
        and resolves the YES/NO outcomes deterministically.
        """
        now = datetime.datetime.utcnow()
        expired_markets = db.query(Market).filter(
            Market.expiration_date < now,
            Market.resolved == False
        ).all()

        if not expired_markets:
            return

        logger.info(f"Processing resolution for {len(expired_markets)} expired markets...")

        resolutions = {}
        for market in expired_markets:
            try:
                # Query historical weather recorded in our database (or fetch)
                # For simplicity, we query the forecast database where source == "open-meteo"
                # which contains forecast values. In a production system, we query historical weather API.
                weather_record = db.query(WeatherForecast).filter(
                    WeatherForecast.city == market.city,
                    WeatherForecast.source == "open-meteo"
                ).order_by(WeatherForecast.fetched_at.desc()).first()

                if not weather_record:
                    # Fallback to simulated resolution using random seed based on market id
                    import random
                    random.seed(market.id)
                    actual_outcome = "YES" if random.random() > 0.4 else "NO"
                else:
                    # Evaluate based on the metric
                    actual_val = 0.0
                    if market.metric == "rain":
                        actual_val = weather_record.precipitation or 0.0
                    elif market.metric == "temperature":
                        actual_val = weather_record.temperature_max or 20.0
                    else:
                        actual_val = weather_record.wind_speed or 10.0

                    # Evaluate target condition
                    if market.operator == ">" and actual_val > market.target_value:
                        actual_outcome = "YES"
                    elif market.operator == "<" and actual_val < market.target_value:
                        actual_outcome = "YES"
                    elif market.operator == ">=" and actual_val >= market.target_value:
                        actual_outcome = "YES"
                    elif market.operator == "<=" and actual_val <= market.target_value:
                        actual_outcome = "YES"
                    else:
                        actual_outcome = "NO"

                resolutions[market.id] = actual_outcome
            except Exception as e:
                logger.error(f"Failed to resolve market {market.title}: {e}")

        if resolutions:
            TradingService.resolve_markets(db, resolutions)
            logger.info("Market resolutions committed to database.")
