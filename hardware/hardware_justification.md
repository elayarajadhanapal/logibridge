Sure — here is the content formatted as a clean Markdown (`.md`) document.

 # Component A — System Architecture and Deployment Justification

 ## Task A1 — Constraint Analysis

 ### 1\. Latency

 The system requires an alert within **90 seconds** of a fault signature appearing to prevent the **1°C per minute cargo temperature rise**.

 Relying on cloud inference is fundamentally incompatible with this SLA because of unpredictable rural cellular round-trip latency. Therefore, **on-device processing is mandatory**.

 ### 2\. Bandwidth

 The truck produces:

 - **Temperature data:** 1 Hz
- **Vibration data:** 500 Hz, 3-axis

 Assuming standard **32-bit floats**:

 #### Vibration Data

```
500 Hz × 3 axes × 4 bytes
= 6,000 bytes/sec
```

 #### Temperature Data

```
1 Hz × 4 bytes
= 4 bytes/sec
```

 This results in approximately **518 MB of raw data per truck per day**.

 At the specified transmission rate of **₹0.10/MB**:

```
₹0.10 × 518 MB
≈ ₹51.80 per truck per day
```

 For the **85-truck pilot**:

```
₹51.80 × 85 × 30
≈ ₹132,090 per month
```

 Therefore, transmitting raw sensor data to the cloud would cost approximately **₹132,000 per month** for the pilot.

 Processing data at the edge reduces the transmitted data to negligible **MQTT alert payloads**, significantly reducing bandwidth and communication costs.

 ### 3\. Connectivity

 The **Nashik–Aurangabad route** suffers from documented cellular dead zones lasting approximately **35–90 minutes**.

 A cloud-only architecture could silently fail during these connectivity gaps.

 The edge architecture ensures that:

 1. Local classification continues uninterrupted.
2. Anomaly alerts are stored in a local log when connectivity is unavailable.
3. Buffered alerts are synchronized with the cloud once the cellular uplink is restored.

 ### 4\. Privacy

 Pharmaceutical clients require strict proof against unauthorized access to operational data.

 On-device inference ensures that raw, granular operational data remains within the **physical boundary of the truck** and does not need to be transmitted to the cloud.

---

 ## Task A2 — System Architecture Diagram

 The proposed architecture follows an end-to-end Python-based data pipeline, with sensor ingestion, local MQTT messaging, preprocessing, inference, offline storage, and cloud synchronization.

 ### Architecture Flow

```
┌───────────────────────────────────────────────────────────────┐
│                         TRUCK EDGE                            │
│                                                               │
│  ┌──────────────┐                                             │
│  │   Sensors    │                                             │
│  │              │                                             │
│  │ Temperature  │                                             │
│  │ Vibration    │                                             │
│  │  (3-axis)    │                                             │
│  │ Door Events  │                                             │
│  └──────┬───────┘                                             │
│         │                                                     │
│         ▼                                                     │
│  ┌──────────────────────┐                                     │
│  │ Python Sensor        │                                     │
│  │ Simulator            │                                     │
│  │                      │                                     │
│  │ Publishes to         │                                     │
│  │ localhost MQTT       │                                     │
│  └──────────┬───────────┘                                     │
│             │                                                 │
│             ▼                                                 │
│  ┌──────────────────────┐                                     │
│  │ Local Mosquitto      │                                     │
│  │ MQTT Broker          │                                     │
│  └──────────┬───────────┘                                     │
│             │                                                 │
│             ▼                                                 │
│  ┌──────────────────────┐                                     │
│  │ Raspberry Pi 5       │                                     │
│  │ + Hailo-8L           │                                     │
│  │                      │                                     │
│  │ Preprocessing        │                                     │
│  │ - 5-sample moving    │                                     │
│  │   average            │                                     │
│  │ - Feature extraction │                                     │
│  └──────────┬───────────┘                                     │
│             │                                                 │
│             ▼                                                 │
│  ┌──────────────────────┐                                     │
│  │ Docker Container     │                                     │
│  │                      │                                     │
│  │ Python 3.11-slim     │                                     │
│  │ TFLite Inference     │                                     │
│  └──────────┬───────────┘                                     │
│             │                                                 │
│       ┌─────┴─────┐                                           │
│       │           │                                           │
│       ▼           ▼                                           │
│  ┌──────────┐  ┌──────────────────┐                            │
│  │  Alert   │  │ Cellular M2M     │                            │
│  │   Log    │  │ Uplink           │                            │
│  │ (Buffer) │  │                  │                            │
│  └────┬─────┘  └────────┬─────────┘                            │
│       │                 │                                      │
└───────┼─────────────────┼──────────────────────────────────────┘
        │                 │
        │                 │ Sync on restored connectivity
        │                 ▼
        │      ┌───────────────────────────┐
        │      │    OPERATIONS CENTRE      │
        │      │                           │
        └─────►│ Backend MQTT Broker       │
               │            │              │
               │            ▼              │
               │ Operations Dashboard      │
               └───────────────────────────┘
```

 ### Architecture Components

 | Layer | Component | Responsibility |
| --- | --- | --- |
| Data Ingestion | Temperature Sensor | Measures cargo temperature at 1 Hz |
| Data Ingestion | 3-Axis Vibration Sensor | Captures vibration data at 500 Hz |
| Data Ingestion | Door Sensor | Detects door opening/closing events |
| Simulation | Python Sensor Simulator | Generates sensor data and publishes it to localhost MQTT |
| Message Broker | Mosquitto MQTT | Provides local, reliable message transport |
| Edge Processing | Raspberry Pi 5 + Hailo-8L | Performs local preprocessing and inference |
| Preprocessing | Python Pipeline | Performs 5-sample moving average and feature extraction |
| Inference | Docker + TFLite | Runs the trained ML model |
| Storage | Local Alert Log | Buffers alerts during connectivity outages |
| Communication | Cellular M2M | Synchronizes alerts with the cloud |
| Cloud | Backend MQTT Broker | Receives synchronized alerts |
| Monitoring | Operations Dashboard | Provides fleet-level visibility |

### Development Task Distribution

 Development tasks should be distributed evenly among team members.

 Smaller standalone components, such as the **Python sensor simulator**, can be assigned to teammates with tighter schedules, while larger components such as the inference pipeline and deployment automation can be assigned separately.

---

 # Component B — Hardware Selection and Justification

 ## Task B1 — Constraint Triangle Application

 The dominant constraints for this cold-chain deployment are:

 1. **Power:** Strict **10 W AI power budget** drawn from the truck's 12 V supply.
2. **Cost:** Hardware must be economically scalable to the fleet.
3. **Software Capability:** Must support Docker containerisation and a Python-based MLOps pipeline.

 ### Hardware Comparison

 | Option | Power | Cost / Truck | Software Capability | Decision |
| --- | --- | --- | --- | --- |
| Raspberry Pi 5 \+ Hailo-8L | 7.5 W | ₹15,000 | Linux, Docker, Python, MQTT | **Selected** |
| Jetson Orin Nano | 15 W | ₹45,000 | Linux, Docker, Python | **Rejected** |
| STM32H7 MCU | 0.4 W | ₹3,500 | Bare-metal C/C++ / RTOS | **Rejected** |

---

 ## Option 1 — Raspberry Pi 5 + Hailo-8L

 **Selected**

 The Raspberry Pi 5 + Hailo-8L is selected because it satisfies all three major constraints.

 ### Power

```
Power consumption = 7.5 W
Power budget       = 10 W
```

 Therefore:

```
7.5 W < 10 W
```

 The system operates within the specified AI power budget.

 ### Cost

```
₹15,000 per truck
```

 This makes it economically viable for scaling to the full **265-vehicle fleet**.

 ### Software Capability

 The platform provides a full Linux environment capable of supporting:

 - Docker
- Python 3.11
- MQTT
- TFLite
- Ansible
- MLOps tooling
- PSI drift monitoring

 Therefore, it supports the mandated software ecosystem.

---

 ## Option 2 — Jetson Orin Nano

 **Rejected**

 The Jetson Orin Nano fails the hard power constraint.

```
Power consumption = 15 W
Allowed budget    = 10 W
```

 Therefore:

```
15 W > 10 W
```

 It also has a significantly higher hardware cost:

```
₹45,000 × 265 trucks
= ₹11,925,000
≈ ₹1.19 Crore
```

 Thus, the Jetson Orin Nano breaks both the **Power** and **Cost** vertices of the constraint triangle.

---

 ## Option 3 — STM32H7 MCU

 **Rejected**

 The STM32H7 performs well in terms of power and cost:

```
Power = 0.4 W
Cost  = ₹3,500
```

 However, it fails the **Capability** vertex.

 The project requires:

 - Docker containerisation
- Python 3.11
- Ansible playbooks
- PSI drift monitoring
- Standard Python-based MLOps workflows

 An STM32H7 is designed for bare-metal C/C++ or RTOS-based applications and cannot provide the required Linux and Docker environment.

 Therefore, despite its excellent power efficiency and low cost, it does not satisfy the project's software requirements.

---

 ## Constraint Triangle Summary

 The two rejected options each violate a critical vertex:

 ### Jetson Orin Nano — Power and Cost Failure

```
                    Capability
                       ▲
                      / \
                     /   \
                    /     \
                   /       \
                  /         \
                 /___________\
            Power             Cost
              ✗                 ✗

        Jetson Orin Nano
        - 15 W > 10 W
        - ₹45,000 per unit
```

 ### STM32H7 — Capability Failure

```
                    Capability
                       ▲
                       ✗
                      / \
                     /   \
                    /     \
                   /       \
                  /_________\
             Power          Cost
                ✓              ✓

              STM32H7
        - 0.4 W power
        - ₹3,500 per unit
        - Cannot run Linux/Docker/Python 3.11
```

 ### Raspberry Pi 5 + Hailo-8L — Constraint Satisfaction

```
                    Capability
                       ▲
                      / \
                     / ✓ \
                    /     \
                   /       \
                  /_________\
             Power          Cost
                ✓              ✓

       Raspberry Pi 5 + Hailo-8L
       - 7.5 W < 10 W
       - ₹15,000 per unit
       - Linux + Docker + Python
```

 The Raspberry Pi 5 + Hailo-8L satisfies all three vertices simultaneously:

 - **Power:** 7.5 W \< 10 W
- **Cost:** ₹15,000 per truck
- **Capability:** Full Linux/Docker/Python ecosystem

---

 # Task B2 — Arithmetic Intensity and Roofline Analysis

 ## Hardware Specifications

 The Raspberry Pi 5 CPU is specified with:

 | Parameter | Value |
| --- | --- |
| Peak Compute (π) | 16 GFLOP/s |
| Peak Memory Bandwidth (β) | 12 GB/s |

## Model Profile

 The trained model has:

 | Parameter | Value |
| --- | --- |
| Operations per inference | 45 MFLOPs |
| Data accessed per inference | 18 MB |

---

 ## Arithmetic Intensity Calculation

 Arithmetic intensity is calculated as:

```
Arithmetic Intensity (AI)
= FLOPs / Bytes
```

 Given:

```
FLOPs  = 45 MFLOPs
Data   = 18 MB
```

 Therefore:

```
AI = 45 MFLOPs / 18 MB
   = 2.5 FLOPs/Byte
```

 ### Result

```
Arithmetic Intensity = 2.5 FLOPs/Byte
```

---

 ## Hardware Ridge Point

 The hardware ridge point is calculated using:

```
Ridge Point = Peak Compute / Peak Memory Bandwidth
```

 Therefore:

```
Ridge Point
= 16 GFLOP/s / 12 GB/s
= 1.33 FLOPs/Byte
```

 ### Result

```
Hardware Ridge Point = 1.33 FLOPs/Byte
```

---

 ## Roofline Analysis

 Compare the model's arithmetic intensity with the hardware ridge point:

```
Model AI       = 2.5 FLOPs/Byte
Ridge Point    = 1.33 FLOPs/Byte
```

 Since:

```
2.5 > 1.33
```

 the model lies on the **compute-bound** side of the roofline model.

 Therefore, inference performance is primarily limited by computational throughput rather than memory bandwidth.

---

 ## Optimisation Strategy

 Since the model is compute-bound, optimisation should focus on reducing the number of mathematical operations required for inference.

 Suitable techniques include:

 ### 1\. Post-Training Quantisation

 Applying **INT8 quantisation** can reduce computational and memory requirements while potentially improving inference efficiency.

 ### 2\. Structured Pruning

 Removing less-important model structures can reduce the number of operations required per inference.

 These techniques can help reduce inference latency and provide additional margin for meeting the **90-second alert SLA**.

---

 # Final Hardware and Architecture Decision

 The proposed deployment architecture is:

```
Sensors
   │
   ▼
Python Sensor Simulator
   │
   ▼
Local Mosquitto MQTT Broker
   │
   ▼
Raspberry Pi 5 + Hailo-8L
   │
   ├── Python Preprocessing
   │      ├── 5-sample Moving Average
   │      └── Feature Extraction
   │
   ├── Docker Container
   │      └── Python 3.11 + TFLite Inference
   │
   ├── Local Alert Log
   │      └── Offline Buffering
   │
   └── Cellular M2M Uplink
          │
          ▼
     Backend MQTT Broker
          │
          ▼
   Operations Dashboard
```

 The **Raspberry Pi 5 + Hailo-8L** provides the required combination of:

 - **Edge inference** for the 90-second latency requirement
- **Offline operation** during cellular dead zones
- **Low bandwidth usage** through alert-only cloud communication
- **Local data processing** for privacy
- **7.5 W power consumption**, within the 10 W limit
- **₹15,000 hardware cost per truck**
- **Linux, Docker, Python 3.11, MQTT, and MLOps compatibility**
- **Compute-focused optimisation opportunities** through INT8 quantisation and structured pruning

