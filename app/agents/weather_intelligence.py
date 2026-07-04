import logging
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.services.weather_service import WeatherService
from app.database.schemas import WeatherForecast

logger = logging.getLogger("weather_intelligence_agent")

class WeatherIntelligenceAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Weather Intelligence Agent. Your job is to analyze global weather forecasts, "
            "identify climate anomalies, assess forecasting source confidence, and compile structured weather insights."
        )
        super().__init__("WeatherIntelligenceAgent", system_prompt)

    async def run(self, db: Session, city: str):
        """
        Fetches global forecasts for a city, runs LLM analysis to identify anomalies,
        and saves the forecast details to the database.
        """
        logger.info(f"[{self.name}] Running global weather intelligence for {city}")
        
        # Fetch forecast from service
        forecast_result = await WeatherService.fetch_global_forecast(city)
        if forecast_result["status"] != "success":
            logger.error(f"[{self.name}] Failed to fetch forecast for {city}")
            return None

        forecast_data = forecast_result["data"]
        
        # Persist forecasts to database
        for f in forecast_data:
            # Check if forecast already exists for this city/date/source
            existing = db.query(WeatherForecast).filter(
                WeatherForecast.city == f["city"],
                WeatherForecast.forecast_date == f["forecast_date"],
                WeatherForecast.source == f["source"]
            ).first()
            
            if existing:
                existing.temperature_max = f["temperature_max"]
                existing.temperature_min = f["temperature_min"]
                existing.rain_probability = f["rain_probability"]
                existing.precipitation = f["precipitation"]
                existing.wind_speed = f["wind_speed"]
            else:
                db_forecast = WeatherForecast(**f)
                db.add(db_forecast)
        
        db.commit()

        # Generate a weather intelligence brief using the LLM
        prompt = (
            f"Analyze the following 7-day weather forecast for {city}:\n"
            f"{[{'date': f['forecast_date'].strftime('%Y-%m-%d'), 'temp_max': f['temperature_max'], 'rain_prob': f['rain_probability'], 'precipitation': f['precipitation']} for f in forecast_data]}\n"
            f"Identify any anomalies (e.g., temperatures 5C above normal, unusually high rain probability) and outline source confidence."
        )
        
        analysis = await self.call_llm(prompt)
        logger.info(f"[{self.name}] Weather brief generated for {city}: {analysis[:100]}...")
        return {
            "city": city,
            "forecasts": forecast_data,
            "brief": analysis
        }
