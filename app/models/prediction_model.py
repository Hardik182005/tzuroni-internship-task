import math
import logging
from typing import Dict, Any

logger = logging.getLogger("prediction_model")

class PredictionModel:
    @staticmethod
    def calculate_prediction(
        metric: str,
        target_value: float,
        operator: str,
        global_forecast: Dict[str, Any],
        local_forecast: Dict[str, Any],
        research_brief: Dict[str, Any],
        market_yes_price: float
    ) -> Dict[str, Any]:
        """
        Ensemble prediction pipeline using Bayesian updating and probability calibration.
        Blends global models, regional agencies, news sentiment, and market odds.
        """
        # 1. Base Probability from Meteorological data
        if metric == "rain":
            p_global = global_forecast.get("rain_probability", 0.3)
            p_local = local_forecast.get("rain_probability", 0.3)
        elif metric == "temperature":
            # For temperature exceeding a threshold, we check max temp compared to target
            temp_max_g = global_forecast.get("temperature_max", 20.0)
            temp_max_l = local_forecast.get("temperature_max", 20.0)
            
            # Simple soft threshold approximation using sigmoid
            # P(temp > target) = sigmoid((temp - target) / scale)
            avg_temp = 0.5 * (temp_max_g + temp_max_l)
            scale = 2.0  # Celsius degrees scale
            diff = avg_temp - target_value
            p_global = 1.0 / (1.0 + math.exp(-diff / scale))
            p_local = p_global
        else:  # wind, etc.
            val_g = global_forecast.get("wind_speed", 10.0)
            val_l = local_forecast.get("wind_speed", 10.0)
            avg_val = 0.5 * (val_g + val_l)
            diff = avg_val - target_value
            p_global = 1.0 / (1.0 + math.exp(-diff / 5.0))
            p_local = p_global

        # Blend meteorological priors (weighted: 60% global model, 40% local country agency)
        p_meteo = 0.6 * p_global + 0.4 * p_local

        # 2. Bayesian Update using news sentiment indicator
        # News sentiment acts as a multiplier/shifter
        # Sentiment scale is -1.0 (bad/stormy/extreme) to 1.0 (clear/sunny/pleasant)
        sentiment = research_brief.get("sentiment_score", 0.0)
        
        # If it's a rain metric, negative sentiment (bad weather news) increases probability of rain
        sentiment_shift = 0.0
        if metric == "rain":
            # Storm reports shift probability up
            sentiment_shift = -0.15 * sentiment
        elif metric == "temperature":
            # Severe heatwave reports shift temperature probability up
            if sentiment < 0 and avg_temp > target_value - 3.0:
                sentiment_shift = 0.12 * abs(sentiment)
            else:
                sentiment_shift = 0.05 * sentiment

        p_updated = p_meteo + sentiment_shift
        p_model = max(0.01, min(0.99, p_updated))  # Calibrate bounds

        # 3. Market Edge Calculation
        # Market implied probability is the YES price
        p_market = market_yes_price
        
        # EV buy YES: p_model * (1.0 / p_market) - 1.0 = (p_model - p_market) / p_market
        # EV buy NO: (1.0 - p_model) * (1.0 / (1.0 - p_market)) - 1.0 = (p_market - p_model) / (1.0 - p_market)
        
        edge_yes = p_model - p_market
        edge_no = p_market - p_model
        
        ev_yes = edge_yes / p_market if p_market > 0 else 0.0
        ev_no = edge_no / (1.0 - p_market) if p_market < 1.0 else 0.0

        # Trading thresholds
        min_edge = 0.02  # 2% edge minimum
        
        if edge_yes >= min_edge and ev_yes > 0:
            decision = "BUY YES"
            expected_value = ev_yes
            edge = edge_yes
        elif edge_no >= min_edge and ev_no > 0:
            decision = "BUY NO"
            expected_value = ev_no
            edge = edge_no
        else:
            decision = "NO TRADE"
            expected_value = 0.0
            edge = 0.0

        fair_odds = round(1.0 / p_model, 2) if p_model > 0 else 999.0

        return {
            "model_probability": round(p_model, 4),
            "fair_odds": fair_odds,
            "expected_value": round(expected_value, 4),
            "edge": round(edge, 4),
            "decision": decision,
            "reasoning": (
                f"Model combined global forecast ({p_global:.1%}) and local agency ({p_local:.1%}) "
                f"yielding raw prior ({p_meteo:.1%}). Applied news sentiment adjustment of {sentiment_shift:+.1%}. "
                f"Model probability stands at {p_model:.1%} vs market price of {p_market:.1%}. "
                f"Decision is {decision} with EV of {expected_value:.1%}."
            )
        }
