# ─────────────────────────────────────────────────────────────
TIPO_A_CARPETA = {
    ("CONVENCIONAL", "METEOROL"): "ESTACION METEOROLOGICA CONVENCIONAL",
    ("AUTOM",        "METEOROL"): "ESTACION METEOROLOGICA AUTOMATICA",
    ("CONVENCIONAL", "HIDROL")  : "ESTACION HIDROLOGICA CONVENCIONAL",
    ("AUTOM",        "HIDROL")  : "ESTACION HIDROLOGICA AUTOMATICA",
}

DEPARTAMENTOS = [
    "amazonas", "ancash", "apurimac", "arequipa", "ayacucho", "cajamarca",
    "cusco", "huancavelica", "huanuco", "ica", "junin", "la-libertad",
    "lambayeque", "lima", "loreto", "madre-de-dios", "moquegua", "pasco",
    "piura", "puno", "san-martin", "tacna", "tumbes", "ucayali"
]

# Archivo donde se guarda el inventario para no repetir el sondeo
INVENTARIO_FILE = "inventario_senamhi.json"

# ─────────────────────────────────────────────────────────────

def resolver_tipo(txt: str) -> str:
    u = txt.upper()
    for (s, c), nombre in TIPO_A_CARPETA.items():
        if s in u and c in u:
            return nombre
    return "ESTACION DESCONOCIDA"

def limpiar_nombre(texto: str) -> str:
    v = "".join(c for c in texto if c.isalnum() or c in " -_()").strip()
    return " ".join(v.split())

def dep_display(dep_url: str) -> str:
    """'la-libertad' → 'LA LIBERTAD'"""
    return dep_url.replace("-", " ").upper()
