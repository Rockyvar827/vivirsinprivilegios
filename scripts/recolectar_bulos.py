import json
import re
import sys
import unicodedata
import datetime as dt
import time
from pathlib import Path
import requests
import feedparser

# Uso (pensado para ejecutarse TODOS LOS DIAS, p. ej. con un workflow programado):
#   python recolectar_bulos.py            -> ultimos 3 dias, top 15, solo lo NUEVO
#   python recolectar_bulos.py 7 20       -> ultimos 7 dias, top 20
#   python recolectar_bulos.py 3 15 --todos -> incluye tambien lo ya visto otros dias
#   (redes sociales y tendencias: ver redes.py; se activan solas si esta junto a este script)
#   python recolectar_bulos.py --descartados -> ademas lista lo que el filtro DESCARTA de los verificadores,
#                                               para comprobar que no se escapa nada
# ENFOQUE: personas negras migrantes (mujeres y hombres), mujeres negras y estereotipos deshumanizantes.
#
# Guarda un historial en datos/vistos.json (subelo al repositorio) para no repetir candidatos.
# Este script SOLO recoge y ordena candidatos. No usa Gemini y no escribe posts.

HEADERS = {"User-Agent": "vivirsinprivilegios-monitor"}

# (nombre, url, es_verificador)
# Las dos de Maldita figuran en agregadores de RSS como activas.
# El resto NO estan comprobadas: el script te dira cuales responden y cuales no.
FEEDS = [
    ("Maldita.es", "https://maldita.es/feed/", True),
    ("Maldito Bulo", "https://maldita.es/malditobulo/feed", True),
    ("Newtral", "https://www.newtral.es/feed/", True),
    ("EFE Verifica", "https://verifica.efe.com/feed/", True),
    ("Verificat", "https://www.verificat.cat/feed/", True),
    ("Google Noticias: migrantes negros", "https://news.google.com/rss/search?q=migrantes+negros+bulo&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: subsaharianos", "https://news.google.com/rss/search?q=subsaharianos+bulo+OR+estereotipos&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: mujeres negras", "https://news.google.com/rss/search?q=%22mujeres+negras%22+racismo+Espa%C3%B1a&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: mujeres migrantes africanas", "https://news.google.com/rss/search?q=mujeres+migrantes+africanas+estereotipos&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: cayucos Canarias", "https://news.google.com/rss/search?q=cayuco+Canarias+bulo&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: deshumanizacion", "https://news.google.com/rss/search?q=deshumanizar+migrantes+discurso+de+odio&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: afrodescendientes", "https://news.google.com/rss/search?q=afrodescendientes+racismo+Espa%C3%B1a&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: bulo africanos", "https://news.google.com/rss/search?q=bulo+africanos+OR+negros+inmigrantes&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: agresion racista", "https://news.google.com/rss/search?q=agresi%C3%B3n+racista+persona+negra+Espa%C3%B1a&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: odio migrantes Canarias", "https://news.google.com/rss/search?q=discurso+de+odio+migrantes+Canarias&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: latinoamericanos", "https://news.google.com/rss/search?q=latinoamericanos+inmigrantes+bulo+OR+racismo&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: afrolatinos", "https://news.google.com/rss/search?q=afrolatinos+OR+afrocolombianos+OR+dominicanos+racismo+Espa%C3%B1a&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: ley de nietos", "https://news.google.com/rss/search?q=%22ley+de+nietos%22+bulo+OR+nacionalidad&hl=es&gl=ES&ceid=ES:es", False),
    ("Google Noticias: manteros", "https://news.google.com/rss/search?q=manteros+venta+ambulante+racismo&hl=es&gl=ES&ceid=ES:es", False),
]

# ENFOQUE: personas negras migrantes (mujeres y hombres, de cualquier pais, dentro o fuera de la UE),
# mujeres negras y estereotipos deshumanizadores. Se buscan en TITULO + RESUMEN.

# Personas negras / origen subsahariano. Se evita "agujero negro", "mercado negro", etc.
FOCO_NEGRO = re.compile(
    r"afrodescend\w*|afroespa\w*|afroeurope\w*|afrofob\w*|negrofob\w*|antinegr\w*|\bafro\b|blackface|perfil racial|"
    r"subsahariano\w*|africano\w*|africana\w*|"
    r"\b(?:personas?|mujeres?|hombres?|chicas?|chicos?|j[oó]venes|ni[ñn][oa]s?|futbolistas?|jugador(?:es|a|as)?|"
    r"poblaci[oó]n|comunidad(?:es)?|familias?|v[ií]ctimas?|migrantes?|inmigrantes?)\s+negr[oa]s?\b|"
    r"senegal\w*|mali\b|maliense\w*|gambia\w*|guinea\w*|nigeri\w*|camerun\w*|costa de marfil|ghan\w*|"
    r"mauritan\w*|eritre\w*|som[aá]l\w*|et[ií]op\w*|sud[aá]n\w*|congole\w*|angole\w*|cabo verde|"
    r"manter\w*|top manta|venta ambulante|"
    r"cayuco\w*|ruta canaria|ruta atl[aá]ntica|nuadib\w*|el hierro",
    re.I,
)

# Palabras de migracion en general (solo cuentan junto a un estereotipo)
MIGRANTES = re.compile(
    r"inmigra\w*|migrant\w*|migraci\w*|extranjer\w*|refugiad\w*|asilo|\bmenas?\b|cayuco\w*|patera\w*|"
    r"efecto llamada|gran sustituci\w*|paguita\w*|regulariz\w*|empadron\w*|barco nodriza",
    re.I,
)

# Lenguaje y estereotipos deshumanizantes (invasion, plaga, animalizacion, criminalizacion...)
DESHUMANIZANTE = re.compile(
    r"invasi[oó]n|invasor\w*|avalancha|oleada|horda\w*|plaga|par[aá]sit\w*|animales|bestias?|\bmanada\b|"
    r"ilegales|gran sustituci\w*|reemplazo|barco nodriza|efecto llamada|deshumaniz\w*|"
    r"\bmenas?\b.{0,30}(?:peligro\w*|delincuen\w*|violador\w*)",
    re.I,
)
ESTEREOTIPO = re.compile(
    r"delincuen\w*|delinq\w*|criminal\w*|violador\w*|agresi[oó]n sexual|mafias?|ocup[ao]s?|paguita\w*|ajudes?|"
    r"subvencion\w*|ayudas?|empadron\w*|colapso|saturaci\w*|natalidad|dan a luz|dar a luz|"
    r"prostitu\w*|hipersexual\w*|trata de (?:mujeres|personas)|2\.?800",
    re.I,
)

MUJERES = re.compile(
    r"mujer(?:es)?\s+(?:negr\w*|africana\w*|subsahariana\w*|migrante\w*|inmigrante\w*|latinoamericana\w*|dominicana\w*|colombiana\w*|venezolana\w*|cubana\w*|hondure\w*|ecuatoriana\w*)|"
    r"\b(?:chicas?|ni[ñn]as?|madres?)\s+(?:negr\w*|africana\w*|migrante\w*|inmigrante\w*)|"
    r"prostitu\w*|hipersexual\w*|trata de (?:mujeres|personas)|natalidad|dan a luz|dar a luz|pelo afro|cabello afro",
    re.I,
)
HOMBRES = re.compile(
    r"hombres?\s+(?:negr\w*|africano\w*|subsahariano\w*|migrante\w*|inmigrante\w*|latinoamericano\w*|dominicano\w*|colombiano\w*|venezolano\w*|cubano\w*|hondure\w*|ecuatoriano\w*)|"
    r"\bj[oó]venes\s+(?:negr\w*|africano\w*|migrante\w*|inmigrante\w*)|"
    r"\bmenas?\b|manter\w*|top manta|venta ambulante|violador\w*|agresi[oó]n sexual|\bmanada\b",
    re.I,
)

# Falsos positivos: "extranjero" referido a espanoles que viven fuera, politica de otros paises, etc.
EXCLUIR = re.compile(r"voto cera|desde el extranjero|en el extranjero|agujero negro|mercado negro|lista negra|viernes negro|"
    r"pucherazo|fraude electoral|censo electoral|tarjeta censal|granjas? vietnamit\w*", re.I)

# Latinoamericanos (incluye personas afrolatinas: dominicanas, colombianas, venezolanas, cubanas, ecuatorianas,
# hondurenas, haitianas...). Solo cuentan si hay contexto de migracion o nacionalidad, para no
# recoger noticias de politica latinoamericana.
LATAM = re.compile(
    r"latinoamerican\w*|hispanoamerican\w*|sudamerican\w*|afrolatin\w*|afrocolomb\w*|afrovenezol\w*|"
    r"colombian\w*|venezolan\w*|dominican\w*|ecuatorian\w*|cuban[oa]s?\b|hondure\w*|haitian\w*|"
    r"brasile\w*|peruan\w*|ley de nietos|ley de memoria democr\w*",
    re.I,
)
LATAM_CONTEXTO = re.compile(
    r"inmigra\w*|migrant\w*|migraci\w*|extranjer\w*|refugiad\w*|asilo|regulariz\w*|nacionaliz\w*|"
    r"nacionalidad|ley de nietos|empadron\w*|racis\w*|xenof\w*|discrimina\w*|odio|"
    r"estereotip\w*|prostitu\w*|bandas? latinas?|trata de (?:mujeres|personas)",
    re.I,
)


def es_latam(texto):
    return bool(LATAM.search(texto) and LATAM_CONTEXTO.search(texto))


# Avisos de sensibilidad: no excluyen el candidato, pero piden mas cuidado y bajan su puntuacion
POLITICA = re.compile(r"\b(?:Vox|PP|PSOE|Sumar|Podemos|Junts|ERC|Abascal|S[aá]nchez|Feij[oó]o|Ayuso|Gobierno)\b")
ELECTORAL = re.compile(r"elecci\w+|electoral\w*|pucherazo|\bvoto\b|\bvotos\b|\bvotar\b|\bvotando\b", re.I)

# Temas siempre vigentes para cuando una semana no traiga nada de un colectivo.
# Son TEMAS a investigar con datos de la biblioteca, no hechos.
IDEAS_MUJERES = [
    "Mujeres negras: del estereotipo de la hipersexualizacion a la realidad",
    "Trata y prostitucion: no todas las mujeres africanas migrantes son victimas ni lo contrario",
    "Mujeres migrantes negras y trabajo de cuidados: quien sostiene a quien",
    "'Las inmigrantes vienen a parir': que dicen los datos de natalidad y sanidad",
    "Pelo afro, cuerpo y belleza: comentarios que parecen halagos y no lo son",
    "Violencia machista y mujeres negras migrantes: barreras para denunciar",
    "Mujeres latinoamericanas y afrolatinas: del estereotipo de 'cuidadora' o 'exotica' a la realidad",
    "Dominicanas, colombianas, venezolanas: el estereotipo de la prostitucion y que dicen los datos",
]
IDEAS_HOMBRES = [
    "Hombres negros migrantes y delincuencia: que dicen los datos",
    "'Violadores' y 'peligrosos': el estereotipo del hombre negro como amenaza",
    "Manteros y venta ambulante: el estereotipo frente a la realidad legal",
    "Jovenes migrantes solos (menas): del bulo del 'peligro' a los datos de proteccion",
    "Perfil racial: identificaciones policiales y hombres negros",
    "Hombres latinoamericanos y afrolatinos: 'bandas latinas', delincuencia y que dicen los datos",
    "Ley de Nietos y nacionalizados: bulos sobre privilegios y que dice la ley",
]
IDEAS_DESHUMANIZACION = [
    "'Invasion', 'avalancha', 'plaga': como el lenguaje convierte personas en amenaza",
    "'Vuelve a tu pais': el racismo cotidiano hacia personas negras con nacionalidad espanola",
    "Ser negro no es ser extranjero: afroespanolas y afroespanoles nacidos en Espana",
    "Llegar en cayuco no es un delito: que dice la ley y que dicen los datos de llegadas",
    "Animalizar para excluir: de los insultos a los monos en los estadios al discurso politico",
]


DATOS = Path(__file__).resolve().parent.parent / "datos"
VISTOS = DATOS / "vistos.json"


def clave(i):
    """Identificador estable de una entrada: el enlace, o el titulo si es de Google Noticias."""
    if "news.google.com" in i["enlace"] or not i["enlace"]:
        return "t:" + sin_acentos(i["titulo"].lower())[:120]
    return i["enlace"]


def cargar_vistos():
    try:
        v = json.loads(VISTOS.read_text(encoding="utf-8"))
    except Exception:
        return {}
    corte = (dt.date.today() - dt.timedelta(days=60)).isoformat()
    return {k: f for k, f in v.items() if f >= corte}


def guardar_vistos(vistos):
    DATOS.mkdir(parents=True, exist_ok=True)
    VISTOS.write_text(json.dumps(vistos, ensure_ascii=False, indent=1), encoding="utf-8")


def avisos(g):
    texto = " ".join(i["titulo"] for i in g["items"])
    res = []
    if POLITICA.search(texto):
        res.append("POLITICA")
    if ELECTORAL.search(texto):
        res.append("ELECTORAL")
    return res


def texto_grupo(g):
    return " ".join(i["titulo"] + " " + i["resumen"] for i in g["items"])


def etiquetas(g):
    texto = texto_grupo(g)
    res = []
    if FOCO_NEGRO.search(texto):
        res.append("FOCO: PERSONAS NEGRAS")
    if es_latam(texto):
        res.append("LATINOAMERICANOS (incluye afrolatinos)")
    if not res:
        res.append("GENERICO: migrantes, sin foco en personas negras")
    if MUJERES.search(texto):
        res.append("MUJERES")
    if HOMBRES.search(texto):
        res.append("HOMBRES")
    if DESHUMANIZANTE.search(texto):
        res.append("ESTEREOTIPO DESHUMANIZANTE")
    elif ESTEREOTIPO.search(texto):
        res.append("ESTEREOTIPO")
    return res


def es_del_tema(i):
    texto = i["titulo"] + " " + i["resumen"]
    if EXCLUIR.search(texto):
        return False
    if FOCO_NEGRO.search(texto) or es_latam(texto):
        return True
    # migracion en general solo vale si trae un estereotipo o lenguaje deshumanizante
    return bool(MIGRANTES.search(texto) and (DESHUMANIZANTE.search(texto) or ESTEREOTIPO.search(texto)))


def fecha_max(g):
    f = [i["fecha"] for i in g["items"] if i["fecha"]]
    return max(f) if f else dt.datetime.min


PARADAS = set(
    "para como pero sobre entre desde hasta esta este estos estas esto sido "
    "tiene tienen hace hacen todo todos toda todas mas muy sin son los las "
    "del una uno unos unas por con que qué cual cuál donde cuando quien "
    "tras segun contra bajo ante cada otro otra otros otras ser fue era "
    "bulo falso falsa falsos falsas viral virales video imagen".split()
)


def sin_acentos(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def limpiar_html(texto):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", texto or "")).strip()


def palabras(texto):
    t = sin_acentos(texto.lower())
    return {w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 3 and w not in PARADAS}


def fecha_entrada(e):
    for campo in ("published_parsed", "updated_parsed"):
        v = e.get(campo)
        if v:
            return dt.datetime(*v[:6])
    return None


def leer_feed(nombre, url, es_verificador):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 429:  # demasiadas peticiones: esperar y reintentar una vez
        time.sleep(10)
        r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    if "news.google.com" in url:
        time.sleep(2)  # pausa entre consultas a Google para evitar el 429
    datos = feedparser.parse(r.content)
    items = []
    for e in datos.entries:
        items.append({
            "fuente": nombre,
            "verificador": es_verificador,
            "titulo": limpiar_html(e.get("title", "")),
            "resumen": limpiar_html(e.get("summary", ""))[:500],
            "enlace": e.get("link", ""),
            "fecha": fecha_entrada(e),
        })
    return items


GENERICAS = {"inmigrantes", "inmigrante", "migrantes", "migrante", "inmigracion", "migracion",
             "espana", "espanol", "espanola", "gobierno", "elecciones", "personas", "desmontando",
             "noticias", "sobre", "video", "videos"}


def agrupar(items, umbral=0.3):
    """Agrupa noticias del mismo tema: similitud de titulo o 2+ palabras distintivas compartidas."""
    grupos = []
    for it in items:
        p = palabras(it["titulo"])
        if not p:
            continue
        for g in grupos:
            inter = p & g["palabras"]
            union = p | g["palabras"]
            distintivas = {w for w in inter if len(w) >= 5 and w not in GENERICAS}
            if (union and len(inter) / len(union) >= umbral) or len(distintivas) >= 2:
                g["items"].append(it)
                g["palabras"] |= p
                break
        else:
            grupos.append({"palabras": set(p), "items": [it]})
    return grupos


def puntuar(g):
    fuentes = {i["fuente"].split(":")[0] for i in g["items"]}
    hay_verificador = any(i["verificador"] for i in g["items"])
    texto = texto_grupo(g)
    foco = bool(FOCO_NEGRO.search(texto))
    deshum = bool(DESHUMANIZANTE.search(texto))
    estereo = bool(ESTEREOTIPO.search(texto))
    mujer = bool(MUJERES.search(texto))
    limite = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=2)
    reciente = any(i["fecha"] and i["fecha"] >= limite for i in g["items"])
    # mas fuentes distintas = mas repercusion; un verificador implica bulo o discurso viral;
    # mas palabras del tema = mas central; y se premia lo muy reciente
    return (
        len(fuentes) * 2
        + (3 if hay_verificador else 0)
        + (3 if foco else 0)
        + (2 if deshum else 1 if estereo else 0)
        + (1.5 if mujer else 0)
        + (2 if es_latam(texto) else 0)
        + min(sum(i.get("alcance", 0) for i in g["items"]) / 100, 4)  # difusion en redes
        + (1 if reciente else 0)
        + len(g["items"]) * 0.5
        - (2 if avisos(g) else 0)
        - (3 if not hay_verificador else 0)  # sin verificador: es tema, no bulo comprobado
    )


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    todos_flag = "--todos" in sys.argv
    dias = int(args[0]) if len(args) > 0 else 3
    top = int(args[1]) if len(args) > 1 else 15
    hoy = dt.date.today().isoformat()
    vistos = cargar_vistos()
    print(f"REVISION DIARIA {hoy}  (ultimos {dias} dias)")
    print()
    limite = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(days=dias)

    todos = []
    print("ESTADO DE LAS FUENTES")
    for nombre, url, verif in FEEDS:
        try:
            items = leer_feed(nombre, url, verif)
            print(f"  OK     {nombre}: {len(items)} entradas")
            todos += items
        except Exception as e:
            print(f"  ERROR  {nombre}: {str(e)[:90]}")

    hay_redes = False
    try:  # redes.py es OPCIONAL: si no esta junto a este script, simplemente no se usa
        from redes import leer_redes
        hay_redes = True
    except ImportError:
        pass
    if hay_redes:
        print()
        print("REDES Y TENDENCIAS (senales SIN VERIFICAR: sirven de alerta, nunca de fuente)")
        items_redes, estados_redes = leer_redes()
        print("\n".join(estados_redes))
        todos += items_redes

    recientes = [i for i in todos if i["fecha"] is None or i["fecha"] >= limite]
    del_tema = [
        i for i in recientes
        if es_del_tema(i)
    ]
    print()
    print(f"Entradas leidas: {len(todos)}  recientes ({dias} dias): {len(recientes)}  del tema: {len(del_tema)}")

    if "--descartados" in sys.argv:
        print()
        print("DESCARTADOS POR EL FILTRO (solo verificadores, para revisar si se escapa algo):")
        for i in recientes:
            if i["verificador"] and not es_del_tema(i):
                print(f"  - [{i['fuente']}] {i['titulo'][:120]}")
        print()

    grupos = agrupar(del_tema)
    grupos.sort(key=lambda g: (bool(FOCO_NEGRO.search(texto_grupo(g))), es_latam(texto_grupo(g)), puntuar(g), fecha_max(g)), reverse=True)

    for g in grupos:
        nuevas = [i for i in g["items"] if clave(i) not in vistos]
        g["nuevas"] = len(nuevas)
    total_grupos = len(grupos)
    todos_grupos = grupos
    if not todos_flag:
        grupos = [g for g in grupos if g["nuevas"] > 0]
    n_con_novedades = sum(1 for g in grupos if g["nuevas"])
    # Senal de redes = grupo sin ningun verificador que incluye publicaciones de redes o tendencias
    def es_senal(g):
        return not any(i["verificador"] for i in g["items"]) and any(i.get("red") for i in g["items"])
    def alcance(g):
        return sum(i.get("alcance", 0) for i in g["items"])
    senales = sorted([g for g in grupos if es_senal(g)], key=lambda g: (alcance(g), len(g["items"])), reverse=True)
    grupos = [g for g in grupos if not es_senal(g)]
    print(f"Candidatos: {total_grupos}  con novedades desde la ultima revision: {n_con_novedades}")

    resumen = {}
    for g in todos_grupos:  # las ideas dependen de TODO lo visto en la ventana, no solo de lo nuevo
        for e in etiquetas(g):
            resumen[e] = resumen.get(e, 0) + 1
    print()
    print("TEMAS ENCONTRADOS POR COLECTIVO (todos los candidatos, no solo el top):")
    for e, n in resumen.items():
        print(f"  {e}: {n}")
    print()
    print(f"CANDIDATOS (top {top})")
    salida = []
    for n, g in enumerate(grupos[:top], 1):
        puntos = puntuar(g)
        av = avisos(g)
        aviso_txt = f"  ATENCION: {' + '.join(av)}" if av else ""
        estado = "NUEVO" if g["nuevas"] == len(g["items"]) else ("YA VISTO + NOVEDADES" if g["nuevas"] else "YA VISTO")
        sin_verif = "" if any(i["verificador"] for i in g["items"]) else "  SIN VERIFICADOR (solo tema)"
        print(f"{n}. {estado}  puntuacion {puntos:.1f}  [{' + '.join(etiquetas(g))}]{aviso_txt}{sin_verif}  fuentes: {', '.join(sorted({i['fuente'] for i in g['items']}))}")
        for i in g["items"][:4]:
            marca = "[VERIFICADOR] " if i["verificador"] else ""
            print(f"     {marca}{i['titulo'][:150]}")
            enlace = i["enlace"]
            if "news.google.com" in enlace:
                enlace = "(enlace de Google Noticias: solo sirve como senal de repercusion)"
            print(f"       {enlace}")
        salida.append({
            "estado": estado,
            "puntuacion": puntos,
            "etiquetas": etiquetas(g),
            "avisos": av,
            "entradas": [
                {**i, "fecha": i["fecha"].isoformat() if i["fecha"] else None}
                for i in g["items"]
            ],
        })

    if hay_redes:
        print()
        print(f"SENALES EN REDES, SIN VERIFICAR (top {min(top, 10)}): alerta para investigar, NO se publica nada sin fuente")
        if not senales:
            print("  (ninguna con alcance suficiente en esta revision)")
    for n, g in enumerate(senales[:10], 1):
        av = avisos(g)
        estado = "NUEVO" if g["nuevas"] == len(g["items"]) else "YA VISTO + NOVEDADES"
        print(f"S{n}. {estado}  alcance {alcance(g):.0f}  publicaciones: {len(g['items'])}  [{' + '.join(etiquetas(g))}]"
              f"{'  ATENCION: ' + ' + '.join(av) if av else ''}  en: {', '.join(sorted({i['fuente'] for i in g['items']}))}")
        for i in sorted(g["items"], key=lambda x: x.get("alcance", 0), reverse=True)[:2]:
            print(f"     ({i.get('alcance', 0):.0f}) {i['titulo'][:150]}")
            print(f"       {i['enlace']}")
        salida.append({
            "tipo": "senal_red", "estado": estado, "alcance": alcance(g), "etiquetas": etiquetas(g), "avisos": av,
            "entradas": [{**i, "fecha": i["fecha"].isoformat() if i["fecha"] else None} for i in g["items"]],
        })

    # ALERTAS: lo urgente, para que un workflow te lo notifique (datos/alertas.md; se borra si no hay)
    ALERTA_ALCANCE = 200
    alertas = []
    for g in grupos:
        et = etiquetas(g)
        if g["nuevas"] and any(e.startswith(("FOCO", "LATINO")) for e in et) and any(i["verificador"] for i in g["items"]):
            v = next(i for i in g["items"] if i["verificador"])
            alertas.append(f"- VERIFICADO NUEVO [{', '.join(et)}]: {v['titulo'][:140]}\n  {v['enlace']}")
    for g in senales:
        if g["nuevas"] and alcance(g) >= ALERTA_ALCANCE:
            top_i = max(g["items"], key=lambda x: x.get("alcance", 0))
            alertas.append(f"- SENAL EN REDES SIN VERIFICAR (alcance {alcance(g):.0f}, {len(g['items'])} publicaciones) "
                           f"[{', '.join(etiquetas(g))}]: {top_i['titulo'][:140]}\n  {top_i['enlace']}")
    DATOS.mkdir(parents=True, exist_ok=True)
    fa = DATOS / "alertas.md"
    if alertas:
        fa.write_text(f"# Alertas {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n" + "\n".join(alertas) + "\n", encoding="utf-8")
        print()
        print(f"ALERTAS ({len(alertas)}): escritas en {fa}")
    elif fa.exists():
        fa.unlink()

    ruta = DATOS / f"candidatos_{dt.datetime.now().strftime('%Y-%m-%d_%H%M')}.json"
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    for g in grupos + senales:
        for i in g["items"]:
            vistos.setdefault(clave(i), hoy)
    guardar_vistos(vistos)
    faltan = [
        ("MUJERES", "MUJERES NEGRAS", IDEAS_MUJERES),
        ("HOMBRES", "HOMBRES NEGROS", IDEAS_HOMBRES),
        ("ESTEREOTIPO DESHUMANIZANTE", "LENGUAJE DESHUMANIZANTE", IDEAS_DESHUMANIZACION),
    ]
    for etq, nombre, ideas in faltan:
        if etq not in resumen:
            print()
            print(f"SIN NOTICIAS DE {nombre} EN LOS ULTIMOS {dias} DIAS. IDEAS SIEMPRE VIGENTES (rotan cada dia):")
            k = dt.date.today().toordinal()
            for idea in (ideas[k % len(ideas)], ideas[(k + 1) % len(ideas)]):
                print(f"  - {idea}")
    print()
    print(f"Guardado en {ruta}")


if __name__ == "__main__":
    main()