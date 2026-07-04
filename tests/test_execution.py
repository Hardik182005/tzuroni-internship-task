import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.schemas import Base, Market, PortfolioState, Order, Trade
from app.services.trading_service import TradingService

def test_paper_trading_execution_and_resolution():
    os.environ["INITIAL_BALANCE"] = "10000.0"

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed default portfolio
    portfolio = PortfolioState(
        cash_balance=10000.0,
        equity=10000.0,
        open_positions_value=0.0
    )
    db.add(portfolio)

    # Seed market
    market = Market(
        id="test-market",
        slug="test-slug",
        title="Will London rain?",
        city="London",
        metric="rain",
        target_value=0.1,
        yes_price=0.50,
        no_price=0.50,
        expiration_date=datetime.datetime.utcnow() + datetime.timedelta(days=1),
        resolved=False
    )
    db.add(market)
    db.commit()

    # Place order: Buy 100 shares of YES
    # Top ask generated is around 0.51, matching level-by-level
    trade = TradingService.place_and_execute_order(
        db=db,
        market_id="test-market",
        side="YES",
        price_limit=0.60,
        quantity=100.0,
        order_type="MARKET"
    )

    assert trade is not None
    assert trade.side == "YES"
    assert trade.quantity == 100.0
    
    # Assert cash has decreased by (100 * fill_price) + fee
    assert db.query(PortfolioState).first().cash_balance < 10000.0

    # Resolve market to YES
    TradingService.resolve_markets(db, {"test-market": "YES"})

    # Check that market is resolved
    resolved_market = db.query(Market).filter(Market.id == "test-market").first()
    assert resolved_market.resolved is True
    assert resolved_market.resolution_result == "YES"

    # Check cash has received payout of $100
    # Current cash should be around 10000.0 - cost - fee + 100.0
    assert db.query(PortfolioState).first().cash_balance > 9900.0

    db.close()
