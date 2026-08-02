#!/usr/bin/env python3
"""El porton del registro.

Lee cada plantilla de `plantillas/` y comprueba, contra el diccionario vivo,
que TODA capacidad declarada exista de verdad. Si alguna no existe, sale con
error y el pull request no se puede fusionar.

Es deliberadamente corto: la regla es una sola y tiene que poder leerse entera.
"""

import json
import pathlib
import sys
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os

BASE = os.environ.get("DICCIONARIO", "https://diccionario.daiacaba.com.ar").rstrip("/")
DICCIONARIO = f"{BASE}/api/v1/ficha"
CARPETA = os.environ.get("CARPETA", "plantillas")
CAMPOS_OBLIGATORIOS = ("providerId", "serviceId", "name", "description", "declara")

# El diccionario rechaza con 403 al agente por defecto de urllib: hay que
# identificarse. Verificado el 02-ago-2026.
AGENTE = "ans-universe-verificador/1.0 (+https://ans.zone)"


def consultar(paquete: str, funcion: str):
    """Devuelve la ficha, o None si el diccionario no la tiene."""
    url = f"{DICCIONARIO}/{paquete}/{funcion}"
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(pedido, timeout=20) as r:
            ficha = json.load(r)
            return ficha if ficha.get("funcion") else None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main() -> int:
    plantillas = sorted(pathlib.Path(CARPETA).glob("*.json"))
    if not plantillas:
        print("No hay plantillas que verificar.")
        return 0

    fallas = []
    for ruta in plantillas:
        print(f"\n=== {ruta.name} ===")
        p = json.loads(ruta.read_text(encoding="utf-8"))

        faltantes = [c for c in CAMPOS_OBLIGATORIOS if c not in p]
        if faltantes:
            fallas.append(f"{ruta.name}: le faltan campos: {', '.join(faltantes)}")
            print(f"  MAL  faltan campos: {', '.join(faltantes)}")
            continue

        # El nombre del archivo tiene que seguir la convención de Domain Connect.
        esperado = f"{p['providerId']}.{p['serviceId']}.json"
        if ruta.name != esperado:
            fallas.append(f"{ruta.name}: debería llamarse {esperado}")
            print(f"  MAL  el archivo debería llamarse {esperado}")

        capacidades = p["declara"].get("capacidades", [])
        if not capacidades:
            fallas.append(f"{ruta.name}: no declara ninguna capacidad")
            print("  MAL  no declara ninguna capacidad")
            continue

        for c in capacidades:
            nombre = f"{c['paquete']}::{c['funcion']}"
            ficha = consultar(c["paquete"], c["funcion"])
            if ficha:
                donde = "navegador" if ficha.get("wasm") else "taller"
                print(f"  OK   {nombre:<28} v{ficha.get('version')} - {ficha.get('licencia')} - {donde}")
            else:
                fallas.append(f"{ruta.name}: {nombre} no está respaldada por el diccionario")
                print(f"  MAL  {nombre:<28} NADIE LA RESPALDA")

    print()
    if fallas:
        print(f"RECHAZADO — {len(fallas)} problema(s):")
        for f in fallas:
            print(f"  - {f}")
        return 1

    print(f"ACEPTADO — {len(plantillas)} plantilla(s), todas las capacidades respaldadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
