FROM python:3.11-slim

WORKDIR /app

# Copy only necessary files first for better caching
COPY pyproject.toml poetry.lock ./
COPY src ./src

# Install dependencies
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

EXPOSE 8000

CMD ["uvicorn", "chatbot_ai_system.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
