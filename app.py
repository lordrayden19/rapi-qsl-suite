import json
import os
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# File JSON untuk menyimpan arsip log secara permanen di server
LOGS_FILE = "server_logs.json"


def load_server_logs():
  if os.path.exists(LOGS_FILE):
    try:
      with open(LOGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except:
      pass
  return {"devQsoLogs": [], "operatorLogs": []}


def save_server_logs(data):
  with open(LOGS_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)


@app.route("/")
def index():
  # Pastikan file HTML utama Anda berada di dalam folder 'templates'
  # dengan nama index.html
  return render_template("index.html")


@app.route("/api/logs", methods=["GET"])
def get_server_logs():
  return jsonify(load_server_logs())


@app.route("/api/logs", methods=["POST"])
def update_server_logs():
  req_data = request.json
  logs = load_server_logs()
  if "devQsoLogs" in req_data:
    logs["devQsoLogs"] = req_data["devQsoLogs"]
  if "operatorLogs" in req_data:
    logs["operatorLogs"] = req_data["operatorLogs"]
  save_server_logs(logs)
  return jsonify({"status": "success"})


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=5000)
    
