FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright dependencies manually (avoiding obsolete packages)
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browser only (without system deps since we installed them manually)
RUN playwright install chromium

COPY . .

# Create necessary directories for uploads and storage
RUN mkdir -p /app/data/uploads /app/data/documents /app/data/screenshots/fipe /app/data/pdfs /app/data/lens_temp

EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "mkdir -p /app/data/uploads /app/data/documents /app/data/screenshots/fipe /app/data/pdfs /app/data/lens_temp && alembic upgrade head && python start_server.py"]
