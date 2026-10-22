"""Vigila paginas oficiales y crea un borrador en src/content/novedades si cambian."""
import difflib
import json
import sys
import time
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
SNAPSHOTS = RAIZ / "monitor" / "state" / "paginas"
SALIDA = RAIZ / "src" / "content" / "novedades"
CABECERAS = {
    "User-Agent": "vivirsinprivilegios-monitor (+https://vivirsinprivilegios.org)",
}

# Paginas vigiladas. Para anadir una, copia un bloque y cambia los datos.
# "id": nombre corto unico, sin espacios (se usa en nombres de fichero)
# "categoria": nacionalidad, residencia, asilo, estudiantes, legislacion u otros
PAGINAS = [
    {
        "id": "migraciones-faq-reloex",
        "nombre": "Preguntas frecuentes del Reglamento de Extranjería",
        "organismo": "Ministerio de Inclusión, Seguridad Social y Migraciones",
        "url": "https://inclusion.gob.es/web/migraciones/preguntas-frecuentes-reglamento-de-extranjeria",
        "categoria": "residencia",
    },
    {
        "id": "migraciones-estado-autorizacion",
        "nombre": "Consulta del estado de su autorización de extranjería",
        "organismo": "Ministerio de Inclusión, Seguridad Social y Migraciones",
        "url": "https://inclusion.gob.es/web/migraciones/consulta-sobre-el-estado-de-su-autorizacion-de-extranjeria",
        "categoria": "residencia",
    },
]


class Texto(HTMLParser):
    """Extrae el texto visible, sin menus, cabecera, pie ni scripts."""

    IGNORAR = {"script", "style", "noscript", "nav", "header", "footer", "svg"}
    BLOQUES = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6",
               "tr", "section", "article", "ul", "ol", "table"}

    def __init__(self):
        super().__init__()
        self.profundidad = 0
        self.partes = []

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self.profundidad += 1
        elif tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self.IGNORAR:
            self.profundidad = max(0, self.profundidad - 1)
        elif tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_data(self, data):
        if self.profundidad == 0:
            self.partes.append(data)


def extraer_lineas(html):
    p = Texto()
    p.feed(html)
    lineas = [" ".join(l.split()) for l in "".join(p.partes).splitlines()]
    return [l for l in lineas if l]


def crear_borrador(pagina, diff):
    hoy = date.today().isoformat()
    base = f"{hoy}-cambio-{pagina['id']}"
    ruta = SALIDA / f"{base}.md"
    n = 2
    while ruta.exists():
        ruta = SALIDA / f"{base}-{n}.md"
        n += 1
    q = lambda s: json.dumps(s, ensure_ascii=False)  # comillas seguras para YAML
    recorte = [l[:300] for l in diff[:40]]
    extra = f"\n(... y {len(diff) - 40} líneas más)" if len(diff) > 40 else ""
    contenido = f"""---
title: {q("Posible cambio en: " + pagina["nombre"])}
description: {q("Se ha detectado un cambio en una página oficial de " + pagina["organismo"] + ". Resumen pendiente de revisión.")}
pubDate: {hoy}
checkedDate: {hoy}
source: {q(pagina["organismo"])}
sourceUrl: {q(pagina["url"])}
category: {q(pagina["categoria"])}
draft: true
---
**Resumen pendiente de redactar.** Abre la página oficial, comprueba qué ha cambiado
de verdad y, si es relevante, redacta el resumen. Después cambia `draft: true` a
`draft: false`. Si el cambio es irrelevante (un enlace, una fecha), borra este fichero.

Líneas que han cambiado (`-` antes, `+` ahora):

```diff
{chr(10).join(recorte)}{extra}
```

## Qué cambia

(Escribe aquí, con tus palabras, qué cambia.)

## A quién afecta

(Escribe aquí a quién afecta y desde cuándo.)
"""
    SALIDA.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta.name


def revisar(pagina):
    r = requests.get(pagina["url"], headers=CABECERAS, timeout=30)
    r.raise_for_status()
    lineas = extraer_lineas(r.text)
    if len("\n".join(lineas)) < 200:
        raise ValueError("contenido casi vacío (¿la página carga con JavaScript?)")

    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snap = SNAPSHOTS / f"{pagina['id']}.txt"
    if not snap.exists():
        snap.write_text("\n".join(lineas), encoding="utf-8")
        return "base", None

    antiguas = snap.read_text(encoding="utf-8").splitlines()
    if antiguas == lineas:
        return "igual", None

    diff = [
        l for l in difflib.unified_diff(antiguas, lineas, lineterm="", n=0)
        if l[:1] in "+-" and not l.startswith(("+++", "---"))
    ]
    nombre = crear_borrador(pagina, diff)
    snap.write_text("\n".join(lineas), encoding="utf-8")  # solo si el borrador se creó
    return "cambio", nombre


def main():
    fallos = 0
    for pagina in PAGINAS:
        try:
            estado, nombre = revisar(pagina)
        except (requests.RequestException, ValueError) as e:
            fallos += 1
            print(f"[ERROR] {pagina['id']}: {e}")
        else:
            if estado == "base":
                print(f"[BASE]   {pagina['id']}: copia inicial guardada")
            elif estado == "igual":
                print(f"[IGUAL]  {pagina['id']}")
            else:
                print(f"[CAMBIO] {pagina['id']}: borrador {nombre}")
        time.sleep(2)  # no saturar los servidores
    if fallos == len(PAGINAS):
        sys.exit(1)


if __name__ == "__main__":
    main()