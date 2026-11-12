# AlarmOps (SIMULATION ONLY). Default: a small read-only web page + JSON API for Cloud Run.
# Batch mode (print alarms and exit):
#   docker run --rm alarmops:local python -m alarmops.service --rules alarms.yaml --data data/replay.csv
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ALARMOPS_ROOT=/app PORT=8080
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir .
COPY alarms.yaml gate.yaml ./
COPY data/replay.csv data/faults.csv data/post_deploy_alarm_log_healthy.csv data/post_deploy_alarm_log_drift.csv ./data/
RUN useradd --create-home appuser
USER appuser
EXPOSE 8080
CMD ["python", "-m", "alarmops.web"]
