# ESP32 / MQTT

Publish JSON telemetry to `machines/<machine-id>/telemetry` (or the configured wildcard topic):

```json
{"machine_id":"CNC-01","temperature":63.2,"vibration":2.1,"rpm":1480}
```

Enable the MQTT listener in `backend/.env`. Values from MQTT are stored with `source=hardware`. For a physical prototype, use sensor-specific calibration, safe electrical isolation, and bounded publish intervals.
