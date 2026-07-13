FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY rag/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rag/ ./rag/

# Cloud Run injects $PORT
CMD exec uvicorn rag.api:app --host 0.0.0.0 --port ${PORT:-8080}
