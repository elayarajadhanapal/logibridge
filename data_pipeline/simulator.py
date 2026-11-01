import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_pipeline_dashboard_iface import SimulatorDashboard  # noqa: E402
from dashboard.dashboard_api import (  # noqa: E402  (repo root added by the iface)
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TRUCK_ID,
)


DEFAULT_BROKER_HOST = DEFAULT_HOST
DEFAULT_BROKER_PORT = DEFAULT_PORT

TEMPERATURE_SETPOINT_C = 4.0
TEMPERATURE_STD_C = 0.3
TEMPERATURE_DRIFT_PER_READING_C = 0.08

# Vibration is published as the compressor RMS value at 0.5 Hz (one reading
# every 2 s), as specified in Task C1. The raw 500 Hz x 3-axis signal is
# reduced to RMS on the sensor node and never put on MQTT.
VIBRATION_PERIOD_SECONDS = 2
VIBRATION_NORMAL_MEAN_G = 0.45
VIBRATION_NORMAL_STD_G = 0.05
VIBRATION_ANOMALY_MEAN_G = 1.2
VIBRATION_ANOMALY_STD_G = 0.15

DOOR_OPEN_PROBABILITY = 0.02    # per second while closed
DOOR_CLOSE_PROBABILITY = 0.10   # per second while open (mean ~10 s open)


def generate_temperature(
    anomaly: str,
    drift_readings: int,
) -> float:
    """
    Generate one temperature reading.

    Normal:
        N(4.0, 0.3)

    Temperature drift:
        +0.08 C per reading.

    drift_readings is the number of readings since the drift anomaly
    was switched on (0 when no drift is active).
    """

    temperature = np.random.normal(
        TEMPERATURE_SETPOINT_C,
        TEMPERATURE_STD_C,
    )

    if anomaly in ("temp_drift", "combined"):
        temperature += TEMPERATURE_DRIFT_PER_READING_C * drift_readings

    return float(temperature)


def generate_vibration(anomaly: str) -> float:
    """
    Generate one compressor vibration RMS reading in g.

    Normal:   N(0.45, 0.05)
    Anomaly:  step to N(1.2, 0.15) (bearing wear)
    """

    if anomaly in ("vibration", "combined"):
        mean = VIBRATION_ANOMALY_MEAN_G
        std = VIBRATION_ANOMALY_STD_G
    else:
        mean = VIBRATION_NORMAL_MEAN_G
        std = VIBRATION_NORMAL_STD_G

    return float(np.random.normal(loc=mean, scale=std))


def publish_temperature(
    dash: SimulatorDashboard,
    anomaly: str,
    drift_readings: int,
    ts: float,
) -> float:
    """Publish one temperature reading."""

    temperature = generate_temperature(
        anomaly,
        drift_readings,
    )

    dash.temperature(round(temperature, 3), ts)

    return temperature


def publish_vibration(
    dash: SimulatorDashboard,
    anomaly: str,
    ts: float,
) -> float:
    """Publish one vibration RMS reading."""

    vibration = generate_vibration(anomaly)

    dash.vibration(round(vibration, 4), ts)

    return vibration


def publish_door_event(
    dash: SimulatorDashboard,
    door_open: bool,
    ts: float,
) -> bool:
    """
    Generate occasional door OPEN / CLOSE events.

    Door is event-based rather than sampled continuously: a message is
    published only when the state changes. Returns the new state.
    """

    if not door_open and np.random.random() < DOOR_OPEN_PROBABILITY:
        dash.door("OPEN", ts)
        return True

    if door_open and np.random.random() < DOOR_CLOSE_PROBABILITY:
        dash.door("CLOSE", ts)
        return False

    return door_open


def create_dashboard(
    broker_host: str,
    broker_port: int,
    truck_id: str,
) -> SimulatorDashboard:
    """Create the MQTT link (topics, payload contract, status, control)."""

    print(
        f"Connecting to MQTT broker "
        f"{broker_host}:{broker_port}..."
    )

    return SimulatorDashboard(
        truck_id=truck_id,
        host=broker_host,
        port=broker_port,
    )


def run_simulation(
    dash: SimulatorDashboard,
    truck_id: str,
    anomaly: str,
    duration: int,
) -> None:
    """Run the sensor simulation. duration = 0 runs until Ctrl+C."""

    print()
    print("LogiEdge Sensor Simulator")
    print("=========================")
    print(f"Truck ID : {truck_id}")
    print(f"Anomaly  : {anomaly}")
    print(f"Duration : {duration or 'until Ctrl+C'} seconds")
    print()

    # The anomaly mode can be changed at runtime from the dashboard
    # (control topic), e.g. to inject drift mid-run for the PSI demo.
    state = {"anomaly": anomaly}

    def on_anomaly(mode: str) -> None:
        print(f"Anomaly mode changed: {state['anomaly']} -> {mode}")
        state["anomaly"] = mode

    dash.on_anomaly_command(on_anomaly)

    drift_readings = 0
    door_open = False
    start_wall = time.time()
    tick = 0

    try:
        while not duration or tick < duration:
            # One tick = 1 s of data time, shared by all streams.
            ts = start_wall + tick
            mode = state["anomaly"]

            # Drift accumulates from the moment it is switched on and
            # resets when the drift anomaly is switched off.
            if mode in ("temp_drift", "combined"):
                drift_readings += 1
            else:
                drift_readings = 0

            temperature = publish_temperature(
                dash,
                mode,
                drift_readings,
                ts,
            )

            vibration_text = "-"
            if tick % VIBRATION_PERIOD_SECONDS == 0:
                vibration = publish_vibration(
                    dash,
                    mode,
                    ts,
                )
                vibration_text = f"{vibration:.3f}g"

            door_open = publish_door_event(
                dash,
                door_open,
                ts,
            )

            print(
                f"[{tick + 1:04d}s] "
                f"mode={mode} "
                f"temperature={temperature:.2f}C "
                f"vibration={vibration_text} "
                f"door={'OPEN' if door_open else 'CLOSED'}"
            )

            tick += 1
            # Pace against the start time so the clock does not drift.
            time.sleep(max(0.0, start_wall + tick - time.time()))

    except KeyboardInterrupt:
        print("\nSimulation interrupted.")

    finally:
        dash.close()

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
        default=0,
        help="Simulation duration in seconds (0 = until Ctrl+C)",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible runs",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.seed is not None:
        np.random.seed(args.seed)

    dash = create_dashboard(
        broker_host=args.broker_host,
        broker_port=args.broker_port,
        truck_id=args.truck_id,
    )

    run_simulation(
        dash=dash,
        truck_id=args.truck_id,
        anomaly=args.anomaly,
        duration=args.duration,
    )


if __name__ == "__main__":
    main()
