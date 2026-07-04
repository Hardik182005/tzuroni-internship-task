import pytest
from app.models.prediction_model import PredictionModel

def test_calculate_prediction_rain_buy_yes():
    # Setup global and local forecast with high rain probability
    global_forecast = {"rain_probability": 0.85, "temperature_max": 20.0, "wind_speed": 10.0}
    local_forecast = {"rain_probability": 0.90, "temperature_max": 20.0, "wind_speed": 10.0}
    research_brief = {"sentiment_score": -0.5, "confidence_score": 0.8} # negative sentiment = bad weather/stormy
    market_yes_price = 0.60 # Market YES price is cheap

    result = PredictionModel.calculate_prediction(
        metric="rain",
        target_value=0.1,
        operator=">",
        global_forecast=global_forecast,
        local_forecast=local_forecast,
        research_brief=research_brief,
        market_yes_price=market_yes_price
    )

    assert result["model_probability"] > 0.80
    assert result["decision"] == "BUY YES"
    assert result["expected_value"] > 0.0
    assert result["edge"] > 0.0

def test_calculate_prediction_temperature_buy_no():
    # Setup conditions where temperature forecast is lower than threshold
    global_forecast = {"rain_probability": 0.1, "temperature_max": 18.0, "wind_speed": 10.0}
    local_forecast = {"rain_probability": 0.1, "temperature_max": 19.0, "wind_speed": 10.0}
    research_brief = {"sentiment_score": 0.5, "confidence_score": 0.8} # pleasant sunny news
    market_yes_price = 0.70 # Market YES price is high for exceeding target

    result = PredictionModel.calculate_prediction(
        metric="temperature",
        target_value=25.0, # Target is high
        operator=">",
        global_forecast=global_forecast,
        local_forecast=local_forecast,
        research_brief=research_brief,
        market_yes_price=market_yes_price
    )

    # Prob of temp exceeding 25 when max forecast is 18.5 should be very low
    assert result["model_probability"] < 0.10
    assert result["decision"] == "BUY NO" # Since model prob < market price, we sell YES (buy NO)
    assert result["expected_value"] > 0.0
