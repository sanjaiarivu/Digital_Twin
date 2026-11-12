# Architecture

```text
ESP32 + sensors --MQTT--> Flask ingestion --> SQL database
                              |                   |
React dashboard <--REST-------+-- model risk -----+
                              +-- simulator (optional)
```

The API serves the overview, machine detail/history, alert management, report export, and maintenance record endpoints. Simulation runs in a background thread and can be disabled independently from MQTT input.
