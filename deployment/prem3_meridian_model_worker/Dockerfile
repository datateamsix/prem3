FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY deployment/prem3_meridian_model_worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /app/app
COPY datasets/music_center/dataset_a/truth/expected_model_ready_weekly.csv \
    /app/datasets/music_center/dataset_a/truth/expected_model_ready_weekly.csv

ENTRYPOINT ["python", "-m", "app.tools.meridian_model_worker"]
