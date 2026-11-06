import json
import os
from flask import Flask, jsonify, render_template, request, Response
import psycopg2
import requests
import re
from urllib.parse import urlencode

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



# Proxy Callbook: permintaan dilakukan dari server Render agar browser tidak
# terhalang kebijakan CORS. Tidak menyimpan kredensial pengguna.
CALLBOOK_REGIONAL_URL = "https://rapiwil16ciamis.alatbantu.xyz/index.php"
# Domain resmi yang tercantum pada panduan Callbook RAPI Nusantara.
# Domain lama tetap menjadi fallback jika domain mail tidak dapat diakses.
CALLBOOK_NATIONAL_URLS = [
  "https://mail.rapinasional.or.id/",
  "https://rapinasional.or.id/",
]

def valid_callsign(value):
  callsign = str(value or "").strip().upper()
  if not re.fullmatch(r"[A-Z0-9]{3,12}", callsign):
    return None
  return callsign

@app.route("/api/callbook/regional", methods=["POST"])
def callbook_regional():
  payload = request.get_json(silent=True) or {}
  callsign = valid_callsign(payload.get("callsign"))
  if not callsign:
    return jsonify({"error": "Callsign tidak valid."}), 400
  try:
    response = requests.get(
        CALLBOOK_REGIONAL_URL,
        params={"page": "callbook", "callsign": callsign},
        headers={"User-Agent": "Mozilla/5.0 (compatible; RAPI-QSL-Suite/1.0)"},
        timeout=(8, 20),
    )
    response.raise_for_status()
    return Response(response.text, content_type="text/html; charset=utf-8")
  except requests.RequestException as exc:
    print("Callbook regional error:", repr(exc))
    return jsonify({"error": "Callbook RAPI Wilayah 16 tidak dapat diakses saat ini."}), 502

@app.route("/api/callbook/national", methods=["POST"])
def callbook_national():
  payload = request.get_json(silent=True) or {}
  callsign = valid_callsign(payload.get("callsign"))
  if not callsign:
    return jsonify({"error": "Callsign tidak valid."}), 400
  last_error = None
  for base_url in CALLBOOK_NATIONAL_URLS:
    session = requests.Session()
    session.headers.update({
        # Header browser umum; tidak melewati CAPTCHA atau proteksi akses.
        "User-Agent": "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
        "Connection": "keep-alive",
    })
    try:
      home = session.get(base_url, timeout=(8, 20), allow_redirects=True)
      home.raise_for_status()
      # Laravel CSRF token dapat tersedia sebagai meta tag atau hidden input.
      token_match = re.search(
          r"""<meta[^>]+name=['"]csrf-token['"][^>]+content=['"]([^'"]+)""",
          home.text, re.I
      )
      if not token_match:
        token_match = re.search(
            r"""<input[^>]+name=['"]_token['"][^>]+value=['"]([^'"]+)""",
            home.text, re.I
        )
      if not token_match:
        return jsonify({"error": "Halaman Callbook Nasional terbuka, tetapi token/form pencarian tidak ditemukan. Struktur situs perlu diperiksa."}), 502
      result = session.post(
          home.url,
          data={"_token": token_match.group(1), "callsign": callsign},
          headers={"Referer": home.url, "Origin": f"{home.scheme}://{home.host}", "Content-Type": "application/x-www-form-urlencoded"},
          timeout=(8, 20),
      )
      result.raise_for_status()
      return Response(result.text, content_type="text/html; charset=utf-8")
    except requests.RequestException as exc:
      last_error = exc
      print(f"Callbook national error ({base_url}):", repr(exc))
      continue

  return jsonify({"error": "Server RAPI Nasional menolak atau tidak dapat menerima permintaan dari Render. Silakan lihat Runtime Logs untuk detail kedua alamat."}), 502


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
  
