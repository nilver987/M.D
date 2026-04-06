"""SENAMHI Scraper v4 — Servidor Flask"""
import threading
from pathlib import Path
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
from scraper import scrape_region, progreso, _lock, REGIONES

app = Flask(__name__)
CORS(app)
OUTPUT_DIR = "./output"
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
_hilo = None

def _reset():
    with _lock:
        progreso.update({
            "estado": "idle", "mensaje": "", "porcentaje": 0,
            "zip_path": None, "errores": [],
            "total": 0, "procesadas": 0, "excel_encontrados": 0,
        })

def _run(region_key):
    try:
        scrape_region(region_key, output_dir=OUTPUT_DIR)
    except Exception:
        pass

@app.route("/api/regiones")
def get_regiones():
    return jsonify([{"key": k, "nombre": v} for k, v in REGIONES.items()])

@app.route("/api/scrape", methods=["POST"])
def iniciar():
    global _hilo
    data = request.get_json(force=True, silent=True) or {}
    region = data.get("region", "").strip().lower()
    if not region:
        return jsonify({"error": "Falta 'region'"}), 400
    if region not in REGIONES:
        return jsonify({"error": f"Región '{region}' no válida"}), 400
    with _lock:
        if progreso["estado"] == "corriendo":
            return jsonify({"error": "Ya hay un scraping en progreso"}), 409
    _reset()
    _hilo = threading.Thread(target=_run, args=(region,), daemon=True)
    _hilo.start()
    return jsonify({"ok": True, "region": region, "nombre": REGIONES[region]})

@app.route("/api/progreso")
def get_progreso():
    with _lock:
        return jsonify(dict(progreso))

@app.route("/api/descargar")
def descargar():
    with _lock:
        p = progreso.get("zip_path")
    if not p or not Path(p).exists():
        return jsonify({"error": "ZIP no disponible aún"}), 404
    return send_file(p, as_attachment=True,
                     download_name=Path(p).name,
                     mimetype="application/zip")

@app.route("/api/cancelar", methods=["POST"])
def cancelar():
    _reset()
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("=" * 50)
    print("  SENAMHI Scraper v4")
    print("  http://localhost:5000")
    print("  Descarga los Excel ORIGINALES del servidor")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
