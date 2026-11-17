FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app
COPY quant_engine /app/quant_engine
COPY ai_agent /app/ai_agent
COPY worker /app/worker

CMD ["python", "-m", "worker.main"]

