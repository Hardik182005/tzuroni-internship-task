# Deployment Guide

This document describes how to deploy and run the AETHER Weather Prediction Trading Agent.

## Prerequisite Setup

Ensure Python 3.12+ and pip/poetry are installed, or Docker & Docker Compose.

### Environment Configuration
Copy `.env.example` to `.env` and set your variables:
```bash
cp .env.example .env
```
Ensure you provide a valid `OPENROUTER_API_KEY` for active LLM-driven prediction reasoning.

---

## Local Setup (Standard Python)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   # OR using Poetry
   poetry install
   ```

2. **Initialize Database and Backend API**:
   The backend API is powered by FastAPI and Uvicorn. Start it:
   ```bash
   uvicorn app.database.connection:app --reload --port 8000
   ```

3. **Launch the Dashboard**:
   The dashboard is a Streamlit interface. Run:
   ```bash
   streamlit run app/dashboard/main.py
   ```

4. **Trigger Pipeline Manually**:
   You can trigger a full pipeline execution by running:
   ```bash
   python scripts/run_pipeline.py
   ```

---

## Docker Deployment (Recommended)

To run the entire suite in isolated containers (FastAPI backend + Streamlit dashboard + database storage):

1. **Build and Start Services**:
   ```bash
   docker-compose up --build -d
   ```
   This will spin up:
   - Backend on `http://localhost:8000`
   - Dashboard on `http://localhost:8501`

2. **Check Logs**:
   ```bash
   docker-compose logs -f
   ```

3. **Stop Containers**:
   ```bash
   docker-compose down
   ```
