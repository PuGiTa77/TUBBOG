from flask import Flask, request, jsonify, render_template
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# MySQL Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'tubbog_db'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ================= UPDATE =================
@app.route("/update", methods=["POST"])
def update():
    json_data = request.json
    s1 = json_data.get("s1", 0)
    s2 = json_data.get("s2", 0)
    s3 = json_data.get("s3", 0)
    flow = json_data.get("flow", 0)

    status = "NORMAL"
    if s1 > 3.0:
        status = "CRITICAL"
    elif s1 > 1.5:
        status = "WARNING"

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
        print("❌ DB ERROR:", e)
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
    month = request.args.get("month")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if date:
        cursor.execute("""
            SELECT * FROM sensor_logs
            WHERE DATE(timestamp) = %s
            ORDER BY timestamp
        """, (date,))
    elif month:
        cursor.execute("""
            SELECT * FROM sensor_logs
            WHERE DATE_FORMAT(timestamp, '%Y-%m') = %s
            ORDER BY timestamp
        """, (month,))
    else:
        cursor.execute("SELECT * FROM sensor_logs ORDER BY timestamp")

    logs = cursor.fetchall()

    for log in logs:
        log['timestamp'] = log['timestamp'].strftime("%Y-%m-%d %H:%M:%S")

    cursor.close()
    conn.close()

    return jsonify(logs)


# ================= ADD CONTACT =================
@app.route("/api/add-contact", methods=["POST"])
def add_contact():
    data = request.json
    phone = data.get("phone")

    if not phone:
        return {"status": "error"}, 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("INSERT INTO alert_contacts (phone_number) VALUES (%s)", (phone,))
        conn.commit()

        cursor.close()
        conn.close()

        return {"status": "success"}

    except Exception as e:
        print("❌ ERROR:", e)
        return {"status": "error"}, 500


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
@app.route('/api/compare-months')
def compare_months():
    mA = request.args.get('monthA')
    mB = request.args.get('monthB')
    year = request.args.get('year')

    def get_data(month):
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT s1, s2, s3, flow, timestamp
            FROM sensor_logs
            WHERE MONTH(timestamp)=%s AND YEAR(timestamp)=%s
            ORDER BY timestamp
        """, (month, year))

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "labels": [r[4].strftime("%m-%d") for r in rows],
            "s1": [r[0] for r in rows],
            "s2": [r[1] for r in rows],
            "s3": [r[2] for r in rows],
            "flow": [r[3] for r in rows]
        }

    return jsonify({
        "A": get_data(mA),
        "B": get_data(mB)
    })


# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)