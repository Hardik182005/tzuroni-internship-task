# Probabilistic Prediction Pipeline

This document explains the mathematical and statistical methodologies utilized by AETHER's Prediction Agent.

## Mathematical Formulation

To calculate the probability of a specific weather event $E$ (e.g., precipitation exceeding 0.1 mm, or max temperature exceeding 30°C), the model uses a calibrated ensemble blending physical meteorological forecast models, local country agency alerts, and news sentiment indicators.

### 1. The Meteorological Prior
The physical prior $P_{\text{meteo}}$ is calculated as a weighted combination of the global model forecast $P_{\text{global}}$ and the country-specific local meteorological agency forecast $P_{\text{local}}$:

$$P_{\text{meteo}} = w_1 \cdot P_{\text{global}} + w_2 \cdot P_{\text{local}}$$

Where we set:
- $w_1 = 0.60$ (weight assigned to the global European-physics-based ensemble model from Open-Meteo)
- $w_2 = 0.40$ (weight assigned to country-specific local models)

### 2. Bayesian Sentiment Adjustment
We treat news sentiment ($S \in [-1, 1]$) as a likelihood signal that updates the prior. A negative sentiment score (storm warnings, flood alarms) shifts the probability towards the extreme weather event:

$$P_{\text{updated}} = P_{\text{meteo}} + \Delta S$$

Where:
- $\Delta S = -0.15 \cdot S$ (for precipitation events, since bad weather sentiment increases rain odds)
- $\Delta S = +0.12 \cdot |S|$ (for extreme temperature events when the base forecast is already close to threshold)

### 3. Probability Calibration
The updated probability is passed through a calibration function mapping it strictly to $[0.01, 0.99]$ to avoid zero/one probabilities which would lead to extreme Kelly sizing:

$$P_{\text{calibrated}} = \max(0.01, \min(0.99, P_{\text{updated}}))$$

### 4. Expected Value (EV) and Expected Edge
We compare our calibrated model probability $P_{\text{model}}$ against the Polymarket implied probability $P_{\text{market}}$ (which is represented by the price of the contract, $YES\_Price \in (0, 1)$):

#### Buying YES Contract:
- **Expected Edge**: $\text{Edge}_{\text{YES}} = P_{\text{model}} - P_{\text{market}}$
- **Expected Value (EV)**: $\text{EV}_{\text{YES}} = \frac{P_{\text{model}} - P_{\text{market}}}{P_{\text{market}}}$

#### Buying NO Contract:
- **Expected Edge**: $\text{Edge}_{\text{NO}} = P_{\text{market}} - P_{\text{model}}$
- **Expected Value (EV)**: $\text{EV}_{\text{NO}} = \frac{P_{\text{market}} - P_{\text{model}}}{1 - P_{\text{market}}}$

A trade decision is only triggered if the **Expected Edge** $\ge 2.0\%$ and the corresponding **EV** $> 0.0$.
Otherwise, the agent outputs `NO TRADE` to protect capital.
