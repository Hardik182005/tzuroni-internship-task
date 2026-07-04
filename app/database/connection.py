import os
from fastapi import FastAPI, BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

# Load env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./weather_trading.db")

# Create SQLAlchemy engine
# SQLite needs connect_args={"check_same_thread": False} for multi-threaded/async environments
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SessionLocal = scoped_session(session_factory)

# Import schemas to ensure they are created
from app.database.schemas import Base

def init_db():
    Base.metadata.create_all(bind=engine)
    # Initialize portfolio state if not exists
    session = SessionLocal()
    from app.database.schemas import PortfolioState
    p_state = session.query(PortfolioState).order_by(PortfolioState.id.desc()).first()
    if not p_state:
        initial_balance = float(os.getenv("INITIAL_BALANCE", "10000.0"))
        default_state = PortfolioState(
            cash_balance=initial_balance,
            equity=initial_balance,
            open_positions_value=0.0,
            daily_return=0.0,
            weekly_return=0.0,
            win_rate=0.0,
            loss_rate=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            profit_factor=1.0,
            exposure_pct=0.0
        )
        session.add(default_state)
        session.commit()
    session.close()

# Initialize DB on import
init_db()

# Initialize FastAPI App
app = FastAPI(
    title="Weather Prediction AI Trading Engine API",
    description="Backend API for the autonomous weather predicting and paper trading multi-agent system.",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "database": DATABASE_URL.split("///")[-1]}

@app.get("/markets")
def get_markets():
    session = SessionLocal()
    from app.database.schemas import Market
    markets = session.query(Market).all()
    session.close()
    return markets

@app.get("/predictions")
def get_predictions():
    session = SessionLocal()
    from app.database.schemas import Prediction
    predictions = session.query(Prediction).order_by(Prediction.id.desc()).limit(100).all()
    session.close()
    return predictions

@app.get("/trades")
def get_trades():
    session = SessionLocal()
    from app.database.schemas import Trade
    trades = session.query(Trade).order_by(Trade.executed_at.desc()).limit(100).all()
    session.close()
    return trades

@app.get("/portfolio")
def get_portfolio():
    session = SessionLocal()
    from app.database.schemas import PortfolioState
    portfolio = session.query(PortfolioState).order_by(PortfolioState.id.desc()).first()
    session.close()
    return portfolio

@app.post("/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    from scripts.run_pipeline import run_pipeline_sync
    background_tasks.add_task(run_pipeline_sync)
    return {"status": "Pipeline run triggered in background"}
