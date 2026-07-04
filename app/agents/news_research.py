import logging
from sqlalchemy.orm import Session
from app.agents.base import BaseAgent
from app.services.research_service import ResearchService
from app.database.schemas import NewsResearch

logger = logging.getLogger("news_research_agent")

class NewsResearchAgent(BaseAgent):
    def __init__(self):
        system_prompt = (
            "You are the News Research Agent. Your job is to search news reports, meteorological journals, "
            "and social discussions (Reddit, Twitter) to assess sentiment, severity of weather anomalies, and compile briefing cards."
        )
        super().__init__("NewsResearchAgent", system_prompt)

    async def run(self, db: Session, city: str):
        """
        Collects social media and news reports, writes research briefing to DB, and returns sentiment summary.
        """
        logger.info(f"[{self.name}] Running news research scraping for {city}")
        
        research_data = await ResearchService.gather_research(city)
        
        # Save to database
        db_research = NewsResearch(
            city=research_data["city"],
            summary=research_data["summary"],
            sentiment_score=research_data["sentiment_score"],
            confidence_score=research_data["confidence_score"],
            sources=research_data["sources"]
        )
        db.add(db_research)
        db.commit()

        # Run LLM synthesis on the scraped data
        prompt = (
            f"Analyze this weather intelligence briefing for {city}:\n"
            f"Summary: {research_data['summary']}\n"
            f"Sentiment: {research_data['sentiment_score']} (Scale: -1 to 1)\n"
            f"Confidence: {research_data['confidence_score']}\n"
            f"Synthesize key risks to city infrastructure, extreme weather odds, and assign an AI confidence rating."
        )

        analysis = await self.call_llm(prompt)
        logger.info(f"[{self.name}] LLM news analysis complete for {city}.")
        return {
            "city": city,
            "sentiment": research_data["sentiment_score"],
            "analysis": analysis
        }
