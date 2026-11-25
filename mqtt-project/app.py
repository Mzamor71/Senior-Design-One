
from flask import Flask, jsonify, render_template, request
import sqlite3
import json
from pathlib import Path

app = Flask(__name__)

DATABASE_PATH = (
    Path.home()
    / "mqtt-project"
    / "database"
    / "iot_data.db"
)


def get_database_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@app.route("/")
def home():
    return jsonify({
        "message": "Raspberry Pi IoT API is running",
        "dashboard": "/dashboard",
        "endpoints": [
            "/api/health",
            "/api/messages",
            "/api/latest",
            "/api/history"
        ]
    })


@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


@app.route("/api/health")
def health():
    if not DATABASE_PATH.exists():
        return jsonify({
            "status": "error",
            "database": False
        }), 503

    try:
        connection = get_database_connection()

        count = connection.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]

        connection.close()

        return jsonify({
            "status": "online",
            "database": True,
            "message_count": count
        })

    except sqlite3.Error as error:
        return jsonify({
            "status": "error",
            "database": False,
            "message": str(error)
        }), 500


@app.route("/api/messages")
def get_messages():
    limit = request.args.get("limit", default=100, type=int)
    limit = max(1, min(limit or 100, 500))

    connection = get_database_connection()

    try:
        rows = connection.execute("""
            SELECT
                id,
                received_at,
                topic,
                device_id,
                device_type,
                payload_json
            FROM messages
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        messages = []

        for row in rows:
            messages.append({
                "id": row["id"],
                "received_at": row["received_at"],
                "topic": row["topic"],
                "device_id": row["device_id"],
                "device_type": row["device_type"],
                "payload": json.loads(row["payload_json"])
            })

        return jsonify(messages)

    finally:
        connection.close()


@app.route("/api/latest")
def get_latest():
    connection = get_database_connection()

    try:
        rows = connection.execute("""
            SELECT
                id,
                received_at,
                topic,
                device_id,
                device_type,
                payload_json
            FROM messages
            WHERE id IN (
                SELECT MAX(id)
                FROM messages
                GROUP BY device_id
            )
            ORDER BY id DESC
        """).fetchall()

        devices = []

        for row in rows:
            payload = json.loads(row["payload_json"])

            detection = payload.get("detection", {})

            if not isinstance(detection, dict):
                detection = {}

            devices.append({
                "device_id": row["device_id"],
                "device_type": row["device_type"],
                "received_at": row["received_at"],
                "temperature": payload.get("temperature"),
                "humidity": payload.get("humidity"),
                "detected_object": detection.get("object"),
                "confidence": detection.get("confidence"),

                # XIAO ESP32S3 telemetry
                "wifi_rssi": payload.get("wifi_rssi"),
                "uptime_seconds": payload.get("uptime_seconds")
            })

        return jsonify(devices)

    finally:
        connection.close()


@app.route("/api/history")
def get_history():
    limit = request.args.get("limit", default=50, type=int)
    limit = max(1, min(limit or 50, 500))

    connection = get_database_connection()

    try:
        rows = connection.execute("""
            SELECT
                received_at,
                device_id,
                json_extract(
                    payload_json, '$.temperature'
                ) AS temperature,
                json_extract(
                    payload_json, '$.humidity'
                ) AS humidity
            FROM messages
            WHERE device_type = 'environmental_sensor'
              AND (
                  json_extract(payload_json, '$.temperature') IS NOT NULL
                  OR
                  json_extract(payload_json, '$.humidity') IS NOT NULL
              )
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        history = []

        for row in reversed(rows):
            history.append({
                "received_at": row["received_at"],
                "device_id": row["device_id"],
                "temperature": row["temperature"],
                "humidity": row["humidity"]
            })

        return jsonify(history)

    finally:
        connection.close()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
