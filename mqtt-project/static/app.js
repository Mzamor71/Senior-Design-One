
const REFRESH_INTERVAL = 3000;

const API = {
    health: "/api/health",
    latest: "/api/latest",
    messages: "/api/messages?limit=20",
    history: "/api/history?limit=50"
};


// ========================================
// GENERAL HELPERS
// ========================================

async function fetchJSON(url) {
    const response = await fetch(url, {
        cache: "no-store"
    });

    if (!response.ok) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`);
    }

    return response.json();
}


function formatTime(timestamp) {
    if (!timestamp) return "Unknown";

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
        return "Unknown";
    }

    return date.toLocaleString();
}


function formatClock() {
    setText("system-clock", new Date().toLocaleTimeString());
}


function setText(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.textContent = value ?? "";
    }
}


function setWidth(id, value) {
    const element = document.getElementById(id);

    if (element) {
        element.style.width = value;
    }
}


function setClassName(id, className) {
    const element = document.getElementById(id);

    if (element) {
        element.className = className;
    }
}


function addCell(row, value, className = "") {
    const cell = document.createElement("td");

    cell.textContent = value ?? "--";

    if (className) {
        cell.className = className;
    }

    row.appendChild(cell);

    return cell;
}


// ========================================
// API CONNECTION STATUS
// ========================================

function updateConnectionStatus(online) {
    const indicator = document.getElementById("api-indicator");
    const label = document.getElementById("api-status");

    if (indicator) {
        indicator.classList.toggle("online", online);
        indicator.classList.toggle("offline", !online);
    }

    if (label) {
        label.textContent = online
            ? "API CONNECTED"
            : "API UNAVAILABLE";
    }
}


// ========================================
// ENVIRONMENTAL DATA
// ========================================

function updateEnvironmentalData(devices) {
    const esp32 = devices.find(
        device => device.device_type === "environmental_sensor"
    );

    if (!esp32) {
        setText("temperature", "--");
        setText("humidity", "--");
        setText("temperature-time", "NO DATA");
        setText("humidity-time", "NO DATA");
        return;
    }

    setText(
        "temperature",
        esp32.temperature != null
            ? Number(esp32.temperature).toFixed(1)
            : "--"
    );

    setText(
        "humidity",
        esp32.humidity != null
            ? Number(esp32.humidity).toFixed(1)
            : "--"
    );

    setText("temperature-time", formatTime(esp32.received_at));
    setText("humidity-time", formatTime(esp32.received_at));
}


// ========================================
// AI DETECTION DATA
// ========================================

function updateDetectionData(devices) {
    const jetson = devices.find(
        device => device.device_type === "ai_camera"
    );

    if (!jetson) {
        setText("detected-object", "--");
        setText("confidence", "--");
        setWidth("confidence-bar", "0%");
        setText("detection-time", "NO DATA");
        return;
    }

    setText(
        "detected-object",
        jetson.detected_object ?? "--"
    );

    const confidence = jetson.confidence;

    if (
        confidence != null &&
        Number.isFinite(Number(confidence))
    ) {
        const percentage = Math.max(
            0,
            Math.min(100, Number(confidence) * 100)
        );

        setText("confidence", percentage.toFixed(1));
        setWidth("confidence-bar", `${percentage}%`);

    } else {
        setText("confidence", "--");
        setWidth("confidence-bar", "0%");
    }

    setText("detection-time", formatTime(jetson.received_at));
}


// ========================================
// XIAO ESP32S3 TELEMETRY
// ========================================

function formatUptime(seconds) {
    if (
        seconds == null ||
        !Number.isFinite(Number(seconds))
    ) {
        return "--";
    }

    const totalSeconds = Math.max(
        0,
        Math.floor(Number(seconds))
    );

    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);

    return `${days}d ${hours}h ${minutes}m`;
}


function updateXiaoData(devices) {
    const xiao = devices.find(
        device =>
            device.device_id === "xiao_esp32s3_01" ||
            device.device_type === "esp32s3_node"
    );

    if (!xiao) {
        setText("xiao-rssi", "--");
        setText("xiao-uptime", "--");
        setText("xiao-last-seen", "NO DATA");
        setText("xiao-signal-quality", "NO DATA");

        setWidth("xiao-signal-bar", "0%");

        setClassName(
            "xiao-status-indicator",
            "xiao-status-indicator offline"
        );

        setText("xiao-status", "NO DATA");

        return;
    }

    // WIFI SIGNAL STRENGTH

    const rssi = Number(xiao.wifi_rssi);

    if (
        xiao.wifi_rssi != null &&
        Number.isFinite(rssi)
    ) {
        setText("xiao-rssi", `${rssi} dBm`);

        const percentage = Math.max(
            0,
            Math.min(100, ((rssi + 100) / 70) * 100)
        );

        setWidth("xiao-signal-bar", `${percentage}%`);

        let quality = "WEAK SIGNAL";

        if (rssi >= -50) {
            quality = "EXCELLENT SIGNAL";
        } else if (rssi >= -60) {
            quality = "GOOD SIGNAL";
        } else if (rssi >= -70) {
            quality = "FAIR SIGNAL";
        }

        setText("xiao-signal-quality", quality);

    } else {
        setText("xiao-rssi", "--");
        setText("xiao-signal-quality", "NO SIGNAL DATA");

        setWidth("xiao-signal-bar", "0%");
    }


    // DEVICE UPTIME

    setText(
        "xiao-uptime",
        formatUptime(xiao.uptime_seconds)
    );


    // LAST MESSAGE RECEIVED

    setText(
        "xiao-last-seen",
        formatTime(xiao.received_at)
    );


    // DEVICE CONNECTION STATUS

    const lastReceived = new Date(
        xiao.received_at
    ).getTime();

    const age = Date.now() - lastReceived;

    // XIAO publishes approximately every 5 seconds.
    // Allow 15 seconds before marking it stale.

    const online =
        Number.isFinite(lastReceived) &&
        age >= -60000 &&
        age <= 15000;

    if (online) {
        setClassName(
            "xiao-status-indicator",
            "xiao-status-indicator online"
        );

        setText("xiao-status", "ONLINE");

    } else {
        setClassName(
            "xiao-status-indicator",
            "xiao-status-indicator offline"
        );

        setText("xiao-status", "STALE");
    }
}


// ========================================
// DEVICE REGISTRY
// ========================================

function updateDeviceTable(devices) {
    const table = document.getElementById("device-table");

    if (!table) return;

    table.replaceChildren();

    if (devices.length === 0) {
        const row = table.insertRow();
        const cell = row.insertCell();

        cell.colSpan = 4;
        cell.className = "empty-state";
        cell.textContent = "No devices have submitted data.";

        return;
    }

    devices.forEach(device => {
        const row = table.insertRow();

        addCell(row, device.device_id, "device-id");
        addCell(row, device.device_type);

        const statusCell = row.insertCell();
        const status = document.createElement("span");

        status.className = "data-status";
        status.textContent = "DATA RECEIVED";

        statusCell.appendChild(status);

        addCell(row, formatTime(device.received_at));
    });
}


// ========================================
// MESSAGE HISTORY
// ========================================

function summarizePayload(payload) {
    if (
        !payload ||
        typeof payload !== "object"
    ) {
        return "No payload information";
    }

    const parts = [];

    if (payload.temperature != null) {
        parts.push(
            `Temperature: ${payload.temperature} °C`
        );
    }

    if (payload.humidity != null) {
        parts.push(
            `Humidity: ${payload.humidity}%`
        );
    }

    if (
        payload.detection &&
        typeof payload.detection === "object"
    ) {
        if (payload.detection.object) {
            parts.push(
                `Object: ${payload.detection.object}`
            );
        }

        if (payload.detection.confidence != null) {
            const confidence = Number(
                payload.detection.confidence
            );

            parts.push(
                `Confidence: ${
                    Number.isFinite(confidence)
                        ? (confidence * 100).toFixed(1)
                        : "--"
                }%`
            );
        }
    }

    if (payload.wifi_rssi != null) {
        parts.push(
            `Wi-Fi: ${payload.wifi_rssi} dBm`
        );
    }

    if (payload.uptime_seconds != null) {
        parts.push(
            `Uptime: ${formatUptime(payload.uptime_seconds)}`
        );
    }

    return parts.length > 0
        ? parts.join(" | ")
        : "JSON message received";
}


function updateMessageTable(messages) {
    const table = document.getElementById("message-table");

    if (!table) return;

    table.replaceChildren();

    if (messages.length === 0) {
        const row = table.insertRow();
        const cell = row.insertCell();

        cell.colSpan = 5;
        cell.className = "empty-state";
        cell.textContent = "No MQTT messages have been stored.";

        return;
    }

    messages.forEach(message => {
        const row = table.insertRow();

        addCell(row, message.id, "device-id");
        addCell(row, message.device_id, "device-id");
        addCell(row, message.topic, "topic-text");
        addCell(row, summarizePayload(message.payload));
        addCell(row, formatTime(message.received_at));
    });
}


// ========================================
// HISTORICAL CHARTS
// ========================================

function drawChart(
    canvasId,
    records,
    field,
    lineColor,
    unit
) {
    const canvas = document.getElementById(canvasId);

    if (!canvas) return;

    const context = canvas.getContext("2d");

    if (!context) return;

    const width = canvas.clientWidth;

    if (width <= 0) return;

    const height = 190;

    const pixelRatio = window.devicePixelRatio || 1;

    canvas.width = width * pixelRatio;
    canvas.height = height * pixelRatio;

    context.setTransform(
        pixelRatio, 0,
        0, pixelRatio,
        0, 0
    );

    context.clearRect(0, 0, width, height);

    const left = 43;
    const right = 15;
    const top = 15;
    const bottom = 30;

    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;


    // Ignore null values instead of converting them to zero.

    const points = records
        .map(record => ({
            value: record[field] == null
                ? NaN
                : Number(record[field]),

            time: record.received_at
        }))
        .filter(point => Number.isFinite(point.value));


    context.font = "10px Consolas, monospace";
    context.fillStyle = "#8295aa";
    context.strokeStyle = "#263648";
    context.lineWidth = 1;

    if (points.length === 0) {
        context.fillText(
            "NO HISTORICAL DATA",
            left,
            height / 2
        );

        return;
    }


    let minimum = Math.min(
        ...points.map(point => point.value)
    );

    let maximum = Math.max(
        ...points.map(point => point.value)
    );

    if (minimum === maximum) {
        minimum -= 1;
        maximum += 1;

    } else {
        const padding = (maximum - minimum) * 0.15;

        minimum -= padding;
        maximum += padding;
    }


    // HORIZONTAL GRID LINES AND LABELS

    for (let i = 0; i <= 4; i++) {
        const y = top + (plotHeight / 4) * i;

        const value = maximum -
            ((maximum - minimum) / 4) * i;

        context.beginPath();
        context.moveTo(left, y);
        context.lineTo(left + plotWidth, y);
        context.stroke();

        context.fillStyle = "#8295aa";

        context.fillText(
            value.toFixed(1),
            3,
            y + 3
        );
    }


    // CALCULATE DATA COORDINATES

    const coordinates = points.map((point, index) => {
        const x = points.length === 1
            ? left + plotWidth / 2
            : left + (index / (points.length - 1)) * plotWidth;

        const y = top +
            ((maximum - point.value) / (maximum - minimum)) *
            plotHeight;

        return { x, y };
    });


    // DRAW DATA LINE

    if (coordinates.length > 1) {
        context.beginPath();

        coordinates.forEach((point, index) => {
            if (index === 0) {
                context.moveTo(point.x, point.y);
            } else {
                context.lineTo(point.x, point.y);
            }
        });

        context.strokeStyle = lineColor;
        context.lineWidth = 2;
        context.stroke();
    }


    // DRAW DATA POINTS

    coordinates.forEach(point => {
        context.beginPath();

        context.arc(
            point.x,
            point.y,
            3,
            0,
            Math.PI * 2
        );

        context.fillStyle = lineColor;
        context.fill();
    });


    // FIRST AND LAST TIMESTAMPS

    const firstTime = points[0].time;
    const lastTime = points[points.length - 1].time;

    context.fillStyle = "#8295aa";
    context.font = "9px Consolas, monospace";

    context.textAlign = "left";

    context.fillText(
        firstTime
            ? new Date(firstTime).toLocaleTimeString()
            : "",
        left,
        height - 7
    );

    context.textAlign = "right";

    context.fillText(
        lastTime
            ? new Date(lastTime).toLocaleTimeString()
            : "",
        left + plotWidth,
        height - 7
    );

    context.textAlign = "left";
}


// ========================================
// MAIN DASHBOARD UPDATE
// ========================================

async function updateDashboard() {
    const errorMessage = document.getElementById("error-message");

    try {
        const [
            health,
            devicesResponse,
            messagesResponse,
            historyResponse
        ] = await Promise.all([
            fetchJSON(API.health),
            fetchJSON(API.latest),
            fetchJSON(API.messages),
            fetchJSON(API.history)
        ]);


        const devices = Array.isArray(devicesResponse)
            ? devicesResponse
            : [];

        const messages = Array.isArray(messagesResponse)
            ? messagesResponse
            : [];

        const history = Array.isArray(historyResponse)
            ? historyResponse
            : [];


        updateConnectionStatus(
            health.status === "online" &&
            health.database === true
        );

        updateEnvironmentalData(devices);
        updateDetectionData(devices);
        updateXiaoData(devices);

        updateDeviceTable(devices);
        updateMessageTable(messages);


        // TEMPERATURE HISTORY

        drawChart(
            "temperature-chart",
            history,
            "temperature",
            "#5798d6",
            "°C"
        );


        // HUMIDITY HISTORY

        drawChart(
            "humidity-chart",
            history,
            "humidity",
            "#43bd91",
            "%"
        );


        setText(
            "database-count",
            health.message_count ?? 0
        );

        setText(
            "last-updated",
            `UPDATED ${new Date().toLocaleTimeString()}`
        );

        if (errorMessage) {
            errorMessage.textContent = "";
        }

    } catch (error) {
        updateConnectionStatus(false);

        if (errorMessage) {
            errorMessage.textContent =
                `Unable to retrieve monitoring data: ${error.message}`;
        }

        console.error(
            "Dashboard update failed:",
            error
        );
    }
}


// ========================================
// START DASHBOARD
// ========================================

formatClock();

setInterval(formatClock, 1000);

updateDashboard();

setInterval(
    updateDashboard,
    REFRESH_INTERVAL
);

window.addEventListener("resize", updateDashboard);
