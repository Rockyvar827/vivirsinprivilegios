"""Detecta novedades de extranjeria en el BOE y crea borradores en src/content/novedades."""
import argparse
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "monitor" / "state" / "boe.json"
SALIDA = RAIZ / "src" / "content" / "novedades"
API = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"
CABECERAS = {
    "Accept": "application/json",
    "User-Agent": "vivirsinprivilegios-monitor (+https://vivirsinprivilegios.org)",
}

# Departamentos que vigilamos (en minusculas)
DEPARTAMENTOS = (
    "ministerio de inclusión",
    "ministerio del interior",
    "ministerio de justicia",
)

# Palabras que indican extranjeria en cualquier departamento
CLAVES_FUERTES = (
    "extranjer", "protección internacional", "asilo", "refugiad", "visado",
    "arraigo", "reagrupación familiar", "migraci", "inmigra",
    "nacionalidad española", "permiso de residencia", "autorización de residencia",
)

# Palabras mas genericas: solo cuentan si viene de uno de los departamentos de arriba
CLAVES_DEBILES = ("residencia", "estancia", "nacionalidad", "estudiantes extranjeros")

# Becas: solo cuentan si vienen de estos departamentos
DEPARTAMENTOS_BECAS = (
    "ministerio de educación",
    "ministerio de asuntos exteriores",
)
CLAVES_BECAS = ("becas", "ayudas al estudio", "ayudas para estudiantes")

# Secciones del BOE que miramos (I disposiciones generales, III otras disposiciones, T Tribunal Constitucional)
SECCIONES = ("i.", "iii.", "t.")

CATEGORIAS = (
    ("nacionalidad", "nacionalidad"),
    ("asilo", "asilo"),
    ("refugiad", "asilo"),
    ("protección internacional", "asilo"),
    ("estudiante", "estudiantes"),
    ("residencia", "residencia"),
    ("arraigo", "residencia"),
    ("reagrupación", "residencia"),
    ("visado", "residencia"),
    ("extranjer", "residencia"),
)

# Titulos que contienen palabras clave pero no tratan de extranjeria
# Las concesiones individuales de nacionalidad (Reales Decretos "por carta de naturaleza") llevan
# nombres de personas y no son novedades normativas
EXCLUIR = ("turista extranjero", "carta de naturaleza", "se concede la nacionalidad española")

def lista(x):
    if x is None:
        return []
    return list(x) if isinstance(x, list) else [x]


def texto_url(v):
    if isinstance(v, dict):
        return v.get("texto") or v.get("#text") or ""
    return v or ""


def descargar(dia):
    r = requests.get(API.format(fecha=dia.strftime("%Y%m%d")), headers=CABECERAS, timeout=30)
    if r.status_code == 404:  # dias sin BOE (domingos, festivos)
        return None
    r.raise_for_status()
    return r.json()


def items_del_sumario(datos):
    sumario = datos["data"]["sumario"]
    for diario in lista(sumario.get("diario")):
        for seccion in lista(diario.get("seccion")):
            nombre_sec = seccion.get("nombre", "")
            for dep in lista(seccion.get("departamento")):
                nombre_dep = dep.get("nombre", "")
                candidatos = lista(dep.get("item"))
                for ep in lista(dep.get("epigrafe")):
                    candidatos += lista(ep.get("item"))
                for it in candidatos:
                    yield nombre_sec, nombre_dep, it


def es_relevante(seccion, departamento, titulo):
    if not seccion.lower().startswith(SECCIONES):
        return False
    t = titulo.lower()
    if any(x in t for x in EXCLUIR):
        return False
    if any(c in t for c in CLAVES_FUERTES):
        return True
    vigilado = any(d in departamento.lower() for d in DEPARTAMENTOS)
    if any(d in departamento.lower() for d in DEPARTAMENTOS_BECAS) and any(c in t for c in CLAVES_BECAS):
        return True
    return vigilado and any(c in t for c in CLAVES_DEBILES)


def categoria(titulo, seccion):
    t = titulo.lower()
    for clave, cat in CATEGORIAS:
        if clave in t:
            return cat
    return "legislacion" if seccion.lower().startswith("i.") else "otros"


def crear_borrador(dia, seccion, departamento, it):
    ident = it.get("identificador", "")
    titulo = " ".join(it.get("titulo", "").split())
    url = texto_url(it.get("url_html")) or f"https://www.boe.es/diario_boe/txt.php?id={ident}"
    nombre = f"{dia.isoformat()}-{ident.lower()}.md"
    ruta = SALIDA / nombre
    if ruta.exists():
        return None

    titulo_corto = titulo if len(titulo) <= 110 else titulo[:107].rstrip() + "..."
    descripcion = f"Disposición publicada en el BOE el {dia.strftime('%d/%m/%Y')} ({departamento.title()}). Resumen pendiente de revisión."
    q = lambda s: json.dumps(s, ensure_ascii=False)  # comillas seguras para YAML

    contenido = f"""---
title: {q(titulo_corto)}
description: {q(descripcion)}
pubDate: {dia.isoformat()}
checkedDate: {date.today().isoformat()}
source: "BOE"
sourceUrl: {q(url)}
category: {q(categoria(titulo, seccion))}
draft: true
---

**Resumen pendiente de redactar.** Cambia `draft: true` a `draft: false` cuando lo hayas revisado.

Título oficial: {titulo}

Departamento: {departamento}

Identificador BOE: {ident}

## Qué cambia

(Escribe aquí, con tus palabras, qué cambia.)

## A quién afecta

(Escribe aquí a quién afecta y desde cuándo.)
"""
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return nombre


def cargar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    return {"ultima_fecha": None, "vistos": []}


def guardar_estado(estado):
    estado["vistos"] = estado["vistos"][-3000:]  # evita que crezca sin limite
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fecha", nargs="?", help="fecha inicial AAAA-MM-DD")
    ap.add_argument("--desde", help="fecha inicial AAAA-MM-DD (para pruebas)")
    args = ap.parse_args()

    if args.fecha and args.desde:
        ap.error("indica la fecha como argumento posicional o con --desde, no ambos")

    estado = cargar_estado()
    hoy = date.today()
    fecha = args.desde or args.fecha
    if fecha:
        inicio = datetime.strptime(fecha, "%Y-%m-%d").date()
    elif estado["ultima_fecha"]:
        inicio = date.fromisoformat(estado["ultima_fecha"]) + timedelta(days=1)
    else:
        inicio = hoy - timedelta(days=3)

    nuevos = []
    dia = inicio
    while dia <= hoy:
        datos = descargar(dia)
        if datos:
            for seccion, dep, it in items_del_sumario(datos):
                ident = it.get("identificador", "")
                if not ident or ident in estado["vistos"]:
                    continue
                if es_relevante(seccion, dep, it.get("titulo", "")):
                    nombre = crear_borrador(dia, seccion, dep, it)
                    estado["vistos"].append(ident)
                    if nombre:
                        nuevos.append(nombre)
        estado["ultima_fecha"] = dia.isoformat()
        dia += timedelta(days=1)
        time.sleep(1)  # no saturar la API

    guardar_estado(estado)
    print(f"Revisado desde {inicio} hasta {hoy}. Borradores nuevos: {len(nuevos)}")
    for n in nuevos:
        print(" -", n)


if __name__ == "__main__":
    main()