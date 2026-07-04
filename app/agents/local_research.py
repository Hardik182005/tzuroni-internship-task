import logging
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.services.weather_service import WeatherService
from app.database.schemas import WeatherForecast

logger = logging.getLogger("local_weather_research_agent")

class LocalWeatherResearchAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the Local Weather Research Agent. Your job is to extract forecasts, warnings, "
            "alerts, and confidence reports from country-specific meteorological agencies (NOAA, IMD, BOM, JMA, Met Office, etc.)."
        )
        super().__init__("LocalWeatherResearchAgent", system_prompt)

    async def run(self, db: Session, city: str):
        """
        Fetches regional weather agency data for a city, processes warnings, and logs in DB.
        """
        logger.info(f"[{self.name}] Fetching local country-specific weather research for {city}")
        
        local_result = await WeatherService.fetch_local_forecast(city)
        if local_result["status"] != "success":
            logger.error(f"[{self.name}] Failed to fetch local agency forecast for {city}")
            return None

        agency = local_result["agency"]
        forecast_data = local_result["data"]

        # Persist forecasts to database
        for f in forecast_data:
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
                existing.extreme_alerts = f["extreme_alerts"]
            else:
                db_forecast = WeatherForecast(**f)
                db.add(db_forecast)

        db.commit()

        # Prepare summary of warnings
        warnings = [f["extreme_alerts"] for f in forecast_data if f["extreme_alerts"] is not None]
        
        prompt = (
            f"Review the country-specific forecasts and alerts issued by {agency} for {city}:\n"
            f"{[{'date': f['forecast_date'].strftime('%Y-%m-%d'), 'alerts': f['extreme_alerts'], 'temp_max': f['temperature_max']} for f in forecast_data]}\n"
            f"Synthesize the local agency alerts and compare them with generic forecasts. Formulate warning briefs."
        )
        
        synthesis = await self.call_llm(prompt)
        logger.info(f"[{self.name}] Local agency analysis completed for {city} via {agency}.")
        return {
            "city": city,
            "agency": agency,
            "warnings": warnings,
            "brief": synthesis
        }
