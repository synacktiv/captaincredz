FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends supervisor sqlite3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY supervisord.conf /etc/supervisor/supervisord.conf

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY ./app /app

# Run supervisord in the foreground (-n) so the container doesn't exit
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]