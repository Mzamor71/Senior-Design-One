
import json
import getpass
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


# ==========================================
# MQTT CONFIGURATION
# ==========================================

BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883

MQTT_USERNAME = "perfuser"
MQTT_TOPIC = "lab/#"


# ==========================================
# SQLITE DATABASE CONFIGURATION
# ==========================================

DATABASE_DIR = Path.home() / "mqtt-project" / "database"
DATABASE_PATH = DATABASE_DIR / "iot_data.db"


def initialize_database():
    """Create the database and messages table if necessary."""

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                device_id TEXT,
                device_type TEXT,
                payload_json TEXT NOT NULL
            )
        """)

        connection.commit()

    finally:
        connection.close()

    print(f"SQLite database ready: {DATABASE_PATH}")


def save_message(topic, data):
    """Save one valid JSON message into SQLite."""

    received_at = datetime.now(timezone.utc).isoformat()

    if isinstance(data, dict):
        device_id = data.get("device_id")
        device_type = data.get("device_type")
    else:
        device_id = None
        device_type = None

    # Preserve the complete JSON message
    payload_json = json.dumps(data, ensure_ascii=False)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        cursor = connection.execute("""
            INSERT INTO messages (
                received_at,
                topic,
                device_id,
                device_type,
                payload_json
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            received_at,
            topic,
            device_id,
            device_type,
            payload_json
        ))

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


# ==========================================
# JSON FIELD EXTRACTION
# ==========================================

def extract_fields(data, parent_key=""):
    """Recursively extract values from JSON objects and lists."""

    extracted = {}

    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}.{key}" if parent_key else key

            extracted.update(
                extract_fields(value, new_key)
            )

    elif isinstance(data, list):
        for index, value in enumerate(data):
            new_key = f"{parent_key}[{index}]"

            extracted.update(
                extract_fields(value, new_key)
            )

    else:
        extracted[parent_key] = data

    return extracted


# ==========================================
# MQTT CONNECTION CALLBACK
# ==========================================

def on_connect(client, userdata, flags, reason_code, properties):

    if reason_code == 0:
        print("\nSuccessfully connected to MQTT broker!")

        client.subscribe(MQTT_TOPIC)

        print(f"Subscribed to: {MQTT_TOPIC}")
        print("Waiting for incoming messages...\n")

    else:
        print(f"MQTT connection failed: {reason_code}")


# ==========================================
# INCOMING MQTT MESSAGE CALLBACK
# ==========================================

def on_message(client, userdata, message):

    print("\n===================================")
    print("NEW MQTT MESSAGE")
    print("===================================")

    print(f"Topic: {message.topic}")

    try:
        # Decode incoming MQTT bytes into UTF-8 text
        payload_text = message.payload.decode("utf-8-sig").strip()

        print("\nDECODED PAYLOAD:")
        print(repr(payload_text))

        # Convert JSON text into a Python object
        data = json.loads(payload_text)

        print("\nJSON PARSING SUCCESSFUL!")

        print("\nDECODED JSON:")
        print(json.dumps(data, indent=4))

        # Save valid JSON into SQLite
        try:
            record_id = save_message(message.topic, data)

            print("\nDATABASE STORAGE SUCCESSFUL!")
            print(f"Database record ID: {record_id}")
            print(f"Database location: {DATABASE_PATH}")

        except sqlite3.Error as error:
            print("\nDATABASE STORAGE ERROR:")
            print(error)

        # Extract JSON fields
        extracted = extract_fields(data)

        print("\nEXTRACTED INFORMATION:")

        for key, value in extracted.items():
            print(f"{key}: {value}")

        # Identify device
        if isinstance(data, dict):
            device_id = data.get("device_id", "Unknown")
            print(f"\nDEVICE IDENTIFIED: {device_id}")

    except UnicodeDecodeError:
        print("Error: Message is not valid UTF-8 text.")

    except json.JSONDecodeError as error:
        print("Error: Incoming message is not valid JSON.")
        print(f"JSON error details: {error}")

    except Exception as error:
        print(f"Unexpected processing error: {error}")

    print("===================================\n")


# ==========================================
# MAIN PROGRAM
# ==========================================

def main():

    # Create the database before receiving messages
    initialize_database()

    mqtt_password = getpass.getpass("Enter MQTT password: ")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )

    client.username_pw_set(
        MQTT_USERNAME,
        mqtt_password
    )

    client.on_connect = on_connect
    client.on_message = on_message

    print("\nConnecting to Raspberry Pi MQTT broker...")

    try:
        client.connect(
            BROKER_HOST,
            BROKER_PORT,
            60
        )

        client.loop_forever()

    except KeyboardInterrupt:
        print("\nStopping MQTT receiver...")

    except Exception as error:
        print(f"Connection error: {error}")

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
