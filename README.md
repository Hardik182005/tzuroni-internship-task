# 🌌 AETHER — Autonomous Multi-Agent Weather Prediction & Quantitative Trading Engine

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.12+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Hermes Framework](https://img.shields.io/badge/Agent_Framework-Hermes-orange.svg?style=for-the-badge&logo=ai&logoColor=white)](https://github.com/nousresearch/hermes-agent)
[![FastAPI Backend](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit UI](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Polymarket Markets](https://img.shields.io/badge/Market-Polymarket-0072CE.svg?style=for-the-badge&logo=polygon&logoColor=white)](https://polymarket.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

*A production-grade, fully autonomous, multi-agent AI system designed to predict weather outcome prediction markets on Polymarket and execute risk-managed paper trades using the Kelly Criterion.*

[Architecture Design](file:///c:/Users/hardi/OneDrive/Desktop/Interntask/tzuroni-internship-task/docs/architecture.md) • [Prediction Model](file:///c:/Users/hardi/OneDrive/Desktop/Interntask/tzuroni-internship-task/docs/prediction_model.md) • [Risk Engine](file:///c:/Users/hardi/OneDrive/Desktop/Interntask/tzuroni-internship-task/docs/risk_management.md) • [FastAPI Reference](file:///c:/Users/hardi/OneDrive/Desktop/Interntask/tzuroni-internship-task/docs/api.md) • [Database Design](file:///c:/Users/hardi/OneDrive/Desktop/Interntask/tzuroni-internship-task/docs/database.md)

</div>

---

## 🏛️ System Architecture

AETHER deploys a modular, asynchronous architecture combining live meteorological REST feeds, news and social sentiment scrapers, and Polymarket order book models. The core is powered by **10 specialized Hermes Agents** communicating over a unified SQLite + SQLAlchemy database layer.

```mermaid
graph TD
    subgraph Data Layer
        OM[Open-Meteo Forecasts]
        NOAA[NOAA US API]
        IMD[IMD India API]
        BOM[BOM Australia API]
        MO[Met Office UK API]
        News[News & Twitter/X Scrapers]
    end

    subgraph Multi-Agent System (Hermes)
        SA[Supervisor Agent]
        WIA[Weather Intelligence Agent]
        LWRA[Local Weather Agent]
        MA[Market Discovery Agent]
        RA[Sentiment Agent]
        PA[Bayesian Prediction Agent]
        RMA[Risk Management Agent]
        EA[Execution Agent]
        PTA[Portfolio Agent]
        HA[Hedging Agent]
    end

    subgraph Execution & Dashboard
        DB[(SQLite & SQLAlchemy)]
        API[FastAPI Backend]
        Dash[Streamlit Bloomberg Terminal]
        PT[Paper Trader Matching Engine]
    end

    OM --> WIA
    NOAA & IMD & BOM & MO --> LWRA
    News --> RA
    
    SA --> MA
    SA --> WIA
    SA --> LWRA
    SA --> RA
    SA --> PA
    PA --> RMA
    RMA --> EA
    EA --> PT
    PT --> PTA
    PTA --> HA
    
    MA -.-> DB
    WIA -.-> DB
    PA -.-> DB
    EA -.-> DB
    PTA -.-> DB
    
    DB --> Dash
    DB --> API
```

---

## 🤖 The 10 Hermes Agents

| Agent Name | Core Responsibility | Core Inputs / Tools |
| :--- | :--- | :--- |
| **Supervisor Agent** | Pipeline scheduling, retries, and contract resolution. | Time-triggers, weather historical results |
| **Weather Intelligence** | Fetching and parsing global meteorological data. | Open-Meteo API |
| **Local Weather Research** | Parsing country-specific alerts (NOAA, IMD, BOM). | Local meteorological APIs |
| **Market Agent** | Crawling and analyzing Polymarket active contracts. | Polymarket Gamma API |
| **News Research Agent** | Scraping social sentiment (Twitter, Reddit, reports). | Sentiment Analysis models |
| **Prediction Agent** | Bayesian ensembling of probabilities and EV. | Prediction Model ensembler |
| **Risk Management** | Calculating Kelly allocation sizes and daily stop-losses. | Kelly Sizing, VaR calculations |
| **Execution Agent** | Walking order books level-by-level to complete trades. | Paper Trader Engine |
| **Portfolio Agent** | Auditing returns, Sharpe/Sortino ratios, and drawdowns. | Portfolio snapshots database |
| **Hedging Agent** | Deploying offset trades for capital protection. | Correlation matrices, hedge logs |

---

## 📈 Mathematical & Quantitative Models

### 1. Bayesian Probability Ensemble
AETHER blends physics-based forecast probabilities ($P_{\text{global}}$) with country agency warnings ($P_{\text{local}}$) and social sentiment likelihood offsets ($\Delta S$) to compute a final calibrated event probability $P_{\text{model}}$:

$$P_{\text{model}} = \text{clip}\left( 0.6 \cdot P_{\text{global}} + 0.4 \cdot P_{\text{local}} - 0.15 \cdot \text{Sentiment}, \; 0.01, \; 0.99 \right)$$

### 2. Expected Value (EV) & Edge
The model compares $P_{\text{model}}$ with the contract market price ($P_{\text{market}}$) to identify profitable expected value discrepancies:

$$\text{EV}_{\text{YES}} = \frac{P_{\text{model}} - P_{\text{market}}}{P_{\text{market}}}$$

Trades are executed only when the expected edge $\ge 2.0\%$ and the expected value is positive.

### 3. Kelly Sizing with Exposure Caps
Allocation percentages of total portfolio equity are sized dynamically using the Kelly Criterion:

$$f^* = \frac{P_{\text{model}} - P_{\text{market}}}{1 - P_{\text{market}}}$$

To manage tail risks, AETHER applies a **Half-Kelly multiplier ($0.5$)**, limits any single trade to **20% maximum exposure**, and enforces a **5% daily loss circuit breaker**.

---

## 🚀 Quick Start Guide

### Prerequisites
Make sure you have Python 3.12+ and [Poetry](https://python-poetry.org/) or [Docker](https://docker.com) installed.

### 1. Setup Environment Configuration
Copy the `.env.example` file and set your keys:
```bash
cp .env.example .env
```
Ensure you paste a valid `OPENROUTER_API_KEY` for active LLM-driven prediction reasoning. To receive mobile alerts, get a token from `@BotFather` and your chat ID from `@userinfobot` and configure:
```bash
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 2. Run Containerized Services (Docker Compose)
To spin up the FastAPI service, Streamlit dashboard, and SQLite storage inside isolated containers:
```bash
docker-compose up --build -d
```
- **Streamlit Terminal Dashboard**: Open `http://localhost:8501`
- **FastAPI REST API Docs**: Open `http://localhost:8000/docs`

### 3. Run Locally (Standard Python)
```bash
# Install dependencies
pip install -r requirements.txt

# Start the FastAPI backend API
uvicorn app.database.connection:app --port 8000

# Start the Streamlit frontend UI
streamlit run app/dashboard/main.py

# Manually trigger a pipeline run
python scripts/run_pipeline.py
```

---

## 🧪 Testing and Verification

To execute the unit and integration test suite (covering Bayesian probability calibration, Kelly position sizing, and order book walks):
```bash
python -m pytest
```

---

## 🔗 Reference Links

- **Hermes Agent Framework**: [NousResearch/hermes-agent](https://github.com/nousresearch/hermes-agent)
- **Polymarket Paper Trader Simulator**: [agent-next/polymarket-paper-trader](https://github.com/agent-next/polymarket-paper-trader)
- **PolyWeather Research**: [yangyuan-zhen/PolyWeather](https://github.com/yangyuan-zhen/PolyWeather)
- **Open-Meteo API**: [open-meteo.com](https://open-meteo.com)
- **Polymarket Discovery**: [polymarket.com](https://polymarket.com)
- **OpenRouter LLMs**: [openrouter.ai](https://openrouter.ai)
