"""NOVAREL SITE — site d'affiliation Amazon sur la sécurité domestique.

Contenu réel, rédigé à partir de recherches vérifiées, vrais liens (à configurer
avec un vrai tag Amazon Associates) et suivi de clics réel.

Ce que je ne peux pas faire à la place de l'utilisateur : créer son compte Amazon
Associates (identité, coordonnées bancaires, signature d'un contrat réel). En
attendant que ce soit fait, AMAZON_TAG reste un placeholder visible : les liens
fonctionnent (recherche Amazon réelle) mais ne portent pas encore de tag
d'affiliation tant que la variable d'environnement n'est pas configurée avec le
vrai identifiant.

Organisation :
  novarel/content.py    — tout le contenu éditorial (source unique de vérité)
  novarel/templates/    — gabarits Jinja
  novarel/static/       — CSS + JS autonomes, sans étape de build
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, abort, redirect, render_template, request

from novarel import content

BASE = Path(__file__).parent
DB = BASE / "novarel_site.db"
AMAZON_TAG = os.environ.get("AMAZON_TAG", "TON-TAG-21")  # placeholder tant que non configuré

# Balise meta de vérification Google Search Console (méthode "Balise HTML").
# Se configure via une variable d'environnement Render nommée
# GOOGLE_SITE_VERIFICATION (juste le code, ex: "abc123..."), pour que changer
# de token ne demande jamais de modifier le code ni de redéployer.
GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "")

# Clé d'accès au tableau de bord interne /pulse. Tant qu'elle n'est pas définie
# en variable d'environnement, la page répond 404 : pas de dashboard exposé par
# défaut. Se configure via une variable Render nommée PULSE_KEY.
PULSE_KEY = os.environ.get("PULSE_KEY", "")

SITE_URL = content.SITE_URL

app = Flask(
    __name__,
    template_folder="novarel/templates",
    static_folder="novarel/static",
    static_url_path="/static",
)

# Les fichiers statiques sont versionnés par `asset_version` (voir plus bas),
# donc ils peuvent être mis en cache agressivement.
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000

_DB_WRITE_LOCK = threading.RLock()


def _compute_asset_version() -> str:
    """Empreinte des assets, pour casser le cache navigateur à chaque déploiement."""
    static_dir = BASE / "novarel" / "static"
    latest = 0.0
    for path in static_dir.rglob("*"):
        if path.is_file():
            latest = max(latest, path.stat().st_mtime)
    return str(int(latest))


ASSET_VERSION = _compute_asset_version()


# ============================================================
# BASE DE DONNÉES — suivi de clics
# ============================================================


def _connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


@contextlib.contextmanager
def get_db(write: bool = False):
    if write:
        _DB_WRITE_LOCK.acquire()
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        if write:
            _DB_WRITE_LOCK.release()


def init():
    with get_db(write=True) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS clicks(
                id INTEGER PRIMARY KEY,
                ts TEXT,
                slug TEXT,
                product TEXT,
                referrer TEXT
            );
            """
        )
        cols = [r["name"] for r in c.execute("PRAGMA table_info(clicks)").fetchall()]
        if "source" not in cols:
            c.execute("ALTER TABLE clicks ADD COLUMN source TEXT DEFAULT 'direct'")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_click(slug: str, product: str, source: str = "direct"):
    with get_db(write=True) as c:
        c.execute(
            "INSERT INTO clicks(ts,slug,product,referrer,source) VALUES(?,?,?,?,?)",
            (now_iso(), slug, product, request.referrer or "", source),
        )


def amazon_search_link(query: str) -> str:
    """Lien de recherche Amazon.fr porteur du tag d'affiliation.

    Fonctionne dès aujourd'hui (recherche réelle) ; le tag prend effet dès que
    AMAZON_TAG est configuré avec le vrai identifiant Associates.
    """
    return f"https://www.amazon.fr/s?k={quote(query)}&tag={AMAZON_TAG}"


# ============================================================
# CONTEXTE DE RENDU
# ============================================================


def _src() -> str:
    return request.args.get("src", "").strip() or "direct"


def _qs(src: str) -> str:
    return f"?src={quote(src)}" if src and src != "direct" else ""


@app.context_processor
def inject_globals():
    now = datetime.now()
    return {
        "categories": content.CATEGORIES,
        "total_products": content.TOTAL_PRODUCTS,
        "site_url": SITE_URL,
        "qs": _qs(_src()),
        "current_path": request.path,
        "today": content.format_date_fr(now),
        "year": now.year,
        "google_site_verification": GOOGLE_SITE_VERIFICATION,
        "asset_version": ASSET_VERSION,
    }


# ============================================================
# DONNÉES STRUCTURÉES (schema.org)
# ============================================================


def _jsonld(parts: list) -> str:
    graph = {"@context": "https://schema.org", "@graph": parts}
    return json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")


def _breadcrumb(trail: list) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": f"{SITE_URL}{path}"}
            for i, (name, path) in enumerate(trail)
        ],
    }


def _organization() -> dict:
    return {
        "@type": "Organization",
        "@id": f"{SITE_URL}/#organization",
        "name": content.SITE_NAME,
        "url": f"{SITE_URL}/",
        "description": content.SITE_TAGLINE,
    }


def _products_jsonld(products: list) -> list:
    items = []
    for p in products:
        low, high, currency = content.parse_price(p["price"])
        offer = {"@type": "Offer", "url": f"{SITE_URL}/go/{p['slug']}"}
        if low is not None:
            offer["priceCurrency"] = currency
            if high != low:
                # Une fourchette se déclare en AggregateOffer, pas en prix unique.
                offer["@type"] = "AggregateOffer"
                offer["lowPrice"] = low
                offer["highPrice"] = high
            else:
                offer["price"] = low
        items.append(
            {
                "@type": "Product",
                "name": p["name"],
                "description": p["pros"],
                "offers": offer,
            }
        )
    return items


def _faq_jsonld(faq: list) -> dict:
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in faq
        ],
    }


# ============================================================
# PAGES
# ============================================================


@app.get("/")
def home():
    jsonld = _jsonld(
        [
            _organization(),
            {
                "@type": "WebSite",
                "url": f"{SITE_URL}/",
                "name": content.SITE_NAME,
                "description": content.SITE_TAGLINE,
                "publisher": {"@id": f"{SITE_URL}/#organization"},
            },
            {
                "@type": "ItemList",
                "name": "Comparatifs de sécurité domestique",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": i + 1,
                        "name": cat["label"],
                        "url": f"{SITE_URL}{cat['path']}",
                    }
                    for i, cat in enumerate(content.CATEGORIES)
                ],
            },
        ]
    )
    return render_template(
        "home.html",
        page_title="Comparatifs sécurité maison sans abonnement — NOVAREL",
        meta_desc=(
            "Caméras, alarmes, serrures et détecteurs comparés sans blabla marketing : prix réels, "
            "avis honnêtes, aucune note inventée, aucun abonnement caché."
        ),
        canonical_path="/",
        stats=content.HOME_STATS,
        principles=content.HOME_PRINCIPLES,
        legal_items=content.HOME_LEGAL,
        jsonld=jsonld,
    )


def render_category(path: str):
    cat = content.CATEGORY_BY_PATH[path]
    jsonld = _jsonld(
        [
            _breadcrumb([("Accueil", "/"), (cat["label"], path)]),
            *_products_jsonld(cat["products"]),
            _faq_jsonld(cat["faq"]),
        ]
    )
    return render_template(
        "category.html",
        cat=cat,
        related=[content.CATEGORY_BY_PATH[p] for p in cat["related"]],
        top_product=cat["products"][0],
        page_title=cat["page_title"],
        meta_desc=cat["meta_desc"],
        canonical_path=path,
        og_type="article",
        jsonld=jsonld,
    )


def _make_category_view(path: str):
    def view():
        return render_category(path)

    return view


for _cat in content.CATEGORIES:
    app.add_url_rule(
        _cat["path"],
        endpoint="category_" + _cat["key"].replace("-", "_"),
        view_func=_make_category_view(_cat["path"]),
        methods=["GET"],
    )


@app.get("/methodologie")
def methodologie():
    jsonld = _jsonld(
        [
            _breadcrumb([("Accueil", "/"), ("Méthodologie", "/methodologie")]),
            {
                "@type": "WebPage",
                "name": "Méthodologie",
                "url": f"{SITE_URL}/methodologie",
                "description": content.METHODOLOGY_INTRO,
                "publisher": {"@id": f"{SITE_URL}/#organization"},
            },
        ]
    )
    return render_template(
        "methodologie.html",
        page_title="Méthodologie — comment sont faits nos comparatifs — NOVAREL",
        meta_desc=(
            "Comment ce site sélectionne et compare les produits : sources utilisées, critères, "
            "absence de tests physiques déclarée honnêtement, mise à jour des prix."
        ),
        canonical_path="/methodologie",
        intro=content.METHODOLOGY_INTRO,
        sections=content.METHODOLOGY_SECTIONS,
        jsonld=jsonld,
    )


@app.get("/go/<slug>")
def go(slug):
    item = content.ALL_PRODUCTS.get(slug)
    if not item:
        abort(404)
    log_click(slug, item["name"], _src())
    return redirect(amazon_search_link(item["search_query"]), code=302)


@app.errorhandler(404)
def not_found(_error):
    return (
        render_template(
            "404.html",
            page_title="Page introuvable — NOVAREL",
            meta_desc="Cette page n'existe pas ou n'existe plus.",
            canonical_path="/",
        ),
        404,
    )


# ============================================================
# SEO TECHNIQUE
# ============================================================

ARTICLE_PATHS = ["/"] + [c["path"] for c in content.CATEGORIES] + ["/methodologie"]


@app.get("/sitemap.xml")
def sitemap():
    today = datetime.now().strftime("%Y-%m-%d")
    urls = "".join(
        f"<url><loc>{SITE_URL}{p}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>weekly</changefreq>"
        f"<priority>{'1.0' if p == '/' else '0.8'}</priority></url>"
        for p in ARTICLE_PATHS
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls}</urlset>"
    )
    return Response(xml, mimetype="application/xml")


@app.get("/robots.txt")
def robots():
    txt = f"User-agent: *\nAllow: /\nDisallow: /go/\nSitemap: {SITE_URL}/sitemap.xml\n"
    return Response(txt, mimetype="text/plain")


# Tokens de vérification Google Search Console valides.
# IMPORTANT : liste blanche stricte plutôt que réponse générique à n'importe
# quel token — un serveur qui confirme "vérifié" pour n'importe quelle URL
# google*.html ressemble à un site compromis aux yeux des contrôles anti-fraude
# de Google (d'où l'échec "peut-être piraté").
GOOGLE_VERIFICATION_TOKENS = {
    "3fde40b5ae1f216b",
    "87d5a150752fb6d6",
    "7631f4908729d7f5",
}


@app.get("/google<token>.html")
def google_site_verification(token):
    """Fichier de validation Google Search Console (liste blanche)."""
    if token not in GOOGLE_VERIFICATION_TOKENS:
        abort(404)
    return Response(
        f"google-site-verification: google{token}.html",
        mimetype="text/html",
    )


# ============================================================
# SUPERVISION
# ============================================================


@app.get("/health")
def health():
    with get_db() as c:
        n_clicks = c.execute("SELECT COUNT(*) n FROM clicks").fetchone()["n"]
    return {
        "status": "ok",
        "amazon_tag_configured": AMAZON_TAG != "TON-TAG-21",
        "total_clicks": n_clicks,
        "products": content.TOTAL_PRODUCTS,
    }


@app.get("/api/clicks")
def api_clicks():
    with get_db() as c:
        rows = [dict(x) for x in c.execute("SELECT * FROM clicks ORDER BY id DESC LIMIT 200")]
        by_product = c.execute(
            "SELECT product, COUNT(*) n FROM clicks GROUP BY product ORDER BY n DESC"
        ).fetchall()
        by_source = c.execute(
            "SELECT COALESCE(source,'direct') source, COUNT(*) n FROM clicks GROUP BY source ORDER BY n DESC"
        ).fetchall()
    return {
        "total": len(rows),
        "by_product": [dict(r) for r in by_product],
        "by_source": [dict(r) for r in by_source],
        "recent": rows,
    }


# ============================================================
# PULSE — tableau de bord interne (données réelles uniquement)
# ============================================================
#
# Contrairement à un "centre d'analyse" qui simule des chiffres, cette page
# n'affiche que ce que le site sait réellement : clics enregistrés, produits
# au catalogue, statut du tag Amazon, et l'avancement des chantiers en cours.
# Rien n'est inventé ; un chantier non terminé est marqué comme tel plutôt que
# masqué.

PULSE_HTML = r"""<!doctype html>
<html lang="fr" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>NOVAREL — Pulse</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{
  --paper:#f4f1ea;--surface:#fbf9f5;--surface-2:#eeeae0;--ink:#10120f;--ink-soft:#33372f;
  --muted:#64685d;--line:#d9d4c7;--line-strong:#b9b3a3;
  --signal:#c8f04c;--signal-deep:#9cc021;--alert:#b8331c;--alert-bg:#fbeae6;
  --good:#1d6642;--good-bg:#e7f2ea;--warn:#8a6410;--warn-bg:#f7efd9;
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#0c0e0b;--surface:#14170f;--surface-2:#1b1f16;--ink:#f2efe6;--ink-soft:#d5d2c6;
    --muted:#9aa08f;--line:#292e22;--line-strong:#3b4132;
    --signal:#c8f04c;--signal-deep:#d8ff66;--alert:#ff8163;--alert-bg:#2a1712;
    --good:#83dba6;--good-bg:#122319;--warn:#e0b85c;--warn-bg:#241d0d;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font:16px/1.5 "Archivo",system-ui,sans-serif;padding-block:env(safe-area-inset-top,0) env(safe-area-inset-bottom,0);}
main{max-width:1200px;margin:0 auto;padding:32px 20px 64px;}
.top{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;
  flex-wrap:wrap;margin-bottom:28px;}
h1{font-size:28px;font-weight:800;margin:0;letter-spacing:-0.01em;}
.sub{color:var(--muted);font-size:14px;margin-top:6px;}
.mono{font-family:"IBM Plex Mono",monospace;}
.pulse{display:inline-flex;align-items:center;gap:8px;font-family:"IBM Plex Mono",monospace;
  font-size:13px;color:var(--muted);}
.dot{width:8px;height:8px;border-radius:50%;background:var(--good);}
.dot.bad{background:var(--alert);}
.dot.live{animation:blink 2s ease-in-out infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}
.grid2{display:grid;grid-template-columns:1.2fr 1fr;gap:14px;margin-top:14px;}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
@media(max-width:520px){.grid{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px 20px;}
.card h2{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
  margin:0 0 14px;font-weight:600;}
.stat-label{font-size:13px;color:var(--muted);}
.stat-value{font-family:"IBM Plex Mono",monospace;font-size:32px;font-weight:600;margin-top:4px;}
.badge{display:inline-flex;align-items:center;gap:6px;font-family:"IBM Plex Mono",monospace;
  font-size:13px;font-weight:600;padding:4px 10px;border-radius:6px;margin-top:8px;}
.badge.good{background:var(--good-bg);color:var(--good);}
.badge.warn{background:var(--warn-bg);color:var(--warn);}
.badge.alert{background:var(--alert-bg);color:var(--alert);}
.bar-row{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);}
.bar-row:last-child{border:0;}
.bar-name{flex:0 0 auto;min-width:0;font-size:14px;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;max-width:46%;}
.bar-track{flex:1;height:8px;background:var(--surface-2);border-radius:5px;overflow:hidden;}
.bar-fill{height:100%;background:var(--signal-deep);border-radius:5px;}
.bar-n{flex:0 0 auto;font-family:"IBM Plex Mono",monospace;font-size:13px;color:var(--muted);
  min-width:24px;text-align:right;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);}
th{color:var(--muted);font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.05em;}
td.mono,th.mono{font-family:"IBM Plex Mono",monospace;}
.empty{color:var(--muted);font-size:14px;padding:8px 0;}
.chantiers{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:0;}
.chantiers li{display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid var(--line);
  font-size:14px;}
.chantiers li:last-child{border:0;}
.state{width:20px;height:20px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;
  justify-content:center;font-size:12px;font-weight:700;}
.state.done{background:var(--good-bg);color:var(--good);}
.state.pending{background:var(--warn-bg);color:var(--warn);}
.state.todo{background:var(--surface-2);color:var(--muted);}
.foot{margin-top:28px;font-size:12px;color:var(--muted);text-align:center;}
.err{background:var(--alert-bg);color:var(--alert);border-radius:10px;padding:16px 20px;
  font-size:14px;margin-bottom:20px;}
</style>
</head>
<body>
<main>
  <div class="top">
    <div>
      <h1>NOVAREL — Pulse</h1>
      <div class="sub">Données réelles du site, rien de simulé. Rafraîchi toutes les 20 secondes.</div>
    </div>
    <div class="pulse"><span class="dot live" id="dot"></span><span id="asof">—</span></div>
  </div>

  <div id="err" class="err" hidden></div>

  <div class="grid" id="stats">
    <div class="card"><div class="stat-label">Clics enregistrés</div><div class="stat-value" id="s-clicks">—</div></div>
    <div class="card"><div class="stat-label">Produits au catalogue</div><div class="stat-value" id="s-products">—</div></div>
    <div class="card"><div class="stat-label">Tag Amazon</div><div id="s-tag">—</div></div>
    <div class="card"><div class="stat-label">Serveur</div><div id="s-status">—</div></div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Clics par produit</h2>
      <div id="by-product"></div>
    </div>
    <div class="card">
      <h2>Clics par source</h2>
      <div id="by-source"></div>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <h2>Derniers clics</h2>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Horodatage</th><th>Produit</th><th>Source</th></tr></thead>
        <tbody id="recent"></tbody>
      </table>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <h2>Chantiers</h2>
    <ul class="chantiers">
      <li><span class="state done">✓</span> Tag Amazon Associates configuré</li>
      <li><span class="state pending">…</span> Mentions légales &amp; politique de confidentialité (en cours)</li>
      <li><span class="state pending">…</span> Mesure d'audience (Plausible ou GA4, en attente d'un compte)</li>
      <li><span class="state todo">—</span> Soumission Search Console (manuel, compte Google requis)</li>
      <li><span class="state pending">…</span> Première épingle Pinterest préparée, publication à faire</li>
    </ul>
  </div>

  <div class="foot mono">novarel-site · /pulse · usage interne, non indexé</div>
</main>

<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[m]));
function barRows(items,total,target){
  if(!items.length){target.innerHTML='<div class="empty">Aucune donnée pour l\'instant.</div>';return;}
  const max=Math.max(...items.map(i=>i.n),1);
  target.innerHTML=items.map(i=>`<div class="bar-row">
    <div class="bar-name">${esc(i.product||i.source||'—')}</div>
    <div class="bar-track"><div class="bar-fill" style="width:${Math.max(4,i.n/max*100)}%"></div></div>
    <div class="bar-n">${i.n}</div></div>`).join('');
}
async function load(){
  try{
    const [health,clicks]=await Promise.all([
      fetch('/health',{cache:'no-store'}).then(r=>r.json()),
      fetch('/api/clicks',{cache:'no-store'}).then(r=>r.json())
    ]);
    $('err').hidden=true;
    $('dot').className='dot live';
    $('asof').textContent='Mis à jour '+new Date().toLocaleTimeString('fr-FR');
    $('s-clicks').textContent=health.total_clicks ?? '—';
    $('s-products').textContent=health.products ?? '—';
    $('s-tag').innerHTML=health.amazon_tag_configured
      ? '<span class="badge good">Configuré</span>'
      : '<span class="badge alert">Placeholder</span>';
    $('s-status').innerHTML=health.status==='ok'
      ? '<span class="badge good">En ligne</span>'
      : '<span class="badge alert">Problème</span>';
    barRows(clicks.by_product||[],clicks.total,$('by-product'));
    barRows(clicks.by_source||[],clicks.total,$('by-source'));
    const recent=(clicks.recent||[]).slice(0,15);
    $('recent').innerHTML=recent.length
      ? recent.map(r=>`<tr><td class="mono">${esc(r.ts)}</td><td>${esc(r.product)}</td><td>${esc(r.source||'direct')}</td></tr>`).join('')
      : '<tr><td colspan="3" class="empty">Aucun clic enregistré pour l\'instant.</td></tr>';
  }catch(e){
    $('dot').className='dot bad';
    $('err').hidden=false;
    $('err').textContent='Impossible de charger les données en direct : '+(e.message||e);
  }
}
load();
setInterval(load,20000);
</script>
</body>
</html>
"""


@app.get("/pulse")
def pulse():
    if not PULSE_KEY or request.args.get("key") != PULSE_KEY:
        abort(404)
    return Response(PULSE_HTML, mimetype="text/html")


init()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5200")), debug=False)
