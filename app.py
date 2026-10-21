import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search-callsign', methods=['POST'])
def search_callsign():
    data = request.get_json() or {}
    callsign = data.get('callsign', '').strip().upper()
    
    if not callsign:
        return jsonify({"status": "error", "message": "Callsign tidak boleh kosong!"}), 400

    local_database = {
        "JZ10IXM": {
            "name": "DIAN HERMAWAN",
            "address": "Kabupaten Ciamis, Jawa Barat"
        },
        "JZ09ABC": {
            "name": "BUDI SANTOSO",
            "address": "Bandung, Jawa Barat"
        }
    }

    if callsign in local_database:
        return jsonify({
            "status": "success",
            "source": "Database Lokal",
            "callsign": callsign,
            "name": local_database[callsign]["name"],
            "address": local_database[callsign]["address"]
        })
    else:
        return jsonify({
            "status": "success",
            "source": "Auto-Generate",
            "callsign": callsign,
            "name": f"ANGGOTA RAPI ({callsign})",
            "address": "Wilayah RAPI Indonesia"
        })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)