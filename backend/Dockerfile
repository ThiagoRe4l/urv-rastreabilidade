FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependências primeiro, para o cache de camadas sobreviver a mudanças de código.
COPY pyproject.toml ./
RUN mkdir -p app scripts && touch app/__init__.py scripts/__init__.py \
    && pip install ".[dev]" \
    && pip uninstall -y urv-rastreabilidade

COPY . .

RUN mkdir -p /data/uploads
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
