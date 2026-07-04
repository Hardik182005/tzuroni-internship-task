# Multi-Agent Workflow Sequence

This document describes how the AETHER agents interact and execute the end-to-end trading loop.

## Workflow Sequence

The Supervisor Agent orchestrates execution. The pipeline is designed to be triggered periodically (e.g., hourly) or run on demand via the API or CLI.

```mermaid
sequenceDiagram
    autonumber
    participant SA as Supervisor Agent
    participant MA as Market Agent
    participant DB as SQLite Database
    participant WI as Weather Intelligence Agent
    participant LW as Local Research Agent
    participant RA as News Research Agent
    participant PA as Prediction Agent
    participant RM as Risk Management Agent
    participant EA as Execution Agent
    
    SA->>MA: 1. Trigger prediction markets scan
    MA->>DB: Save discovered / simulated weather markets
    MA-->>SA: Return active markets list
    
    loop For each city represented in active markets
        SA->>WI: 2. Trigger global weather forecast fetch
        WI->>DB: Save global forecasts (Open-Meteo)
        SA->>LW: 3. Trigger local country meteorology fetch
        LW->>DB: Save country warnings & forecast perturbations
        SA->>RA: 4. Trigger news & social sentiment gather
        RA->>DB: Save sentiment scores & research briefs
    end
    
    loop For each active prediction market
        SA->>PA: 5. Analyze market predictions
        PA->>DB: Query latest weather & news data
        PA->>PA: Run ensembled Bayesian updating
        PA->>DB: Save model probability, EV, and decision
        
        opt If Decision is BUY YES or BUY NO
            SA->>RM: 6. Request position size sizing
            RM->>DB: Query current portfolio equity & drawdowns
            RM->>RM: Apply Fractional Kelly formula & exposure caps
            RM-->>SA: Return trade sizing (shares)
            
            opt If share size > 0
                SA->>EA: 7. Trigger paper trade execution
                EA->>DB: Match against CLOB order book (walk bids/asks)
                EA->>DB: Deduct cash, save Order & Trade records
            end
        end
    end
    
    SA->>DB: 8. Trigger Portfolio Agent performance recalculation
    SA->>DB: 9. Trigger Hedging Agent portfolio protection
```

## Error Recovery & Fail-safes
- **LLM Outage/Limit Fallbacks**: If OpenRouter calls fail, the `BaseAgent` retries 3 times using exponential backoff, and automatically cycles through fallback models (Gemma-2, Mistral, Llama-3). If all fail, it falls back to deterministic model-driven reasoning to prevent workflow disruption.
- **Data Scraper Failures**: If meteorological APIs fail, the `WeatherService` generates historical/monsoon-calibrated climatological forecasts, ensuring the prediction pipeline never crashes.
- **Risk Circuit Breakers**: Position sizing calculation automatically returns `0` shares if daily portfolio drawdowns exceed 5% or if cumulative drawdown exceeds 20%.
