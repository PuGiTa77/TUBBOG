from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Global data storage
data = {
    "distance": 0,
    "status": "Normal"
}

# ---------------- Dashboard ----------------
@app.route("/")
def dashboard():
    return render_template("dashboard.html")

# ---------------- Receive Data from ESP8266 ----------------
@app.route("/update", methods=["POST"])
def update():

    global data

    json_data = request.json
    distance = json_data["distance"]

    data["distance"] = distance

    if distance < 20:
        data["status"] = "FLOOD WARNING"
    else:
        data["status"] = "Normal"

    return {"message": "Data received"}

# ---------------- Send Data to Dashboard ----------------
@app.route("/data")
def get_data():
    return jsonify(data)

# ---------------- Run Server ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)