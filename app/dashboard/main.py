import os
import streamlit as pd_st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime

# Load env variables
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./weather_trading.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# Import schemas to read database
from app.database.schemas import Market, WeatherForecast, Prediction, Order, Trade, PortfolioState

# Setup page config
pd_st.set_page_config(
    page_title="AETHER — Quantitative Weather Intel & Prediction Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Sleek CSS for Dark Mode & Rich Typography (Inter font)
pd_st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Space Grotesk', sans-serif;
    }
    .stApp {
        background: linear-gradient(135deg, #0e121a 0%, #151b26 100%);
        color: #f1f5f9;
    }
    .main-header {
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        background: linear-gradient(to right, #00f2fe, #4facfe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background-color: rgba(30, 41, 59, 0.45);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    .metric-title {
        color: #94a3b8;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    .metric-value {
        color: #f8fafc;
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Load data helper
def load_data():
    db = SessionLocal()
    markets = pd.read_sql("SELECT * FROM markets", con=engine)
    forecasts = pd.read_sql("SELECT * FROM weather_forecasts", con=engine)
    predictions = pd.read_sql("SELECT * FROM predictions", con=engine)
    orders = pd.read_sql("SELECT * FROM orders", con=engine)
    trades = pd.read_sql("SELECT * FROM trades", con=engine)
    portfolio = pd.read_sql("SELECT * FROM portfolio_states ORDER BY timestamp ASC", con=engine)
    db.close()
    return markets, forecasts, predictions, orders, trades, portfolio

# Title bar
pd_st.markdown('<div class="main-header">A E T H E R</div>', unsafe_allow_html=True)
pd_st.markdown("<p style='color: #64748b; font-size: 1.1rem; margin-top: -10px; margin-bottom: 2rem;'>Autonomous Quantitative Weather Prediction & Risk Management Terminal</p>", unsafe_allow_html=True)

# Load data
markets, forecasts, predictions, orders, trades, portfolio = load_data()

# Check if portfolio is empty (default state)
if portfolio.empty:
    pd_st.info("No pipeline run detected. Click the 'Run Multi-Agent Pipeline' button in the sidebar to fetch live data and start the trading agent.")
    # Sidebar control
    if pd_st.sidebar.button("Run Multi-Agent Pipeline"):
        pd_st.sidebar.text("Pipeline started in background...")
        # Trigger via httpx to local backend
        import requests
        try:
            r = requests.post("http://localhost:8000/pipeline/run")
            pd_st.sidebar.success("Pipeline running! Refresh in a minute.")
        except Exception as e:
            pd_st.sidebar.error(f"Backend offline: {e}")
    pd_st.stop()

# Sidebar Setup
pd_st.sidebar.header("Control Panel")
if pd_st.sidebar.button("Run Multi-Agent Pipeline Now"):
    with pd_st.spinner("Executing supervisor orchestrator workflow..."):
        import requests
        try:
            r = requests.post("http://localhost:8000/pipeline/run")
            pd_st.sidebar.success("Successfully completed!")
            markets, forecasts, predictions, orders, trades, portfolio = load_data()
        except Exception as e:
            pd_st.sidebar.error(f"Connection failed: {e}")

# Display latest portfolio state metrics
current_portfolio = portfolio.iloc[-1]
cash = current_portfolio['cash_balance']
equity = current_portfolio['equity']
open_val = current_portfolio['open_positions_value']
total_pnl = round(equity - 10000.0, 2)
drawdown = current_portfolio['max_drawdown']
sharpe = current_portfolio['sharpe_ratio']

# Header Widgets Layout
c1, c2, c3, c4, c5 = pd_st.columns(5)
with c1:
    pd_st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-title'>Net Equity</div>
        <div class='metric-value'>${equity:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with c2:
    pd_st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-title'>Cash Balance</div>
        <div class='metric-value'>${cash:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
with c3:
    pd_st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-title'>Total Realized P&L</div>
        <div class='metric-value' style='color: {"#10b981" if total_pnl >= 0 else "#ef4444"}'>
            {"+" if total_pnl >= 0 else ""}${total_pnl:,.2f}
        </div>
    </div>
    """, unsafe_allow_html=True)
with c4:
    pd_st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-title'>Max Drawdown</div>
        <div class='metric-value' style='color: #f59e0b'>{drawdown:.2%}</div>
    </div>
    """, unsafe_allow_html=True)
with c5:
    pd_st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-title'>Sharpe Ratio</div>
        <div class='metric-value' style='color: #38bdf8'>{sharpe:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

pd_st.write("")

# Main Dashboard Navigation
tab1, tab2, tab3, tab4 = pd_st.tabs(["📊 Portfolio & Execution", "🌧️ Weather Forecasts", "🎯 Prediction Markets", "📈 Performance Statistics"])

# Tab 1: Portfolio and Execution
with tab1:
    tc1, tc2 = pd_st.columns([2, 1])
    with tc1:
        pd_st.subheader("Equity Curve & Drawdown Tracking")
        # Plotly Equity Curve
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=pd.to_datetime(portfolio['timestamp']),
            y=portfolio['equity'],
            mode='lines+markers',
            name='Total Portfolio Equity',
            line=dict(color='#00f2fe', width=3),
            fill='tozeroy',
            fillcolor='rgba(0, 242, 254, 0.1)'
        ))
        fig_equity.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='rgba(148,163,184,0.1)', title="Time"),
            yaxis=dict(gridcolor='rgba(148,163,184,0.1)', title="Equity ($)"),
            margin=dict(l=20, r=20, t=10, b=20),
            height=320,
            font=dict(color='#f1f5f9')
        )
        pd_st.plotly_chart(fig_equity, use_container_width=True)

    with tc2:
        pd_st.subheader("Capital Allocation")
        # Capital pie chart
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Cash Balance', 'Open Positions Value'],
            values=[cash, open_val],
            hole=.4,
            marker=dict(colors=['#1e293b', '#4facfe'])
        )])
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=20, b=20),
            height=320,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(color='#f1f5f9')
        )
        pd_st.plotly_chart(fig_pie, use_container_width=True)

    pd_st.subheader("Recent Execution Logs")
    if not trades.empty:
        # Merge trades and markets to display descriptions
        merged_trades = trades.merge(markets, left_on="market_id", right_on="id", suffixes=("_trade", "_market"))
        merged_trades = merged_trades.sort_values(by="executed_at", ascending=False)
        pd_st.dataframe(
            merged_trades[["executed_at", "title", "side", "execution_price", "quantity", "slippage_bps"]].rename(
                columns={
                    "executed_at": "Timestamp",
                    "title": "Prediction Market",
                    "side": "Side Bought",
                    "execution_price": "Price ($)",
                    "quantity": "Contracts Bought",
                    "slippage_bps": "Slippage (bps)"
                }
            ),
            use_container_width=True,
            hide_index=True
        )
    else:
        pd_st.info("No trades executed yet.")

# Tab 2: Weather Forecasts
with tab2:
    st_c1, st_c2 = pd_st.columns([1, 3])
    with st_c1:
        # Select city to view details
        cities = sorted(list(forecasts['city'].unique()))
        selected_city = pd_st.selectbox("Select Target City", cities)
        
        # Load local warnings
        city_warnings = forecasts[(forecasts['city'] == selected_city) & (forecasts['extreme_alerts'].notna())]
        if not city_warnings.empty:
            pd_st.warning(f"⚠️ Extreme Weather Warning: {city_warnings.iloc[-1]['extreme_alerts']}")
        else:
            pd_st.success("✅ Meteorological conditions are nominal. No warnings in effect.")

    with st_c2:
        pd_st.subheader(f"Temperature and Rain Probabilities for {selected_city}")
        city_data = forecasts[forecasts['city'] == selected_city].sort_values(by="forecast_date")
        # Plot temperature max vs precipitation probability
        fig_weather = go.Figure()
        # Add temperature line
        fig_weather.add_trace(go.Scatter(
            x=pd.to_datetime(city_data['forecast_date']),
            y=city_data['temperature_max'],
            name='Max Temperature (°C)',
            line=dict(color='#ff7f0e', width=3),
            yaxis='y1'
        ))
        # Add rain probability bars
        fig_weather.add_trace(go.Bar(
            x=pd.to_datetime(city_data['forecast_date']),
            y=city_data['rain_probability'] * 100,
            name='Rain Probability (%)',
            marker_color='#1f77b4',
            opacity=0.6,
            yaxis='y2'
        ))
        
        fig_weather.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='rgba(148,163,184,0.1)'),
            yaxis1=dict(title='Max Temp (°C)', side='left', gridcolor='rgba(148,163,184,0.1)'),
            yaxis2=dict(title='Rain Prob (%)', side='right', overlaying='y', range=[0, 100]),
            margin=dict(l=20, r=20, t=10, b=20),
            height=350,
            font=dict(color='#f1f5f9'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        pd_st.plotly_chart(fig_weather, use_container_width=True)

# Tab 3: Prediction Markets
with tab3:
    pd_st.subheader("Active Weather Prediction Markets & Agent Predictions")
    
    if not predictions.empty:
        # Merge predictions with markets
        merged_pred = predictions.merge(markets, left_on="market_id", right_on="id", suffixes=("", "_market"))
        merged_pred = merged_pred.sort_values(by="created_at", ascending=False)

        pd_st.dataframe(
            merged_pred[["created_at", "title", "yes_price", "model_probability", "expected_value", "edge", "decision", "reasoning"]].rename(
                columns={
                    "created_at": "Prediction Time",
                    "title": "Prediction Market Question",
                    "yes_price": "Polymarket YES Price ($)",
                    "model_probability": "Agent Model Prob",
                    "expected_value": "Expected Value (EV)",
                    "edge": "Predicted Edge",
                    "decision": "Action Taken",
                    "reasoning": "Model Inference Reasoning"
                }
            ),
            use_container_width=True,
            hide_index=True
        )
        
        # Display odds comparison chart
        pd_st.subheader("Model Probabilities vs. Market Implied Probability")
        fig_odds = px.scatter(
            merged_pred,
            x="yes_price",
            y="model_probability",
            color="decision",
            hover_data=["title"],
            labels={"yes_price": "Market YES price", "model_probability": "Agent YES probability"},
            color_discrete_map={"BUY YES": "#10b981", "BUY NO": "#ef4444", "NO TRADE": "#64748b"}
        )
        fig_odds.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines', line=dict(color='white', dash='dash'), name='Fair Line'))
        fig_odds.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(gridcolor='rgba(148,163,184,0.1)', range=[0, 1]),
            yaxis=dict(gridcolor='rgba(148,163,184,0.1)', range=[0, 1]),
            margin=dict(l=20, r=20, t=10, b=20),
            height=350,
            font=dict(color='#f1f5f9')
        )
        pd_st.plotly_chart(fig_odds, use_container_width=True)
    else:
        pd_st.info("No predictions generated yet.")

# Tab 4: Performance Statistics
with tab4:
    pd_st.subheader("Statistical Reports & Forecast Verification")
    
    # Calculate Brier Score
    resolved = markets[markets['resolved'] == True]
    if not resolved.empty:
        # Merge with prediction
        merged_res = resolved.merge(predictions, left_on="id", right_on="market_id")
        
        if not merged_res.empty:
            # Code result as 1.0 (YES) or 0.0 (NO)
            actual_val = merged_res['resolution_result'].apply(lambda x: 1.0 if x == "YES" else 0.0)
            model_prob = merged_res['model_probability']
            
            brier_score = np.mean((model_prob - actual_val) ** 2)
            
            # Displays
            sc1, sc2, sc3 = pd_st.columns(3)
            with sc1:
                pd_st.metric("Brier Score (Forecasting Error)", f"{brier_score:.4f}", help="Lower is better. 0 is perfect prediction.")
            with sc2:
                # Count correct predictions
                correct = ((model_prob > 0.5) & (actual_val == 1.0)) | ((model_prob <= 0.5) & (actual_val == 0.0))
                accuracy = np.mean(correct)
                pd_st.metric("Prediction Accuracy", f"{accuracy:.1%}")
            with sc3:
                pd_st.metric("Total Resolved Markets", f"{len(merged_res)}")
                
            # Draw calibration curve
            pd_st.subheader("Probability Calibration Curve")
            fig_cal = go.Figure()
            fig_cal.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines', line=dict(color='gray', dash='dash'), name='Perfect Calibration'))
            
            # Simple binning
            bins = np.linspace(0, 1, 6)
            bin_centers = 0.5 * (bins[:-1] + bins[1:])
            empirical_probs = []
            mean_predicted = []
            
            for i in range(len(bins)-1):
                mask = (model_prob >= bins[i]) & (model_prob < bins[i+1])
                if np.sum(mask) > 0:
                    empirical_probs.append(np.mean(actual_val[mask]))
                    mean_predicted.append(np.mean(model_prob[mask]))
                else:
                    empirical_probs.append(None)
                    mean_predicted.append(bin_centers[i])
                    
            fig_cal.add_trace(go.Scatter(
                x=mean_predicted,
                y=empirical_probs,
                mode='markers+lines',
                name='Empirical Calibration',
                marker=dict(color='#00f2fe', size=10),
                line=dict(color='#00f2fe', width=2)
            ))
            
            fig_cal.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(gridcolor='rgba(148,163,184,0.1)', title="Mean Predicted Probability", range=[0,1]),
                yaxis=dict(gridcolor='rgba(148,163,184,0.1)', title="Empirical Probability", range=[0,1]),
                margin=dict(l=20, r=20, t=10, b=20),
                height=350,
                font=dict(color='#f1f5f9')
            )
            pd_st.plotly_chart(fig_cal, use_container_width=True)
        else:
            pd_st.info("No resolved predictions to verify forecasting performance.")
    else:
        pd_st.info("No prediction markets have been resolved yet. Waiting for market expirations to generate statistical reports.")
