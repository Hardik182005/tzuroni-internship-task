import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Ensure the root directory is on the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline_execution.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("pipeline_runner")

load_dotenv()

from app.database.connection import SessionLocal
from app.agents.supervisor import SupervisorAgent

async def run_pipeline_async():
    """
    Main async function to trigger the pipeline run.
    """
    logger.info("Initializing multi-agent pipeline run...")
    db = SessionLocal()
    
    cities_str = os.getenv("TRADING_CITIES", "New York,London,Mumbai,Tokyo,Sydney")
    cities = [c.strip() for c in cities_str.split(",")]
    
    supervisor = SupervisorAgent()
    
    try:
        await supervisor.run_pipeline(db, cities)
    finally:
        db.close()

def run_pipeline_sync():
    """
    Synchronous wrapper to run the async pipeline.
    Useful for FastAPI background tasks or direct script invocation.
    """
    asyncio.run(run_pipeline_async())

if __name__ == "__main__":
    logger.info("Starting pipeline runner script...")
    run_pipeline_sync()
    logger.info("Pipeline runner script execution finished.")
