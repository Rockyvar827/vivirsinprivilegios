import os, re, sys, time, unicodedata
import datetime as dt
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

MODELO = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
CARPETA_SALIDA = "src/content/extranjeria"
MAX_BORRADORES = 5
LIMITE_CARACTERES = 40000
HEADERS = {"Accept": "application/json", "User-Agent": "vivirsinprivilegios-monitor"}

PALABRAS = [
    r"extranjer\w*", r"inmigra\w*", r"migraci\w*", r"nacionalidad",
    r"asilo", r"protecci[oó]n internacional", r"refugiad\w*", r"ap[aá]trida\w*",
    r"visado\w*", r"arraigo", r"reagrupaci[oó]n familiar", r"regularizaci[oó]n",
    r"NIE", r"TIE", r"CCSE", r"DELE",
    r"Inclusi[oó]n, Seguridad Social y Migraciones",
    r"residencia temporal", r"residencia de larga duraci[oó]n",
    r"autorizaci[oó]n de residencia", r"estancia por estudios",
]
NORMAS_CLAVE = [
    r"Ley Org[aá]nica 4/2000", r"Real Decreto 1155/2024",
    r"Real Decreto 557/2011", r"Ley 12/2009",
]
PATRON = re.compile(r"\b(" + "|".join(PALABRAS + NORMAS_CLAVE) + r")\b", re.I)

# Ruido que coincide con las palabras clave pero no es un tramite de extranjeria
EXCLUIR = re.compile(
    r"carta de naturaleza"
    r"|formalizaci[oó]n de contratos"
    r"|licitaci[oó]n"
    r"|libre designaci[oó]n"
    r"|\bse nombra\b|nombramiento"
    r"|\bconvenio\b|\badenda\b"
    r"|subvenci[oó]n"
    r"|encomienda de gesti[oó]n"
    r"|recurso interpuesto contra la (?:negativa|calificaci[oó]n)",
    re.I,
)


def es_relevante(item):
    # Los anuncios (BOE-B) son contratos, licitaciones y notificaciones: no son normas
    if item["id"].startswith("BOE-B-"):
        return False
    titulo = item["titulo"]
    return bool(PATRON.search(titulo)) and not EXCLUIR.search(titulo)
CATEGORIAS = {"documentacion", "residencia", "asilo", "reclamaciones", "galicia"}
VALLA = chr(96) * 3

INSTRUCCIONES = """Eres redactor de la web vivirsinprivilegios.org, seccion de extranjeria en Espana.
Redactas un BORRADOR de guia sobre un tramite o cambio normativo de extranjeria, en Markdown con frontmatter, imitando la estructura, tono y encabezados de la PLANTILLA.
El frontmatter debe tener EXACTAMENTE estos campos:
title: titulo claro (entre comillas simples)
seoTitle: titulo SEO corto (entre comillas dobles)
description: resumen de una o dos frases (entre comillas simples)
pubDate: la fecha de hoy en formato AAAA-MM-DD
category: UNO solo de estos valores: documentacion, residencia, asilo, reclamaciones, galicia
tags: lista de etiquetas
draft: true
REGLAS OBLIGATORIAS:
1. Usa SOLO el texto oficial de la disposicion que se te entrega. No inventes nada.
2. En el cuerpo incluye siempre: enlace al BOE, referencia (BOE-A-...), fecha de publicacion y fecha de entrada en vigor.
3. Explica a quien afecta, que tramite cambia, que debe hacer la persona y los plazos.
4. Si algo es dudoso, interpretable o no consta en el texto, escribe [REVISAR] justo ahi.
5. Escribe en espanol claro y sin tecnicismos innecesarios.
6. Si la disposicion NO afecta a tramites de personas extranjeras, responde solo con la palabra DESCARTAR.
7. Devuelve unicamente el contenido del archivo .md, sin explicaciones ni bloques de codigo.
8. Escribe todo el texto, incluidas las etiquetas (tags), con tildes y enes correctas (por ejemplo: extranjería, nacionalidad, Galicia).
9. No uses encabezado de nivel 1 (#) en el cuerpo ni la palabra "borrador". Empieza el cuerpo directamente con un parrafo introductorio. La unica marca de revision es [REVISAR].
10. Fecha de entrada en vigor: busca la frase "entrara en vigor" en el texto. Si indica un plazo (por ejemplo "a los seis meses de su publicacion"), copia ese plazo literalmente y no calcules fechas. Si no aparece en el texto entregado, escribe [REVISAR].
11. Cifras, edades, plazos, cantidades e importes solo si figuran literalmente en el texto entregado.
12. La description del frontmatter debe tener 155 caracteres como maximo.
13. La fecha de publicacion en el BOE es la que se indica en FECHA DE PUBLICACION EN EL BOE: usala, escrita como dia de mes de año (por ejemplo 20 de noviembre de 2024).
14. Los enlaces van en formato Markdown con texto descriptivo, por ejemplo [BOE-A-2024-24099](url). Nunca pongas la direccion suelta."""


def recorrer(nodo):
    items = []
    if isinstance(nodo, dict):
        if "identificador" in nodo and "titulo" in nodo:
            url = nodo.get("url_html")
            items.append({
                "id": nodo["identificador"],
                "titulo": nodo["titulo"],
                "url": url if isinstance(url, str) else None,
            })
            return items
        for v in nodo.values():
            items += recorrer(v)
    elif isinstance(nodo, list):
        for x in nodo:
            items += recorrer(x)
    return items


def sumario(fecha):
    url = f"https://www.boe.es/datosabiertos/api/boe/sumario/{fecha:%Y%m%d}"
    r = requests.get(url, headers=HEADERS, timeout=60)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    return recorrer(r.json())


def extractos_vigor(resto):
    """Fragmentos de la parte recortada que hablan de entrada en vigor."""
    trozos = []
    for m in re.finditer(r"entrar[aá]n? en vigor", resto, re.I):
        ini = max(0, m.start() - 300)
        fin = min(len(resto), m.end() + 300)
        if trozos and ini <= trozos[-1][1]:
            trozos[-1][1] = fin
        else:
            trozos.append([ini, fin])
        if len(trozos) >= 6:
            break
    return "\n...\n".join(resto[a:b] for a, b in trozos)


def texto_oficial(item):
    url = item["url"] or f"https://www.boe.es/diario_boe/txt.php?id={item['id']}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    cont = soup.find(id="textoxslt") or soup.body
    completo = cont.get_text("\n", strip=True)
    recortado = len(completo) > LIMITE_CARACTERES
    extractos = extractos_vigor(completo[LIMITE_CARACTERES:]) if recortado else ""
    return url, completo[:LIMITE_CARACTERES], recortado, extractos


def slug(texto):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    if len(t) > 60:
        t = t[:60].rsplit("-", 1)[0]
    return t.strip("-")


def redactar(client, plantilla, fecha, item, url, texto, recortado=False, extractos=""):
    aviso = ""
    if recortado:
        aviso = (
            "AVISO IMPORTANTE: el texto oficial de abajo esta RECORTADO y solo contiene el principio de la norma. "
            "Empieza el cuerpo del post con una linea que diga: [REVISAR] Basado solo en el inicio del texto oficial; "
            "completar con el texto íntegro del BOE. No describas partes que no aparezcan en el texto entregado.\n\n"
        )
    prompt = aviso + (
        f"FECHA DE HOY: {fecha:%Y-%m-%d}\nFECHA DE PUBLICACION EN EL BOE: {fecha:%Y-%m-%d}\nREFERENCIA: {item['id']}\n"
        f"ENLACE BOE: {url}\nTITULO OFICIAL: {item['titulo']}\n\n"
        f"PLANTILLA DE ESTILO:\n{plantilla}\n\n"
        f"TEXTO OFICIAL DE LA DISPOSICION:\n{texto}"
    )
    if extractos:
        prompt += (
            "\n\nFRAGMENTOS DE LA PARTE RECORTADA QUE MENCIONAN LA ENTRADA EN VIGOR "
            "(usalos para la fecha de entrada en vigor del real decreto o norma principal, "
            "no de disposiciones concretas):\n" + extractos
        )
    for intento in range(3):
        try:
            resp = client.models.generate_content(
                model=MODELO,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=INSTRUCCIONES, temperature=0.2
                ),
            )
            return (resp.text or "").strip()
        except Exception as e:
            print("Error Gemini, reintento:", e)
            time.sleep(30 * (intento + 1))
    return ""


def limpiar(md):
    md = re.sub(r"^" + VALLA + r"(?:markdown|md)?\s*", "", md)
    md = re.sub(r"\s*" + VALLA + r"$", "", md)
    return md.strip() + "\n"


def validar(md):
    m = re.search(r"^category:\s*['\"]?(\w+)['\"]?\s*$", md, re.M)
    if m and m.group(1) not in CATEGORIAS:
        md = re.sub(r"^category:.*$", "category: 'residencia'", md, count=1, flags=re.M)
    elif not m:
        md = md.replace("\n---\n", "\ncategory: 'residencia'\n---\n", 1)
    if re.search(r"^draft:", md, re.M):
        md = re.sub(r"^draft:.*$", "draft: true", md, count=1, flags=re.M)
    else:
        md = md.replace("\n---\n", "\ndraft: true\n---\n", 1)
    return md


def main():
    hoy = dt.datetime.now(ZoneInfo("Europe/Madrid")).date()
    arg = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    fecha = dt.date.fromisoformat(arg) if arg else hoy

    items = [i for i in sumario(fecha) if es_relevante(i)]
    vistos, unicos = set(), []
    for i in items:
        if i["id"] not in vistos:
            vistos.add(i["id"])
            unicos.append(i)

    if not unicos:
        with open("/tmp/resumen_pr.txt", "w", encoding="utf-8") as f:
            f.write("Sin novedades.\n")
        print("Sin novedades hoy.")
        return

    resumen = [
        f"Disposiciones del BOE del {fecha:%d/%m/%Y} que coinciden con los filtros: {len(unicos)}",
        "",
    ]
    with open("scripts/plantilla_extranjeria.md", encoding="utf-8") as f:
        plantilla = f.read()
    client = genai.Client()  # lee GEMINI_API_KEY del entorno
    os.makedirs(CARPETA_SALIDA, exist_ok=True)

    creados = 0
    for item in unicos:
        resumen.append(f"- {item['id']}: {item['titulo']}")
        if creados >= MAX_BORRADORES:
            resumen.append("  (sin borrador: limite diario alcanzado)")
            continue
        url, texto, recortado, extractos = texto_oficial(item)
        md = redactar(client, plantilla, fecha, item, url, texto, recortado, extractos)
        time.sleep(15)  # respeta el limite de peticiones por minuto
        if not md:
            resumen.append("  (SIN RESPUESTA de Gemini: revisar clave, modelo o limite de peticiones)")
            continue
        if md.strip().upper().startswith("DESCARTAR"):
            resumen.append("  (descartado por Gemini: no afecta a tramites de extranjeria)")
            continue
        if not md.startswith("---"):
            resumen.append("  (FORMATO INESPERADO: la respuesta no empieza por el frontmatter, no se guarda)")
            print("Inicio de la respuesta de Gemini:", md[:300])
            continue
        ruta = f"{CARPETA_SALIDA}/boe-{fecha:%Y-%m-%d}-{slug(item['titulo'])}.md"
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(validar(limpiar(md)))
        resumen.append(f"  borrador creado: {ruta}")
        creados += 1

    resumen += [
        "",
        "Revisar cada borrador contra el texto del BOE y quitar todos los [REVISAR] antes de publicar.",
    ]
    with open("/tmp/resumen_pr.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(resumen))


if __name__ == "__main__":
    main()
