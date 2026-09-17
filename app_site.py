"""
NOVAREL SITE — le premier vrai site d'affiliation, contenu réel.

Contrairement à NOVAREL et NOVAREL CAPITAL (100% simulation), ce site est
RÉEL : vrai contenu rédigé à partir de recherches vérifiées, vrais liens
(à configurer avec un vrai tag Amazon Associates), vrai suivi de clics.

Ce que je ne peux pas faire à la place de l'utilisateur : créer son compte
Amazon Associates (identité, coordonnées bancaires, signature d'un contrat
réel). En attendant que ce soit fait, AMAZON_TAG reste un placeholder
visible : les liens fonctionnent (recherche Amazon réelle) mais ne portent
pas encore de tag d'affiliation tant que la variable d'environnement n'est
pas configurée avec le vrai identifiant.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, redirect, request

BASE = Path(__file__).parent
DB = BASE / "novarel_site.db"
AMAZON_TAG = os.environ.get("AMAZON_TAG", "TON-TAG-21")  # placeholder tant que non configuré

app = Flask(__name__)

_DB_WRITE_LOCK = threading.RLock()


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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def amazon_search_link(query: str) -> str:
    """Construit un lien de recherche Amazon.fr porteur du tag d'affiliation.
    Fonctionne dès aujourd'hui (recherche réelle) ; le tag prend effet dès
    que AMAZON_TAG est configuré avec le vrai identifiant Associates.
    """
    return f"https://www.amazon.fr/s?k={quote(query)}&tag={AMAZON_TAG}"


def log_click(slug: str, product: str):
    with get_db(write=True) as c:
        c.execute(
            "INSERT INTO clicks(ts,slug,product,referrer) VALUES(?,?,?,?)",
            (now_iso(), slug, product, request.referrer or ""),
        )


# ============================================================
# CONTENU RÉEL — article de comparatif
# ============================================================
# Rassemblé à partir de recherches vérifiées (comparatifs indépendants,
# fiches produit). Les prix sont des ordres de grandeur : à vérifier au
# moment de l'achat, ils varient dans le temps.

CAMERAS = [
    {
        "slug": "reolink-argus-4-pro",
        "name": "Reolink Argus 4 Pro",
        "price": "≈150–180 €",
        "power": "Batterie",
        "resolution": "4K",
        "storage": "Carte SD locale / NVR — aucun abonnement requis",
        "pros": "Excellent angle de vue (180°), flux RTSP pour les utilisateurs avancés, polyvalente",
        "cons": "Batterie à recharger périodiquement selon l'usage",
        "search_query": "Reolink Argus 4 Pro caméra extérieure",
    },
    {
        "slug": "reolink-rlc-810a",
        "name": "Reolink RLC-810A",
        "price": "≈90–120 €",
        "power": "Filaire (PoE)",
        "resolution": "4K",
        "storage": "Carte SD ou NAS — gratuit, sans abonnement",
        "pros": "Qualité d'image très stable (pas de coupure batterie), vision nocturne couleur",
        "cons": "Nécessite un câblage Ethernet (PoE), installation un peu plus technique",
        "search_query": "Reolink RLC-810A caméra PoE",
    },
    {
        "slug": "blink-outdoor-4",
        "name": "Blink Outdoor 4",
        "price": "≈100 € (souvent en kit)",
        "power": "Batterie (jusqu'à 2 ans d'autonomie annoncée)",
        "resolution": "1080p",
        "storage": "Stockage local basique gratuit ; fonctions IA avancées via abonnement optionnel",
        "pros": "Installation la plus simple du comparatif, très bonne autonomie, écosystème Amazon",
        "cons": "Résolution plus modeste que les modèles 4K, certaines fonctions réservées à l'abonnement",
        "search_query": "Blink Outdoor 4 caméra extérieure sans fil",
    },
    {
        "slug": "eufycam-gamme",
        "name": "EufyCam (gamme avec HomeBase)",
        "price": "≈200–250 € (kit avec base)",
        "power": "Batterie",
        "resolution": "2K à 4K selon le modèle",
        "storage": "100% local via la HomeBase — réputée sans aucun frais récurrent",
        "pros": "Aucun coût récurrent même pour la détection intelligente, marque reconnue sur ce point précis",
        "cons": "Investissement de départ plus élevé (la base HomeBase est obligatoire)",
        "search_query": "EufyCam HomeBase caméra sécurité",
    },
]

ARTICLE_INTRO = (
    "« Sans abonnement » est devenu un argument marketing que presque toutes les marques "
    "utilisent — jusqu'à ce qu'on découvre, une fois la caméra installée, qu'elle n'enregistre "
    "que 24 heures sans le plan cloud payant, ou que la détection intelligente est bloquée sans "
    "abonnement actif. Ce comparatif ne retient que des modèles dont les fonctions essentielles "
    "(enregistrement, détection de mouvement, vision nocturne) fonctionnent réellement sans "
    "dépenser un centime de plus après l'achat."
)

PLACEMENT_TIPS = [
    ("Entrée principale", "Au-dessus de la porte, à 2,5–3 m de hauteur, couvrant l'allée d'accès."),
    ("Portail / garage", "Vue sur les véhicules entrant et sortant."),
    ("Façade arrière", "La cour ou le jardin, souvent la zone la plus isolée d'un logement."),
    ("Angle de la maison", "Permet de couvrir deux façades avec un seul appareil bien placé."),
]


# ============================================================
# GABARIT HTML
# ============================================================

BASE_STYLE = """
*{box-sizing:border-box}body{margin:0;background:#0b0f14;color:#e8edf2;font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:840px;margin:auto;padding:28px 20px}
h1{font-size:32px;margin:0 0 10px}h2{font-size:22px;margin:32px 0 12px;color:#eaf2f8}
.lede{color:#9fb0c0;font-size:17px}
a{color:#7ec4ff}
.badge{display:inline-block;background:#132132;border:1px solid #24425f;border-radius:20px;padding:4px 12px;font-size:12px;color:#8fc4ff;margin-bottom:14px}
.card{background:#111925;border:1px solid #223046;border-radius:14px;padding:20px;margin:18px 0}
.card h3{margin:0 0 6px;font-size:20px}
.price{color:#7bd88f;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:14px 0;font-size:14px}
.grid div span{color:#7f93a8}
.pros{color:#7bd88f}.cons{color:#ff9b9b}
.btn{display:inline-block;margin-top:12px;padding:10px 18px;background:#ff9900;color:#111;font-weight:700;border-radius:8px;text-decoration:none}
table{width:100%;border-collapse:collapse;margin:18px 0;font-size:14px}
th,td{text-align:left;padding:9px;border-bottom:1px solid #223046}
th{color:#8fa3b7}
.tips{background:#0f1620;border-left:3px solid #7ec4ff;border-radius:8px;padding:14px 18px;margin:18px 0}
.tips b{display:block;margin-bottom:2px}
footer{color:#6b7c8d;font-size:13px;margin-top:40px;border-top:1px solid #223046;padding-top:16px}
"""


def render_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{BASE_STYLE}</style></head>
<body><main>{body}
<footer>Ce site perçoit une commission sur les achats réalisés via les liens Amazon ci-dessus, sans coût
supplémentaire pour vous. Les avis et comparatifs restent indépendants.</footer>
</main></body></html>"""


@app.get("/")
def home():
    body = f"""
<span class="badge">Sécurité domestique connectée</span>
<h1>Comparatifs de sécurité maison, sans blabla marketing</h1>
<p class="lede">On compare des produits réels, sur des critères concrets — jamais de note inventée.</p>
<div class="card">
<h3><a href="/cameras-exterieures-sans-abonnement">Meilleures caméras extérieures sans abonnement (2026)</a></h3>
<p>4 modèles comparés sur le seul critère qui compte vraiment : est-ce que ça marche encore une fois l'abonnement refusé ?</p>
</div>
"""
    return render_page("NOVAREL SITE — Sécurité domestique", body)


@app.get("/cameras-exterieures-sans-abonnement")
def article_cameras():
    cards = ""
    for cam in CAMERAS:
        link = f"/go/{cam['slug']}"
        cards += f"""
<div class="card">
<h3>{cam['name']}</h3>
<div class="price">{cam['price']}</div>
<div class="grid">
<div><span>Alimentation :</span> {cam['power']}</div>
<div><span>Résolution :</span> {cam['resolution']}</div>
</div>
<p><b>Stockage :</b> {cam['storage']}</p>
<p class="pros">+ {cam['pros']}</p>
<p class="cons">− {cam['cons']}</p>
<a class="btn" href="{link}">Voir le prix sur Amazon →</a>
</div>
"""

    rows = "".join(
        f"<tr><td>{c['name']}</td><td>{c['price']}</td><td>{c['resolution']}</td>"
        f"<td>{c['power']}</td></tr>"
        for c in CAMERAS
    )

    tips_html = "".join(
        f'<div class="tips"><b>{label}</b>{tip}</div>' for label, tip in PLACEMENT_TIPS
    )

    body = f"""
<span class="badge">Comparatif 2026</span>
<h1>Meilleures caméras extérieures sans abonnement</h1>
<p class="lede">{ARTICLE_INTRO}</p>

<table><thead><tr><th>Modèle</th><th>Prix</th><th>Résolution</th><th>Alimentation</th></tr></thead>
<tbody>{rows}</tbody></table>

<h2>Le détail des 4 modèles</h2>
{cards}
<h2>Est-ce légal d'installer une caméra chez moi ?</h2>
<p>Oui, mais avec des règles précises fixées par la CNIL : vous ne pouvez filmer que <strong>l'intérieur de votre propriété</strong> (maison, jardin, allée privée). Il est interdit de filmer la voie publique — même pour surveiller votre voiture garée devant chez vous — ainsi que la propriété de vos voisins.</p>
<p>Si une personne extérieure à la famille entre régulièrement chez vous (nounou, femme de ménage...), vous devez l'informer de la présence de la caméra. En cas de non-respect, un recours est possible auprès de la CNIL, de la police/gendarmerie ou de la justice.</p>
<h2>Où placer sa caméra pour qu'elle serve vraiment</h2>
<p>Une caméra mal placée manque les intrusions ou devient inutilisable à cause de l'éblouissement solaire.</p>
{tips_html}

<p class="lede" style="margin-top:24px">Les prix indiqués sont des ordres de grandeur constatés au moment de la rédaction ;
vérifiez le prix actuel avant achat, il évolue régulièrement.</p>
"""
    return render_page("Meilleures caméras extérieures sans abonnement (2026)", body)


@app.get("/go/<slug>")
def go(slug):
    cam = next((c for c in CAMERAS if c["slug"] == slug), None)
    if not cam:
        return "Lien inconnu", 404
    log_click(slug, cam["name"])
    return redirect(amazon_search_link(cam["search_query"]), code=302)


@app.get("/health")
def health():
    with get_db() as c:
        n_clicks = c.execute("SELECT COUNT(*) n FROM clicks").fetchone()["n"]
    return {
        "status": "ok",
        "amazon_tag_configured": AMAZON_TAG != "TON-TAG-21",
        "total_clicks": n_clicks,
    }


@app.get("/api/clicks")
def api_clicks():
    with get_db() as c:
        rows = [dict(x) for x in c.execute("SELECT * FROM clicks ORDER BY id DESC LIMIT 200")]
        by_product = c.execute(
            "SELECT product, COUNT(*) n FROM clicks GROUP BY product ORDER BY n DESC"
        ).fetchall()
    return {
        "total": len(rows),
        "by_product": [dict(r) for r in by_product],
        "recent": rows,
    }


init()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5200")), debug=False)
