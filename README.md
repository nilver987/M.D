# SENAMHI Scraper v4
**Descarga los archivos Excel ORIGINALES del servidor SENAMHI — sin generarlos.**

---

## Instalación

```bash
cd backend
pip install -r requirements.txt
```

---

## Uso

```bash
# Terminal 1: inicia el servidor
cd backend
python server.py

# Luego: abre frontend/index.html en el navegador
```

O desde consola directamente:
```bash
python scraper.py lima
python scraper.py cusco --output ./mis_datos
```

---

## Cómo funciona

1. **Chrome headless** navega `senamhi.gob.pe/main.php?dp={region}&p=descarga-datos-hidrometeorologicos`
2. Espera que el JS cargue el mapa y las tablas de estaciones
3. Hace clic en cada marcador/estación para abrir el popup con links de descarga
4. **Captura TODOS los links `.xlsx` y `.xls`** que aparecen en cualquier parte del DOM
5. **Chrome se cierra** — ya terminó su trabajo
6. `requests` descarga cada archivo Excel directamente del servidor
7. Los archivos se meten en un ZIP organizado:

```
SENAMHI_Lima_20250101.zip
└── Lima/
    ├── INDICE.txt
    ├── Meteorologica_Convencional/
    │   └── NOMBRE_ESTACION/
    │       └── 2023/
    │           └── archivo_original.xlsx   ← el Excel tal como lo sirve SENAMHI
    ├── Meteorologica_Automatica/
    ├── Hidrologica_Convencional/
    └── Hidrologica_Automatica/
```

---

## Notas

- No se modifica ni genera ningún Excel — son los archivos originales de SENAMHI
- No requiere login para la mayoría de archivos públicos
- El ZIP incluye un `INDICE.txt` con la lista completa de archivos descargados
