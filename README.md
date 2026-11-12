# Digital Twin – Smart Machine Monitoring

A locally runnable industrial monitoring demo with a React dashboard, Flask REST API, persistence, deterministic predictive maintenance, and simulated or MQTT sensor input. Simulation is clearly labeled throughout; real ESP32 readings enter through the MQTT topic documented below.

## Requirements

- Python 3.10+
- Node.js 18+
- Optional: MySQL 8 and an MQTT broker (Mosquitto, for example)

## Run on Windows

1. In a terminal, run `cd backend`, create a virtual environment (`py -m venv .venv`), activate it (`.venv\Scripts\Activate.ps1`) and install dependencies (`pip install -r requirements.txt`).
2. Copy `.env.example` to `.env`. The default uses local SQLite so the app starts without extra services. Set `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/digital_twin` to use MySQL.
3. Start the API with `python app.py`.
4. In another terminal, run `cd frontend`, `npm install`, then `npm run dev`. Open the URL printed by Vite.

The API seeds three sample machines and generates simulation readings automatically. Start with a trained model using `python ../ml_model/train.py`; otherwise the API uses the clearly identified deterministic rule-based demo fallback. Set `MODEL_PATH=../ml_model/model.joblib` in `backend/.env` to load a trained model.

## MQTT / ESP32

Install and configure a broker, set `MQTT_ENABLED=true`, `MQTT_BROKER=localhost`, and optionally `MQTT_TOPIC=machines/+/telemetry` in `backend/.env`. Publish JSON such as `{"machine_id":"CNC-01","temperature":63.2,"vibration":2.1,"rpm":1480}`. Sensor values received this way are marked **Hardware**. Disable simulation with `SIMULATION_ENABLED=false` when using hardware only.

## API

- `GET /api/health`, `GET /api/dashboard`
- `GET|POST /api/machines`, `GET /api/machines/<id>`
- `GET /api/machines/<id>/history?limit=100`
- `POST /api/readings` (machine_id, temperature, vibration, rpm; source optional)
- `GET /api/alerts`, `PATCH /api/alerts/<id>`
- `GET /api/predictions/<machine_id>`
- `POST /api/maintenance` (machine_id, description, performed_by)
- `GET /api/machines/<id>/report`

The schema is in `database/schema.sql`. This demo has no user authentication; do not expose it to an untrusted network without adding authentication and deployment security.
