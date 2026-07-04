# FastAPI Backend Service API

This document lists the REST API endpoints exposed by the AETHER backend service running on `http://localhost:8000`.

## Endpoints Reference

### 1. Health Status
Check database connection and system health.
- **URL**: `/health`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "status": "healthy",
    "database": "weather_trading.db"
  }
  ```

### 2. Fetch Prediction Markets
Get list of prediction markets loaded in SQLite.
- **URL**: `/markets`
- **Method**: `GET`
- **Response**: Array of Market objects.

### 3. Fetch Predictions
Get latest probability model outputs.
- **URL**: `/predictions`
- **Method**: `GET`
- **Response**: Array of Prediction records.

### 4. Fetch Trade History
Get details of all executed paper transactions.
- **URL**: `/trades`
- **Method**: `GET`
- **Response**: Array of Trade records.

### 5. Fetch Portfolio State
Get current cash, total equity, Sharpe Ratio, drawdown, etc.
- **URL**: `/portfolio`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "timestamp": "2026-07-03T10:00:00",
    "cash_balance": 9850.50,
    "equity": 10120.30,
    "open_positions_value": 269.80,
    "daily_return": 0.012,
    "max_drawdown": 0.005,
    "sharpe_ratio": 1.82,
    "sortino_ratio": 2.10,
    "win_rate": 0.66,
    "loss_rate": 0.34,
    "profit_factor": 1.45,
    "exposure_pct": 0.026
  }
  ```

### 6. Run Pipeline Trigger
Asynchronously triggers a new multi-agent supervisor pipeline run in the background.
- **URL**: `/pipeline/run`
- **Method**: `POST`
- **Response**:
  ```json
  {
    "status": "Pipeline run triggered in background"
  }
  ```
