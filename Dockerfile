FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml .
# Create a dummy README to satisfy build backend if needed, though we can mostly just pip install . or similar
RUN touch README.md
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Environment variables should be supplied at runtime or via .env file
# CMD ["python", "-m", "src.bot"]
CMD ["sh", "-c", "alembic upgrade head && python -m src.bot"]
