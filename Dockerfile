FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY foulball/ foulball/
COPY templates/ templates/
COPY webapp_v2.py .

# Copy spray profiles (needed at runtime for per-batter pull tendency)
COPY .cache/spray_profiles.json .cache/spray_profiles.json

# Foul observation log lands here by default. THIS DIRECTORY IS EPHEMERAL —
# it is wiped on every redeploy. Set FOULCAST_LOG_DB to a path on a mounted
# volume before logging anything you care about, and export after each game
# (/api/log/export.jsonl). See NOTES_STEP8.md.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV FLASK_ENV=production

EXPOSE 8080

CMD ["gunicorn", "webapp_v2:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120"]
