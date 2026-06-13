FROM python:3.11-slim

WORKDIR /app

# System deps for lxml, fastembed (numpy/onnxruntime), and curl_cffi.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first so they cache when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# App code.
COPY . .

# SQLite lives on the Fly volume mounted at /data.
ENV DATABASE_URL="sqlite+aiosqlite:////data/quant_researcher.db"
ENV APP_HOST="0.0.0.0"
ENV PORT=8000

EXPOSE 8000

# Use shell form so $PORT expands at runtime.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
