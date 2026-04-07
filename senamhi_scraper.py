import os
import time
import shutil
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc

from senamhi_config import DEPARTAMENTOS, resolver_tipo, limpiar_nombre, dep_display


# ═══════════════════════════════════════════════════════════════
#  SCRAPER
# ═══════════════════════════════════════════════════════════════

class SenamhiScraper:
    def __init__(self, base_dir="D:\\SENAMI\\estaciones_senamhi"):
        self.base_dir = base_dir
        self.temp_dir = os.path.abspath(
            os.path.join(os.path.dirname(base_dir), "temp_downloads"))
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

        options = uc.ChromeOptions()
        options.add_experimental_option("prefs", {
            "download.default_directory": self.temp_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
        })
        print("Iniciando navegador...")
        self.driver = uc.Chrome(options=options, version_main=146)
        self.driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
            "behavior": "allow", "downloadPath": self.temp_dir, "eventsEnabled": True
        })
        self.wait = WebDriverWait(self.driver, 45)

    # ── Utilidades ────────────────────────────────────────────

    def limpiar_temp(self):
        for f in os.listdir(self.temp_dir):
            try: os.remove(os.path.join(self.temp_dir, f))
            except: pass

    def wait_for_download(self, timeout=10):
        for _ in range(timeout):
            time.sleep(1)
            v = [f for f in os.listdir(self.temp_dir)
                 if not f.endswith(".crdownload") and not f.endswith(".tmp")]
            if v:
                return os.path.join(self.temp_dir, v[0])
        return None

    # ── Navegación de iframes ─────────────────────────────────

    def _ir_nivel1_mapa(self):
        self.driver.switch_to.default_content()
        f = self.wait.until(EC.presence_of_element_located(
            (By.XPATH, "//iframe[contains(@src,'mapa-estaciones')]")))
        self.driver.switch_to.frame(f)

    def _ir_nivel2_modal(self):
        popup = self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".leaflet-popup-content")))
        self.driver.switch_to.frame(popup.find_element(By.TAG_NAME, "iframe"))
        WebDriverWait(self.driver, 45).until(
            EC.presence_of_element_located((By.ID, "CBOFiltro")))

    def _ir_nivel3_tabla(self):
        sub = WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        self.driver.switch_to.frame(sub)
        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.ID, "export2")))

    def _reconectar_completo(self):
        self.driver.switch_to.default_content()
        self._ir_nivel1_mapa()
        self._ir_nivel2_modal()
        self._ir_nivel3_tabla()
        time.sleep(1)

    def _forzar_cerrar_modal(self):
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, ".leaflet-popup-close-button")
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        except: pass

    # ── Leer metadatos ────────────────────────────────────────

    def _leer_metadatos(self, dep_url: str):
        nombre = "DESCONOCIDA"
        tipo   = "ESTACION DESCONOCIDA"
        dep    = dep_url.upper()

        try:
            textos = self.driver.execute_script("""
                return Array.from(document.querySelectorAll('td, font, b, span, div, p'))
                    .map(el => el.textContent.trim().toUpperCase())
                    .filter(t => t.length > 0);
            """)
            textos.sort(key=len)

            for txt in textos:
                if "ESTACI" in txt and ":" in txt and nombre == "DESCONOCIDA":
                    cand = txt.split("CODIGO")[0].split(":", 1)[-1].replace('"','').strip()
                    if cand:
                        nombre = limpiar_nombre(cand)
                if tipo == "ESTACION DESCONOCIDA":
                    if ("CONVENCIONAL" in txt or "AUTOM" in txt) and \
                       ("METEOROL" in txt or "HIDROL" in txt):
                        tipo = resolver_tipo(txt)

            # Departamento: td siguiente al label "Departamento" (evita confundir con Distrito)
            try:
                td = self.driver.find_element(By.XPATH,
                    "//td[.//div[contains(translate(text(),"
                    "'departamento','DEPARTAMENTO'),'DEPARTAMENTO')]"
                    "]/following-sibling::td[1]")
                dep = limpiar_nombre(td.text.strip().upper())
            except: pass

        except Exception as e:
            print(f"    [!] Error metadatos: {e}")

        return nombre, tipo, dep

    # ─────────────────────────────────────────────────────────
    #  FASE 1: SONDEO (construye inventario sin descargar nada)
    # ─────────────────────────────────────────────────────────

    def _leer_metadatos_popup(self, dep_url: str):
        """Lee nombre y tipo desde el popup SIN entrar a la pestaña Tabla.
        Más rápido para el sondeo."""
        nombre = "DESCONOCIDA"
        tipo   = "ESTACION DESCONOCIDA"
        try:
            # Entrar al iframe del popup (nivel 2 básico, sin esperar CBOFiltro)
            popup = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".leaflet-popup-content")))
            self.driver.switch_to.frame(popup.find_element(By.TAG_NAME, "iframe"))
            time.sleep(2)

            textos = self.driver.execute_script("""
                return Array.from(document.querySelectorAll('td, font, b, span, div, p'))
                    .map(el => el.textContent.trim().toUpperCase())
                    .filter(t => t.length > 0);
            """)
            textos.sort(key=len)

            for txt in textos:
                if "ESTACI" in txt and ":" in txt and nombre == "DESCONOCIDA":
                    cand = txt.split("CODIGO")[0].split(":", 1)[-1].replace('"','').strip()
                    if cand:
                        nombre = limpiar_nombre(cand)
                if tipo == "ESTACION DESCONOCIDA":
                    if ("CONVENCIONAL" in txt or "AUTOM" in txt) and \
                       ("METEOROL" in txt or "HIDROL" in txt):
                        tipo = resolver_tipo(txt)

            self.driver.switch_to.parent_frame()
        except Exception as e:
            try: self.driver.switch_to.parent_frame()
            except: pass

        return nombre, tipo

    def sondear_inventario(self) -> dict:
        """
        Recorre todos los departamentos y estaciones sin descargar nada.
        Devuelve un dict:
          { "amazonas": { "ESTACION METEOROLOGICA CONVENCIONAL": ["CHIRIACO", ...], ... }, ... }
        """
        inventario = {}
        MARCADOR = ".leaflet-marker-icon"

        for dep in DEPARTAMENTOS:
            print(f"\n[SONDEO] {dep_display(dep)}...")
            inventario[dep] = {}

            try:
                self.driver.get(
                    f"https://www.senamhi.gob.pe/main.php?dp={dep}&p=estaciones")
                time.sleep(3)
                self._ir_nivel1_mapa()
            except Exception as e:
                print(f"  [!] Error cargando {dep}: {e}")
                continue

            try:
                self.wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, MARCADOR)))
                time.sleep(2)
                marcadores = self.driver.find_elements(By.CSS_SELECTOR, MARCADOR)
                total = len(marcadores)
                print(f"  {total} estaciones encontradas")

                for idx in range(total):
                    try:
                        marcadores = self.driver.find_elements(By.CSS_SELECTOR, MARCADOR)
                        if idx >= len(marcadores): break

                        self.driver.execute_script("arguments[0].click();", marcadores[idx])
                        time.sleep(2)

                        nombre, tipo = self._leer_metadatos_popup(dep)

                        if tipo not in inventario[dep]:
                            inventario[dep][tipo] = []
                        if nombre not in inventario[dep][tipo]:
                            inventario[dep][tipo].append(nombre)

                        print(f"    [{idx+1}/{total}] {nombre} — {tipo}")

                        # Cerrar popup y volver al iframe del mapa
                        self._forzar_cerrar_modal()
                        self.driver.switch_to.default_content()
                        self._ir_nivel1_mapa()

                    except Exception as ex:
                        print(f"    [!] Error en marcador #{idx}: {ex}")
                        try:
                            self._forzar_cerrar_modal()
                            self.driver.switch_to.default_content()
                            self._ir_nivel1_mapa()
                        except: pass

            except TimeoutException:
                print(f"  [!] Sin marcadores en {dep}")
            except Exception as e:
                print(f"  [!] Error: {e}")
            finally:
                self.driver.switch_to.default_content()

        return inventario

    # ─────────────────────────────────────────────────────────
    #  FASE 2: DESCARGA según selección
    # ─────────────────────────────────────────────────────────

    def descargar_seleccion(self, seleccion: list, inventario: dict):
        """
        seleccion: lista de (dep_url, tipo_filtro, nombre_filtro)
          - tipo_filtro y nombre_filtro = None → descargar todo el departamento
        """
        for (dep, tipo_filtro, nombre_filtro) in seleccion:
            print(f"\n{'='*60}\nDescargando: {dep_display(dep)}\n{'='*60}")

            try:
                self.driver.get(
                    f"https://www.senamhi.gob.pe/main.php?dp={dep}&p=estaciones")
                time.sleep(3)
                self._ir_nivel1_mapa()
            except Exception as e:
                print(f"  [!] Error cargando {dep}: {e}")
                continue

            MARCADOR = ".leaflet-marker-icon"
            try:
                self.wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, MARCADOR)))
                time.sleep(2)
                marcadores = self.driver.find_elements(By.CSS_SELECTOR, MARCADOR)
                total = len(marcadores)
                print(f"  [✓] {total} estaciones en {dep_display(dep)}")

                for idx in range(total):
                    try:
                        marcadores = self.driver.find_elements(By.CSS_SELECTOR, MARCADOR)
                        if idx >= len(marcadores): break

                        self.driver.execute_script("arguments[0].click();", marcadores[idx])
                        time.sleep(3)

                        self._extraer_estacion(dep, tipo_filtro, nombre_filtro)

                    except Exception as ex:
                        print(f"  [!] Error en marcador #{idx}: {ex}")
                        self._forzar_cerrar_modal()

            except TimeoutException:
                print(f"  [!] Sin marcadores en {dep}")
            except Exception as e:
                print(f"  [!] Error: {e}")
            finally:
                self.driver.switch_to.default_content()

    def _extraer_estacion(self, dep_url: str, tipo_filtro, nombre_filtro):
        try:
            popup = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".leaflet-popup-content")))
            time.sleep(1)
            self.driver.switch_to.frame(popup.find_element(By.TAG_NAME, "iframe"))

            try:
                tab = self.wait.until(EC.presence_of_element_located((By.ID, "tabla-tab")))
                time.sleep(1)
                self.driver.execute_script("arguments[0].click();", tab)
            except TimeoutException:
                print("    [!] Pestaña Tabla no encontrada.")
                return

            print("    [⏳] Esperando tabla...")
            try:
                WebDriverWait(self.driver, 60).until(
                    EC.presence_of_element_located((By.ID, "CBOFiltro")))
                time.sleep(5)
            except TimeoutException:
                print("    [!] Timeout.")
                return

            nombre, tipo_carpeta, dep_carpeta = self._leer_metadatos(dep_url)

            # ── Aplicar filtro si el usuario eligió una estación específica ──
            if nombre_filtro and nombre.upper() != nombre_filtro.upper():
                print(f"    [-] Saltando {nombre} (no es la estación seleccionada)")
                return
            if tipo_filtro and tipo_carpeta != tipo_filtro:
                print(f"    [-] Saltando {nombre} (tipo no coincide)")
                return

            print(f"    [+] {nombre}  |  {tipo_carpeta}  |  {dep_carpeta}")
            ruta_final = os.path.join(self.base_dir, dep_carpeta, tipo_carpeta, nombre)
            os.makedirs(ruta_final, exist_ok=True)

            try:
                fechas = [o.text.strip()
                          for o in Select(self.driver.find_element(By.ID, "CBOFiltro")).options
                          if o.text.strip()]
                print(f"        {len(fechas)} meses.")
            except:
                print("    [!] Sin fechas.")
                return

            for fecha in fechas:
                try:
                    sel_el  = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "CBOFiltro")))
                    sel_obj = Select(sel_el)
                    if sel_obj.first_selected_option.text.strip() != fecha:
                        sel_obj.select_by_visible_text(fecha)
                        time.sleep(3)

                    self._reconectar_completo()
                    self.limpiar_temp()

                    try:
                        btn = WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.ID, "export2")))
                        self.driver.execute_script("arguments[0].click();", btn)

                        archivo = self.wait_for_download(timeout=10)
                        if archivo:
                            destino = os.path.join(ruta_final, f"{limpiar_nombre(fecha)}.csv")
                            if os.path.exists(destino): os.remove(destino)
                            shutil.move(archivo, destino)
                            print(f"      [✓] {fecha}.csv")
                        else:
                            print(f"      [-] Mes vacío: {fecha}")
                    except TimeoutException:
                        print(f"      [-] Sin botón exportar: {fecha}")

                    self.driver.switch_to.default_content()
                    self._ir_nivel1_mapa()
                    self._ir_nivel2_modal()

                except Exception as ef:
                    print(f"      [!] Error mes {fecha}: {ef}")
                    try:
                        self.driver.switch_to.default_content()
                        self._ir_nivel1_mapa()
                        self._ir_nivel2_modal()
                    except: pass

        except Exception as e:
            print(f"    [!] Error crítico: {e}")
        finally:
            try: self.driver.switch_to.parent_frame()
            except: pass
            self._forzar_cerrar_modal()

    def cerrar(self):
        print("\nCerrando navegador...")
        try: self.driver.quit()
        except: pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)
