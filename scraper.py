"""
SENAMHI Scraper v4
==================
Estrategia REAL y definitiva:
  1. Selenium abre la página de descarga de la región
  2. Espera que el JS cargue la lista de estaciones  
  3. Para CADA estación hace clic → espera el popup/panel
  4. Captura TODOS los links href que terminen en .xlsx o .xls
  5. Descarga cada Excel con requests (sin manipularlo, tal cual)
  6. Los mete en ZIP organizado por: TipoEstacion/NombreEstacion/Año/archivo.xlsx

NO se genera ningún Excel nuevo — se descargan LOS ORIGINALES del servidor.
"""

import os, re, time, json, zipfile, logging, threading, requests
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from urllib.parse import urljoin, urlparse

import urllib3
urllib3.disable_warnings()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException,
    ElementClickInterceptedException, WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("senamhi")

BASE = "https://www.senamhi.gob.pe"

REGIONES = {
    "amazonas":     "Amazonas",
    "ancash":       "Ancash",
    "apurimac":     "Apurimac",
    "arequipa":     "Arequipa",
    "ayacucho":     "Ayacucho",
    "cajamarca":    "Cajamarca",
    "cusco":        "Cusco",
    "huancavelica": "Huancavelica",
    "huanuco":      "Huanuco",
    "ica":          "Ica",
    "junin":        "Junin",
    "la-libertad":  "La_Libertad",
    "lambayeque":   "Lambayeque",
    "lima":         "Lima",
    "loreto":       "Loreto",
    "madre-de-dios":"Madre_de_Dios",
    "moquegua":     "Moquegua",
    "pasco":        "Pasco",
    "piura":        "Piura",
    "puno":         "Puno",
    "san-martin":   "San_Martin",
    "tacna":        "Tacna",
    "tumbes":       "Tumbes",
    "ucayali":      "Ucayali",
}

TIPOS = {
    "CON": "Meteorologica_Convencional",
    "AUT": "Meteorologica_Automatica",
    "SUT": "Meteorologica_Automatica",
    "HCO": "Hidrologica_Convencional",
    "HAU": "Hidrologica_Automatica",
}

# ── Progreso compartido ────────────────────────────────────────────────────────
progreso = {
    "estado": "idle", "mensaje": "", "porcentaje": 0,
    "zip_path": None, "errores": [],
    "total": 0, "procesadas": 0, "excel_encontrados": 0,
}
_lock = threading.Lock()

def upd(estado=None, msg=None, pct=None, zip_=None,
        err=None, total=None, proc=None, excel=None):
    with _lock:
        if estado  is not None: progreso["estado"]           = estado
        if msg     is not None: progreso["mensaje"]          = msg
        if pct     is not None: progreso["porcentaje"]       = int(min(pct, 100))
        if zip_    is not None: progreso["zip_path"]         = zip_
        if err     is not None: progreso["errores"].append(str(err)[:120])
        if total   is not None: progreso["total"]            = total
        if proc    is not None: progreso["procesadas"]       = proc
        if excel   is not None: progreso["excel_encontrados"]= excel
    if msg: log.info(msg)


# ══════════════════════════════════════════════════════════════════════════════
#  DRIVER
# ══════════════════════════════════════════════════════════════════════════════
def make_driver(download_dir: str):
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--log-level=3")
    opts.add_experimental_option("excludeSwitches",
                                 ["enable-automation", "enable-logging"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    # Configurar carpeta de descarga automática
    prefs = {
        "download.default_directory": str(Path(download_dir).resolve()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "plugins.always_open_pdf_externally": True,
    }
    opts.add_experimental_option("prefs", prefs)

    svc = Service(ChromeDriverManager().install())
    drv = webdriver.Chrome(service=svc, options=opts)
    drv.set_page_load_timeout(45)
    drv.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return drv


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRAER TODOS LOS LINKS .XLSX DE LA PÁGINA (via JS + DOM)
# ══════════════════════════════════════════════════════════════════════════════
def extraer_links_excel_pagina(driver):
    """
    Extrae TODOS los href que apunten a archivos .xlsx o .xls
    en el DOM actual (incluyendo los cargados dinámicamente).
    """
    try:
        links_raw = driver.execute_script("""
            var links = [];
            // Todos los <a href>
            document.querySelectorAll('a[href]').forEach(function(a) {
                var h = a.href || '';
                if (h.match(/\\.xlsx?($|\\?)/i)) {
                    links.push({
                        url: h,
                        texto: (a.textContent || '').trim().substring(0, 80)
                    });
                }
            });
            // También buscar en atributos data- y onclick
            document.querySelectorAll('[data-url],[data-href],[data-file]').forEach(function(el) {
                ['data-url','data-href','data-file'].forEach(function(attr) {
                    var v = el.getAttribute(attr) || '';
                    if (v.match(/\\.xlsx?($|\\?)/i)) {
                        links.push({url: v, texto: (el.textContent||'').trim().substring(0,80)});
                    }
                });
            });
            // Buscar en el HTML fuente links xlsx
            var html = document.documentElement.innerHTML;
            var re = /["'](https?:\\/\\/[^"']*\\.xlsx?)[^"']*/gi;
            var m;
            while ((m = re.exec(html)) !== null) {
                links.push({url: m[1], texto: 'found_in_html'});
            }
            // Deduplicar por URL
            var seen = {};
            return links.filter(function(l) {
                if (seen[l.url]) return false;
                seen[l.url] = true;
                return true;
            });
        """)
        return links_raw or []
    except Exception as e:
        log.debug(f"extraer_links_excel: {e}")
        return []


def extraer_info_estaciones_js(driver):
    """
    Extrae la lista de estaciones desde variables JS del mapa Leaflet.
    Devuelve lista de dicts con cod, nombre, tipo.
    """
    try:
        raw = driver.execute_script("""
            // Buscar en todas las variables globales un array de estaciones
            var result = [];
            var checked = {};
            for (var k in window) {
                try {
                    var v = window[k];
                    if (Array.isArray(v) && v.length > 0 && !checked[k]) {
                        checked[k] = true;
                        var item = v[0];
                        if (item && typeof item === 'object' &&
                            (item.cod_est || item.COD_EST || item.codigo ||
                             item.CODIGO || item.estacion || item.ESTACION)) {
                            result = v;
                            break;
                        }
                    }
                } catch(e) {}
            }
            return JSON.stringify(result);
        """)
        if raw:
            data = json.loads(raw)
            estaciones = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                cod = str(
                    item.get("cod_est") or item.get("COD_EST") or
                    item.get("codigo") or item.get("CODIGO") or ""
                ).strip()
                if not cod:
                    continue
                nom = str(
                    item.get("nom_est") or item.get("NOM_EST") or
                    item.get("nombre") or item.get("ESTACION") or
                    item.get("estacion") or f"Est_{cod}"
                ).strip()
                tip = str(
                    item.get("tip_est") or item.get("TIP_EST") or
                    item.get("tipo") or item.get("TIPO") or "CON"
                ).strip().upper()
                estaciones.append({
                    "cod": cod.zfill(6),
                    "nombre": nom,
                    "tipo": tip,
                })
            return estaciones
    except Exception as e:
        log.debug(f"extraer_info_estaciones_js: {e}")
    return []


# ══════════════════════════════════════════════════════════════════════════════
#  DESCARGAR UN EXCEL CON REQUESTS
# ══════════════════════════════════════════════════════════════════════════════
def descargar_excel(url, session, timeout=30):
    """
    Descarga un archivo Excel de la URL dada.
    Retorna los bytes del archivo, o None si falla.
    """
    try:
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36",
            "Referer": BASE,
            "Accept": "application/vnd.openxmlformats-officedocument"
                      ".spreadsheetml.sheet,application/vnd.ms-excel,*/*",
        }
        r = session.get(url, headers=hdrs, timeout=timeout, verify=False,
                        allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 200:
            # Verificar que no sea HTML (página de error/login)
            ct = r.headers.get("Content-Type", "")
            if "html" in ct and len(r.content) < 5000:
                return None
            # Verificar que tenga cabecera de ZIP (xlsx = zip)
            if r.content[:4] in (b'PK\x03\x04', b'PK\x05\x06') or \
               b'\xd0\xcf\x11\xe0' == r.content[:4]:  # .xls viejo
                return r.content
            # Si es grande igual lo intentamos
            if len(r.content) > 2000:
                return r.content
        return None
    except Exception as e:
        log.debug(f"descargar_excel {url}: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  INFERIR METADATOS DEL URL (tipo estacion, nombre, año, mes)
# ══════════════════════════════════════════════════════════════════════════════
def inferir_meta(url, texto_link=""):
    """
    Del URL y texto del link infiere: tipo_estacion, nombre, año, mes, nombre_archivo.
    """
    url_lower = url.lower()
    texto = (texto_link or "").strip()

    # Nombre del archivo desde el URL
    path = urlparse(url).path
    filename = Path(path).name or "datos.xlsx"
    if not filename.lower().endswith((".xlsx", ".xls")):
        filename += ".xlsx"

    # Año: buscar 4 dígitos que parezcan año
    anio_match = re.search(r'\b(19[5-9]\d|20[0-3]\d)\b', url + " " + texto)
    anio = anio_match.group(1) if anio_match else "0000"

    # Mes
    mes_match = re.search(r'[_\-/](\d{1,2})[_\-/]', url)
    mes = f"{int(mes_match.group(1)):02d}" if mes_match else "00"

    # Tipo de estación desde URL o texto
    tipo = "Meteorologica_Convencional"
    for key, label in [
        ("hco", "Hidrologica_Convencional"),
        ("hau", "Hidrologica_Automatica"),
        ("hid", "Hidrologica_Convencional"),
        ("aut", "Meteorologica_Automatica"),
        ("sut", "Meteorologica_Automatica"),
        ("con", "Meteorologica_Convencional"),
        ("met", "Meteorologica_Convencional"),
    ]:
        if key in url_lower or key in texto.lower():
            tipo = label
            break

    # Nombre de estación desde texto del link o URL
    nombre = texto if texto and texto != "found_in_html" else ""
    if not nombre:
        # Intentar extraer del path
        parts = path.strip("/").split("/")
        for part in reversed(parts):
            if len(part) > 3 and not part.lower().endswith((".xlsx", ".xls", ".php")):
                nombre = part.replace("_", " ").replace("-", " ").title()
                break
    if not nombre:
        nombre = filename.replace(".xlsx", "").replace(".xls", "")

    # Limpiar nombre para filesystem
    nombre_safe = re.sub(r'[\\/:*?"<>|]', '_', nombre).strip()[:50]

    return {
        "tipo": tipo,
        "nombre": nombre_safe or "Estacion",
        "anio": anio,
        "mes": mes,
        "filename": filename,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPING PRINCIPAL — NAVEGAR Y RECOLECTAR TODOS LOS EXCEL
# ══════════════════════════════════════════════════════════════════════════════
def recolectar_excel_region(driver, region_key, session):
    """
    Navega la página de descarga de la región.
    Estrategia multi-capa para encontrar TODOS los links Excel:
      A) Links .xlsx directamente en el HTML inicial
      B) Hacer clic en cada marcador del mapa → capturar links que aparecen
      C) Hacer clic en cada fila/botón de la tabla de estaciones → capturar links
      D) Buscar en todo el page_source links xlsx con regex
    
    Retorna: lista de {url, meta}
    """
    url_descarga = f"{BASE}/main.php?dp={region_key}&p=descarga-datos-hidrometeorologicos"
    url_estaciones = f"{BASE}/main.php?dp={region_key}&p=estaciones"

    todos_los_links = {}  # url -> meta

    def agregar_links(links_nuevos, fuente=""):
        for item in links_nuevos:
            u = item.get("url", "")
            if not u:
                continue
            # Normalizar URL relativa
            if u.startswith("/"):
                u = BASE + u
            elif not u.startswith("http"):
                u = BASE + "/" + u.lstrip("/")
            if u not in todos_los_links:
                meta = inferir_meta(u, item.get("texto", ""))
                todos_los_links[u] = meta
                log.debug(f"  Link encontrado ({fuente}): {u}")

    # ── A: Página de descarga directa ─────────────────────────────────────
    upd(msg=f"Cargando página de descarga de {REGIONES[region_key]}...")
    try:
        driver.get(url_descarga)
        time.sleep(6)
        links = extraer_links_excel_pagina(driver)
        agregar_links(links, "descarga_directa")
        log.info(f"  Descarga directa: {len(links)} links")
    except Exception as e:
        log.warning(f"  Error cargando descarga directa: {e}")

    # También buscar en el HTML completo con regex
    try:
        src = driver.page_source
        matches = re.findall(
            r'(?:href|src|url|data-url|data-href)[=:\s]+["\']([^"\']*\.xlsx?[^"\']*)["\']',
            src, re.IGNORECASE
        )
        for m in matches:
            url_abs = m if m.startswith("http") else BASE + "/" + m.lstrip("/")
            todos_los_links[url_abs] = inferir_meta(url_abs)
        log.info(f"  Regex en descarga: {len(matches)} matches")
    except Exception as e:
        log.debug(f"  Regex descarga: {e}")

    # ── B: Página de estaciones (mapa con marcadores) ──────────────────────
    upd(msg="Analizando mapa de estaciones...")
    try:
        driver.get(url_estaciones)
        time.sleep(7)

        # Extraer info de estaciones del JS
        estaciones_js = extraer_info_estaciones_js(driver)
        log.info(f"  Estaciones JS: {len(estaciones_js)}")

        # Links en la página de estaciones
        links = extraer_links_excel_pagina(driver)
        agregar_links(links, "mapa_inicial")

        # Hacer clic en cada marcador del mapa para abrir popup
        marcadores = driver.find_elements(
            By.CSS_SELECTOR,
            ".leaflet-marker-icon, .leaflet-marker-pane img, "
            "[class*='marker'], [class*='estacion-marker']"
        )
        log.info(f"  Marcadores en mapa: {len(marcadores)}")

        upd(msg=f"Explorando {len(marcadores)} marcadores del mapa...",
            total=len(marcadores))

        for i, marcador in enumerate(marcadores):
            try:
                upd(pct=5 + int((i / max(len(marcadores), 1)) * 30),
                    proc=i,
                    msg=f"Marcador {i+1}/{len(marcadores)}...")

                driver.execute_script("arguments[0].scrollIntoView(true);", marcador)
                driver.execute_script("arguments[0].click();", marcador)
                time.sleep(1.5)

                # Capturar links del popup
                links_popup = extraer_links_excel_pagina(driver)
                agregar_links(links_popup, f"popup_{i}")

                # Cerrar popup si existe
                try:
                    close_btn = driver.find_element(
                        By.CSS_SELECTOR,
                        ".leaflet-popup-close-button, [class*='close'], "
                        "button[aria-label='Close']"
                    )
                    close_btn.click()
                    time.sleep(0.3)
                except Exception:
                    pass

            except (StaleElementReferenceException,
                    ElementClickInterceptedException) as e:
                log.debug(f"  Marcador {i}: {e}")
                continue
            except Exception as e:
                log.debug(f"  Marcador {i} error: {e}")
                continue

    except Exception as e:
        log.warning(f"  Error en página estaciones: {e}")

    # ── C: Buscar paneles/tablas con listado de estaciones ─────────────────
    upd(msg="Buscando tablas de estaciones con links Excel...")
    try:
        # Hacer clic en cada fila de tabla que tenga links xlsx
        filas = driver.find_elements(
            By.CSS_SELECTOR,
            "table tr td a, .lista-estaciones a, .estacion-item a, "
            "[class*='estacion'] a, [class*='station'] a"
        )
        for fila in filas[:100]:  # límite de 100
            try:
                href = fila.get_attribute("href") or ""
                if href.lower().endswith((".xlsx", ".xls")):
                    todos_los_links[href] = inferir_meta(
                        href, fila.text.strip()[:80]
                    )
            except Exception:
                pass
    except Exception as e:
        log.debug(f"  Tablas: {e}")

    # ── D: Buscar endpoints AJAX que devuelvan links Excel ─────────────────
    upd(msg="Buscando endpoints adicionales de descarga...")
    # Intentar endpoints conocidos de SENAMHI directamente con requests
    hdrs = {
        "User-Agent": "Mozilla/5.0",
        "Referer": url_descarga,
        "X-Requested-With": "XMLHttpRequest",
    }
    endpoints_ajax = [
        f"{BASE}/main.php?dp={region_key}&p=descarga-datos-hidrometeorologicos&format=json",
        f"{BASE}/mapas/descarga-datos/map_hist_data.php?dp={region_key}",
        f"{BASE}/site/senamhi-estaciones/get_archivos.php?dp={region_key}",
        f"{BASE}/site/descarga-datos/get_archivos.php?dp={region_key}",
    ]
    for ep in endpoints_ajax:
        try:
            r = session.get(ep, headers=hdrs, timeout=10, verify=False)
            if r.status_code == 200 and len(r.text) > 50:
                # Buscar links xlsx en la respuesta
                matches = re.findall(
                    r'["\']([^"\']*\.xlsx?[^"\']*)["\']', r.text, re.IGNORECASE
                )
                for m in matches:
                    u = m if m.startswith("http") else BASE + "/" + m.lstrip("/")
                    todos_los_links[u] = inferir_meta(u)
                if matches:
                    log.info(f"  AJAX {ep}: {len(matches)} links")
        except Exception:
            pass

    log.info(f"TOTAL links Excel encontrados: {len(todos_los_links)}")
    return todos_los_links


# ══════════════════════════════════════════════════════════════════════════════
#  CREAR ZIP CON LOS EXCELS DESCARGADOS
# ══════════════════════════════════════════════════════════════════════════════
def crear_zip_con_excels(region_key, archivos_descargados, output_dir):
    """
    archivos_descargados: lista de {meta: {...}, bytes: b'...'}
    Estructura ZIP:
      {Region}/
      ├── {Tipo}/
      │   └── {Nombre}/
      │       └── archivo_original.xlsx
      └── INDICE.txt
    """
    nom_reg = REGIONES.get(region_key, region_key)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"SENAMHI_{nom_reg}_{ts}.zip"
    zip_path = Path(output_dir) / zip_name
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    indice_lineas = [
        f"SENAMHI — Datos Hidrometeorológicos",
        f"Región: {nom_reg}",
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total archivos: {len(archivos_descargados)}",
        "=" * 60,
        "",
    ]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # Contador para nombres únicos
        nombres_usados = defaultdict(int)

        for item in archivos_descargados:
            meta      = item["meta"]
            data      = item["bytes"]
            tipo      = meta["tipo"]
            nombre    = meta["nombre"]
            anio      = meta["anio"]
            filename  = meta["filename"]

            # Garantizar nombre único
            ruta_base = f"{nom_reg}/{tipo}/{nombre}/{anio}"
            clave = f"{ruta_base}/{filename}"
            if clave in nombres_usados:
                nombres_usados[clave] += 1
                stem = Path(filename).stem
                ext  = Path(filename).suffix
                filename_final = f"{stem}_{nombres_usados[clave]}{ext}"
            else:
                nombres_usados[clave] = 0
                filename_final = filename

            ruta_zip = f"{nom_reg}/{tipo}/{nombre}/{anio}/{filename_final}"
            zf.writestr(ruta_zip, data)

            indice_lineas.append(
                f"{tipo:35s} | {nombre:40s} | {anio} | {filename_final}"
            )

        # Agregar índice de texto
        zf.writestr(
            f"{nom_reg}/INDICE.txt",
            "\n".join(indice_lineas)
        )

    sz = zip_path.stat().st_size
    log.info(f"ZIP: {zip_path} ({sz // 1024:,} KB, {len(archivos_descargados)} archivos)")
    return str(zip_path)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
def scrape_region(region_key, output_dir="./output"):
    if region_key not in REGIONES:
        raise ValueError(f"Región no válida: '{region_key}'")

    with _lock:
        progreso.update({
            "errores": [], "zip_path": None,
            "total": 0, "procesadas": 0, "excel_encontrados": 0,
        })

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    nom_reg = REGIONES[region_key]

    upd(estado="corriendo", msg=f"Iniciando scraping de {nom_reg}...", pct=2)

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36",
    })

    driver = None
    try:
        upd(msg="Iniciando Chrome headless...", pct=3)
        driver = make_driver(output_dir)

        # ── Paso 1: Recolectar todos los links Excel ───────────────────────
        upd(msg="Explorando el sitio SENAMHI buscando archivos Excel...", pct=5)
        todos_links = recolectar_excel_region(driver, region_key, session)

        if not todos_links:
            upd(estado="error",
                msg="No se encontraron archivos Excel en el sitio para esta región.",
                pct=100)
            return None

        upd(msg=f"Encontrados {len(todos_links)} archivos Excel. Descargando...",
            pct=37, total=len(todos_links), excel=len(todos_links))

        # Transferir cookies de Selenium a requests
        try:
            for cookie in driver.get_cookies():
                session.cookies.set(cookie["name"], cookie["value"])
        except Exception:
            pass

    except Exception as e:
        upd(estado="error", msg=f"Error Chrome: {e}", err=str(e))
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    # ── Paso 2: Descargar cada Excel (sin Selenium — solo requests) ────────
    archivos_ok = []
    total = len(todos_links)

    for idx, (url, meta) in enumerate(todos_links.items()):
        pct = 37 + int((idx / total) * 55)
        upd(
            msg=f"[{idx+1}/{total}] Descargando: {meta['filename']}",
            pct=pct, proc=idx + 1,
        )
        data = descargar_excel(url, session)
        if data:
            archivos_ok.append({"meta": meta, "bytes": data})
            log.info(f"  ✓ {meta['filename']} ({len(data)//1024} KB)")
        else:
            upd(err=f"No descargado: {url[:80]}")
            log.warning(f"  ✗ {url[:80]}")

    if not archivos_ok:
        upd(estado="error",
            msg="Se encontraron links pero no se pudo descargar ningún archivo. "
                "Puede que el servidor requiera autenticación.",
            pct=100)
        return None

    upd(msg=f"Descargados {len(archivos_ok)}/{total} archivos. Empaquetando ZIP...",
        pct=93, proc=total)

    # ── Paso 3: Crear ZIP ──────────────────────────────────────────────────
    try:
        zip_path = crear_zip_con_excels(region_key, archivos_ok, output_dir)
        upd(
            estado="listo",
            msg=f"✓ Listo. {len(archivos_ok)} archivos Excel en el ZIP.",
            pct=100, zip_=zip_path, proc=total,
        )
        return zip_path
    except Exception as e:
        upd(estado="error", msg=f"Error creando ZIP: {e}", err=str(e))
        raise


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="SENAMHI Scraper v4 — descarga Excel reales")
    p.add_argument("region", help=f"Región: {', '.join(REGIONES)}")
    p.add_argument("--output", default="./output")
    a = p.parse_args()
    try:
        z = scrape_region(a.region.lower(), a.output)
        print(f"\n✅  ZIP generado: {z}")
    except ValueError as e:
        print(f"❌  {e}")
