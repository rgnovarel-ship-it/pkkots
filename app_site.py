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


init()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5200")), debug=False)
