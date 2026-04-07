# MENERIA VIII — Descargador de Estaciones SENAMHI

Herramienta para descargar datos históricos de estaciones meteorológicas e hidrológicas del [SENAMHI](https://www.senamhi.gob.pe) (Servicio Nacional de Meteorología e Hidrología del Perú). Permite sondear el inventario de estaciones por departamento y descargar los datos en formato CSV, tanto desde una interfaz web como desde la línea de comandos.

---

## Estructura del proyecto

```
MENERIA_VIII/
├── app.py                  # Servidor Flask (interfaz web)
├── senamhi.py              # Punto de entrada CLI
├── senamhi_scraper.py      # Lógica de scraping con Selenium
├── senamhi_config.py       # Configuración: departamentos, tipos de estación
├── senamhi_menu.py         # Menú interactivo de consola
├── templates/
│   └── index.html          # Interfaz web
├── inventario_senamhi.json # Inventario generado (se crea automáticamente)
├── estaciones_senamhi/     # Carpeta de destino de los CSV descargados
└── temp_downloads/         # Carpeta temporal durante las descargas
```

---

## Requisitos previos

- Python **3.10** o superior
- **Google Chrome** instalado
- `pip` actualizado

---

## Instalación

### 1. Clonar o descomprimir el proyecto

```bash
# Si descargaste el .rar, extráelo y entra a la carpeta:
cd MENERIA_VIII
```

### 2. (Recomendado) Crear un entorno virtual

```bash
python -m venv venv

# Activar en Windows:
venv\Scripts\activate

# Activar en Linux/macOS:
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install flask selenium undetected-chromedriver
```

> **Nota:** `undetected-chromedriver` descarga automáticamente el ChromeDriver compatible con tu versión de Chrome.

---

## Uso — Interfaz Web (recomendado)

### 1. Iniciar el servidor

```bash
python app.py
```

### 2. Abrir el navegador

Ve a: [http://localhost:5000](http://localhost:5000)

### 3. Sondear el inventario

Haz clic en **"Sondear Inventario"**. El sistema recorrerá todos los departamentos del Perú y construirá la lista de estaciones disponibles. Este proceso puede tardar varios minutos y solo necesita hacerse una vez (el resultado se guarda en `inventario_senamhi.json`).

### 4. Seleccionar y descargar

Una vez cargado el inventario, selecciona los departamentos, tipos de estación o estaciones individuales que deseas descargar y haz clic en **"Descargar"**. El progreso se muestra en tiempo real.

### 5. Encontrar los archivos descargados

Los CSV se guardan organizados en:

```
estaciones_senamhi/
└── <DEPARTAMENTO>/
    └── <TIPO DE ESTACIÓN>/
        └── <NOMBRE DE ESTACIÓN>/
            └── <mes>.csv
```

---

## Uso — Línea de Comandos (modo consola)

```bash
python senamhi.py
```

El script te guiará con un menú interactivo:

1. **Inventario:** Si ya existe `inventario_senamhi.json`, te preguntará si deseas reutilizarlo. Si no, iniciará el sondeo automáticamente.
2. **Selección:** Elige un departamento y, dentro de él, una estación específica o todo el departamento.
3. **Confirmación:** Revisa el resumen y confirma la descarga.
4. **Descarga:** Los archivos CSV se guardan en `estaciones_senamhi/`.

---

## Tipos de estaciones soportados

| Tipo y categoría                        | Carpeta de destino                          |
|-----------------------------------------|---------------------------------------------|
| Convencional · Meteorológica            | `ESTACION METEOROLOGICA CONVENCIONAL`       |
| Automática · Meteorológica              | `ESTACION METEOROLOGICA AUTOMATICA`         |
| Convencional · Hidrológica              | `ESTACION HIDROLOGICA CONVENCIONAL`         |
| Automática · Hidrológica                | `ESTACION HIDROLOGICA AUTOMATICA`           |

---

## Departamentos cubiertos

El sistema sondea los 24 departamentos del Perú:

> Amazonas, Áncash, Apurímac, Arequipa, Ayacucho, Cajamarca, Cusco, Huancavelica, Huánuco, Ica, Junín, La Libertad, Lambayeque, Lima, Loreto, Madre de Dios, Moquegua, Pasco, Piura, Puno, San Martín, Tacna, Tumbes, Ucayali.

---

## Notas importantes

- El sondeo inicial abre un navegador Chrome visible y navega automáticamente por el sitio del SENAMHI. **No cierres el navegador** durante el proceso.
- Si el sondeo se interrumpe, puedes relanzarlo; el inventario parcial se sobreescribirá.
- La carpeta `temp_downloads/` se limpia automáticamente al terminar.
- Si Chrome se actualiza, `undetected-chromedriver` puede necesitar actualizarse también:  
  ```bash
  pip install --upgrade undetected-chromedriver
  ```

---

## Solución de problemas frecuentes

| Problema | Solución |
|---|---|
| `SessionNotCreatedException` al iniciar | Actualiza Chrome o reinstala `undetected-chromedriver` |
| El sondeo no encuentra estaciones en un departamento | El sitio del SENAMHI puede estar caído; intenta más tarde |
| `Operación en curso` en la web | Espera a que termine la operación actual o reinicia el servidor |
| Los CSV no aparecen en la carpeta | Revisa que `estaciones_senamhi/` exista y tenga permisos de escritura |
