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

ENV FLASK_ENV=production
ENV PORT=8080

EXPOSE 8080

CMD gunicorn webapp_v2:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
