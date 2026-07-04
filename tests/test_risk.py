import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.schemas import Base, Prediction, PortfolioState, Market
from app.agents.risk_management import RiskManagementAgent

def test_kelly_sizing():
    # Set environment variables
    os.environ["FRACTIONAL_KELLY"] = "0.5"
    os.environ["MAX_EXPOSURE_PCT"] = "0.20"
    os.environ["MAX_DAILY_LOSS_PCT"] = "0.05"
    os.environ["INITIAL_BALANCE"] = "10000.0"

    # Setup database engine in memory
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed default portfolio state
    portfolio = PortfolioState(
        cash_balance=10000.0,
        equity=10000.0,
        open_positions_value=0.0,
        daily_return=0.0
    )
    db.add(portfolio)

    market = Market(
        id="test-market",
        slug="test-slug",
        title="Will it rain?",
        city="London",
        metric="rain",
        yes_price=0.50,
        no_price=0.50,
        expiration_date=datetime.datetime.utcnow() + datetime.timedelta(days=1)
    )
    db.add(market)
    db.commit()

    prediction = Prediction(
        market_id="test-market",
        model_probability=0.70, # Model predicts 70% yes
        fair_odds=1.43,
        expected_value=0.40,
        edge=0.20,
        decision="BUY YES"
    )

    risk_agent = RiskManagementAgent()
    shares = risk_agent.run(db, prediction, market)

    # Kelly formula: f* = (p - p_market) / (1 - p_market) = (0.7 - 0.5) / 0.5 = 0.40
    # Fractional Kelly: 0.40 * 0.5 = 0.20 (20%)
    # Sized Capital = 10000 * 20% = 2000
    # Shares = 2000 / 0.50 = 4000 shares
    assert shares == 4000.0

    db.close()
