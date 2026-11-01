# LogiEdge — Intelligent Edge AI Platform for Cold-Chain Logistics

LogiEdge is an edge-AI prototype for monitoring refrigerated trucks using temperature, vibration, and door sensors.

The current development setup runs on Linux with:

- Python virtual environment (`.venv`)
- Python 3.12+
- MQTT using Mosquitto
- Paho MQTT Python client
- NumPy
- Sensor simulator
- MQTT monitoring utility

---

## 1. Project Structure

The relevant project structure is:

```text
logibridge/
├── .venv/
├── data_pipeline/
│   └── simulator.py
├── monitor/
│   └── mqtt_monitor.py
├── preprocessing/
│   └── ...
├── requirements.txt
└── README.md
```

> The `.venv` directory should not be committed to Git.

---

# 2. Prerequisites

The following are required:

- Linux environment
- Python 3.11+
- `python3`
- `pip`
- Mosquitto MQTT broker
- Git

For the current development environment, Python 3.12 is being used.

Check Python:

```bash
python3 --version
```

Example:

```text
Python 3.12.9
```

Check Git:

```bash
git --version
```

---

# 3. Clone the Repository

If the repository has not already been cloned:

```bash
git clone https://github.com/elayarajadhanapal/logibridge.git
cd logibridge
```

If the repository is already available locally:

```bash
cd ~/workspace/mledge/logibridge
```

---

# 4. Create the Python Virtual Environment

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

After activation, the shell should show something similar to:

```text
(.venv) user@machine:~/workspace/mledge/logibridge$
```

Verify that Python is coming from the virtual environment:

```bash
which python
```

Expected:

```text
/home/<user>/workspace/mledge/logibridge/.venv/bin/python
```

Also verify:

```bash
which python3
```

---

# 5. Upgrade pip

With the virtual environment activated:

```bash
python -m pip install --upgrade pip
```

Check:

```bash
python -m pip --version
```

---

# 6. Install Python Dependencies

The project dependencies are maintained in:

```text
requirements.txt
```

Install them with:

```bash
python -m pip install -r requirements.txt
```

Current dependencies include:

```text
paho-mqtt
numpy
pytest
```

Verify the important packages:

```bash
python -c "import numpy; print('NumPy:', numpy.__version__)"
```

```bash
python -c "import paho.mqtt.client as mqtt; print('Paho MQTT: OK')"
```

> Mosquitto is an operating-system service and is **not** installed through `requirements.txt`.

---

# 7. Install Mosquitto

Mosquitto is the local MQTT broker used by LogiEdge.

On Rocky Linux:

```bash
sudo dnf install mosquitto
```

Check the installed version:

```bash
mosquitto -h
```

Or:

```bash
mosquitto -v
```

---

# 8. Start Mosquitto

Start the MQTT broker:

```bash
sudo systemctl start mosquitto
```

Check its status:

```bash
sudo systemctl status mosquitto
```

The expected state is:

```text
Active: active (running)
```

To start Mosquitto automatically when the machine boots:

```bash
sudo systemctl enable mosquitto
```

If Mosquitto is already running, there is no need to start it again.

---

# 9. Verify MQTT

Before running the simulator, verify that MQTT communication works.

Open **Terminal 1** and subscribe:

```bash
mosquitto_sub -h localhost -t 'test/logibridge' -v
```

Open **Terminal 2** and publish:

```bash
mosquitto_pub \
    -h localhost \
    -t 'test/logibridge' \
    -m 'hello-logibridge'
```

Terminal 1 should display:

```text
test/logibridge hello-logibridge
```

This confirms that the local MQTT broker is working.

---

# 10. Activate the Python Environment

Every time a new terminal is opened, activate the environment:

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate
```

Verify:

```bash
which python
```

It should point to:

```text
.../logibridge/.venv/bin/python
```

---

# 11. Start the LogiEdge Sensor Simulator

The simulator publishes raw sensor data to the local MQTT broker.

The simulator supports:

```text
none
temp_drift
vibration
combined
```

The default MQTT broker is:

```text
localhost:1883
```

The default truck ID is:

```text
FB-042
```

---

## 11.1 Normal Case

Run:

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly none \
    --duration 10
```

This simulates normal operation.

Expected sensor characteristics:

```text
Temperature ≈ 4.0°C
Vibration   ≈ 0.45g
```

---

## 11.2 Temperature Drift

Run:

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly temp_drift \
    --duration 30
```

The temperature gradually increases over time.

The simulator applies:

```text
+0.08°C per reading
```

in the temperature-drift scenario.

---

## 11.3 Vibration Anomaly

Run:

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly vibration \
    --duration 10
```

The vibration distribution changes to approximately:

```text
Mean ≈ 1.2g
```

The vibration payload contains:

```text
500 samples/second
3 axes
```

Therefore each one-second vibration message contains:

```text
500 × 3 = 1,500 values
```

---

## 11.4 Combined Anomaly

Run:

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly combined \
    --duration 30
```

This simulates both:

- Temperature drift
- Vibration anomaly

---

# 12. Monitor MQTT Sensor Data

The raw vibration payload is intentionally large because the simulator generates 500 Hz × 3-axis data.

Instead of displaying all 1,500 values, use the MQTT monitor.

Open another terminal:

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate
```

Start the monitor:

```bash
python monitor/mqtt_monitor.py
```

You should see:

```text
Connecting to localhost:1883...
Connected to MQTT broker: localhost:1883
Subscribed to: logibridge/trucks/FB-042/sensors/#
```

---

# 13. Run Simulator and Monitor Together

The recommended development setup uses two terminals.

### Terminal 1 — MQTT Monitor

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python monitor/mqtt_monitor.py
```

### Terminal 2 — Simulator

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly none \
    --duration 10
```

The monitor displays a summary instead of printing the complete vibration payload.

Example:

```text
Temperature
-----------
Truck       : FB-042
Temperature : 3.872 °C
Setpoint    : 4.0 °C

Vibration
---------
Truck       : FB-042
Sample rate : 500 Hz
Axes        : x, y, z
Samples     : 500
Shape       : (500, 3)
Duration    : 1 sec
Mean        : 0.450 g
Min         : 0.261 g
Max         : 0.639 g
```

---

# 14. MQTT Topic Structure

The simulator publishes data under the following topic hierarchy:

```text
logibridge/
└── trucks/
    └── FB-042/
        └── sensors/
            ├── temperature
            ├── vibration
            └── door
```

For example:

```text
logibridge/trucks/FB-042/sensors/temperature
```

```text
logibridge/trucks/FB-042/sensors/vibration
```

```text
logibridge/trucks/FB-042/sensors/door
```

The truck ID can be changed using:

```bash
--truck-id
```

For example:

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-001 \
    --anomaly none \
    --duration 10
```

---

# 15. Quick Start

For a normal development session, the following is sufficient.

### Terminal 1 — Start Mosquitto

Check:

```bash
sudo systemctl status mosquitto
```

If it is not running:

```bash
sudo systemctl start mosquitto
```

### Terminal 2 — Start MQTT Monitor

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python monitor/mqtt_monitor.py
```

### Terminal 3 — Run Simulator

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly none \
    --duration 10
```

---

# 16. Test All Four Scenarios

### Normal

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly none \
    --duration 10
```

### Temperature Drift

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly temp_drift \
    --duration 30
```

### Vibration

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly vibration \
    --duration 10
```

### Combined

```bash
python simulator/sensor_simulator.py \
    --truck-id FB-042 \
    --anomaly combined \
    --duration 30
```

---

# 17. Troubleshooting

## Python command not found

Check:

```bash
python3 --version
```

Then recreate the environment if necessary:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## Paho MQTT module not found

Make sure the virtual environment is active:

```bash
source .venv/bin/activate
```

Then:

```bash
python -m pip install -r requirements.txt
```

---

## Mosquitto is not running

Check:

```bash
sudo systemctl status mosquitto
```

Start it:

```bash
sudo systemctl start mosquitto
```

---

## MQTT connection refused

Check that Mosquitto is listening:

```bash
ss -lntp | grep 1883
```

Then:

```bash
sudo systemctl restart mosquitto
```

---

## Simulator appears to work but monitor receives nothing

Make sure:

1. Mosquitto is running.
2. Monitor is connected to `localhost:1883`.
3. Simulator uses the same broker.
4. Both terminals are using the correct project directory.

The simulator default is:

```text
Broker: localhost
Port:   1883
```

---

# 18. Deactivating the Virtual Environment

When finished:

```bash
deactivate
```

The environment can be activated again with:

```bash
source .venv/bin/activate
```

---

# 19. Development Flow

The current LogiEdge development flow is:

```text
Sensor Simulator
       │
       ▼
   MQTT Broker
   (Mosquitto)
       │
       ▼
MQTT Monitor
(debugging only)
       │
       ▼
Preprocessing
       │
       ├── Temperature moving average
       ├── Vibration moving average
       └── Sliding window
       │
       ▼
Six Features
       │
       ▼
Normalization
       │
       ▼
ML Inference
       │
       ▼
Normal / Warning / Critical
       │
       ▼
Local Alert Log
       │
       ▼
Cloud Synchronization
```

The MQTT monitor is only a development/debugging utility. It is not part of the production inference path.

---

# 20. Important Notes

### Virtual environment

Do not commit `.venv/` to Git.

Recommended `.gitignore` entry:

```text
.venv/
__pycache__/
*.pyc
```

### Mosquitto

Mosquitto is a system service and should not be added to `requirements.txt`.

### Raw vibration data

The large vibration MQTT payload is intentional.

The simulator produces:

```text
500 Hz × 3 axes
```

and therefore sends:

```text
500 × 3 = 1,500 values
```

for every one-second vibration batch.

The monitor summarizes this data for easier debugging without changing the raw data received by the preprocessing pipeline.

---

## Current Status

Implemented:

- Python virtual environment
- Python dependency management
- Mosquitto MQTT broker
- MQTT connectivity test
- Raw temperature simulator
- Raw 3-axis vibration simulator
- Door event simulator
- Four anomaly modes
- MQTT monitor

Next development step:

```text
MQTT → Preprocessing → 30-second sliding window → 6 features
```

The preprocessing stage will consume the raw MQTT data and produce the six features required by the LogiEdge ML pipeline.