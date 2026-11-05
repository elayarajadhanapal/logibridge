FROM python:3.11-slim

WORKDIR /app

COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY inference/ ./inference/
COPY dashboard/ ./dashboard/
COPY data_pipeline/training_stats.npy ./training_stats.npy

ENV MODEL_PATH=/app/model.tflite
ENV MODEL_DIR=/app/models
ENV TRAINING_STATS_PATH=/app/training_stats.npy
ENV TRUCK_ID=truck-001
ENV MODEL_NAME=M1
ENV LOGIBRIDGE_MQTT_HOST=host.docker.internal
ENV LOGIBRIDGE_MQTT_PORT=1883

COPY model.tflite .

CMD ["python", "inference/inference_service.py"]