from senamhi_config import dep_display


# ═══════════════════════════════════════════════════════════════
#  MENÚ INTERACTIVO
# ═══════════════════════════════════════════════════════════════

def mostrar_inventario(inventario: dict):
    """Imprime el inventario completo de forma legible."""
    print("\n" + "═"*65)
    print("  INVENTARIO COMPLETO DE ESTACIONES SENAMHI")
    print("═"*65)
    total_est = sum(
        len(ests) for dep in inventario.values()
        for ests in dep.values()
    )
    print(f"  {len(inventario)} departamentos  |  {total_est} estaciones en total\n")

    for i, (dep, tipos) in enumerate(sorted(inventario.items()), 1):
        total_dep = sum(len(e) for e in tipos.values())
        print(f"  [{i:02d}] {dep_display(dep):<25}  ({total_dep} estaciones)")
        for tipo, estaciones in sorted(tipos.items()):
            print(f"         {tipo}")
            for est in sorted(estaciones):
                print(f"           • {est}")
    print("═"*65)

def menu_seleccion(inventario: dict) -> list:
    """
    Pregunta al usuario qué descargar.
    Devuelve lista de tuplas: [(dep_url, tipo_carpeta, nombre_estacion), ...]
    donde tipo_carpeta y nombre_estacion pueden ser None para "todo".
    """
    deps_sorted = sorted(inventario.keys())

    print("\n¿Qué deseas descargar?\n")
    print("  [0] TODOS los departamentos (descarga completa)")
    for i, dep in enumerate(deps_sorted, 1):
        total = sum(len(e) for e in inventario[dep].values())
        print(f"  [{i:02d}] {dep_display(dep)}  ({total} estaciones)")

    while True:
        resp = input("\nEscribe el número del departamento (o 0 para todo): ").strip()
        if resp == "0":
            # Todo
            seleccion = []
            for dep in deps_sorted:
                seleccion.append((dep, None, None))
            return seleccion
        try:
            idx = int(resp)
            if 1 <= idx <= len(deps_sorted):
                dep_elegido = deps_sorted[idx - 1]
                break
            print(f"  [!] Número fuera de rango. Escribe entre 0 y {len(deps_sorted)}.")
        except ValueError:
            print("  [!] Entrada inválida. Escribe solo el número.")

    # ── Preguntar si quiere todo el departamento o una estación ──
    tipos = inventario[dep_elegido]
    todas_estaciones = [(tipo, est)
                        for tipo, ests in sorted(tipos.items())
                        for est in sorted(ests)]

    print(f"\n  Departamento: {dep_display(dep_elegido)}\n")
    print("  [0] TODO el departamento")
    for i, (tipo, est) in enumerate(todas_estaciones, 1):
        print(f"  [{i:02d}] {est:<35} ({tipo})")

    while True:
        resp2 = input("\nEscribe el número de la estación (o 0 para todo el departamento): ").strip()
        if resp2 == "0":
            return [(dep_elegido, None, None)]
        try:
            idx2 = int(resp2)
            if 1 <= idx2 <= len(todas_estaciones):
                tipo_sel, est_sel = todas_estaciones[idx2 - 1]
                print(f"\n  ✓ Seleccionado: {est_sel} ({tipo_sel}) en {dep_display(dep_elegido)}")
                return [(dep_elegido, tipo_sel, est_sel)]
            print(f"  [!] Número fuera de rango. Escribe entre 0 y {len(todas_estaciones)}.")
        except ValueError:
            print("  [!] Entrada inválida. Escribe solo el número.")
