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

# Project Structure

```text
logibridge/
│
├── dashboard/
│   ├── __init__.py
│   ├── dashboard_api.py
│   ├── logiedge_dashboard.html
│   └── README.md
│
├── data_pipeline/
│   ├── models/
│   │   ├── M1/
│   │   │   ├── model.keras
│   │   │   └── model.tflite
│   │   ├── M2/
│   │   │   └── model.tflite
│   │   └── M3/
│   │       ├── model.tflite
│   │       ├── model_before_90pct.tflite
│   │       └── model_before_separate_test.tflite
│   │
│   ├── benchmark_models.py
│   ├── classifier.joblib
│   ├── data_pipeline_dashboard_iface.py
│   ├── dataset.npz
│   ├── dataset_check.py
│   ├── dataset_generator.py
│   ├── preprocessing.py
│   ├── reference_dist.json
│   ├── simulator.py
│   ├── train_classifier.py
│   ├── training_keras_m1.py
│   ├── training_keras_m2.py
│   ├── training_keras_m3.py
│   └── training_stats.npy
│
├── deployment/
│   ├── dataset.npz
│   └── mosquitto.conf
│
├── docs/
│   ├── DASHBOARD_IFACE.md
│   ├── INTERFACES.md
│   └── SETUP.md
│
├── edge_runtime/
│   └── edge_runtime_dashboard_iface.py
│
├── hardware/
│   └── hardware_justification.md
│
├── inference/
│   ├── export_m1_tflite.py
│   ├── inference_dashboard_iface.py
│   ├── inference_service.py
│   ├── psi_monitor.py
│   └── verify_m1_tflite.py
│
├── monitoring/
│   ├── monitoring_dashboard_iface.py
│   └── mqtt_monitor.py
│
├── optimisation/
│   └── optimisation_dashboard_iface.py
│
├── scenario_architecture/
│   ├── constraint_analysis.md
│   └── system_architecture.png
│
├── .gitignore
├── Dockerfile
├── LICENSE
├── logibridge_deploy.yml
├── model.tflite
├── README.md
├── requirements.txt
├── requirements-docker.txt
├── run.bat
├── run.py
└── Task E3 initial answer.docx
```

### Important generated and deployment artifacts

| File | Purpose |
|---|---|
| `data_pipeline/dataset.npz` | Generated training dataset |
| `data_pipeline/classifier.joblib` | Trained classifier artifact |
| `data_pipeline/training_stats.npy` | Feature normalization statistics |
| `data_pipeline/models/M1/model.tflite` | M1 TFLite model |
| `data_pipeline/models/M2/model.tflite` | M2 TFLite model |
| `data_pipeline/models/M3/model.tflite` | M3 TFLite model |
| `data_pipeline/reference_dist.json` | PSI reference distribution |
| `model.tflite` | Root-level model used by the current Dockerfile and Ansible deployment |
| `logibridge_deploy.yml` | Ansible deployment playbook |
| `requirements-docker.txt` | Docker image dependencies |
| `deployment/mosquitto.conf` | MQTT broker configuration |
logibridge/
├── .venv/
├── data_pipeline/
│   ├── simulator.py
│   ├── preprocessing.py
│   ├── training_stats.npy
│   └── data_pipeline_dashboard_iface.py
├── dashboard/
│   └── logiedge_dashboard.html
├── monitoring/
│   └── mqtt_monitor.py
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

The simulator publishes sensor data to the local MQTT broker through
`data_pipeline/data_pipeline_dashboard_iface.py` (topics and payloads in `docs/INTERFACES.md`),
so the dashboard and `preprocessing.py` receive it directly.

Options: `--anomaly`, `--truck-id`, `--broker-host`, `--broker-port`,
`--duration` (seconds, `0` = until Ctrl+C, the default) and `--seed`.
The anomaly mode can also be switched at runtime from the dashboard.

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
MH15-RF-0427
```

---

## 11.1 Normal Case

Run:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
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
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
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
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly vibration \
    --duration 10
```

The vibration distribution changes to approximately:

```text
Mean ≈ 1.2g
```

Vibration is published as one compressor RMS value every 2 seconds (0.5 Hz).
The raw 500 Hz × 3-axis signal is reduced to RMS on the sensor node and is not sent over MQTT.

---

## 11.4 Combined Anomaly

Run:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly combined \
    --duration 30
```

This simulates both:

- Temperature drift
- Vibration anomaly

---

# 12. Monitor MQTT Sensor Data

Use the MQTT monitor to print the sensor messages in a readable form.

Open another terminal:

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate
```

Start the monitor:

```bash
python monitoring/mqtt_monitor.py
```

You should see:

```text
Connecting to localhost:1883...
Connected to MQTT broker: localhost:1883
Subscribed to: logibridge/trucks/MH15-RF-0427/sensors/#
```

---

# 13. Run Simulator and Monitor Together

The recommended development setup uses two terminals.

### Terminal 1 — MQTT Monitor

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python monitoring/mqtt_monitor.py
```

### Terminal 2 — Simulator

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 10
```

The monitor prints each sensor message as a short summary.

Example:

```text
Temperature
-----------
Truck       : MH15-RF-0427
Temperature : 3.872 °C

Vibration
---------
Truck       : MH15-RF-0427
RMS         : 0.452 g
```

---

# 14. MQTT Topic Structure

The simulator publishes data under the following topic hierarchy:

```text
logibridge/
└── trucks/
    └── MH15-RF-0427/
        └── sensors/
            ├── temperature
            ├── vibration
            └── door
```

For example:

```text
logibridge/trucks/MH15-RF-0427/sensors/temperature
```

```text
logibridge/trucks/MH15-RF-0427/sensors/vibration
```

```text
logibridge/trucks/MH15-RF-0427/sensors/door
```

The truck ID can be changed using:

```bash
--truck-id
```

For example:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0001 \
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

python monitoring/mqtt_monitor.py
```

### Terminal 3 — Run Simulator

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 10
```

---

# 16. Test All Four Scenarios

### Normal

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 10
```

### Temperature Drift

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly temp_drift \
    --duration 30
```

### Vibration

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly vibration \
    --duration 10
```

### Combined

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
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

### Vibration data

Vibration is published as one RMS value every 2 seconds (Task C1: `vibration_rms` at 0.5 Hz).
The raw 500 Hz × 3-axis signal stays on the sensor node.

---

## Current Status

Implemented:

- Python virtual environment
- Python dependency management
- Mosquitto MQTT broker
- MQTT connectivity test
- Temperature simulator (1 Hz)
- Vibration RMS simulator (0.5 Hz)
- Door OPEN / CLOSE event simulator
- Four anomaly modes, switchable at runtime from the dashboard
- MQTT monitor
- Preprocessing: 5-sample moving average, 30 s window / 10 s step, 6 features,
  normalisation with `training_stats.npy`, published on `features`

Preprocessing modes:

```bash
python data_pipeline/preprocessing.py                     # live: normalise and publish features (default)
python data_pipeline/preprocessing.py --stats-shift 3     # live, stats mean shifted by 3 sigma (C2 experiment)
python data_pipeline/preprocessing.py --mode normal       # 10 min of Normal data -> training_stats.npy
python data_pipeline/preprocessing.py --mode temp_drift   # 10 min -> dataset_temp_drift.npy
```

`python run.py` starts the broker, preprocessing, the simulator and the dashboard together.

# 21. Machine Learning Inference Pipeline

The LogiEdge inference pipeline processes sensor data, extracts features, normalizes them using training statistics, and publishes the model predictions over MQTT.

### 21.1 End-to-end inference flow

```text
Temperature / Vibration / Door Sensors
                 |
                 v
          MQTT Broker
            Mosquitto
                 |
                 v
          Preprocessing
                 |
                 v
       Moving Average Filtering
                 |
                 v
       Sliding Window Processing
          30 seconds / 10 seconds
                 |
                 v
          Feature Extraction
                 |
                 v
       Six-dimensional feature vector
                 |
                 v
       Feature Normalization
        training_stats.npy
                 |
                 v
          MQTT Features Topic
                 |
                 v
          Inference Service
                 |
                 v
          TFLite Model
                 |
                 v
       Normal / Warning / Critical
                 |
                 v
        MQTT Inference Output
```

### 21.2 Feature extraction

The preprocessing component applies a five-sample moving average and processes sensor readings using a 30-second sliding window with a 10-second step.

The six extracted features are:

| Feature | Description |
|---|---|
| `temp_mean` | Mean temperature within the window |
| `temp_std` | Temperature standard deviation |
| `temp_roc` | Temperature rate of change |
| `vib_rms` | Vibration RMS feature |
| `vib_peak` | Vibration peak feature |
| `vib_kurt` | Vibration kurtosis feature |

The extracted features are normalized using the training statistics stored in:

```text
data_pipeline/training_stats.npy
```

The normalized feature vectors are published to MQTT for inference.

### 21.3 Run preprocessing

Open a separate terminal:

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python data_pipeline/preprocessing.py
```

The default mode runs live preprocessing.

The following modes are also available:

```bash
# Live preprocessing
python data_pipeline/preprocessing.py

# C2 experiment: shift the statistics mean by 3 sigma
python data_pipeline/preprocessing.py --stats-shift 3

# Collect normal data for training statistics
python data_pipeline/preprocessing.py --mode normal

# Collect temperature-drift data
python data_pipeline/preprocessing.py --mode temp_drift
```

The normal and temperature-drift collection modes run for approximately 10 minutes according to the implemented preprocessing configuration.

Do not run the training-statistics collection mode when you only want to execute the already configured live inference pipeline.

### 21.4 Start the inference service

The inference service loads the selected TFLite model and subscribes to the preprocessed feature stream.

For the local development environment, use the M1 model.

Set the required environment variables:

```bash
export TRUCK_ID="MH15-RF-0427"
export MODEL_NAME="M1"
export MODEL_PATH="$PWD/data_pipeline/models/M1/model.tflite"
export MODEL_DIR="$PWD/data_pipeline/models"
export TRAINING_STATS_PATH="$PWD/data_pipeline/training_stats.npy"
```

Start the service:

```bash
python inference/inference_service.py
```

Keep this terminal running.

The service requires the MQTT broker and preprocessing component to be active.

### 21.5 Verify inference output

The inference service publishes its output under:

```text
logibridge/trucks/MH15-RF-0427/inference
```

To inspect the messages directly:

```bash
mosquitto_sub \
    -h localhost \
    -p 1883 \
    -t "logibridge/trucks/MH15-RF-0427/inference" \
    -v
```

The inference payload contains the probability output used by the PSI monitoring component.

---

# 22. E1 — PSI-Based Drift Monitoring

E1 implements Population Stability Index (PSI) monitoring to identify changes in the model's inference confidence distribution.

The implementation uses a reference distribution collected from clean Normal-class inference windows and compares it against a rolling distribution of recent inference confidence scores.

### 22.1 PSI monitoring configuration

| Parameter | Configuration |
|---|---|
| Reference samples | 300 |
| Reference scenario | Normal / clean data |
| Confidence score | Maximum predicted class probability |
| Confidence bins | 4 |
| Monitoring window | Last 100 inferences |
| Monitoring interval | 60 seconds |
| Drift alert threshold | PSI > 0.25 |
| Recovery threshold | PSI < 0.10 |
| Reference file | `data_pipeline/reference_dist.json` |

The confidence bins are:

```text
[0.00, 0.25)
[0.25, 0.50)
[0.50, 0.75)
[0.75, 1.00]
```

### 22.2 How the reference distribution is generated

The reference distribution must be generated using clean Normal sensor data.

First, ensure that the MQTT broker, preprocessing component, simulator, and inference service are running.

Run the simulator in Normal mode:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 3600
```

In another terminal, execute:

```bash
python inference/psi_monitor.py --mode reference
```

The collector waits until it receives 300 inference confidence values.

Expected output:

```text
Connected to MQTT: localhost:1883
Collecting 300 clean Normal inference confidences...
Keep simulator running with --anomaly none.
Subscribed: logibridge/trucks/MH15-RF-0427/inference
Collected: 300/300
Reference distribution saved: data_pipeline/reference_dist.json
```

The generated file is:

```text
data_pipeline/reference_dist.json
```

This file contains the reference sample count, bin edges, bin counts, bin proportions, and collection timestamp.

**Important:** Generate the reference distribution using Normal data, not an anomaly scenario. Keep the generated file for subsequent monitoring and deployment.

### 22.3 Start live PSI monitoring

Once `reference_dist.json` exists, start the monitor:

```bash
python inference/psi_monitor.py --mode monitor
```

The monitor:

1. Subscribes to the inference MQTT topic.
2. Receives predicted probability values.
3. Extracts the maximum confidence score.
4. Maintains a rolling buffer of the latest 100 inference values.
5. Calculates PSI every 60 seconds.
6. Prints the current PSI value.
7. Raises an alert when PSI exceeds 0.25.
8. Prints the recovery message when PSI falls below 0.10.

Example:

```text
[PSI] 0.056
[LOGIBRIDGE RECOVERY] PSI=0.056
```

### 22.4 Test drift detection using combined anomaly

Keep the preprocessing service, inference service, and PSI monitor running.

Stop only the simulator using `Ctrl+C`.

Restart it in combined anomaly mode:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly combined \
    --duration 3600
```

The combined scenario introduces temperature drift and vibration anomalies.

The PSI monitor should detect a change in the inference confidence distribution.

Example output:

```text
[PSI] 0.116
[PSI] 0.197
[PSI] 0.299
[LOGIBRIDGE DRIFT ALERT] PSI=0.299
```

The alert format is:

```text
[LOGIBRIDGE DRIFT ALERT] PSI=<value>
```

The alert threshold is strictly greater than 0.25.

### 22.5 Verify recovery

After observing the drift alert, stop the combined-anomaly simulator.

Restart it with clean Normal data:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 3600
```

Continue observing the PSI output.

The recovery condition is:

```text
PSI < 0.10
```

Example:

```text
[PSI] 0.054
[LOGIBRIDGE RECOVERY] PSI=0.054
```

The monitor continues running, allowing the confidence distribution to be observed as it returns towards the reference distribution.

Note: The current implementation can print a recovery message whenever PSI is below 0.10, including during normal baseline operation.

### 22.6 E1 execution checklist

- [ ] MQTT broker is running.
- [ ] Preprocessing is running.
- [ ] Simulator is running in Normal mode.
- [ ] Inference service is receiving features.
- [ ] 300 clean inference values have been collected.
- [ ] `data_pipeline/reference_dist.json` exists.
- [ ] PSI monitor is running.
- [ ] Combined anomaly has been injected.
- [ ] PSI exceeds 0.25 and a drift alert is printed.
- [ ] Normal data has been restored.
- [ ] PSI falls below 0.10.

---

# 23. E1 — Complete Terminal Setup

For reproducing the E1 experiment, keep the required processes running in separate terminals.

All terminals should use the project root:

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate
```

### Terminal 1 — MQTT Broker

Start Mosquitto:

```bash
mosquitto -c deployment/mosquitto.conf -v
```

Keep this terminal running.

If Mosquitto is already running on port 1883, do not start another broker on the same port.

### Terminal 2 — Preprocessing

```bash
python data_pipeline/preprocessing.py
```

This process receives sensor data and publishes normalized feature vectors.

### Terminal 3 — Sensor Simulator

Start clean Normal data:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 3600
```

### Terminal 4 — Inference Service

Set the model configuration:

```bash
export TRUCK_ID="MH15-RF-0427"
export MODEL_NAME="M1"
export MODEL_PATH="$PWD/data_pipeline/models/M1/model.tflite"
export MODEL_DIR="$PWD/data_pipeline/models"
export TRAINING_STATS_PATH="$PWD/data_pipeline/training_stats.npy"
```

Start inference:

```bash
python inference/inference_service.py
```

### Terminal 5 — MQTT Debug Monitor (Optional)

```bash
python monitoring/mqtt_monitor.py
```

This terminal is useful for checking incoming sensor messages.

### Terminal 6 — PSI Monitoring

First, generate the reference distribution:

```bash
python inference/psi_monitor.py --mode reference
```

Wait until 300 samples are collected.

After the reference file is generated, start live monitoring:

```bash
python inference/psi_monitor.py --mode monitor
```

To test the anomaly and recovery scenarios, change only the simulator process in Terminal 3.

**Important execution dependency:** Preprocessing must be running for the inference service to receive the feature messages. Starting the simulator and inference service alone is not sufficient.

---

# 24. E2 — Docker-Based Inference Deployment Using Ansible

This component packages the LogiBridge inference service into a Docker image and deploys it using Ansible.

The deployment uses a local Docker registry to store and retrieve the inference image.

The Ansible playbook automates:
1. Creation of the deployment directory.
2. Copying the TFLite model.
3. Copying the PSI reference distribution.
4. Stopping the existing inference container when deployment files change.
5. Pulling the inference image from the local registry.
6. Starting the inference container.
7. Waiting 15 seconds and verifying that the container is running.

## 24.1 Deployment architecture

```text
                LogiBridge Repository
                         |
                         v
                  Dockerfile
                         |
                         v
               Build Inference Image
                         |
                         v
                Local Docker Registry
                   localhost:5000
                         |
                         v
                 Ansible Playbook
                         |
              +----------+----------+
              |                     |
              v                     v
       Copy model.tflite     Copy reference_dist.json
              |                     |
              v                     v
      /opt/logibridge/       /opt/logibridge/
              |                     |
              +----------+----------+
                         |
                         v
               Pull Docker Image
                         |
                         v
               Start Inference Container
                         |
                         v
                Verify Container Status
```

The model is mounted from the host into the container. The reference distribution is copied to the deployment directory on the host; the current playbook does not mount it into the container.

## 24.2 Prerequisites

The tested deployment environment uses:

- Windows with WSL2.
- Ubuntu running under WSL2.
- Docker Desktop with WSL2 integration enabled.
- Ansible.
- Python Docker SDK.
- `community.docker` Ansible collection.
- Local Mosquitto broker.

Docker Desktop must be running before executing Docker commands from WSL.

Verify:

```bash
docker --version
docker info
docker ps
```

If these commands cannot communicate with the Docker daemon, resolve Docker Desktop and WSL integration before proceeding.

## 24.3 Install Ansible and Docker dependencies

From Ubuntu or Ubuntu WSL:

```bash
sudo apt update

sudo apt install -y ansible python3-docker
```

Install the Ansible Docker collection:

```bash
ansible-galaxy collection install community.docker
```

Verify Ansible:

```bash
ansible --version
```

Verify the collection:

```bash
ansible-galaxy collection list | grep community.docker
```

Verify the Docker SDK:

```bash
python3 -c "import docker; print('Docker SDK:', docker.__version__)"
```

The tested environment used:

```text
Ansible Core: 2.20.1
community.docker: 5.0.4
Docker SDK: 7.1.0
```

## 24.4 Verify the deployment files

The following files are required by the current Dockerfile and Ansible playbook:

```text
logibridge/
├── Dockerfile
├── requirements-docker.txt
├── model.tflite
├── logibridge_deploy.yml
├── inference/
│   └── inference_service.py
└── data_pipeline/
    ├── training_stats.npy
    ├── reference_dist.json
    └── models/
        └── M1/
            └── model.tflite
```

Check the required files:

```bash
ls -lh Dockerfile
ls -lh requirements-docker.txt
ls -lh model.tflite
ls -lh data_pipeline/training_stats.npy
ls -lh data_pipeline/reference_dist.json
ls -lh logibridge_deploy.yml
```

### Model-file verification

The Dockerfile uses the root-level model:

```text
model.tflite
```

The Ansible playbook also copies this same root-level model to:

```text
/opt/logibridge/model.tflite
```

The repository additionally contains the M1 model at:

```text
data_pipeline/models/M1/model.tflite
```

Verify that the root-level deployment model is the intended M1 model before continuing.

```bash
sha256sum model.tflite data_pipeline/models/M1/model.tflite
```

If the hashes match, the two files are identical.

## 24.5 Build the Docker image

The Dockerfile uses Python 3.11 slim as its base image.

It installs dependencies from:

```text
requirements-docker.txt
```

It copies:
- `inference/`
- `dashboard/`
- `data_pipeline/training_stats.npy`
- Root-level `model.tflite`

The inference service is started using:

```dockerfile
CMD ["python", "inference/inference_service.py"]
```

Build the image from the repository root:

```bash
docker build -t logibridge-inference:m1 -f Dockerfile .
```

Verify:

```bash
docker images
```

Expected image:

```text
logibridge-inference    m1
```

## 24.6 Start the local Docker registry

Pull the registry image:

```bash
docker pull registry:2
```

Start the local registry:

```bash
docker run -d \
    --name logibridge-registry \
    --restart=always \
    -p 5000:5000 \
    registry:2
```

Verify that the registry is running:

```bash
docker ps
```

The registry is available at:

```text
localhost:5000
```

If the registry container already exists, start it instead of creating another:

```bash
docker start logibridge-registry
```

## 24.7 Tag and push the image

Tag the locally built image:

```bash
docker tag \
    logibridge-inference:m1 \
    localhost:5000/logibridge-inference:m1
```

Push it:

```bash
docker push localhost:5000/logibridge-inference:m1
```

Verify the registry repository:

```bash
curl http://localhost:5000/v2/_catalog
```

Expected:

```json
{"repositories":["logibridge-inference"]}
```

The image is now available in the local registry.

## 24.8 Prepare the Ansible deployment directory

The playbook deploys files under:

```text
/opt/logibridge
```

The current playbook does not enable privilege escalation using `become: true`.

Therefore, on a new Linux/WSL machine, prepare the directory before running the playbook:

```bash
sudo mkdir -p /opt/logibridge
sudo chown "$USER":"$USER" /opt/logibridge
```

Verify that the current user can write to it:

```bash
test -w /opt/logibridge && echo "Deployment directory is writable"
```

This step is important because the playbook must copy files into `/opt/logibridge`.

## 24.9 Validate the Ansible playbook

The deployment playbook is:

```text
logibridge_deploy.yml
```

Run the syntax check:

```bash
ansible-playbook -i localhost, logibridge_deploy.yml --syntax-check
```

Expected:

```text
playbook: logibridge_deploy.yml
```

## 24.10 Execute the Ansible deployment

Run the playbook:

```bash
ansible-playbook -i localhost, logibridge_deploy.yml
```

The playbook executes seven tasks.

| Task | Action |
|---|---|
| 1 | Create `/opt/logibridge` |
| 2 | Copy root-level `model.tflite` into the deployment directory |
| 3 | Copy `data_pipeline/reference_dist.json` into the deployment directory |
| 4 | Stop the running container if the copied model or reference distribution changes |
| 5 | Pull `localhost:5000/logibridge-inference:m1` |
| 6 | Start the `logibridge-inference` container |
| 7 | Wait 15 seconds and verify that the container is running |

The container receives the following environment variables:

```text
MODEL_PATH=/app/model.tflite
MODEL_DIR=/app/models
TRAINING_STATS_PATH=/app/training_stats.npy
TRUCK_ID=MH15-RF-0427
MODEL_NAME=M1
LOGIBRIDGE_MQTT_HOST=host.docker.internal
LOGIBRIDGE_MQTT_PORT=1883
```

The model file is mounted into the container using:

```text
/opt/logibridge/model.tflite:/app/model.tflite:ro
```

This is a read-only mount.

The reference distribution is copied to the host deployment directory:

```text
/opt/logibridge/reference_dist.json
```

It is not mounted into the container by the current playbook.

## 24.11 Verify the first deployment

After the playbook completes, inspect the output.

The first successful deployment should create or update the deployment files and start the inference container.

An example successful result is:

```text
PLAY RECAP
localhost : ok=7 changed=3 unreachable=0 failed=0 skipped=0
```

The exact number of changed tasks can vary depending on the state of the machine.

Check the running container:

```bash
docker ps
```

Expected container name:

```text
logibridge-inference
```

Expected image:

```text
localhost:5000/logibridge-inference:m1
```

Check the deployment files:

```bash
ls -lh /opt/logibridge/
```

Expected:

```text
model.tflite
reference_dist.json
```

Inspect container logs:

```bash
docker logs logibridge-inference
```

## 24.12 Verify Ansible idempotency

Ansible should not make unnecessary changes when the deployment inputs remain unchanged.

Execute the same playbook again:

```bash
ansible-playbook -i localhost, logibridge_deploy.yml
```

The second run should report:

```text
PLAY RECAP
localhost : ok=6 changed=0 unreachable=0 failed=0 skipped=1
```

The stop-container task is skipped because neither the model nor the reference distribution changed.

The important result is:

```text
changed=0
```

This verifies idempotent behaviour for an unchanged deployment.

## 24.13 Verify the deployed container

List containers:

```bash
docker ps
```

Inspect the inference container:

```bash
docker inspect logibridge-inference
```

Inspect its logs:

```bash
docker logs logibridge-inference
```

If the container is not running:

```bash
docker ps -a
```

Then inspect its logs to identify the startup error.

## 24.14 E2 execution checklist

- [ ] Docker Desktop or Docker daemon is running.
- [ ] WSL2 Docker integration is enabled, if using Windows.
- [ ] Ansible is installed.
- [ ] Docker SDK is installed.
- [ ] `community.docker` collection is installed.
- [ ] Root-level `model.tflite` is the intended M1 model.
- [ ] `data_pipeline/training_stats.npy` exists.
- [ ] `data_pipeline/reference_dist.json` exists.
- [ ] Docker image builds successfully.
- [ ] Local registry is running.
- [ ] Image has been pushed to the registry.
- [ ] `/opt/logibridge` is writable by the deployment user.
- [ ] Ansible syntax check passes.
- [ ] First deployment succeeds.
- [ ] Container is running.
- [ ] Model and reference files exist in the deployment directory.
- [ ] Second deployment reports `changed=0`.

**Environment limitation:** The tested container uses `host.docker.internal` to communicate with the host MQTT broker. This configuration was tested with Docker Desktop and WSL2 integration. A native Linux Docker installation may require a different MQTT host address.
---

# 25. E3 — OTA Strategy Selection

FreightBridge updates the truck inference model every six weeks.

The OTA strategy evaluation uses the following inputs:

| Parameter | Value |
|---|---:|
| Model format | INT8 TFLite |
| Model size | 280 KB |
| M2M SIM data tariff | ₹0.10 / MB |
| Pilot fleet | 85 trucks |
| Update frequency | Every 6 weeks |

For bandwidth calculations, 1 MB is treated as 1,000 KB.

### 25.1 Full replacement

In full replacement, the updated model is sent to all 85 trucks in one update cycle.

Calculation:

```text
Model size = 280 KB

Fleet size = 85

Total data transfer:
85 × 280 KB = 23,800 KB

                  = 23.8 MB

Bandwidth cost:
23.8 × ₹0.10 = ₹2.38
```

**Total cost per update cycle: ₹2.38**

Advantages:
- Entire fleet receives the update in one rollout.
- Simple deployment process.
- No separate canary validation stage.

Disadvantages:
- A faulty model could affect all 85 trucks simultaneously.
- Limited opportunity to detect model issues before fleet-wide deployment.
- Rural connectivity interruptions can cause deployment failures across multiple trucks.

### 25.2 Canary deployment — 10 trucks first

In canary deployment, the new model is initially sent to 10 trucks. After validation, it is rolled out to the remaining 75 trucks.

Initial canary transfer:

```text
10 × 280 KB = 2,800 KB

             = 2.8 MB

Cost:
2.8 × ₹0.10 = ₹0.28
```

Remaining fleet transfer:

```text
75 × 280 KB = 21,000 KB

              = 21 MB

Cost:
21 × ₹0.10 = ₹2.10
```

Total rollout:

```text
2.8 MB + 21 MB = 23.8 MB

₹0.28 + ₹2.10 = ₹2.38
```

**Total cost per complete update cycle: ₹2.38**

Advantages:
- Limits initial exposure to 10 trucks.
- Allows the updated model to be evaluated before fleet-wide rollout.
- Reduces the risk of a faulty model affecting the entire fleet.
- Supports staged deployment when truck connectivity is intermittent.

Disadvantages:
- Requires an additional rollout stage.
- Complete fleet deployment takes longer than a single full replacement.
- Requires monitoring and validation before proceeding to the remaining trucks.

### 25.3 Shadow mode

In shadow mode, the updated model is transferred to the trucks and runs alongside the existing model. The existing model continues to provide the operational prediction while the candidate model's outputs are evaluated.

Assuming the candidate model is transferred to all 85 trucks:

```text
85 × 280 KB = 23,800 KB

              = 23.8 MB

Cost:
23.8 × ₹0.10 = ₹2.38
```

**Total candidate-model transfer cost per update cycle: ₹2.38**

Advantages:
- Allows the new model's predictions to be compared with the existing model.
- Avoids immediately replacing the operational model.
- Provides an opportunity to assess candidate-model behaviour before activation.

Disadvantages:
- Requires additional edge compute resources to run both models.
- Requires sufficient memory and processing capacity.
- Increases operational complexity.
- The candidate model still needs to be transferred over the truck's network connection.

The calculation covers candidate-model transfer only. It does not include additional compute or operational costs.

### 25.4 Strategy comparison

| Strategy | Initial transfer | Remaining transfer | Total transfer | Total cost |
|---|---:|---:|---:|---:|
| Full replacement | 23.8 MB | 0 MB | 23.8 MB | ₹2.38 |
| Canary: 10 trucks first | 2.8 MB | 21 MB | 23.8 MB | ₹2.38 |
| Shadow mode: all 85 trucks | 23.8 MB | 0 MB | 23.8 MB | ₹2.38 |

All three strategies have the same model-transfer cost when the candidate model is delivered to all 85 trucks once. The difference is in deployment sequence, validation, operational complexity, and risk exposure.

### 25.5 Recommendation: Canary deployment

Canary deployment is recommended for the FreightBridge pilot fleet.

Cold-chain logistics is safety-critical because temperature excursions can compromise perishable goods. A faulty model update could also affect the ability to identify abnormal temperature or vibration conditions.

Deploying the new model to 10 trucks first limits the initial exposure. The model can be observed under real operating conditions before the remaining 75 trucks receive the update.

This staged approach is particularly relevant for rural routes, where mobile network connectivity may be intermittent and update delivery may be delayed.

Full replacement is less suitable because all trucks are exposed to the new model simultaneously, leaving no initial validation stage.

Shadow mode provides a useful way to compare model outputs, but requires additional edge compute capacity and operational complexity. For this pilot, canary deployment provides a more direct balance between safety, staged validation, connectivity constraints, and deployment simplicity.

---

# 26. Complete Project Execution Sequence

This section provides the recommended order for reproducing the complete system on a new machine.

### Step 1 — Clone the repository

```bash
git clone https://github.com/elayarajadhanapal/logibridge.git
cd logibridge
```

### Step 2 — Install system prerequisites

Install:
- Python 3.11 or later (Python 3.12 is the tested host development version).
- pip.
- Git.
- Mosquitto.
- Docker, for E2 deployment.
- Ansible and Docker SDK, for E2 deployment.

For Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git mosquitto mosquitto-clients
```

### Step 3 — Create the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 4 — Start the MQTT broker

```bash
sudo systemctl start mosquitto
sudo systemctl status mosquitto
```

If the machine does not use systemd, start Mosquitto directly:

```bash
mosquitto -c deployment/mosquitto.conf -v
```

Use only one broker instance on port 1883.

### Step 5 — Verify MQTT communication

Terminal 1:

```bash
mosquitto_sub -h localhost -t 'test/logibridge' -v
```

Terminal 2:

```bash
mosquitto_pub \
    -h localhost \
    -t 'test/logibridge' \
    -m 'hello-logibridge'
```

Confirm that the subscriber receives the message.

### Step 6 — Run the sensor simulator

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 3600
```

### Step 7 — Run preprocessing

In another terminal:

```bash
cd ~/workspace/mledge/logibridge
source .venv/bin/activate

python data_pipeline/preprocessing.py
```

### Step 8 — Run the inference service

Set the model environment variables:

```bash
export TRUCK_ID="MH15-RF-0427"
export MODEL_NAME="M1"
export MODEL_PATH="$PWD/data_pipeline/models/M1/model.tflite"
export MODEL_DIR="$PWD/data_pipeline/models"
export TRAINING_STATS_PATH="$PWD/data_pipeline/training_stats.npy"
```

Start:

```bash
python inference/inference_service.py
```

### Step 9 — Generate the E1 reference distribution

```bash
python inference/psi_monitor.py --mode reference
```

Wait until 300 clean inference samples are collected.

Verify:

```bash
ls -lh data_pipeline/reference_dist.json
```

### Step 10 — Run E1 drift monitoring

```bash
python inference/psi_monitor.py --mode monitor
```

Inject the combined anomaly by restarting only the simulator:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly combined \
    --duration 3600
```

Verify that the PSI alert is printed.

Restore Normal data:

```bash
python data_pipeline/simulator.py \
    --truck-id MH15-RF-0427 \
    --anomaly none \
    --duration 3600
```

Verify recovery.

### Step 11 — Prepare the E2 Docker image

Ensure Docker is running.

```bash
docker build -t logibridge-inference:m1 -f Dockerfile .
```

### Step 12 — Start the local registry

```bash
docker run -d \
    --name logibridge-registry \
    --restart=always \
    -p 5000:5000 \
    registry:2
```

### Step 13 — Push the image

```bash
docker tag \
    logibridge-inference:m1 \
    localhost:5000/logibridge-inference:m1

docker push localhost:5000/logibridge-inference:m1
```

### Step 14 — Install Ansible deployment dependencies

```bash
sudo apt install -y ansible python3-docker

ansible-galaxy collection install community.docker
```

### Step 15 — Validate and execute the deployment

```bash
ansible-playbook -i localhost, logibridge_deploy.yml --syntax-check
```

Then:

```bash
ansible-playbook -i localhost, logibridge_deploy.yml --ask-become-pass
```

### Step 16 — Verify the deployed service

```bash
docker ps
```

```bash
ls -lh /opt/logibridge/
```

### Step 17 — Verify idempotency

Run the playbook a second time:

```bash
ansible-playbook -i localhost, logibridge_deploy.yml --ask-become-pass
```

Confirm:

```text
changed=0
```

### Step 18 — Refer to E3 OTA strategy

Use Section 25 for the bandwidth calculation, strategy comparison, and recommended canary deployment approach.

---

# 27. Troubleshooting — ML Inference, PSI, Docker and Ansible

### Inference service is running but no predictions are received

Check the following:

1. MQTT broker is running.
2. Sensor simulator is publishing messages.
3. Preprocessing is running.
4. The inference service is connected to the broker.
5. `training_stats.npy` exists.
6. The configured model path points to an existing TFLite model.

The preprocessing component is required because the inference service consumes preprocessed feature messages, not the raw sensor messages.

### PSI monitor remains at zero samples

Check that:

1. The inference service is running.
2. The inference MQTT topic is correct.
3. The simulator is running.
4. Preprocessing is publishing feature messages.
5. Inference predictions are actually being published.

Inspect the inference topic:

```bash
mosquitto_sub \
    -h localhost \
    -p 1883 \
    -t "logibridge/trucks/MH15-RF-0427/inference" \
    -v
```

### Reference distribution file is missing

Run the reference collector while the complete clean inference pipeline is running:

```bash
python inference/psi_monitor.py --mode reference
```

Do not start monitoring until the reference file has been generated.

### Docker daemon connection error

Check:

```bash
docker info
```

Ensure Docker Desktop or the native Docker daemon is running.

For Windows users, verify that WSL2 integration is enabled for the correct Ubuntu distribution.

### Local registry is not reachable

Check:

```bash
docker ps
```

The registry should be running with port 5000 mapped.

If the registry container has already been created, start it instead of creating a duplicate:

```bash
docker start logibridge-registry
```

### Ansible fails with a sudo authentication error

Run the playbook with:

```bash
ansible-playbook -i localhost, logibridge_deploy.yml --ask-become-pass
```

Enter the Linux user's sudo password when prompted.

### Ansible collection is missing

Install:

```bash
ansible-galaxy collection install community.docker
```

### Deployment container is not running

Check:

```bash
docker ps -a
```

Inspect the container logs:

```bash
docker logs logibridge-inference
```

Check whether the required model file exists:

```bash
ls -lh /opt/logibridge/model.tflite
```

### Second Ansible execution reports changes

Check whether any deployment input changed:

- `model.tflite`
- `data_pipeline/reference_dist.json`
- Docker image in the registry
- Container environment variables or configuration

If inputs and configuration are unchanged, the second playbook run should report `changed=0`.

---

# 28. Git and Repository Management

Before committing, check the repository status:

```bash
git status
```

Recommended `.gitignore` entries:

```text
.venv/
venv/
__pycache__/
*.pyc
```

Do not commit:
- Python virtual environments.
- Temporary files.
- Local cache files.
- Machine-specific paths or credentials.

Required project artifacts should be committed if they are part of the assignment deliverables, including:
- Model files required for execution.
- `training_stats.npy`.
- `data_pipeline/reference_dist.json`.
- Dockerfile and Docker dependency file.
- `logibridge_deploy.yml`.
- Source code and README.

Verify the files being committed:

```bash
git status --short
```

Stage and commit:

```bash
git add README.md
git add inference/
git add data_pipeline/
git add deployment/
git add Dockerfile requirements-docker.txt
git add logibridge_deploy.yml model.tflite
```

Review the staged changes:

```bash
git diff --cached --stat
git status
```

Commit:

```bash
git commit -m "Document and complete LogiEdge edge AI deployment"
```

Push:

```bash
git push origin <branch-name>
```

---

# 29. Final Implementation Status

The project covers the following implementation areas:

| Component | Implemented functionality |
|---|---|
| Sensor simulation | Temperature, vibration RMS, and door events |
| MQTT communication | Mosquitto-based sensor and feature messaging |
| Preprocessing | Moving averages, sliding windows, feature extraction |
| Normalization | Training-statistics-based normalization |
| ML inference | TFLite model inference |
| Classification | Normal, Warning, and Critical outputs |
| E1 — PSI reference | 300 clean inference confidence samples |
| E1 — Drift monitoring | Rolling 100-inference PSI monitoring every 60 seconds |
| E1 — Alerting | Drift alert above 0.25 and recovery below 0.10 |
| E2 — Docker | Containerized inference service |
| E2 — Registry | Local Docker registry |
| E2 — Ansible | Seven-task deployment playbook |
| E2 — Idempotency | Second unchanged playbook execution reports `changed=0` |
| E3 — OTA | Full replacement, canary, and shadow-mode comparison |
| E3 — Recommendation | Canary deployment for the 85-truck pilot fleet |

The project is a prototype implementation for the specified LogiBridge assignment scope. The README describes the tested development and deployment workflow; it does not imply that the prototype has been deployed to a live commercial truck fleet.