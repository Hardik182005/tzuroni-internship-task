# Risk Management Engine

This document details the portfolio protection rules and Kelly sizing equations implemented in AETHER.

## The Kelly Criterion Sizing Model

The Kelly Criterion computes the mathematically optimal percentage of total portfolio equity to allocate to a trade to maximize the expected growth rate of capital.

For binary outcomes on Polymarket, the optimal fraction $f^*$ is defined as:

$$f^* = \frac{p \cdot b - q}{b}$$

Where:
- $p$ is the model's winning probability ($P_{\text{model}}$)
- $q$ is the model's losing probability ($1 - P_{\text{model}}$)
- $b$ is the net decimal odds ($1 / \text{market\_price} - 1$)

This simplifies directly to:

### For Buying YES Contracts:
$$f^* = \frac{P_{\text{model}} - P_{\text{market}}}{1 - P_{\text{market}}}$$

### For Buying NO Contracts:
$$f^* = \frac{P_{\text{market}} - P_{\text{model}}}{P_{\text{market}}}$$

## Portfolio Constraints & Limits

In production quantitative trading, pure Kelly sizing is rarely used because it exhibits high volatility and is sensitive to probability estimation errors. We implement the following risk controls:

1. **Fractional Kelly Sizing**: We scale down the Kelly fraction to reduce volatility:
   $$f_{\text{allocated}} = f^* \cdot F$$
   where $F = 0.50$ (Half-Kelly) by default, configurable in `.env`.
   
2. **Maximum Single-Market Concentration Cap**: A single trade can never exceed **20%** of total portfolio equity, protecting capital against forecasting errors.
   
3. **Daily Loss Limit**: If the portfolio's daily return drops below **-5%**, the agent stops placing new trades for the day.
   
4. **Drawdown Circuit Breaker**: If cumulative portfolio equity falls by **20%** or more from the initial balance ($10,000), a global circuit breaker is triggered, stopping all trading activities.
