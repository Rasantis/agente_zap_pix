FROM python:3.11-slim

WORKDIR /app

# Dependências primeiro (cache de camada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY app ./app
COPY ingest ./ingest

ENV PYTHONUNBUFFERED=1

# Render/Railway fornecem $PORT; default 8000 para uso local
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
