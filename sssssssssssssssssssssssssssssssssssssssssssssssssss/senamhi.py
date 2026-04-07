import json
import os

from senamhi_config import INVENTARIO_FILE, dep_display, DEPARTAMENTOS
from senamhi_menu import mostrar_inventario, menu_seleccion
from senamhi_scraper import SenamhiScraper


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    scraper = SenamhiScraper()

    try:
        # ── Cargar o construir inventario ──────────────────────
        if os.path.exists(INVENTARIO_FILE):
            print(f"\n[i] Se encontró el inventario guardado: '{INVENTARIO_FILE}'")
            resp = input("    ¿Usar inventario existente? [S/n]: ").strip().lower()
            if resp in ("", "s", "si", "sí", "y", "yes"):
                with open(INVENTARIO_FILE, "r", encoding="utf-8") as f:
                    inventario = json.load(f)
                print(f"    [✓] Inventario cargado ({sum(len(e) for d in inventario.values() for e in d.values())} estaciones).")
            else:
                inventario = scraper.sondear_inventario()
                with open(INVENTARIO_FILE, "w", encoding="utf-8") as f:
                    json.dump(inventario, f, ensure_ascii=False, indent=2)
                print(f"\n[✓] Inventario guardado en '{INVENTARIO_FILE}'")
        else:
            print("\n[i] No se encontró inventario previo. Iniciando sondeo de todas las estaciones...")
            print("    (Esto puede tardar unos minutos. Solo se hace una vez.)\n")
            inventario = scraper.sondear_inventario()
            with open(INVENTARIO_FILE, "w", encoding="utf-8") as f:
                json.dump(inventario, f, ensure_ascii=False, indent=2)
            print(f"\n[✓] Inventario guardado en '{INVENTARIO_FILE}'")

        # ── Mostrar inventario y preguntar qué descargar ───────
        mostrar_inventario(inventario)
        seleccion = menu_seleccion(inventario)

        # ── Confirmar ──────────────────────────────────────────
        print("\n  Resumen de lo que se va a descargar:")
        for (dep, tipo, est) in seleccion:
            if est:
                print(f"    • {dep_display(dep)} → {tipo} → {est}")
            elif tipo:
                print(f"    • {dep_display(dep)} → {tipo} → (todas)")
            else:
                print(f"    • {dep_display(dep)} → (todo el departamento)")

        conf = input("\n¿Confirmar descarga? [S/n]: ").strip().lower()
        if conf not in ("", "s", "si", "sí", "y", "yes"):
            print("Descarga cancelada.")
            return

        # ── Descargar ──────────────────────────────────────────
        scraper.descargar_seleccion(seleccion, inventario)
        print("\n[✓] Descarga completada.")

    except KeyboardInterrupt:
        print("\n[!] Proceso detenido.")
    except Exception as e:
        print(f"\n[!] Error fatal: {e}")
    finally:
        scraper.cerrar()
        print("Script finalizado.")


if __name__ == "__main__":
    main()
