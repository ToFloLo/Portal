#!/usr/bin/env python3
"""Genera index.html: titulares con resumen e imagen + cine (TMDB).
Solo usa la librería estándar de Python.

Variable de entorno opcional:
  TMDB_API_KEY  clave gratuita de https://www.themoviedb.org/settings/api
"""
import os, re, json, html, datetime, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

# ---- CONFIG ---------------------------------------------------------
# "feed": dirección RSS si la conoces (o None). "home": portada del diario;
# si el feed falla o es None, el script busca el RSS en la propia portada.
SOURCES = {
    "elDiario.es":  {"feed": "https://www.eldiario.es/rss/", "home": "https://www.eldiario.es"},
    "El País":      {"feed": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
                     "home": "https://elpais.com"},
    "Nós Diario":   {"feed": None, "home": "https://www.nosdiario.gal"},
    "Faro de Vigo": {"feed": None, "home": "https://www.farodevigo.es"},
}
ITEMS_PER_FEED = 6
SUMMARY_CHARS = 220
UA = {"User-Agent": "Mozilla/5.0 (portal-personal)"}
# ---------------------------------------------------------------------


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def local(tag):
    return tag.rsplit("}", 1)[-1]


def clean(raw, limit=SUMMARY_CHARS):
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return text


def parse_item(it):
    title = link = img = raw = ""
    for ch in it:
        n = local(ch.tag)
        if n == "title":
            title = (ch.text or "").strip()
        elif n == "link":
            link = (ch.text or ch.get("href") or "").strip() or link
        elif n in ("description", "summary") and not raw:
            raw = ch.text or ""
        elif n == "encoded" and not raw:
            raw = ch.text or ""
        elif n in ("content", "thumbnail") and ch.get("url") and not img:
            kind = (ch.get("type") or "") + (ch.get("medium") or "")
            if "video" not in kind:
                img = ch.get("url")
        elif n == "enclosure" and (ch.get("type") or "").startswith("image") and not img:
            img = ch.get("url")
    if not img:
        m = re.search(r'<img[^>]+src=["\']([^"\']+)', raw)
        if m:
            img = html.unescape(m.group(1))
    return {"title": title, "link": link, "img": img, "summary": clean(raw)}


def read_feed(url):
    root = ET.fromstring(fetch(url))
    out = []
    for it in root.iter():
        if local(it.tag) in ("item", "entry"):
            d = parse_item(it)
            if d["title"] and d["link"]:
                out.append(d)
            if len(out) >= ITEMS_PER_FEED:
                break
    return out


def discover_feed(home):
    """Busca <link rel="alternate" type="application/rss+xml"> en la portada."""
    page = fetch(home).decode("utf-8", "ignore")
    for tag in re.findall(r"<link\b[^>]*>", page, flags=re.I):
        if re.search(r"application/(rss|atom)\+xml", tag, flags=re.I):
            m = re.search(r'href=["\']([^"\']+)', tag)
            if m:
                return urllib.parse.urljoin(home, html.unescape(m.group(1)))
    return None


def news():
    sections = {}
    for name, cfg in SOURCES.items():
        items, tried = [], []
        candidates = [cfg.get("feed")]
        for i in range(2):  # 2º intento: autodescubrir desde la portada
            url = candidates[0] if i == 0 else None
            try:
                if i == 1:
                    url = discover_feed(cfg["home"])
                if not url:
                    continue
                tried.append(url)
                items = read_feed(url)
                if items:
                    print(f"[ok] {name}: {url}")
                    break
            except Exception as e:
                print(f"[aviso] {name} ({url}): {e}")
        if not items:
            print(f"[aviso] {name}: sin datos. Probado: {tried or 'nada'}")
        sections[name] = items
    return sections


def cine():
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        return []
    q = urllib.parse.urlencode({"api_key": key, "language": "es-ES", "region": "ES"})
    films = []
    for kind in ("now_playing", "upcoming"):
        try:
            data = json.loads(fetch(f"https://api.themoviedb.org/3/movie/{kind}?{q}"))
            for m in data.get("results", [])[:12]:
                poster = m.get("poster_path")
                films.append({
                    "kind": kind, "title": m["title"], "date": m.get("release_date", ""),
                    "summary": clean(m.get("overview", "")),
                    "img": f"https://image.tmdb.org/t/p/w185{poster}" if poster else "",
                    "link": f"https://www.themoviedb.org/movie/{m['id']}",
                })
        except Exception as e:
            print(f"[aviso] TMDB {kind}: {e}")
    return films


def teatro():
    """Pendiente: añadir un lector por teatro. Debe devolver una lista de
    dicts con title, date, summary, img, link."""
    return []


def card(d, extra=""):
    e = html.escape
    img = (f'<img src="{e(d["img"])}" alt="" loading="lazy" referrerpolicy="no-referrer">'
           if d.get("img") else '<div class="ph"></div>')
    small = f'<small>{e(extra)}</small>' if extra else ""
    summ = f'<p>{e(d["summary"])}</p>' if d.get("summary") else ""
    return (f'<article><a class="th" href="{e(d["link"])}" target="_blank" rel="noopener">{img}</a>'
            f'<div><h4><a href="{e(d["link"])}" target="_blank" rel="noopener">{e(d["title"])}</a></h4>'
            f'{small}{summ}</div></article>')


CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--ln:#0002;--lk:#0b57d0}
@media(prefers-color-scheme:dark){:root{--bg:#111;--fg:#eee;--mut:#aaa;--ln:#fff3;--lk:#8ab4ff}}
*{box-sizing:border-box}
body{margin:0 auto;max-width:760px;padding:1rem;background:var(--bg);color:var(--fg);
 font-family:system-ui,sans-serif;line-height:1.4}
h1{font-size:1.4rem} h2{margin-top:2rem;border-bottom:1px solid var(--ln);padding-bottom:.3rem}
h3{margin:1.4rem 0 .4rem} h4{margin:0 0 .2rem;font-size:1rem}
a{color:var(--lk);text-decoration:none}
article{display:flex;gap:.8rem;padding:.7rem 0;border-bottom:1px solid var(--ln)}
article .th{flex:0 0 96px}
article img,.ph{width:96px;height:72px;object-fit:cover;border-radius:6px;background:var(--ln);display:block}
article p{margin:.3rem 0 0;font-size:.9rem;color:var(--mut)}
small{color:var(--mut)}
"""


def render():
    today = datetime.date.today().strftime("%d/%m/%Y")
    out = [f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>Mi portal diario</title><style>{CSS}</style></head><body>'
           f'<h1>Mi portal diario · {today}</h1><h2>Noticias</h2>']
    for name, items in news().items():
        out.append(f"<h3>{html.escape(name)}</h3>")
        out += [card(d) for d in items] or ["<p><small>Sin datos hoy</small></p>"]

    out.append("<h2>Cine (España)</h2>")
    films = cine()
    if films:
        for f in films:
            label = "En cartel" if f["kind"] == "now_playing" else "Próximamente"
            out.append(card(f, f"{label} · {f['date']}"))
    else:
        out.append("<p><small>Configura TMDB_API_KEY para ver el cine</small></p>")

    out.append("<h2>Teatro (Madrid)</h2>")
    shows = teatro()
    out += [card(s, s.get("date", "")) for s in shows] or ["<p><small>Pendiente de añadir fuentes</small></p>"]
    out.append("</body></html>")
    return "\n".join(out)


if __name__ == "__main__":
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render())
    print("Generado", path)
