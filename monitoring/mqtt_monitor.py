import json

import numpy as np
import paho.mqtt.client as mqtt


BROKER_HOST = "localhost"
BROKER_PORT = 1883
TRUCK_ID = "FB-042"

TOPIC = f"logibridge/trucks/{TRUCK_ID}/sensors/#"


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connected to MQTT broker: {BROKER_HOST}:{BROKER_PORT}")
    print(f"Subscribed to: {TOPIC}")
    print()
    client.subscribe(TOPIC, qos=1)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        print(f"Invalid JSON received on {msg.topic}")
        return

    if msg.topic.endswith("/temperature"):
        print("Temperature")
        print("-----------")
        print(f"Truck       : {payload['truck_id']}")
        print(f"Temperature : {payload['temperature_c']:.3f} °C")
        print(f"Setpoint    : {payload['setpoint_c']:.1f} °C")
        print()

    elif msg.topic.endswith("/vibration"):
        samples = np.array(payload["samples"])

        print("Vibration")
        print("---------")
        print(f"Truck       : {payload['truck_id']}")
        print(f"Sample rate : {payload['sample_rate_hz']} Hz")
        print(f"Axes        : {', '.join(payload['axes'])}")
        print(f"Samples     : {samples.shape[0]}")
        print(f"Shape       : {samples.shape}")
        print(f"Duration    : {payload['duration_seconds']} sec")
        print(f"Mean        : {samples.mean():.3f} g")
        print(f"Min         : {samples.min():.3f} g")
        print(f"Max         : {samples.max():.3f} g")
        print()

    elif msg.topic.endswith("/door"):
        print("Door Event")
        print("----------")
        print(f"Truck : {payload['truck_id']}")
        print(f"Event : {payload['event']}")
        print()


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="logibridge-monitor",
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to {BROKER_HOST}:{BROKER_PORT}...")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()