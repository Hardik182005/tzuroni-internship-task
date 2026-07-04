import httpx
import logging
import datetime
import random
from typing import List, Dict, Any

logger = logging.getLogger("market_service")

class MarketService:
    @staticmethod
    async def fetch_live_weather_markets() -> List[Dict[str, Any]]:
        """
        Queries the Polymarket Gamma API to find live active weather-related markets.
        """
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            "closed": "false",
            "active": "true",
            "limit": 100
        }
        
        weather_keywords = ["weather", "rain", "temperature", "temp", "degree", "hurricane", "cyclone", "flood", "storm", "aqi", "snow"]
        discovered_markets = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    markets = response.json()
                    for m in markets:
                        title = m.get("title", "").lower()
                        desc = m.get("description", "").lower()
                        
                        # Match keywords to filter weather markets
                        is_weather = any(kw in title or kw in desc for kw in weather_keywords)
                        if is_weather:
                            outcome_prices = m.get("outcomePrices", ["0.5", "0.5"])
                            yes_price = float(outcome_prices[0]) if len(outcome_prices) > 0 else 0.5
                            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0.5
                            
                            exp_str = m.get("endDate", None)
                            if exp_str:
                                expiration_date = datetime.datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
                            else:
                                expiration_date = datetime.datetime.utcnow() + datetime.timedelta(days=2)

                            # Determine city from title
                            city = "Global"
                            from app.services.weather_service import CITY_COORDINATES
                            for c in CITY_COORDINATES.keys():
                                if c.lower() in title:
                                    city = c
                                    break

                            discovered_markets.append({
                                "id": m.get("conditionId", m.get("id")),
                                "slug": m.get("slug", f"market-{m.get('id')}"),
                                "title": m.get("question", m.get("title")),
                                "city": city,
                                "metric": "temperature" if "temperature" in title or "temp" in title else "rain",
                                "target_value": None, # Will extract or estimate if needed
                                "operator": ">",
                                "yes_price": yes_price,
                                "no_price": no_price,
                                "volume_24h": float(m.get("volume24hr", 0.0)),
                                "liquidity": float(m.get("liquidity", 0.0)),
                                "expiration_date": expiration_date,
                                "source": "live"
                            })
                    logger.info(f"Discovered {len(discovered_markets)} live weather markets on Polymarket.")
                else:
                    logger.error(f"Polymarket API returned status code {response.status_code}")
        except Exception as e:
            logger.error(f"Error querying Polymarket Gamma API: {e}")

        return discovered_markets

    @staticmethod
    def generate_simulated_markets(cities: List[str]) -> List[Dict[str, Any]]:
        """
        Generates realistic, deterministic mock prediction markets for cities if live markets are empty.
        This provides structured targets for trading (e.g. Will London exceed 25C tomorrow?).
        """
        sim_markets = []
        today = datetime.datetime.utcnow().date()
        
        # Seed to make prices stable but daily dynamic
        random.seed(int(today.strftime("%Y%m%d")))

        metrics_pool = [
            {"metric": "rain", "title": "Will {city} record precipitation > {val} mm on {date}?", "val_range": (0.1, 5.0), "op": ">"},
            {"metric": "temperature", "title": "Will {city} max temperature exceed {val}°C on {date}?", "val_range": (20.0, 35.0), "op": ">"},
            {"metric": "wind", "title": "Will {city} wind speed exceed {val} km/h on {date}?", "val_range": (25.0, 45.0), "op": ">"}
        ]

        for city in cities:
            # Create 2 markets per city
            chosen_metrics = random.sample(metrics_pool, 2)
            for m_info in chosen_metrics:
                date_target = today + datetime.timedelta(days=1)
                date_str = date_target.strftime("%Y-%m-%d")
                
                # Setup realistic value based on city climate
                val = round(random.uniform(*m_info["val_range"]), 1)
                if city in ["Dubai", "Mumbai", "Delhi"] and m_info["metric"] == "temperature":
                    val = round(random.uniform(33.0, 42.0), 1)
                elif city in ["Sydney", "Melbourne"] and m_info["metric"] == "temperature":
                    val = round(random.uniform(13.0, 18.0), 1)

                title = m_info["title"].format(city=city, val=val, date=date_str)
                slug = f"will-{city.lower().replace(' ', '-')}-{m_info['metric']}-exceed-{str(val).replace('.', '-')}-on-{date_str}"
                
                # Market prices reflect initial priors
                yes_price = round(random.uniform(0.3, 0.7), 2)
                no_price = round(1.0 - yes_price, 2)

                market_id = f"sim-{slug}"
                sim_markets.append({
                    "id": market_id,
                    "slug": slug,
                    "title": title,
                    "city": city,
                    "metric": m_info["metric"],
                    "target_value": val,
                    "operator": m_info["op"],
                    "yes_price": yes_price,
                    "no_price": no_price,
                    "volume_24h": round(random.uniform(1000.0, 15000.0), 2),
                    "liquidity": round(random.uniform(500.0, 5000.0), 2),
                    "expiration_date": datetime.datetime.combine(date_target, datetime.time(23, 59, 59)),
                    "source": "simulated"
                })

        return sim_markets

    @staticmethod
    def get_order_book(market_id: str, yes_price: float) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generates/fetches a realistic CLOB order book for a given market.
        Matches level-by-level fills.
        """
        # We generate a high-fidelity bid/ask queue around the current YES contract price.
        # Bids (buy YES) are priced at or below yes_price.
        # Asks (sell YES) are priced at or above yes_price.
        
        # Spread is typically 1-3 cents
        spread = 0.02
        mid = yes_price
        bid_start = round(mid - spread/2, 2)
        ask_start = round(mid + spread/2, 2)

        bids = []
        asks = []

        # Populate order levels
        for idx in range(5):
            bid_p = round(bid_start - idx * 0.01, 2)
            ask_p = round(ask_start + idx * 0.01, 2)
            
            if bid_p > 0.01:
                bids.append({"price": bid_p, "size": round(random.uniform(100.0, 2000.0), 1)})
            if ask_p < 0.99:
                asks.append({"price": ask_p, "size": round(random.uniform(100.0, 2000.0), 1)})

        return {
            "bids": bids,
            "asks": asks
        }
