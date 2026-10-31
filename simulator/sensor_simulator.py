import argparse
import json
import time
from datetime import datetime, timezone

import numpy as np
import paho.mqtt.client as mqtt


DEFAULT_BROKER_HOST = "localhost"
DEFAULT_BROKER_PORT = 1883
DEFAULT_TRUCK_ID = "FB-042"

TEMPERATURE_SETPOINT_C = 4.0
TEMPERATURE_STD_C = 0.3

VIBRATION_SAMPLE_RATE_HZ = 500
VIBRATION_NORMAL_MEAN_G = 0.45
VIBRATION_NORMAL_STD_G = 0.05
VIBRATION_ANOMALY_MEAN_G = 1.2
VIBRATION_ANOMALY_STD_G = 0.15


def utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def temperature_topic(truck_id: str) -> str:
    return f"logibridge/trucks/{truck_id}/sensors/temperature"


def vibration_topic(truck_id: str) -> str:
    return f"logibridge/trucks/{truck_id}/sensors/vibration"


def door_topic(truck_id: str) -> str:
    return f"logibridge/trucks/{truck_id}/sensors/door"


def generate_temperature(
    anomaly: str,
    elapsed_seconds: int,
) -> float:
    """
    Generate one temperature reading.

    Normal:
        N(4.0, 0.3)

    Temperature drift:
        +0.08 C per reading.

    Since temperature is generated at 1 Hz, elapsed_seconds is
    equivalent to the number of temperature readings generated.
    """

    temperature = np.random.normal(
        TEMPERATURE_SETPOINT_C,
        TEMPERATURE_STD_C,
    )

    if anomaly in ("temp_drift", "combined"):
        temperature += 0.08 * elapsed_seconds

    return float(temperature)


def generate_vibration(anomaly: str) -> np.ndarray:
    """
    Generate one second of 3-axis vibration data.

    500 Hz x 3 axes = 1500 values per second.
    """

    if anomaly in ("vibration", "combined"):
        mean = VIBRATION_ANOMALY_MEAN_G
        std = VIBRATION_ANOMALY_STD_G
    else:
        mean = VIBRATION_NORMAL_MEAN_G
        std = VIBRATION_NORMAL_STD_G

    return np.random.normal(
        loc=mean,
        scale=std,
        size=(VIBRATION_SAMPLE_RATE_HZ, 3),
    )


def publish_temperature(
    client: mqtt.Client,
    truck_id: str,
    anomaly: str,
    elapsed_seconds: int,
) -> None:
    """Publish one raw temperature reading."""

    temperature = generate_temperature(
        anomaly,
        elapsed_seconds,
    )

    payload = {
        "timestamp": utc_timestamp(),
        "truck_id": truck_id,
        "sensor": "temperature",
        "temperature_c": round(temperature, 3),
        "setpoint_c": TEMPERATURE_SETPOINT_C,
        "sample_rate_hz": 1,
    }

    client.publish(
        temperature_topic(truck_id),
        json.dumps(payload),
        qos=1,
    )


def publish_vibration(
    client: mqtt.Client,
    truck_id: str,
    anomaly: str,
) -> None:
    """
    Publish one second of raw vibration samples.

    We batch the 500 Hz samples into one MQTT message.
    This avoids creating 500 MQTT messages every second while
    preserving the underlying raw 500 Hz sensor data.
    """

    samples = generate_vibration(anomaly)

    payload = {
        "timestamp": utc_timestamp(),
        "truck_id": truck_id,
        "sensor": "vibration",
        "sample_rate_hz": VIBRATION_SAMPLE_RATE_HZ,
        "axes": ["x", "y", "z"],
        "duration_seconds": 1,
        "samples": np.round(samples, 4).tolist(),
    }

    client.publish(
        vibration_topic(truck_id),
        json.dumps(payload),
        qos=1,
    )


def publish_door_event(
    client: mqtt.Client,
    truck_id: str,
) -> None:
    """
    Generate an occasional door-open event.

    Door is event-based rather than sampled continuously.
    """

    # Approximately 2% probability of an OPEN event each second.
    if np.random.random() >= 0.02:
        return

    payload = {
        "timestamp": utc_timestamp(),
        "truck_id": truck_id,
        "sensor": "door",
        "event": "OPEN",
    }

    client.publish(
        door_topic(truck_id),
        json.dumps(payload),
        qos=1,
    )


def create_mqtt_client(
    broker_host: str,
    broker_port: int,
    truck_id: str,
) -> mqtt.Client:
    """Create and connect the MQTT client."""

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"logibridge-simulator-{truck_id}",
    )

    print(
        f"Connecting to MQTT broker "
        f"{broker_host}:{broker_port}..."
    )

    client.connect(
        broker_host,
        broker_port,
        keepalive=60,
    )

    client.loop_start()

    return client


def run_simulation(
    client: mqtt.Client,
    truck_id: str,
    anomaly: str,
    duration: int,
) -> None:
    """Run the sensor simulation."""

    print()
    print("LogiEdge Sensor Simulator")
    print("=========================")
    print(f"Truck ID : {truck_id}")
    print(f"Anomaly  : {anomaly}")
    print(f"Duration : {duration} seconds")
    print()

    start_time = time.monotonic()

    try:
        while True:
            elapsed = int(time.monotonic() - start_time)

            if elapsed >= duration:
                break

            publish_temperature(
                client,
                truck_id,
                anomaly,
                elapsed,
            )

            publish_vibration(
                client,
                truck_id,
                anomaly,
            )

            publish_door_event(
                client,
                truck_id,
            )

            print(
                f"[{elapsed + 1:04d}s] "
                f"temperature=OK "
                f"vibration=OK "
                f"truck={truck_id}"
            )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nSimulation interrupted.")

    finally:
        client.loop_stop()
        client.disconnect()

    print("Simulation finished.")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LogiEdge raw sensor simulator"
    )

    parser.add_argument(
        "--truck-id",
        default=DEFAULT_TRUCK_ID,
        help=f"Truck identifier (default: {DEFAULT_TRUCK_ID})",
    )

    parser.add_argument(
        "--broker-host",
        default=DEFAULT_BROKER_HOST,
        help=f"MQTT broker host (default: {DEFAULT_BROKER_HOST})",
    )

    parser.add_argument(
        "--broker-port",
        type=int,
        default=DEFAULT_BROKER_PORT,
        help=f"MQTT broker port (default: {DEFAULT_BROKER_PORT})",
    )

    parser.add_argument(
        "--anomaly",
        choices=[
            "none",
            "temp_drift",
            "vibration",
            "combined",
        ],
        default="none",
        help="Anomaly scenario",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Simulation duration in seconds",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    client = create_mqtt_client(
        broker_host=args.broker_host,
        broker_port=args.broker_port,
        truck_id=args.truck_id,
    )

    run_simulation(
        client=client,
        truck_id=args.truck_id,
        anomaly=args.anomaly,
        duration=args.duration,
    )


if __name__ == "__main__":
    main()