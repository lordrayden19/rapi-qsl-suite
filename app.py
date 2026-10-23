import json
import os
from flask import Flask, jsonify, render_template, request
import psycopg2

app = Flask(__name__)

# Mengambil URL Database dari Environment Variable Render
DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db_connection():
  db_url = DATABASE_URL
  if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
  return psycopg2.connect(db_url, sslmode="require")


# Inisialisasi tabel otomatis jika belum ada di database cloud
def init_db():
  if not DATABASE_URL:
    return
  try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
            CREATE TABLE IF NOT EXISTS app_storage (
                key TEXT PRIMARY KEY,
                data TEXT
            );
        """)
    initial_data = json.dumps({"devQsoLogs": [], "operatorLogs": []})
    cur.execute(
        "INSERT INTO app_storage (key, data) VALUES (%s, %s) ON CONFLICT (key)"
        " DO NOTHING;",
        ("logs_data", initial_data),
    )
    conn.commit()
    cur.close()
    conn.close()
  except Exception as e:
    print("Error init DB:", e)


# Jalankan inisialisasi saat server mulai
init_db()


def load_server_logs():
  if not DATABASE_URL:
    return {"devQsoLogs": [], "operatorLogs": []}
  try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT data FROM app_storage WHERE key = %s;", ("logs_data",))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row[0]:
      return json.loads(row[0])
  except Exception as e:
    print("Error load logs:", e)
  return {"devQsoLogs": [], "operatorLogs": []}


def save_server_logs(data):
  if not DATABASE_URL:
    return
  try:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE app_storage SET data = %s WHERE key = %s;",
        (json.dumps(data), "logs_data"),
    )
    conn.commit()
    cur.close()
    conn.close()
  except Exception as e:
    print("Error save logs:", e)


@app.route("/")
def index():
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
  
