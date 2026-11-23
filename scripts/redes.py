"""Senales de redes sociales y de busquedas, para detectar bulos y lenguaje deshumanizante ANTES de
que un verificador los publique. Lo usa recolectar_bulos.py (mismo directorio).

Solo lee contenido PUBLICO. No guarda nombres de usuario. Cada fuente falla por separado:
si una cae, las demas siguen y el estado se muestra en pantalla.

Configuracion (variables de entorno, todas opcionales):
  BSKY_USER, BSKY_PASS    -> Bluesky (usa una "contrasena de aplicacion", nunca la principal)
  FACTCHECK_API_KEY       -> Google Fact Check Tools API (clave gratuita de Google Cloud)
Ficheros opcionales en datos/:
  canales_telegram.txt    -> un canal PUBLICO de Telegram por linea (sin @), los eliges tu

NO se cubren: Facebook, Instagram, TikTok, WhatsApp (sin acceso publico gratuito) ni X/Twitter
(API de pago). Las alertas de esas plataformas dependen de Google Trends y de los verificadores.
"""
import datetime as dt
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

HEADERS = {"User-Agent": "vivirsinprivilegios-monitor"}
DATOS = Path(__file__).resolve().parent.parent / "datos"

# Interacciones minimas (likes + reposts + respuestas) para que una publicacion cuente como senal
MIN_ALCANCE = 15

# Busquedas para encontrar contenido (incluye lenguaje deshumanizante, para poder detectarlo y contrarrestarlo)
BUSQUEDAS = [
    "inmigrantes ilegales", "invasión migrantes", "gran sustitución", "paguita inmigrantes",
    "menas peligro", "cayucos", "barco nodriza", "africanos ilegales", "inmigrantes negros",
    "bulo inmigrantes", "latinos bandas", "efecto llamada",
]
HASHTAGS = ["inmigracion", "racismo", "cayucos", "menas", "afrodescendientes"]
INSTANCIAS_MASTODON = ["mastodon.social", "masto.es"]
SUBREDDITS = ["spain", "es"]
CONSULTAS_FACTCHECK = ["inmigrantes", "africanos", "cayuco", "menas", "racismo", "latinoamericanos"]


def _limpiar(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()


def _fecha(s):
    """ISO 8601 -> datetime UTC sin zona horaria."""
    try:
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo:
            d = d.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return d
    except Exception:
        return None


def _item(fuente, texto, enlace, fecha, alcance, verificador=False):
    texto = _limpiar(texto)
    return {
        "fuente": fuente, "verificador": verificador, "red": not verificador,
        "titulo": texto[:200], "resumen": texto[:500], "enlace": enlace,
        "fecha": fecha, "alcance": int(alcance or 0),
    }


def _get(url, **kw):
    r = requests.get(url, headers=HEADERS, timeout=30, **kw)
    if r.status_code == 429:
        time.sleep(10)
        r = requests.get(url, headers=HEADERS, timeout=30, **kw)
    r.raise_for_status()
    return r


# ---------------------------------------------------------------- Bluesky
def leer_bluesky():
    user, pw = os.environ.get("BSKY_USER"), os.environ.get("BSKY_PASS")
    if not (user and pw):
        raise RuntimeError("sin configurar (faltan BSKY_USER y BSKY_PASS)")
    r = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                      json={"identifier": user, "password": pw}, timeout=30)
    r.raise_for_status()
    auth = {"Authorization": "Bearer " + r.json()["accessJwt"], **HEADERS}
    items = []
    for q in BUSQUEDAS:
        r = requests.get("https://bsky.social/xrpc/app.bsky.feed.searchPosts",
                         params={"q": q, "limit": 50, "sort": "latest", "lang": "es"},
                         headers=auth, timeout=30)
        r.raise_for_status()
        for p in r.json().get("posts", []):
            rec = p.get("record", {})
            alcance = sum(p.get(k, 0) for k in ("likeCount", "repostCount", "replyCount", "quoteCount"))
            rkey = p["uri"].rsplit("/", 1)[-1]
            enlace = f"https://bsky.app/profile/{p['author']['handle']}/post/{rkey}"
            items.append(_item("Bluesky", rec.get("text", ""), enlace, _fecha(rec.get("createdAt", "")), alcance))
        time.sleep(1)
    return items


# ---------------------------------------------------------------- Mastodon
def leer_mastodon():
    items = []
    for inst in INSTANCIAS_MASTODON:
        for tag in HASHTAGS:
            try:
                datos = _get(f"https://{inst}/api/v1/timelines/tag/{tag}", params={"limit": 40}).json()
            except Exception:
                continue  # una instancia o etiqueta que falla no tumba el resto
            for p in datos:
                if p.get("language") not in (None, "es", "ca", "gl", "eu"):
                    continue
                alcance = p.get("favourites_count", 0) + p.get("reblogs_count", 0) + p.get("replies_count", 0)
                items.append(_item("Mastodon", p.get("content", ""), p.get("url", ""),
                                   _fecha(p.get("created_at", "")), alcance))
            time.sleep(1)
    if not items:
        raise RuntimeError("ninguna instancia respondio")
    return items


# ---------------------------------------------------------------- Reddit
def leer_reddit():
    items = []
    for sub in SUBREDDITS:
        for q in BUSQUEDAS[:6]:
            datos = _get(f"https://www.reddit.com/r/{sub}/search.json",
                         params={"q": q, "restrict_sr": 1, "sort": "new", "t": "week", "limit": 50}).json()
            for c in datos.get("data", {}).get("children", []):
                d = c["data"]
                fecha = dt.datetime.fromtimestamp(d["created_utc"], dt.timezone.utc).replace(tzinfo=None)
                items.append(_item("Reddit", d.get("title", "") + ". " + d.get("selftext", ""),
                                   "https://www.reddit.com" + d.get("permalink", ""),
                                   fecha, d.get("score", 0) + d.get("num_comments", 0)))
            time.sleep(2)
    return items


# ---------------------------------------------------------------- Telegram (canales publicos que elijas)
def _vistas(s):
    s = (s or "").strip().upper().replace(",", ".")
    try:
        if s.endswith("K"):
            return float(s[:-1]) * 1000
        if s.endswith("M"):
            return float(s[:-1]) * 1_000_000
        return float(s)
    except ValueError:
        return 0


def leer_telegram():
    f = DATOS / "canales_telegram.txt"
    if not f.exists():
        raise RuntimeError("sin configurar (crea datos/canales_telegram.txt)")
    canales = [l.strip().lstrip("@") for l in f.read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.startswith("#")]
    items = []
    for c in canales:
        html = _get(f"https://t.me/s/{c}").text
        for b in html.split('tgme_widget_message_wrap')[1:]:
            txt = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', b, re.S)
            link = re.search(r'<a class="tgme_widget_message_date" href="([^"]+)"', b)
            when = re.search(r'<time datetime="([^"]+)"', b)
            views = re.search(r'tgme_widget_message_views">([^<]+)<', b)
            if txt and link:
                items.append(_item("Telegram", txt.group(1), link.group(1),
                                   _fecha(when.group(1)) if when else None,
                                   _vistas(views.group(1)) / 20 if views else 0))  # 20 vistas ~ 1 interaccion
        time.sleep(1)
    return items


# ---------------------------------------------------------------- Google Trends (busquedas en alza en Espana)
def leer_trends():
    r = _get("https://trends.google.com/trending/rss?geo=ES")
    raiz = ET.fromstring(r.content)
    items = []
    for it in raiz.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        trafico = re.sub(r"\D", "", it.findtext("{*}approx_traffic") or "0") or "0"
        noticias = [n.findtext("{*}news_item_title") or "" for n in it.findall("{*}news_item")]
        urls = [n.findtext("{*}news_item_url") or "" for n in it.findall("{*}news_item")]
        pub = it.findtext("pubDate")
        fecha = None
        if pub:
            try:
                from email.utils import parsedate_to_datetime
                fecha = parsedate_to_datetime(pub).astimezone(dt.timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
        items.append(_item("Google Trends ES", titulo + ". " + " | ".join(noticias),
                           next((u for u in urls if u), "https://trends.google.es/trending?geo=ES"),
                           fecha, int(trafico) / 10))
    return items


# ---------------------------------------------------------------- Google Fact Check API (muchos verificadores a la vez)
def leer_factcheck():
    clave = os.environ.get("FACTCHECK_API_KEY")
    if not clave:
        raise RuntimeError("sin configurar (falta FACTCHECK_API_KEY)")
    items = []
    for q in CONSULTAS_FACTCHECK:
        datos = _get("https://factchecktools.googleapis.com/v1alpha1/claims:search",
                     params={"query": q, "languageCode": "es", "maxAgeDays": 3, "pageSize": 20, "key": clave}).json()
        for c in datos.get("claims", []):
            for cr in c.get("claimReview", [])[:1]:
                texto = f"{cr.get('title') or c.get('text', '')}. Afirmacion: {c.get('text', '')}. Valoracion: {cr.get('textualRating', '')}"
                items.append(_item("FactCheck API: " + cr.get("publisher", {}).get("name", "?"),
                                   texto, cr.get("url", ""), _fecha(cr.get("reviewDate", "")), 0, verificador=True))
        time.sleep(1)
    return items


FUENTES = [
    ("Bluesky", leer_bluesky),
    ("Mastodon", leer_mastodon),
    ("Reddit", leer_reddit),
    ("Telegram", leer_telegram),
    ("Google Trends ES", leer_trends),
    ("Google Fact Check API", leer_factcheck),
]


def leer_redes():
    """Devuelve (items, lineas_de_estado). Las publicaciones con poco alcance se descartan."""
    items, estados = [], []
    for nombre, fn in FUENTES:
        try:
            nuevos = list({i["enlace"]: i for i in fn()}.values())  # una publicacion puede salir en varias busquedas
            if nombre not in ("Google Trends ES", "Google Fact Check API"):
                nuevos = [i for i in nuevos if i["alcance"] >= MIN_ALCANCE]
            vistos_url = {i["enlace"] for i in items}
            nuevos = [i for i in nuevos if not (i["enlace"] in vistos_url or vistos_url.add(i["enlace"]))]
            items += nuevos
            estados.append(f"  OK     {nombre}: {len(nuevos)} entradas (alcance >= {MIN_ALCANCE})"
                           if nombre not in ("Google Trends ES", "Google Fact Check API")
                           else f"  OK     {nombre}: {len(nuevos)} entradas")
        except Exception as e:
            estados.append(f"  AVISO  {nombre}: {str(e)[:90]}")
    return items, estados
