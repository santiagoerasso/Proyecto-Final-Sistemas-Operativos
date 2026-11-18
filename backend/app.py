"""API de demostración instrumentada para Prometheus."""
import os
import socket
import time
from datetime import datetime, timezone
from flask import Flask, Response, jsonify, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = Flask(__name__)
INSTANCE_ID = os.getenv("INSTANCE_ID", "sin-id")

REQUESTS = Counter(
    "backend_http_requests_total",
    "Numero de solicitudes HTTP atendidas por cada instancia",
    ["instance_id", "method", "endpoint", "status"],
)
DURATION = Histogram(
    "backend_http_request_duration_seconds",
    "Duracion de cada solicitud HTTP de backend en segundos",
    ["instance_id", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

@app.before_request
def start_timer():
    g.start_time = time.perf_counter()

@app.after_request
def record_metrics(response):
    if request.path not in ("/metrics", "/health"):
        endpoint = request.path if request.path in ("/", "/work") else "other"
        REQUESTS.labels(INSTANCE_ID, request.method, endpoint, str(response.status_code)).inc()
        DURATION.labels(INSTANCE_ID, endpoint).observe(time.perf_counter() - g.start_time)
    return response

@app.get("/")
def index():
    return jsonify({
        "mensaje": "Respuesta distribuida mediante Nginx",
        "instancia": INSTANCE_ID,
        "contenedor": socket.gethostname(),
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
    })

@app.get("/work")
def work():
    try:
        milliseconds = int(request.args.get("ms", "20"))
    except ValueError:
        return jsonify({"error": "ms debe ser un numero entero"}), 400
    milliseconds = max(0, min(milliseconds, 500))
    time.sleep(milliseconds / 1000)
    return jsonify({
        "instancia": INSTANCE_ID,
        "tiempo_simulado_ms": milliseconds,
        "mensaje": "Solicitud procesada",
    })

@app.get("/health")
def health():
    return jsonify({"status": "ok", "instancia": INSTANCE_ID})

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
