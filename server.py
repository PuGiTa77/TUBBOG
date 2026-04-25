from flask import Flask, request, jsonify, render_template
import mysql.connector
from datetime import datetime
import requests
import time
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# MySQL Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'tubbog_db'
}

# Telegram Configuration
BOT_TOKEN = "8626296164:AAHHWkBrac30Wl8d2bBRRJkG6tmcNX2gthw"
LAST_ALERT_SENT = 0 
COOLDOWN_SECONDS = 300  # 5 minutes between alerts

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ================= TELEGRAM LOGIC =================
def broadcast_telegram_alert(message):
    global LAST_ALERT_SENT
    current_time = time.time()

    # Prevent spamming users if an alert was sent recently
    if current_time - LAST_ALERT_SENT < COOLDOWN_SECONDS:
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Fetch all IDs registered via the dashboard 
        cursor.execute("SELECT telegram_id FROM alert_contacts")
        rows = cursor.fetchall()
        
        for (chat_id,) in rows:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id, 
                "text": message, 
                "parse_mode": "Markdown"
            }
            res = requests.post(url, json=payload)

              # DEBUG RESPONSE
            if res.status_code != 200:
                print("Failed:", chat_id, res.text)
            else:
                print("Sent to:", chat_id)

        LAST_ALERT_SENT = current_time
        cursor.close()
        conn.close()
    except Exception as e:
        print("Telegram Broadcast Error:", e)
        # Handle error (e.g., log it, send a notification, etc.)

# ================= UPDATE =================
@app.route("/update", methods=["POST"])
def update():
    json_data = request.json
    s1 = json_data.get("s1", 0)
    s2 = json_data.get("s2", 0)
    s3 = json_data.get("s3", 0)
    flow = json_data.get("flow", 0)

    status = "NORMAL"
    alerts = []

    # -------- SENSOR VALIDATION --------
    def is_invalid(val):
        return val == -1 or val == -1.00

    invalid_sensors = []

    if is_invalid(s1):
        invalid_sensors.append("Sensor 1")
    if is_invalid(s2):
        invalid_sensors.append("Sensor 2")
    if is_invalid(s3):
        invalid_sensors.append("Sensor 3")

    # -------- HANDLE SENSOR ERROR --------
    if invalid_sensors:
        status = "SENSOR_ERROR"

        error_msg = (
            "⚠️ SENSOR ERROR ⚠️\n\n"
            f"Affected: {', '.join(invalid_sensors)}\n\n"
            "Possible causes:\n"
            "- Loose wiring\n"
            "- Sensor disconnected\n"
            "- Hardware failure\n\n"
            "Please check the device immediately."
        )

        broadcast_telegram_alert(error_msg)

        # Replace invalid values with 0 for DB
        s1 = 0 if is_invalid(s1) else s1
        s2 = 0 if is_invalid(s2) else s2
        s3 = 0 if is_invalid(s3) else s3

    # -------- SENSOR CHECK FUNCTION --------
    def check_sensor(sensor_name, value):
        if value <= 8.0:
            return "CRITICAL", (
                f"🚨🌊 FLOOD ALERT 🌊🚨\n\n"
                f"Location: Quilling Sur, Bacucang\n"
                f"{sensor_name}: CRITICAL LEVEL - {value} meters\n"
                f"Advisory: Evacuate immediately. Avoid flooded roads.\n\n"
                f"📞 Contact: NDRRMC: 911 / local DRRMO hotline\n\n"
                f"Move to higher ground immediately."
            )

        elif value <= 9.5:
            return "WARNING", (
                f"⚠️‼️ FLOOD WARNING ‼️⚠️\n\n"
                f"Location: Quilling Sur, Bacucang\n"
                f"{sensor_name}: WARNING LEVEL - {value} meters\n"
                f"Advisory: Water levels are rising. Stay alert. Prepare Go Bags.\n\n"
                f"📞 Contact: NDRRMC: 911 / local DRRMO hotline\n\n"
                f"Monitor the TUBBOG Dashboard."
            )

        return "NORMAL", None

    # -------- ONLY RUN FLOOD LOGIC IF NO SENSOR ERROR --------
    if not invalid_sensors:
        for name, val in [("Sensor 1", s1), ("Sensor 2", s2), ("Sensor 3", s3)]:
            sensor_status, message = check_sensor(name, val)

            if sensor_status == "CRITICAL":
                status = "CRITICAL"
                alerts.append(message)

            elif sensor_status == "WARNING" and status != "CRITICAL":
                status = "WARNING"
                alerts.append(message)

    # -------- SEND ALERTS --------
    for msg in alerts:
        if msg:
            broadcast_telegram_alert(msg)

    # -------- SAVE TO DATABASE --------
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        INSERT INTO sensor_logs (s1, s2, s3, flow, status)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (s1, s2, s3, flow, status))
        conn.commit()

        cursor.close()
        conn.close()

        return {"status": "ok"}

    except Exception as e:
        print("DB ERROR:", e)
        return {"status": "error"}, 500

# ================= LIVE DATA =================
@app.route("/data")
def get_latest():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM sensor_logs ORDER BY timestamp DESC LIMIT 1")
    latest = cursor.fetchone()

    cursor.close()
    conn.close()

    if not latest:
        return jsonify({
            "s1": 0,
            "s2": 0,
            "s3": 0,
            "flow": 0,
            "status": "OFFLINE"
        })

    return jsonify(latest)


# ================= LOGS =================
@app.route("/api/logs")
def get_logs():
    date = request.args.get("date")

    if not date:
        return jsonify([])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        from datetime import datetime

        selected_date = datetime.strptime(date, "%Y-%m-%d").date()
        today = datetime.now().date()

        days_diff = (today - selected_date).days

        # RULE:
        # = 1 day → RAW
        # > 1 day → HOURLY

        if selected_date == today:
            print("📡 USING RAW DATA (today)")

            cursor.execute("""
                SELECT 
                    timestamp,
                    s1, s2, s3,
                    flow,
                    status
                FROM sensor_logs
                WHERE DATE(timestamp) = %s
                ORDER BY timestamp ASC
            """, (date,))

            mode = "raw"

        else:
            print(" USING HOURLY DATA (older than 1 day)")

            cursor.execute("""
                SELECT 
                    CONCAT(date, ' ', LPAD(hour,2,'0'), ':00:00') AS timestamp,
                    avg_s1 AS s1,
                    avg_s2 AS s2,
                    avg_s3 AS s3,
                    avg_flow AS flow,
                    status
                FROM sensor_hourly
                WHERE date = %s
                ORDER BY hour ASC
            """, (date,))

            mode = "hourly"

        data = cursor.fetchall()

        if not data:
            return jsonify({
                "status": "empty",
                "message": "No data found",
                "data": []
            })

        return jsonify({
            "status": "success",
            "mode": mode,
            "data": data
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"status": "error"}), 500

    finally:
        cursor.close()
        conn.close()

# ================= ADD CONTACT =================
@app.route("/api/add-contact", methods=["POST"])
def add_contact():
    data = request.get_json(silent=True) or {}
    telegram_id = data.get("telegram_id", "").strip()

    # -------- VALIDATION --------

    # Empty
    if not telegram_id:
        return jsonify({
        "success": False,
        "message": "Telegram ID is required."
    }), 400

    if not telegram_id.isdigit():
        return jsonify({
            "success": False,
            "message": "Only numbers are allowed. No letters or special characters."
        }), 400

    if len(telegram_id) != 10:
        return jsonify({
        "success": False,
        "message": "Telegram ID must be exactly 10 digits."
    }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # -------- CHECK DUPLICATE --------
        cursor.execute(
            "SELECT * FROM alert_contacts WHERE telegram_id = %s",
            (telegram_id,)
        )
        existing = cursor.fetchone()

        if existing:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": "This Telegram ID is already registered."
            }), 400

        # -------- INSERT --------
        cursor.execute(
            "INSERT INTO alert_contacts (telegram_id) VALUES (%s)",
            (telegram_id,)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Telegram ID added successfully."
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({
            "status": "error",
            "message": "Server error. Please try again."
        }), 500
    

 # ================= HOURLY AVERAGES =================   
@app.route("/api/hourly")
def get_hourly():
    date = request.args.get("date")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT hour, avg_s1, avg_s2, avg_s3, avg_flow, status
        FROM sensor_hourly
        WHERE date = %s
        ORDER BY hour
    """, (date,))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)
    
# ================= DAILY AVERAGES =================
@app.route("/api/daily")
def get_daily():
    month = request.args.get("month")  # format: YYYY-MM

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT date, avg_s1, avg_s2, avg_s3, avg_flow, status
        FROM sensor_daily
        WHERE DATE_FORMAT(date, '%Y-%m') = %s
        ORDER BY date
    """, (month,))

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)


# ================= PAGES =================
@app.route("/")
def dashboard():
    return render_template("index.html")

@app.route("/logs")
def logs_page():
    return render_template("logs.html")

@app.route("/stats")
def stats_page():
    return render_template("stats.html")


# ================= COMPARE MONTHS =================
@app.route("/api/compare-months")
def compare_months():
    monthA = request.args.get("monthA")
    monthB = request.args.get("monthB")
    year = request.args.get("year")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    def get_month_data(month):
        query = """
        SELECT 
            DAY(date) as day,
            avg_s1 as s1,
            avg_s2 as s2,
            avg_s3 as s3,
            avg_flow as flow
        FROM sensor_daily
        WHERE MONTH(date) = %s AND YEAR(date) = %s
        ORDER BY day ASC
        """
        cursor.execute(query, (month, year))
        rows = cursor.fetchall()

        print("Month:", month, "Rows:", rows)

        labels, s1, s2, s3, flow = [], [], [], [], []

        for r in rows:
            labels.append(str(r["day"]))
            s1.append(float(r["s1"]))
            s2.append(float(r["s2"]))
            s3.append(float(r["s3"]))
            flow.append(float(r["flow"]))

        return {
            "labels": labels,
            "s1": s1,
            "s2": s2,
            "s3": s3,
            "flow": flow
        }

    dataA = get_month_data(int(monthA))
    dataB = get_month_data(int(monthB))

    cursor.close()
    conn.close()

    # -------- ERROR HANDLING (UPDATED) --------

    # BOTH EMPTY
    if not dataA["labels"] and not dataB["labels"]:
        return jsonify({
            "status": "empty",
            "message": "No data found for both selected months.",
            "monthA": dataA,
            "monthB": dataB
        })  # removed 404

    # MONTH A EMPTY
    if not dataA["labels"]:
        return jsonify({
            "status": "empty",
            "message": f"No data found for Month A ({monthA}).",
            "monthA": dataA,
            "monthB": dataB
        })  # removed 404

    # MONTH B EMPTY
    if not dataB["labels"]:
        return jsonify({
            "status": "empty",
            "message": f"No data found for Month B ({monthB}).",
            "monthA": dataA,
            "monthB": dataB
        })  #removed 404

    # SUCCESS
    return jsonify({
        "status": "ok",
        "monthA": dataA,
        "monthB": dataB
    })
#  ================= TEST TELEGRAM =================
@app.route("/test-telegram")
def test_telegram():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT telegram_id FROM alert_contacts")
        rows = cursor.fetchall()

        for (chat_id,) in rows:
            print("📨 Sending to:", chat_id)

            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": "🚨 I HAVE ACCESS TO YOUR ACCOUNT!!!! DATA BREACHED!! 🚨"
            }

            res = requests.post(url, json=payload)

            if res.status_code == 200:
                print("Sent to", chat_id)
            else:
                print("Failed:", chat_id, res.text)

        cursor.close()
        conn.close()

        return "Test messages sent!"

    except Exception as e:
        return str(e)

# ================= RAW LOGS (1 DAY) =================
@app.route("/api/raw-logs")
def get_raw_logs():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT timestamp, s1, s2, s3, flow, status
        FROM sensor_logs
        WHERE timestamp >= NOW() - INTERVAL 1 DAY
        ORDER BY timestamp DESC
        LIMIT 500
    """)

    data = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(data)

# ================= CLEAN UP RAW =================

def cleanup_old_raw_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM sensor_logs
            WHERE timestamp < NOW() - INTERVAL 1 DAY
        """)

        conn.commit()
        cursor.close()
        conn.close()

        print("Old raw data cleaned (1 day)")

    except Exception as e:
        print("Cleanup error:", e)


def aggregate_hourly():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sensor_hourly (date, hour, avg_s1, avg_s2, avg_s3, avg_flow, status)
        SELECT 
            DATE(timestamp),
            HOUR(timestamp),
            AVG(s1),
            AVG(s2),
            AVG(s3),
            AVG(flow),
            MAX(status)
        FROM sensor_logs
        WHERE DATE(timestamp) = CURDATE()
        GROUP BY DATE(timestamp), HOUR(timestamp)
        ON DUPLICATE KEY UPDATE
            avg_s1=VALUES(avg_s1),
            avg_s2=VALUES(avg_s2),
            avg_s3=VALUES(avg_s3),
            avg_flow=VALUES(avg_flow),
            status=VALUES(status)
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Hourly updated")


def aggregate_daily():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sensor_daily (date, avg_s1, avg_s2, avg_s3, avg_flow, status)
        SELECT 
            date,
            AVG(avg_s1),
            AVG(avg_s2),
            AVG(avg_s3),
            AVG(avg_flow),
            MAX(status)
        FROM sensor_hourly
        GROUP BY date
        ON DUPLICATE KEY UPDATE
            avg_s1=VALUES(avg_s1),
            avg_s2=VALUES(avg_s2),
            avg_s3=VALUES(avg_s3),
            avg_flow=VALUES(avg_flow),
            status=VALUES(status)
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("Daily updated")

def cleanup_old_raw_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM sensor_logs
        WHERE DATE(timestamp) < CURDATE()
    """)

    conn.commit()
    cursor.close()
    conn.close()

    print("🧹 Old raw deleted (only today kept)")

if __name__ == "__main__":
    scheduler = BackgroundScheduler()

     # every hour
    scheduler.add_job(aggregate_hourly, 'cron', minute=0)

    # midnight
    scheduler.add_job(aggregate_daily, 'cron', hour=0, minute=5)

    # cleanup
    scheduler.add_job(cleanup_old_raw_data, 'cron', hour=0, minute=10)

    scheduler.start()

    print("🚀 Scheduler started")

    app.run(host="0.0.0.0", port=8000)