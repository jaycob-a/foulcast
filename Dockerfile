FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code. `templates/` is the foul-log form and nothing else
# since Step 25 — shelved and unserved, copied so that registering its
# blueprint is a one-line change and not an image change. The spray profiles
# that used to be copied here were read by the prediction endpoints, which no
# longer exist, and the simulation that still reads them does not run in this
# image.
COPY foulball/ foulball/
COPY templates/ templates/
COPY webapp_v2.py .

# The public site: pre-built static pages plus the copy layer webapp_v2 reads
# its slug registry from. Rebuild with `python site_build.py` before deploying;
# without these, /parks/ 404s and the rest of the app is unaffected.
COPY site/ site/
COPY site_data.py .

# Foul observation log lands here by default, and nothing writes to it while
# the log is shelved. THIS DIRECTORY IS EPHEMERAL — it is wiped on every
# redeploy. If the log is ever revived: set FOULCAST_LOG_DB to a path on a
# mounted volume before logging anything you care about, and export after each
# game (/api/log/export.jsonl). See NOTES_STEP8.md.
RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV FLASK_ENV=production

EXPOSE 8080

CMD ["gunicorn", "webapp_v2:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120"]
