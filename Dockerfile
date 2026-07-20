FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    HOME=/home/app

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        curl \
        fonts-crosextra-carlito \
        fonts-dejavu-core \
        fonts-liberation2 \
        libreoffice-writer \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app
COPY pyproject.toml ./
COPY config ./config
COPY navapp ./navapp
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

COPY --chown=app:app . .
RUN mkdir -p /app/media /app/staticfiles /tmp/matplotlib \
    && chown -R app:app /app/media /app/staticfiles /tmp/matplotlib \
    && chmod +x /app/scripts/entrypoint.sh /app/scripts/smoke_report.sh

USER app
EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-", "--error-logfile", "-"]
