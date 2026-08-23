FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    PREM3_API_RUNTIME=cloud

WORKDIR /app

COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /app/app

# In-process ADK Evaluation worker. Not uvicorn. Not meridian-eda-worker.
CMD ["python", "-m", "app.workers.evaluation_worker"]
