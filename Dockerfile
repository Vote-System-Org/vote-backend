# ── Stage 1 — Base ────────────────────────────────────────────────────────────
FROM python:3.10-slim AS base

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 2 — Dependencies ────────────────────────────────────────────────────
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ── Stage 3 — Production ──────────────────────────────────────────────────────
FROM dependencies AS production

COPY . .



# Créer un utilisateur non-root pour la sécurité
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --home /app appuser && \
    chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-"]