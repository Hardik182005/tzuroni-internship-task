import logging
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.database.schemas import Market, WeatherForecast, NewsResearch, Prediction
from app.models.prediction_model import PredictionModel

logger = logging.getLogger("prediction_agent")

class PredictionAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Prediction Agent. Your job is to integrate weather forecasts, country agency warnings, "
            "news briefings, and market prices to produce a calibrated probability and expected value edge."
        )
        super().__init__("PredictionAgent", system_prompt)

    async def run(self, db: Session, market: Market) -> Prediction:
        """
        Runs the probabilistic prediction model for a specific prediction market.
        Combines DB data and writes a Prediction record.
        """
        logger.info(f"[{self.name}] Running prediction pipeline for market: {market.title}")

        # Fetch latest forecasts (global and local) for this city
        # For simple mapping, we fetch forecasts closest to the market target date/expiration
        target_date = market.expiration_date
        
        global_forecast = db.query(WeatherForecast).filter(
            WeatherForecast.city == market.city,
            WeatherForecast.source == "open-meteo"
        ).order_by(WeatherForecast.fetched_at.desc()).first()

        local_forecast = db.query(WeatherForecast).filter(
            WeatherForecast.city == market.city,
            WeatherForecast.source != "open-meteo"
        ).order_by(WeatherForecast.fetched_at.desc()).first()

        # Fetch latest research briefing
        research = db.query(NewsResearch).filter(
            NewsResearch.city == market.city
        ).order_by(NewsResearch.fetched_at.desc()).first()

        # Fallback values if DB records are missing
        g_data = {"rain_probability": 0.35, "temperature_max": 22.0, "wind_speed": 12.0} if not global_forecast else {
            "rain_probability": global_forecast.rain_probability,
            "temperature_max": global_forecast.temperature_max,
            "wind_speed": global_forecast.wind_speed
        }
        
        l_data = {"rain_probability": 0.38, "temperature_max": 23.0, "wind_speed": 13.0} if not local_forecast else {
            "rain_probability": local_forecast.rain_probability,
            "temperature_max": local_forecast.temperature_max,
            "wind_speed": local_forecast.wind_speed
        }

        r_data = {"sentiment_score": 0.0, "confidence_score": 0.70} if not research else {
            "sentiment_score": research.sentiment_score,
            "confidence_score": research.confidence_score
        }

        # Calculate probability and trade decisions
        prediction_result = PredictionModel.calculate_prediction(
            metric=market.metric,
            target_value=market.target_value,
            operator=market.operator,
            global_forecast=g_data,
            local_forecast=l_data,
            research_brief=r_data,
            market_yes_price=market.yes_price
        )

        # Call LLM to verify and adjust reasoning / final decision details if necessary
        prompt = (
            f"Review this weather prediction result for market: {market.title}\n"
            f"Model Probability: {prediction_result['model_probability']:.1%}\n"
            f"Expected Value: {prediction_result['expected_value']:.1%}\n"
            f"Edge: {prediction_result['edge']:.1%}\n"
            f"Suggested Decision: {prediction_result['decision']}\n"
            f"Provide your analytical confirmation or adjustment reasoning. Format response as JSON containing fields:\n"
            f"'confirmed_probability' (float), 'confirmed_decision' (string: BUY YES, BUY NO, NO TRADE), 'final_reasoning' (string)."
        )

        llm_response = await self.call_llm(prompt, json_mode=True)
        
        # Parse LLM verification
        import json
        try:
            verified = json.loads(llm_response)
            candidate_p = verified.get("confirmed_probability", prediction_result["model_probability"])
            candidate_p = float(candidate_p)
            # LLMs sometimes return a percentage-scale number (e.g. 65 instead of
            # 0.65). Normalize, then clamp hard to a valid probability range so a
            # malformed LLM response can never corrupt downstream EV/Kelly math.
            if candidate_p > 1.0:
                candidate_p = candidate_p / 100.0
            p_model = max(0.01, min(0.99, candidate_p))
            decision = verified.get("confirmed_decision", prediction_result["decision"])
            if decision not in ("BUY YES", "BUY NO", "NO TRADE"):
                decision = prediction_result["decision"]
            reasoning = verified.get("final_reasoning", prediction_result["reasoning"])
        except Exception:
            p_model = prediction_result["model_probability"]
            decision = prediction_result["decision"]
            reasoning = prediction_result["reasoning"]

        # Recalculate edge and EV using confirmed model probability
        p_market = market.yes_price
        edge_yes = p_model - p_market
        edge_no = p_market - p_model
        
        if decision == "BUY YES":
            edge = edge_yes
            ev = edge_yes / p_market if p_market > 0 else 0.0
        elif decision == "BUY NO":
            edge = edge_no
            ev = edge_no / (1.0 - p_market) if p_market < 1.0 else 0.0
        else:
            edge = 0.0
            ev = 0.0

        db_prediction = Prediction(
            market_id=market.id,
            model_probability=round(p_model, 4),
            fair_odds=round(1.0 / p_model, 2) if p_model > 0 else 99.0,
            confidence=r_data["confidence_score"],
            expected_value=round(ev, 4),
            edge=round(edge, 4),
            decision=decision,
            reasoning=reasoning
        )
        db.add(db_prediction)
        db.commit()

        logger.info(f"[{self.name}] Saved prediction for '{market.title}': {decision} @ Model Prob {p_model:.1%}")
        return db_prediction
