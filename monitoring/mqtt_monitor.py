import json
import os

import paho.mqtt.client as mqtt


BROKER_HOST = os.environ.get("LOGIBRIDGE_MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("LOGIBRIDGE_MQTT_PORT", "1883"))
TRUCK_ID = "MH15-RF-0427"

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
        print(f"Temperature : {payload['value']:.3f} °C")
        print()

    elif msg.topic.endswith("/vibration"):
        print("Vibration")
        print("---------")
        print(f"Truck       : {payload['truck_id']}")
        print(f"RMS         : {payload['value']:.3f} g")
        print()

    elif msg.topic.endswith("/door"):
        print("Door Event")
        print("----------")
        print(f"Truck : {payload['truck_id']}")
        print(f"Event : {payload['state']}")
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