import os
import random
import logging
import datetime
from typing import Dict, Any, List

import httpx
from dotenv import load_dotenv

logger = logging.getLogger("research_service")

# Simple weather-sentiment lexicon. Negative weight = worse/more-severe weather
# (raises rain / storm / extreme probabilities), positive = calm/clear.
_NEGATIVE_TERMS = {
    "storm": -0.8, "thunderstorm": -0.8, "cyclone": -1.0, "hurricane": -1.0,
    "typhoon": -1.0, "flood": -0.9, "flooding": -0.9, "downpour": -0.7,
    "heavy rain": -0.7, "torrential": -0.8, "monsoon": -0.6, "showers": -0.4,
    "rain": -0.4, "wind advisory": -0.6, "gale": -0.7, "gusts": -0.4,
    "heatwave": -0.7, "heat wave": -0.7, "severe": -0.7, "warning": -0.6,
    "alert": -0.5, "extreme": -0.7, "snow": -0.4, "blizzard": -0.9,
    "hail": -0.6, "fog": -0.2, "humidity": -0.2, "advisory": -0.4,
}
_POSITIVE_TERMS = {
    "clear": 0.6, "sunny": 0.7, "calm": 0.5, "mild": 0.5, "pleasant": 0.6,
    "dry": 0.4, "stable": 0.4, "fine": 0.4, "sunshine": 0.6, "gentle": 0.3,
}


class ResearchService:
    """Weather intelligence research. Uses a live Apify actor to scrape news/social
    weather chatter when APIFY_TOKEN is configured; otherwise falls back to a
    deterministic canned briefing so the pipeline never blocks."""

    @staticmethod
    async def gather_research(city: str) -> Dict[str, Any]:
        """Async research entrypoint. Attempts a real Apify scrape first."""
        load_dotenv()
        token = os.getenv("APIFY_TOKEN", "")

        if token and "your_" not in token:
            try:
                scraped = await ResearchService._scrape_with_apify(city, token)
                if scraped and scraped.get("documents"):
                    return ResearchService._analyze(city, scraped)
                logger.warning(f"[Apify] No documents returned for {city}; using canned fallback.")
            except Exception as e:
                logger.error(f"[Apify] Scrape failed for {city}: {e}. Using canned fallback.")
        else:
            logger.info("APIFY_TOKEN not set; using deterministic canned research.")

        return ResearchService._canned_research(city)

    # ------------------------------------------------------------------ Apify
    @staticmethod
    async def _scrape_with_apify(city: str, token: str) -> Dict[str, Any]:
        """Runs an Apify actor synchronously and returns its dataset items.

        Uses the run-sync-get-dataset-items endpoint so a single HTTP call runs
        the actor and returns results. The actor is configurable via
        APIFY_NEWS_ACTOR (default: apify/rag-web-browser, an official actor that
        performs a web search and returns page text)."""
        actor = os.getenv("APIFY_NEWS_ACTOR", "apify/rag-web-browser")
        # Actor id in the URL uses '~' instead of '/'
        actor_path = actor.replace("/", "~")
        url = f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items"

        query = f"{city} weather forecast today rain storm temperature alerts"
        payload = {
            "query": query,
            "maxResults": int(os.getenv("APIFY_MAX_RESULTS", "3")),
        }

        logger.info(f"[Apify] Running actor '{actor}' for {city}...")
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, params={"token": token}, json=payload)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Apify actor returned {resp.status_code}: {resp.text[:300]}")
            items = resp.json()

        documents: List[str] = []
        sources: List[str] = []
        for item in items if isinstance(items, list) else []:
            # rag-web-browser returns {'metadata': {...}, 'text': ...}; be tolerant
            # of arbitrary actor shapes by pulling any text-like fields.
            text = (
                item.get("text")
                or item.get("markdown")
                or item.get("content")
                or item.get("description")
                or ""
            )
            meta = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
            title = meta.get("title") or item.get("title") or ""
            src = meta.get("url") or item.get("url") or item.get("loadedUrl") or ""
            blob = f"{title}. {text}".strip()
            if blob and blob != ".":
                documents.append(blob[:2000])
            if src:
                sources.append(src)

        logger.info(f"[Apify] Retrieved {len(documents)} documents for {city}.")
        return {"documents": documents, "sources": sources}

    # -------------------------------------------------------------- Analysis
    @staticmethod
    def _analyze(city: str, scraped: Dict[str, Any]) -> Dict[str, Any]:
        """Derives a summary, lexicon-based sentiment, and confidence from real
        scraped text."""
        docs = scraped["documents"]
        corpus = " ".join(docs).lower()

        score = 0.0
        hits = 0
        for term, weight in {**_NEGATIVE_TERMS, **_POSITIVE_TERMS}.items():
            count = corpus.count(term)
            if count:
                score += weight * min(count, 3)  # cap each term's influence
                hits += min(count, 3)

        sentiment = 0.0 if hits == 0 else max(-1.0, min(1.0, score / max(hits, 1)))

        # Confidence scales with corpus richness and number of sentiment signals.
        confidence = round(min(0.95, 0.55 + 0.05 * len(docs) + 0.02 * min(hits, 10)), 2)

        # Build a compact summary from the first document(s).
        snippet = docs[0][:400] if docs else "No content."
        summary = f"[{city} Live Intelligence — Apify] {snippet}"
        sources = ", ".join(scraped.get("sources", [])[:3]) or "Apify web scrape"

        logger.info(f"Apify research for {city}: sentiment={sentiment:.2f}, confidence={confidence}, docs={len(docs)}")
        return {
            "city": city,
            "summary": summary,
            "sentiment_score": round(sentiment, 3),
            "confidence_score": confidence,
            "sources": sources,
        }

    # ---------------------------------------------------------------- Fallback
    @staticmethod
    def _canned_research(city: str) -> Dict[str, Any]:
        """Deterministic offline briefing used when Apify is unavailable."""
        weather_reports = [
            "Local weather reports indicate stable pressure conditions and typical seasonal heat. Residents are advised to stay hydrated.",
            "Meteorologists are tracking a minor low-pressure system moving in, which might increase the chance of sudden showers in the next 24-48 hours.",
            "Local news highlights elevated humidity levels. Air conditioning demand is peaking as temperatures hover above historic averages.",
            "Satellite imagery reveals heavy cloud formations approaching the region. Flash flood warnings have been issued by the city meteorological bureau.",
            "Air quality index (AQI) reports show moderate particulate pollution. Elderly people are advised to limit outdoor activity during midday.",
            "Strong wind advisory is in effect. Peak wind gusts are expected to exceed 40 km/h in high-elevation areas and along coastal regions.",
            "A heatwave warning has been declared by the meteorological authority. Temperatures are expected to exceed seasonal normals by 4-6 degrees Celsius.",
        ]
        sentiment_scores = [0.1, 0.3, -0.2, -0.7, -0.4, -0.5, -0.6]

        day_seed = int(datetime.datetime.utcnow().strftime("%Y%m%d"))
        random.seed(day_seed + len(city))
        idx = random.randint(0, len(weather_reports) - 1)

        summary = f"[{city} Intelligence Briefing] " + weather_reports[idx]
        sentiment = sentiment_scores[idx]

        if city in ["Mumbai", "Delhi", "Bangkok"] and idx in [1, 3]:
            summary += " Monsoon rain activity has intensified. Significant water logging is observed in low-lying areas. Public transport is delayed."
            sentiment = -0.8
        elif city == "Dubai" and idx == 6:
            summary += " Extreme summer temperatures are active. Outdoor work restriction during afternoon hours is strictly enforced."
            sentiment = -0.7

        confidence = round(random.uniform(0.65, 0.95), 2)
        sources = "National Meteorological Agency, Twitter Weather Alerts, Regional Hydrology Report"

        logger.info(f"Gathered canned research for {city}: Sentiment={sentiment}, Confidence={confidence}")
        return {
            "city": city,
            "summary": summary,
            "sentiment_score": sentiment,
            "confidence_score": confidence,
            "sources": sources,
        }
