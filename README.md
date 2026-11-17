# B3 AI Stock Scanner

MVP web para analisar ações brasileiras com candles diários e semanais, indicadores técnicos, sinais quantitativos e explicações educacionais por IA. O projeto não tem integração com corretora e não executa ordens.

## Stack

- Frontend: React, Vite, TypeScript, TailwindCSS, TradingView Lightweight Charts
- Backend: FastAPI, SQLAlchemy, Alembic
- Banco: PostgreSQL com TimescaleDB
- Quant: pandas, numpy
- IA: OpenAI Agents SDK com fallback local
- Infra: Docker Compose

## Código-fonte

O repositório público fica em:

https://github.com/diegojoel/b3-ai-scanner

```bash
git clone https://github.com/diegojoel/b3-ai-scanner.git
cd b3-ai-scanner
```

Copie um dos arquivos `.env*.example` para `.env` e preencha senha, chave de IA e URL do banco na sua máquina. O arquivo `.env` não entra no repositório.

## Aplicacao publicada

A aplicacao pode ser acessada em:

https://b3-ai-scanner-web.onrender.com/

## Como rodar localmente sem Docker

Este modo usa SQLite em `scanner.local.db`, cria as tabelas automaticamente e permite testar o MVP sem PostgreSQL instalado.

1. Em um terminal, suba o backend:

```powershell
.\scripts\run-local-backend.ps1
```

2. Em outro terminal, suba o frontend:

```powershell
.\scripts\run-local-frontend.ps1
```

3. Gere dados demo, indicadores e sinais:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/scanner/run
```

4. Acesse:

- Frontend: http://localhost:5173
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

Se preferir configurar manualmente, copie `.env.local.example` para `.env` e use:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

No frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Usar Supabase PostgreSQL

Copie `.env.supabase.example` para `.env` e substitua `[YOUR-PASSWORD]` pela senha do banco:

```powershell
Copy-Item .env.supabase.example .env
```

A URL usa o formato do SQLAlchemy com o driver `psycopg`:

```text
postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

Depois reinicie o backend. Com `CREATE_DB_ON_STARTUP=true`, o app cria as tabelas no primeiro startup.

## Como rodar com Docker

1. Crie o arquivo de ambiente:

```bash
cp .env.example .env
```

2. Suba os serviços:

```bash
docker compose up --build
```

3. Gere dados demo, indicadores e sinais:

```bash
curl -X POST http://localhost:8000/scanner/run
```

4. Acesse:

- Frontend: http://localhost:5173
- API: http://localhost:8000
- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs

## Deploy barato com Vercel, Render e Supabase

Use o Supabase como PostgreSQL, o Render para o backend FastAPI e a Vercel para o frontend Vite.

### 1. Supabase

No Supabase, copie a connection string do PostgreSQL e use o formato SQLAlchemy:

```text
postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

Guarde esse valor para configurar a variavel `DATABASE_URL` no Render.

### 2. Render Backend

Crie um **Web Service** no Render a partir do repositorio.

Configuracao recomendada:

- Runtime: Docker
- Dockerfile path: `backend/Dockerfile`
- Docker build context directory: `.`
- Health check path: `/health`
- Plan: Starter ou equivalente

Variaveis de ambiente no Render:

```text
DATABASE_URL=postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,https://SEU-PROJETO.vercel.app
CREATE_DB_ON_STARTUP=true
SEED_DEMO_DATA=true
USE_REAL_MARKET_DATA=true
SCAN_ALL_B3=true
B3_UNIVERSE_LIMIT=0
INCLUDE_SMALLCAPS=false
B3_RECENT_TRADING_DAYS=30
B3_REFRESH_BATCH_SIZE=40
AUTO_RUN_SCANNER=true
SCANNER_INTERVAL_SECONDS=180
SCANNER_INITIAL_DELAY_SECONDS=30
```

No plano Free do Render, mantenha `B3_UNIVERSE_LIMIT` entre `40` e `80` no primeiro deploy se quiser uma carga inicial rapida. Use `B3_UNIVERSE_LIMIT=0` para buscar todos os ativos retornados pela brapi. `B3_REFRESH_BATCH_SIZE` limita quantos historicos novos ou desatualizados sao baixados por execucao do scanner, evitando timeouts enquanto o universo completo e preenchido em lotes.

Com `AUTO_RUN_SCANNER=true`, o backend executa o scanner automaticamente a cada `SCANNER_INTERVAL_SECONDS`. No Render Free, use um limite de universo conservador para evitar scanners longos demais.

Depois do deploy, valide:

```text
https://SEU-BACKEND.onrender.com/health
```

### 3. Vercel Frontend

Importe o repositorio na Vercel e configure:

- Framework Preset: Vite
- Root Directory: `frontend`
- Build Command: `npm run build`
- Output Directory: `dist`

Variavel de ambiente na Vercel:

```text
VITE_API_URL=https://SEU-BACKEND.onrender.com
```

Depois que a Vercel gerar a URL final, volte ao Render e atualize `CORS_ORIGINS` incluindo essa URL.

### 4. Primeiro carregamento

Com backend e frontend publicados, chame o scanner uma vez:

```bash
curl -X POST https://SEU-BACKEND.onrender.com/scanner/run
```

Em seguida abra o frontend na Vercel e clique em **Atualizar**.

## Universo B3

Com `SCAN_ALL_B3=true`, o scanner busca o universo de acoes negociadas via brapi e baixa candles diarios reais pelo Yahoo Finance usando tickers `.SA`. `BOVA11` e mantido como benchmark para forca relativa. Use `B3_UNIVERSE_LIMIT=0` para varrer todos os ativos retornados pela brapi, ou defina um numero como `50` para testes rapidos.

Com `INCLUDE_SMALLCAPS=true`, os tickers em `B3_SMALLCAP_TICKERS` entram no universo mesmo quando `B3_UNIVERSE_LIMIT` esta reduzido. Edite essa lista no `.env` para incluir ou remover small caps especificas.

O seed sintetico permanece como fallback quando uma fonte externa falha. Para dados institucionais, substitua o importador em `backend/app/services/market_data.py` por uma fonte licenciada de OHLCV da B3 e mantenha o mesmo formato de DataFrame.

## Endpoints

- `GET /health`
- `GET /assets`
- `GET /signals/today`
- `GET /signals/{ticker}`
- `GET /assets/{ticker}/candles?timeframe=1d`
- `GET /assets/{ticker}/candles?timeframe=1w`
- `GET /assets/{ticker}/indicators`
- `GET /assets/{ticker}/fundamentals`
- `POST /assets/{ticker}/fundamentals`
- `POST /scanner/run`
- `POST /agent/analyze/{ticker}`

## Analise fundamentalista

A camada fundamentalista fica separada do score tecnico. Ela calcula um `Fundamental Risk Score` de 0 a 100 e classifica o ativo como `LOW`, `MEDIUM`, `HIGH`, `EXTREME` ou `UNKNOWN`, usando indicadores como divida liquida/EBITDA, margem EBITDA, liquidez corrente, fluxo de caixa livre, ROE, crescimento e flags de risco de reestruturacao, diluicao ou dependencia fiscal.

Exemplo para cadastrar uma leitura manual:

```bash
curl -X POST http://localhost:8000/assets/BRKM5/fundamentals \
  -H "Content-Type: application/json" \
  -d '{"period_date":"2026-03-31","net_debt_ebitda":16.8,"ebitda_margin":0.03,"free_cash_flow_yield":-0.12,"cash_burn_ratio":1.4,"default_or_restructuring_risk":true,"dilution_risk":true,"fiscal_benefit_dependency":true,"notes":"Exemplo educacional: risco fundamentalista separado do setup tecnico."}'
```

Quando existir dado fundamentalista para o ativo, o dashboard exibe a leitura no detalhe do sinal e o scanner anexa o risco em `metrics.fundamental`.

## Observações

O seed inicial gera séries sintéticas de 10 anos para permitir testar o MVP sem dependências externas. Para dados reais, substitua o importador em `backend/app/services/demo_data.py` por uma fonte licenciada de OHLCV da B3 e mantenha o mesmo formato de DataFrame.

As explicações são formuladas em linguagem educacional e analítica. O sistema não recomenda compra ou venda, não envia ordens e não deve ser interpretado como aconselhamento financeiro.
