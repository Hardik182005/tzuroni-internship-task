# Architecture & Multi-Agent Design

This document details the architecture and agent interaction patterns for AETHER — the Weather Prediction AI Trading Agent.

## Overall System Architecture

The platform follows a decoupled, data-driven architecture. The core multi-agent system runs as an asynchronous pipeline orchestrated by the Supervisor Agent, persisting state to SQLite database tables via SQLAlchemy. The presentation layer (Streamlit Terminal Dashboard) and Web API (FastAPI) query this persistent state in real-time.

```mermaid
graph TB
    subgraph Data Sources
        API_Weather[Open-Meteo API]
        API_Local[Country Meteorological Agencies]
        API_Polymarket[Polymarket Gamma REST API]
        Scrapers[News & Twitter/X Scrapers]
    end

    subgraph Multi-Agent Engine
        SA[Supervisor Agent]
        WIA[Weather Intelligence Agent]
        LWRA[Local Weather Research Agent]
        MA[Market Agent]
        RA[News Research Agent]
        PA[Prediction Agent]
        RMA[Risk Management Agent]
        EA[Execution Agent]
        PTA[Portfolio Agent]
        HA[Hedging Agent]
    end

    subgraph Storage Layer
        DB[(SQLite Database)]
        ORM[SQLAlchemy Models]
    end

    subgraph Interface & Execution
        API[FastAPI Service]
        Dash[Streamlit Bloomberg Terminal Dashboard]
        PT[Paper Trader Engine]
    end

    %% Data flow
    API_Weather --> WIA
    API_Local --> LWRA
    API_Polymarket --> MA
    Scrapers --> RA

    %% Agent Interactions
    SA -->|1. Scans & Resolves Markets| MA
    SA -->|2. Orchestrates Weather Gathering| WIA
    SA -->|2. Orchestrates Local Intelligence| LWRA
    SA -->|2. Orchestrates Social/Sentiment News| RA
    SA -->|3. Combines Features for Forecasting| PA
    PA -->|4. Requests Kelly Allocation| RMA
    RMA -->|5. Passes Risk-Cap Size| EA
    EA -->|6. Places Orders| PT
    PT -->|7. Updates Cash & Balances| PTA
    PTA -->|8. Signals Exposure Breaches| HA
    HA -->|9. Submits Counter-Orders| EA

    %% DB Persistence
    MA -.->|Markets| DB
    WIA -.->|Forecasts| DB
    LWRA -.->|Forecasts| DB
    RA -.->|SentimentBriefs| DB
    PA -.->|Predictions| DB
    EA -.->|Orders & Trades| DB
    PTA -.->|Portfolio Snapshots| DB
    HA -.->|Hedge Logs| DB

    %% App Queries
    DB --> ORM
    ORM --> API
    ORM --> Dash
```

---

## The 10 Hermes Agents

Each agent is built on top of a common `BaseAgent` class implementing persistent logging, OpenRouter LLM interface, multi-model fallbacks (Gemini, Gemma, Mistral, Llama), and auto-recovery error handlers.

1. **Supervisor Agent**: Orchestrates and schedules the entire pipeline sequence, handles failures/retries, and triggers automated end-of-day market resolutions based on actual weather reports.
2. **Weather Intelligence Agent**: Fetches global weather forecasts (7-day ahead arrays) and identifies climate anomalies.
3. **Local Weather Research Agent**: Collects country-specific meteorological agency reports (NOAA for US, BOM for Australia, IMD for India, Met Office for UK, JMA for Japan) and identifies severe storm/temperature alerts.
4. **Market Agent**: Discovers active prediction markets on Polymarket and tracks bids, asks, historical odds, volume, and liquidity depth.
5. **Research Agent**: Scrapes social media and meteorological feeds for real-time sentiment signals.
6. **Prediction Agent**: Combines forecast models, alerts, and sentiment to perform probabilistic event calculations.
7. **Risk Management Agent**: Sizes positions using the Kelly Criterion and fractional Kelly factors.
8. **Execution Agent**: Interfaces with the high-fidelity Paper Trader order book matching engine.
9. **Portfolio Agent**: Audits returns, win rates, Sharpe/Sortino ratios, and drawdowns.
10. **Hedging Agent**: Protects equity by placing offsetting cross-market or YES/NO contract hedges.
