Implement a complete MVP for a B3 AI Stock Scanner.

Goal:
Build a web application that analyzes Brazilian stocks using daily and weekly historical data, generates technical/quantitative signals, and displays suggested entry, stop loss and targets. Do not implement automatic order execution.

Tech stack:
- Frontend: React + Vite + TypeScript + TailwindCSS
- Charts: TradingView Lightweight Charts
- Backend: FastAPI + Python
- Database: PostgreSQL + TimescaleDB
- ORM: SQLAlchemy
- Migrations: Alembic
- Data processing: pandas, numpy
- AI: OpenAI Agents SDK
- Containerization: Docker Compose

Architecture:
- frontend/
- backend/
- worker/
- quant_engine/
- ai_agent/
- database/

Core features:
1. Store B3 assets.
2. Import 10 years of daily OHLCV data.
3. Resample daily candles into weekly candles.
4. Calculate indicators:
   - SMA20, SMA50, SMA200
   - ATR14
   - RSI14
   - volume ratio
   - 20-day breakout
   - 52-week high distance
   - relative strength versus IBOV
5. Generate daily signals using weekly trend + daily trigger.
6. Suggest:
   - entry price
   - stop loss
   - target 1
   - target 2
   - risk/reward
   - setup score from 0 to 100
7. Display signals in a dashboard.
8. Display candlestick chart with:
   - entry line
   - stop line
   - target lines
   - moving averages
   - volume
9. Generate an AI explanation for each signal.
10. Do not send investment advice. Use educational/analytical language only.

Database tables:
- assets
- candles_daily
- candles_weekly
- indicators_daily
- indicators_weekly
- signals
- backtest_results

API endpoints:
- GET /health
- GET /assets
- GET /signals/today
- GET /signals/{ticker}
- GET /assets/{ticker}/candles?timeframe=1d
- GET /assets/{ticker}/indicators
- POST /scanner/run
- POST /agent/analyze/{ticker}

Signal logic:
Weekly filter:
- weekly close > weekly SMA20
- weekly SMA20 rising
- weekly close > weekly SMA50
- relative strength vs IBOV positive

Daily trigger:
- close breaks the highest high of the previous 20 sessions
OR
- close pulls back near SMA20 and then closes above the previous day high

Score:
- weekly trend: 25 points
- daily momentum: 20 points
- relative strength: 20 points
- volume ratio: 15 points
- volatility quality: 10 points
- setup quality: 10 points

Entry:
- breakout setup: entry above current high
- pullback setup: entry above previous day high

Stop:
- below recent swing low
- or 1.5 ATR below entry

Targets:
- target 1 = entry + 2R
- target 2 = entry + 3R

Deliverables:
- working Docker Compose
- backend API
- database migrations
- quant engine
- scanner service
- AI explanation service
- frontend dashboard
- chart detail page
- README with setup instructions
- .env.example

Important constraints:
- No broker integration.
- No order execution.
- No financial advice wording.
- Code must be modular and testable.