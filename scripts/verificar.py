#!/usr/bin/env python3
"""El porton del registro.

Lee cada plantilla de `plantillas/` y comprueba, contra el diccionario vivo,
que TODA capacidad declarada exista de verdad. Si alguna no existe, sale con
error y el pull request no se puede fusionar.

Y si al lado hay un `agentes.json`, comprueba tambien que ningun agente se
atribuya una capacidad que su seccion no declaro. Antes esto no se miraba y las
tres listas (plantilla del registro, plantilla de la seccion, agentes.json) se
desincronizaron sin que nadie se enterara: el catalogo publicitaba funciones que
la seccion no declaraba. Una sola copia manda, y es la plantilla.

Es deliberadamente corto: las reglas son dos y tienen que poder leerse enteras.
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
# El registro de agentes, si lo hay. Un repo de seccion no lo tiene y eso no es
# una rotura: la comprobacion se saltea sola.
AGENTES = os.environ.get("AGENTES", "agentes.json")
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


def revisar_agentes(declaradas: dict) -> list:
    """Ningun agente puede atribuirse una capacidad que su seccion no declaro.

    `declaradas` es {serviceId: {"sf::st_area", ...}} armado con las plantillas
    que ya se verificaron arriba. Devuelve la lista de fallas.
    """
    ruta = pathlib.Path(AGENTES)
    if not ruta.exists():
        return []

    print(f"\n=== {ruta.name} ===")
    fallas = []
    agentes = json.loads(ruta.read_text(encoding="utf-8")).get("agentes", [])
    if not agentes:
        print("  --   no declara agentes")
        return []

    for a in agentes:
        ident = a.get("id", "(sin id)")
        caps = {f"{c['paquete']}::{c['funcion']}" for c in a.get("capacidades", [])}
        if not caps:
            fallas.append(f"agentes.json: {ident} no declara ninguna capacidad")
            print(f"  MAL  {ident:<28} no declara ninguna capacidad")
            continue

        # El agente dice de que seccion es. Sin eso no hay contra que comparar.
        seccion = a.get("plantilla")
        if not seccion:
            fallas.append(f"agentes.json: {ident} no dice de que plantilla sale")
            print(f"  MAL  {ident:<28} sin campo 'plantilla'")
            continue
        clave = seccion.split(".")[-1]      # ansgis.espacios-verdes -> espacios-verdes
        if clave not in declaradas:
            fallas.append(f"agentes.json: {ident} apunta a la plantilla {seccion}, que no existe")
            print(f"  MAL  {ident:<28} la plantilla {seccion} no esta en {CARPETA}/")
            continue

        de_mas = sorted(caps - declaradas[clave])
        if de_mas:
            fallas.append(
                f"agentes.json: {ident} se atribuye {', '.join(de_mas)}, "
                f"que {seccion} no declara"
            )
            print(f"  MAL  {ident:<28} de mas: {', '.join(de_mas)}")
        else:
            print(f"  OK   {ident:<28} sus {len(caps)} capacidades salen de {seccion}")

    return fallas


def main() -> int:
    plantillas = sorted(pathlib.Path(CARPETA).glob("*.json"))
    if not plantillas:
        print("No hay plantillas que verificar.")
        return 0

    fallas = []
    declaradas = {}
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

        declaradas[p["serviceId"]] = {f"{c['paquete']}::{c['funcion']}" for c in capacidades}

        for c in capacidades:
            nombre = f"{c['paquete']}::{c['funcion']}"
            ficha = consultar(c["paquete"], c["funcion"])
            if ficha:
                donde = "navegador" if ficha.get("wasm") else "taller"
                print(f"  OK   {nombre:<28} v{ficha.get('version')} - {ficha.get('licencia')} - {donde}")
            else:
                fallas.append(f"{ruta.name}: {nombre} no está respaldada por el diccionario")
                print(f"  MAL  {nombre:<28} NADIE LA RESPALDA")

    fallas += revisar_agentes(declaradas)

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
