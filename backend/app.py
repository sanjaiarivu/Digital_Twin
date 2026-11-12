"""Flask API for machine telemetry, alerts, predictions, and maintenance."""
from __future__ import annotations

import csv
import io
import json
import os
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "local-demo-key")
db_url = os.getenv("DATABASE_URL", "sqlite:///digital_twin.db")
if db_url.startswith("mysql://"):
    db_url = db_url.replace("mysql://", "mysql+pymysql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CORS(app)
db = SQLAlchemy(app)


def now():
    return datetime.now(timezone.utc)


class Machine(db.Model):
    id = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(80), nullable=False, default="Industrial machine")
    location = db.Column(db.String(100), nullable=False, default="Plant floor")
    expected_rpm = db.Column(db.Float, nullable=False, default=1500)
    created_at = db.Column(db.DateTime(timezone=True), default=now)


class Reading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.String(40), db.ForeignKey("machine.id"), nullable=False, index=True)
    temperature = db.Column(db.Float, nullable=False)
    vibration = db.Column(db.Float, nullable=False)
    rpm = db.Column(db.Float, nullable=False)
    health = db.Column(db.Float, nullable=False)
    failure_risk = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(20), nullable=False, default="simulation")
    created_at = db.Column(db.DateTime(timezone=True), default=now, index=True)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.String(40), nullable=False, index=True)
    type = db.Column(db.String(100), nullable=False)
    reading = db.Column(db.String(80), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default="Open", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now)


class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.String(40), nullable=False)
    failure_risk = db.Column(db.Float, nullable=False)
    health = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(60), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now)


class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    performed_by = db.Column(db.String(100), default="Unassigned")
    created_at = db.Column(db.DateTime(timezone=True), default=now)


MODEL = None
MODEL_METHOD = "Deterministic demo fallback"
model_path = Path(os.getenv("MODEL_PATH", "../ml_model/model.joblib"))
if not model_path.is_absolute():
    model_path = (Path(__file__).parent / model_path).resolve()
try:
    if model_path.exists():
        MODEL = joblib.load(model_path)
        MODEL_METHOD = "Trained Random Forest"
except Exception as exc:
    app.logger.warning("Model unavailable, using demo fallback: %s", exc)


def assess(temp, vibration, rpm, expected_rpm=1500):
    """Return deterministic health and risk, or trained classifier probability."""
    features = [[float(temp), float(vibration), float(rpm)]]
    if MODEL is not None:
        risk = float(MODEL.predict_proba(features)[0][1])
    else:
        # Explicit rule-based demo: risk rises with heat, vibration, and RPM deviation.
        risk = min(.98, max(.02, .12 + max(0, temp - 65) * .012 + max(0, vibration - 2.5) * .12 + abs(rpm - expected_rpm) / max(expected_rpm, 1) * .38))
    health = max(5, min(100, round(100 - risk * 75 - max(0, temp - 70) * .35 - max(0, vibration - 3) * 2, 1)))
    return round(health, 1), round(risk * 100, 1)


def serialize_machine(machine):
    reading = Reading.query.filter_by(machine_id=machine.id).order_by(desc(Reading.created_at)).first()
    if reading:
        return {"id": machine.id, "name": machine.name, "type": machine.type, "location": machine.location,
                "expected_rpm": machine.expected_rpm, "temperature": reading.temperature, "vibration": reading.vibration,
                "rpm": reading.rpm, "health": reading.health, "failure_risk": reading.failure_risk,
                "source": reading.source, "updated_at": reading.created_at.isoformat(), "status": status_for(reading)}
    return {"id": machine.id, "name": machine.name, "type": machine.type, "location": machine.location,
            "expected_rpm": machine.expected_rpm, "temperature": 0, "vibration": 0, "rpm": 0,
            "health": 100, "failure_risk": 0, "source": "simulation", "status": "Normal"}


def status_for(reading):
    return "Critical" if reading.failure_risk >= 65 or reading.temperature >= 85 or reading.vibration >= 5 else (
        "Warning" if reading.failure_risk >= 35 or reading.temperature >= 75 or reading.vibration >= 3.5 else "Normal")


def record_reading(machine, temp, vibration, rpm, source="simulation"):
    health, risk = assess(temp, vibration, rpm, machine.expected_rpm)
    reading = Reading(machine_id=machine.id, temperature=round(float(temp), 1), vibration=round(float(vibration), 2),
                      rpm=round(float(rpm), 1), health=health, failure_risk=risk, source=source)
    db.session.add(reading)
    db.session.add(Prediction(machine_id=machine.id, failure_risk=risk, health=health, method=MODEL_METHOD))
    severity = status_for(reading)
    alerts = []
    if temp >= 75: alerts.append(("High temperature", f"{temp:.1f} °C", "Critical" if temp >= 85 else "Warning"))
    if vibration >= 3.5: alerts.append(("Abnormal vibration", f"{vibration:.2f} mm/s", "Critical" if vibration >= 5 else "Warning"))
    if abs(rpm - machine.expected_rpm) > machine.expected_rpm * .12: alerts.append(("RPM out of range", f"{rpm:.0f} RPM", "Warning"))
    if risk >= 55: alerts.append(("Predictive maintenance risk", f"{risk:.1f}% failure risk", "Critical" if risk >= 75 else "Warning"))
    for kind, value, level in alerts:
        recent = Alert.query.filter_by(machine_id=machine.id, type=kind, status="Open").order_by(desc(Alert.created_at)).first()
        if not recent or (now().replace(tzinfo=None) - recent.created_at.replace(tzinfo=None)).total_seconds() > 180:
            db.session.add(Alert(machine_id=machine.id, type=kind, reading=value, severity=level))
    return reading


def seed():
    if Machine.query.count(): return
    machines = [Machine(id="CNC-01", name="CNC Milling Center", type="CNC Mill", location="Line A · Bay 04", expected_rpm=1500),
                Machine(id="PMP-02", name="Hydraulic Pump", type="Centrifugal Pump", location="Line B · Bay 02", expected_rpm=1800),
                Machine(id="MTR-03", name="Conveyor Motor", type="Electric Motor", location="Line C · Bay 01", expected_rpm=1450)]
    db.session.add_all(machines); db.session.commit()
    for m, vals in zip(machines, [(68.4, 2.1, 1482), (77.2, 3.8, 1760), (59.7, 1.4, 1448)]): record_reading(m, *vals)
    db.session.commit()


@app.get("/api/health")
def healthcheck(): return jsonify({"status": "ok", "model": MODEL_METHOD, "database": "connected"})


@app.get("/api/dashboard")
def dashboard():
    machines = [serialize_machine(m) for m in Machine.query.order_by(Machine.id).all()]
    alerts = Alert.query.order_by(desc(Alert.created_at)).limit(8).all()
    return jsonify({"machines": machines, "counts": {"total": len(machines), "active": sum(1 for m in machines if m["status"] == "Normal"),
        "warning": sum(1 for m in machines if m["status"] == "Warning"), "critical": sum(1 for m in machines if m["status"] == "Critical")},
        "alerts": [alert_json(a) for a in alerts], "model": MODEL_METHOD})


def alert_json(a):
    return {"id": a.id, "machine_id": a.machine_id, "type": a.type, "reading": a.reading, "severity": a.severity,
            "status": a.status, "created_at": a.created_at.isoformat()}


@app.get("/api/machines")
def list_machines(): return jsonify([serialize_machine(m) for m in Machine.query.order_by(Machine.id).all()])


@app.post("/api/machines")
def add_machine():
    data = request.get_json(silent=True) or {}
    if not data.get("id") or not data.get("name"): return jsonify({"error": "id and name are required"}), 400
    if Machine.query.get(data["id"]): return jsonify({"error": "Machine ID already exists"}), 409
    machine = Machine(id=data["id"].strip().upper(), name=data["name"].strip(), type=data.get("type", "Industrial machine"),
                      location=data.get("location", "Plant floor"), expected_rpm=float(data.get("expected_rpm", 1500)))
    db.session.add(machine); db.session.commit()
    return jsonify(serialize_machine(machine)), 201


@app.get("/api/machines/<machine_id>")
def get_machine(machine_id):
    machine = db.session.get(Machine, machine_id)
    return (jsonify(serialize_machine(machine)), 200) if machine else (jsonify({"error": "Machine not found"}), 404)


@app.get("/api/machines/<machine_id>/history")
def history(machine_id):
    limit = min(max(request.args.get("limit", 100, type=int), 1), 1000)
    rows = Reading.query.filter_by(machine_id=machine_id).order_by(desc(Reading.created_at)).limit(limit).all()[::-1]
    return jsonify([{"temperature": r.temperature, "vibration": r.vibration, "rpm": r.rpm, "health": r.health,
        "failure_risk": r.failure_risk, "source": r.source, "created_at": r.created_at.isoformat()} for r in rows])


@app.post("/api/readings")
def ingest():
    data = request.get_json(silent=True) or {}
    machine = db.session.get(Machine, data.get("machine_id"))
    if not machine: return jsonify({"error": "Unknown machine_id"}), 404
    try:
        temp, vibration, rpm = (float(data[k]) for k in ("temperature", "vibration", "rpm"))
        if not all(map(lambda x: x == x and abs(x) < 1e6, (temp, vibration, rpm))): raise ValueError()
    except (KeyError, TypeError, ValueError): return jsonify({"error": "temperature, vibration, and rpm must be finite numbers"}), 400
    reading = record_reading(machine, temp, vibration, rpm, "hardware" if data.get("source") == "hardware" else "simulation")
    db.session.commit()
    return jsonify({"id": reading.id, "health": reading.health, "failure_risk": reading.failure_risk, "status": status_for(reading)}), 201


@app.get("/api/alerts")
def alerts(): return jsonify([alert_json(a) for a in Alert.query.order_by(desc(Alert.created_at)).limit(200).all()])


@app.patch("/api/alerts/<int:alert_id>")
def update_alert(alert_id):
    a = db.session.get(Alert, alert_id)
    if not a: return jsonify({"error": "Alert not found"}), 404
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in ("Open", "Acknowledged", "Resolved"): return jsonify({"error": "Invalid status"}), 400
    a.status = status; db.session.commit(); return jsonify(alert_json(a))


@app.get("/api/predictions/<machine_id>")
def predictions(machine_id):
    rows = Prediction.query.filter_by(machine_id=machine_id).order_by(desc(Prediction.created_at)).limit(100).all()[::-1]
    return jsonify([{"failure_risk": r.failure_risk, "health": r.health, "method": r.method, "created_at": r.created_at.isoformat()} for r in rows])


@app.post("/api/maintenance")
def maintenance():
    data = request.get_json(silent=True) or {}
    if not db.session.get(Machine, data.get("machine_id")) or not data.get("description"):
        return jsonify({"error": "Known machine_id and description are required"}), 400
    item = Maintenance(machine_id=data["machine_id"], description=data["description"], performed_by=data.get("performed_by", "Unassigned"))
    db.session.add(item); db.session.commit()
    return jsonify({"id": item.id, "machine_id": item.machine_id, "description": item.description, "performed_by": item.performed_by, "created_at": item.created_at.isoformat()}), 201


@app.get("/api/maintenance")
def maintenance_history():
    query = Maintenance.query
    machine_id = request.args.get("machine_id")
    if machine_id: query = query.filter_by(machine_id=machine_id)
    rows = query.order_by(desc(Maintenance.created_at)).limit(200).all()
    return jsonify([{"id": row.id, "machine_id": row.machine_id, "description": row.description,
        "performed_by": row.performed_by, "created_at": row.created_at.isoformat()} for row in rows])


@app.get("/api/machines/<machine_id>/report")
def report(machine_id):
    machine = db.session.get(Machine, machine_id)
    if not machine: return jsonify({"error": "Machine not found"}), 404
    rows = Reading.query.filter_by(machine_id=machine_id).order_by(Reading.created_at).all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["timestamp", "machine_id", "temperature_c", "vibration_mm_s", "rpm", "health", "failure_risk_pct", "source"])
    for r in rows: writer.writerow([r.created_at.isoformat(), r.machine_id, r.temperature, r.vibration, r.rpm, r.health, r.failure_risk, r.source])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={machine_id}-report.csv"})


def simulator():
    while True:
        time.sleep(max(2, int(os.getenv("SIMULATION_INTERVAL", "4"))))
        with app.app_context():
            if os.getenv("SIMULATION_ENABLED", "true").lower() != "true": continue
            try:
                for machine in Machine.query.all():
                    prior = Reading.query.filter_by(machine_id=machine.id).order_by(desc(Reading.created_at)).first()
                    t = prior.temperature if prior else 65; v = prior.vibration if prior else 2; rpm = prior.rpm if prior else machine.expected_rpm
                    # Small bounded movement keeps simulated readings plausible and reproducible in range.
                    t = max(35, min(95, t + random.uniform(-1.0, 1.3))); v = max(.3, min(7, v + random.uniform(-.18, .22)))
                    rpm = max(machine.expected_rpm * .65, min(machine.expected_rpm * 1.25, rpm + random.uniform(-24, 20)))
                    record_reading(machine, t, v, rpm, "simulation")
                db.session.commit()
            except Exception:
                db.session.rollback(); app.logger.exception("Simulation tick failed")


def mqtt_listener():
    try:
        import paho.mqtt.client as mqtt
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        def on_connect(client, userdata, flags, reason_code, properties): client.subscribe(os.getenv("MQTT_TOPIC", "machines/+/telemetry"))
        def on_message(client, userdata, message):
            with app.app_context():
                try:
                    payload = json.loads(message.payload.decode()); payload["source"] = "hardware"
                    # Reuse API validation and persistence directly.
                    m = db.session.get(Machine, payload.get("machine_id"))
                    if m: record_reading(m, payload["temperature"], payload["vibration"], payload["rpm"], "hardware"); db.session.commit()
                except Exception: db.session.rollback(); app.logger.exception("Invalid MQTT telemetry")
        client.on_connect = on_connect; client.on_message = on_message
        client.connect(os.getenv("MQTT_BROKER", "localhost"), int(os.getenv("MQTT_PORT", "1883")), 60); client.loop_forever()
    except Exception: app.logger.exception("MQTT connection failed")


with app.app_context():
    db.create_all(); seed()

if os.getenv("SIMULATION_ENABLED", "true").lower() == "true":
    threading.Thread(target=simulator, daemon=True).start()
if os.getenv("MQTT_ENABLED", "false").lower() == "true":
    threading.Thread(target=mqtt_listener, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", use_reloader=False)
