import json
import os
import queue
import threading
import sys
from flask import Flask, Response, jsonify, render_template, request

from senamhi import SenamhiScraper, INVENTARIO_FILE, dep_display

app = Flask(__name__)

progress_queue   = queue.Queue()
scraper_lock     = threading.Lock()
scraper_instance = None
operacion_activa = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/inventario")
def get_inventario():
    if os.path.exists(INVENTARIO_FILE):
        with open(INVENTARIO_FILE, "r", encoding="utf-8") as f:
            return jsonify({"ok": True, "inventario": json.load(f)})
    return jsonify({"ok": False, "inventario": {}})


# ── SONDEO ───────────────────────────────────────────────────

@app.route("/api/sondear", methods=["POST"])
def sondear():
    global operacion_activa, scraper_instance
    if operacion_activa:
        return jsonify({"ok": False, "error": "Operación en curso"}), 400

    def _run():
        global operacion_activa, scraper_instance
        operacion_activa = True
        result = {}
        try:
            import time
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException
            from senamhi import DEPARTAMENTOS

            scraper_instance = SenamhiScraper()
            MARCADOR = ".leaflet-marker-icon"

            for dep in DEPARTAMENTOS:
                dep_nombre = dep.replace("-", " ").upper()
                result[dep] = {}

                progress_queue.put(json.dumps({
                    "tipo": "dep_inicio", "dep": dep, "dep_nombre": dep_nombre
                }))

                try:
                    scraper_instance.driver.get(
                        f"https://www.senamhi.gob.pe/main.php?dp={dep}&p=estaciones")
                    time.sleep(3)
                    scraper_instance._ir_nivel1_mapa()
                except Exception as e:
                    progress_queue.put(json.dumps({
                        "tipo": "dep_error", "dep": dep,
                        "dep_nombre": dep_nombre, "msg": str(e)
                    }))
                    continue

                try:
                    WebDriverWait(scraper_instance.driver, 30).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, MARCADOR)))
                    time.sleep(2)
                    marcadores = scraper_instance.driver.find_elements(By.CSS_SELECTOR, MARCADOR)
                    total = len(marcadores)

                    progress_queue.put(json.dumps({
                        "tipo": "dep_total", "dep": dep,
                        "dep_nombre": dep_nombre, "total": total
                    }))

                    for idx in range(total):
                        try:
                            marcadores = scraper_instance.driver.find_elements(By.CSS_SELECTOR, MARCADOR)
                            if idx >= len(marcadores):
                                break
                            scraper_instance.driver.execute_script(
                                "arguments[0].click();", marcadores[idx])
                            time.sleep(2)
                            nombre, tipo = scraper_instance._leer_metadatos_popup(dep)
                            if tipo not in result[dep]:
                                result[dep][tipo] = []
                            if nombre not in result[dep][tipo]:
                                result[dep][tipo].append(nombre)
                            progress_queue.put(json.dumps({
                                "tipo": "estacion", "dep": dep,
                                "dep_nombre": dep_nombre,
                                "idx": idx + 1, "total": total,
                                "nombre": nombre, "tipo_est": tipo
                            }))
                            scraper_instance._forzar_cerrar_modal()
                            scraper_instance.driver.switch_to.default_content()
                            scraper_instance._ir_nivel1_mapa()
                        except Exception:
                            try:
                                scraper_instance._forzar_cerrar_modal()
                                scraper_instance.driver.switch_to.default_content()
                                scraper_instance._ir_nivel1_mapa()
                            except:
                                pass

                except TimeoutException:
                    progress_queue.put(json.dumps({
                        "tipo": "dep_vacio", "dep": dep, "dep_nombre": dep_nombre
                    }))
                except Exception as e:
                    progress_queue.put(json.dumps({
                        "tipo": "dep_error", "dep": dep,
                        "dep_nombre": dep_nombre, "msg": str(e)
                    }))
                finally:
                    try:
                        scraper_instance.driver.switch_to.default_content()
                    except:
                        pass

                progress_queue.put(json.dumps({
                    "tipo": "dep_ok", "dep": dep, "dep_nombre": dep_nombre,
                    "subtotales": {t: len(e) for t, e in result[dep].items()}
                }))

            with open(INVENTARIO_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            progress_queue.put(json.dumps({"tipo": "sondeo_ok"}))

        except Exception as e:
            progress_queue.put(json.dumps({"tipo": "error_fatal", "msg": str(e)}))
        finally:
            operacion_activa = False
            try:
                scraper_instance.cerrar()
            except:
                pass

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True})


# ── DESCARGA ─────────────────────────────────────────────────

@app.route("/api/descargar", methods=["POST"])
def descargar():
    global operacion_activa, scraper_instance
    if operacion_activa:
        return jsonify({"ok": False, "error": "Operación en curso"}), 400

    data      = request.get_json()
    seleccion = [tuple(x) for x in data.get("seleccion", [])]
    if not seleccion:
        return jsonify({"ok": False, "error": "Sin selección"}), 400
    if not os.path.exists(INVENTARIO_FILE):
        return jsonify({"ok": False, "error": "Primero realiza el sondeo"}), 400

    with open(INVENTARIO_FILE, "r", encoding="utf-8") as f:
        inventario = json.load(f)

    def _run():
        global operacion_activa, scraper_instance
        operacion_activa = True
        try:
            scraper_instance = SenamhiScraper()
            total_est = len(seleccion)
            for i, (dep, tipo_f, nombre_f) in enumerate(seleccion, 1):
                progress_queue.put(json.dumps({
                    "tipo": "descarga_est",
                    "idx": i, "total": total_est,
                    "dep_nombre": dep.replace("-", " ").upper(),
                    "nombre": nombre_f or "—",
                    "tipo_est": tipo_f or "—"
                }))
                scraper_instance.descargar_seleccion(
                    [(dep, tipo_f, nombre_f)], inventario)
            progress_queue.put(json.dumps({"tipo": "descarga_ok"}))
        except Exception as e:
            progress_queue.put(json.dumps({"tipo": "error_fatal", "msg": str(e)}))
        finally:
            operacion_activa = False
            try:
                scraper_instance.cerrar()
            except:
                pass

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"ok": True})


# ── SSE ──────────────────────────────────────────────────────

@app.route("/api/progreso")
def progreso_stream():
    def _gen():
        while True:
            try:
                msg = progress_queue.get(timeout=30)
                yield f"data: {msg}\n\n"
            except queue.Empty:
                yield 'data: {"tipo":"ping"}\n\n'

    return Response(
        _gen(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=False, port=5000, threaded=True)
