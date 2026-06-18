FROM python:3.11-slim

WORKDIR /app

# System deps needed by Prophet (Stan compiler) and LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project
COPY . .

EXPOSE 8000

# Run from project root so `backend.app.main` resolves correctly
CMD ["uvicorn", "backend.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload"]