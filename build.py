#!/usr/bin/env python3
"""Genera index.html con titulares de periódicos y estrenos de cine.
Solo usa la librería estándar. Ejecutar a diario (ver README en la respuesta).

Variables de entorno:
  TMDB_API_KEY  clave gratuita de https://www.themoviedb.org/settings/api
"""
import os, json, html, datetime, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

# ---- CONFIG: comprueba que las URLs de los feeds siguen vigentes ----
FEEDS = {
    "elDiario.es": "https://www.eldiario.es/rss/",
    "El País": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    "Nós Diario": "https://www.nosdiario.gal/rss",          # VERIFICAR
    "Faro de Vigo": "https://www.farodevigo.es/rss/",       # VERIFICAR
}
ITEMS_PER_FEED = 8
UA = {"User-Agent": "Mozilla/5.0 (portal-personal)"}


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def read_feed(url):
    root = ET.fromstring(fetch(url))
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if title and link:
            out.append((title, link))
        if len(out) >= ITEMS_PER_FEED:
            break
    return out


def news():
    sections = {}
    for name, url in FEEDS.items():
        try:
            sections[name] = read_feed(url)
        except Exception as e:  # un feed caído no rompe el resto
            sections[name] = []
            print(f"[aviso] {name}: {e}")
    return sections


def cine():
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        return []
    q = urllib.parse.urlencode(
        {"api_key": key, "language": "es-ES", "region": "ES"}
    )
    films = []
    for kind in ("now_playing", "upcoming"):
        try:
            data = json.loads(fetch(f"https://api.themoviedb.org/3/movie/{kind}?{q}"))
            for m in data.get("results", [])[:12]:
                films.append((kind, m["title"], m.get("release_date", ""),
                              f"https://www.themoviedb.org/movie/{m['id']}"))
        except Exception as e:
            print(f"[aviso] TMDB {kind}: {e}")
    return films


def teatro():
    """Pendiente: no hay fuente única. Añade aquí un scraper por teatro
    (Teatro Español, Teatros del Canal, CDN...) que devuelva
    una lista de (título, fechas, enlace)."""
    return []


def li(title, url, extra=""):
    return (f'<li><a href="{html.escape(url)}" target="_blank" rel="noopener">'
            f'{html.escape(title)}</a> <small>{html.escape(extra)}</small></li>')


def render():
    today = datetime.date.today().strftime("%d/%m/%Y")
    parts = [f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mi portal diario</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:760px;margin:auto;padding:1rem;line-height:1.4}}
h1{{font-size:1.4rem}} h2{{margin-top:1.6rem;border-bottom:1px solid #8884}}
li{{margin:.4rem 0}} small{{opacity:.65}}
@media(prefers-color-scheme:dark){{body{{background:#111;color:#eee}}a{{color:#8ab4ff}}}}
</style></head><body><h1>Mi portal diario · {today}</h1>"""]

    parts.append("<h2>Noticias</h2>")
    for name, items in news().items():
        parts.append(f"<h3>{html.escape(name)}</h3><ul>")
        parts += [li(t, u) for t, u in items] or ["<li><small>Sin datos hoy</small></li>"]
        parts.append("</ul>")

    films = cine()
    parts.append("<h2>Cine (España)</h2><ul>")
    if films:
        for kind, t, d, u in films:
            label = "En cartel" if kind == "now_playing" else "Próximamente"
            parts.append(li(t, u, f"{label} · {d}"))
    else:
        parts.append("<li><small>Configura TMDB_API_KEY</small></li>")
    parts.append("</ul>")

    parts.append("<h2>Teatro (Madrid)</h2><ul>")
    shows = teatro()
    parts += [li(t, u, d) for t, d, u in shows] or ["<li><small>Pendiente de añadir fuentes</small></li>"]
    parts.append("</ul></body></html>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(render())
    print("Generado", out)
