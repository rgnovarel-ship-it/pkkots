"""
NOVAREL VINTED — assistant photo -> fiche de vente pour vendeurs Vinted.

Principe NOVAREL : jamais de fausse donnée. Quand l'IA n'est pas sûre
(marque, taille, état), l'app le dit clairement au lieu d'inventer.

Stack volontairement minimale, un seul fichier, pensé pour Render free tier :
- Flask + SQLite (pas de service DB externe)
- Anthropic Claude (vision) pour l'analyse photo -> JSON structuré
- Pas de suppression de fond en v1 (rembg/onnxruntime est trop lourd pour
  512 Mo de RAM + cold start gratuit) -> ajouté en v2 une fois le produit
  validé (voir README).
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, g, jsonify, redirect, render_template_string, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

BASE = Path(__file__).parent
DB_PATH = BASE / "novarel_vinted.db"
UPLOAD_MAX_MB = 8
FREE_QUOTA_PER_MONTH = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("novarel_vinted")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = UPLOAD_MAX_MB * 1024 * 1024

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
SITE_URL = os.environ.get("NOVAREL_SITE_URL", "https://novarel-site.onrender.com")

# ============================================================
# DB
# ============================================================

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL;")
    return g.db


@app.teardown_appcontext
def close_db(_exc) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            visitor_id TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            title TEXT,
            description TEXT,
            confidence_flags TEXT,
            model TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS visitor_quota (
            visitor_id TEXT NOT NULL,
            year_month TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (visitor_id, year_month)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pro_interest (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            email TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()

# ============================================================
# QUOTA (cookie-based visitor id — volontairement simple pour la v1,
# contournable en navigation privée : suffisant pour valider l'usage,
# pas pour empêcher un abus déterminé)
# ============================================================

def get_or_create_visitor_id() -> str:
    vid = request.cookies.get("nv_visitor")
    if not vid:
        vid = uuid.uuid4().hex
    return vid


def current_year_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def quota_used(db: sqlite3.Connection, visitor_id: str) -> int:
    row = db.execute(
        "SELECT used FROM visitor_quota WHERE visitor_id=? AND year_month=?",
        (visitor_id, current_year_month()),
    ).fetchone()
    return row["used"] if row else 0


def quota_increment(db: sqlite3.Connection, visitor_id: str) -> None:
    ym = current_year_month()
    db.execute(
        """
        INSERT INTO visitor_quota (visitor_id, year_month, used) VALUES (?, ?, 1)
        ON CONFLICT(visitor_id, year_month) DO UPDATE SET used = used + 1
        """,
        (visitor_id, ym),
    )
    db.commit()


# ============================================================
# ANALYSE VISION (Claude)
# ============================================================

ANALYSIS_SYSTEM_PROMPT = """Tu es un assistant d'analyse de vêtements pour un vendeur Vinted.
Analyse UNIQUEMENT ce que tu vois réellement sur la photo. Ne devine jamais une marque,
une taille ou un état que tu ne peux pas lire ou observer avec certitude raisonnable :
dans ce cas, indique explicitement "non identifiable sur la photo" plutôt que d'inventer.
Réponds strictement en JSON valide, avec ce schéma exact :
{
  "type_vetement": "string",
  "couleur_principale": "string",
  "marque": "string ou null si illisible",
  "marque_confiance": "haute|moyenne|non_identifiable",
  "taille_visible": "string ou null si pas d'étiquette visible",
  "taille_confiance": "haute|moyenne|non_identifiable",
  "etat_estime": "neuf_avec_etiquette|tres_bon_etat|bon_etat|satisfaisant|a_preciser",
  "defauts_observes": ["liste de défauts VISIBLES sur la photo, vide si aucun visible"],
  "titre_annonce": "titre court et honnête pour l'annonce Vinted (max 60 caractères)",
  "description_annonce": "description Vinted en 3-5 phrases, honnête, sans exagération, mentionnant l'état réel",
  "conseils_optimisation": ["2 à 4 conseils concrets pour améliorer cette annonce (photo, prix, mots-clés)"]
}
Ne mets aucun texte en dehors du JSON."""


class VisionAnalysisError(Exception):
    pass


def analyze_image_with_claude(image_bytes: bytes, media_type: str) -> dict:
    if not ANTHROPIC_API_KEY:
        raise VisionAnalysisError(
            "Le service d'analyse n'est pas configuré (clé API manquante). "
            "L'administrateur doit définir ANTHROPIC_API_KEY."
        )
    try:
        import anthropic
    except ImportError as exc:
        raise VisionAnalysisError("Dépendance 'anthropic' manquante côté serveur.") from exc

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    try:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=ANALYSIS_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64},
                        },
                        {
                            "type": "text",
                            "text": "Analyse ce vêtement pour une annonce Vinted, en suivant strictement le schéma JSON demandé.",
                        },
                    ],
                }
            ],
        )
    except Exception as exc:  # réseau, quota, clé invalide, etc.
        logger.exception("Appel Anthropic échoué")
        raise VisionAnalysisError(f"Échec de l'analyse : {exc}") from exc

    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    text = text.strip()
    # Robustesse : parfois le modèle entoure le JSON de ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("JSON invalide reçu du modèle: %s", text[:500])
        raise VisionAnalysisError("Réponse d'analyse invalide, réessaie avec une autre photo.") from exc

    return data


# ============================================================
# DESIGN SYSTEM (aligné NOVAREL SITE : Inter, header sticky, dégradés, badges)
# ============================================================

BASE_CSS = """
:root{
  --bg:#0b0d12; --panel:#12151c; --panel-2:#171b24; --border:#232838;
  --text:#eef1f7; --muted:#9aa4b8; --accent:#6d8dff; --accent-2:#22d3a5;
  --danger:#ff6b6b; --radius:14px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  font-display:swap;}
a{color:inherit}
header.nv{position:sticky;top:0;z-index:20;background:rgba(11,13,18,.85);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--border);}
.nv-wrap{max-width:960px;margin:0 auto;padding:14px 20px;display:flex;
  align-items:center;justify-content:space-between;gap:12px;}
.nv-logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:1.05rem;
  letter-spacing:.2px;}
.nv-logo .dot{width:10px;height:10px;border-radius:50%;
  background:linear-gradient(135deg,var(--accent),var(--accent-2));}
.nv-badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.72rem;
  font-weight:700;background:linear-gradient(135deg,rgba(109,141,255,.18),rgba(34,211,165,.18));
  border:1px solid var(--border);color:var(--text);}
main{max-width:720px;margin:0 auto;padding:32px 20px 80px;}
.card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);
  padding:22px;margin-bottom:18px;}
h1{font-size:1.6rem;margin:.2rem 0 .6rem}
h2{font-size:1.1rem;margin:0 0 .8rem}
p.lead{color:var(--muted);margin-top:0}
.btn{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,var(--accent),#4f6de0);
  color:#fff;border:none;padding:12px 20px;border-radius:10px;font-weight:700;cursor:pointer;
  font-size:.95rem;}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn.secondary{background:var(--panel-2);border:1px solid var(--border);color:var(--text)}
input[type=file]{width:100%;padding:14px;background:var(--panel-2);border:1px dashed var(--border);
  border-radius:10px;color:var(--muted)}
input[type=email]{width:100%;padding:12px;background:var(--panel-2);border:1px solid var(--border);
  border-radius:10px;color:var(--text)}
.tabs{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.tab{padding:8px 14px;border-radius:999px;border:1px solid var(--border);background:var(--panel-2);
  font-size:.85rem;font-weight:600;cursor:pointer}
.tab.active{background:linear-gradient(135deg,var(--accent),#4f6de0);border-color:transparent}
.tabpanel{display:none}
.tabpanel.active{display:block}
.pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.72rem;font-weight:700;
  margin-left:6px}
.pill.haute{background:rgba(34,211,165,.18);color:var(--accent-2)}
.pill.moyenne{background:rgba(255,193,7,.18);color:#ffc107}
.pill.non_identifiable{background:rgba(255,107,107,.18);color:var(--danger)}
ul.clean{padding-left:1.1rem;margin:.4rem 0}
.quota{color:var(--muted);font-size:.85rem;margin-top:10px}
.footer-link{display:block;text-align:center;color:var(--muted);font-size:.85rem;margin-top:30px}
.banner{background:linear-gradient(135deg,rgba(109,141,255,.12),rgba(34,211,165,.10));
  border:1px solid var(--border);border-radius:12px;padding:12px 16px;font-size:.85rem;
  color:var(--muted);margin-bottom:22px}
.banner a{color:var(--accent);font-weight:700;text-decoration:none}
"""

HEADER_HTML = """
<header class="nv">
  <div class="nv-wrap">
    <div class="nv-logo"><span class="dot"></span> NOVAREL VINTED</div>
    <span class="nv-badge">Assistant photo &rarr; annonce</span>
  </div>
</header>
"""

HOME_HTML = """
<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NOVAREL VINTED — analyse tes photos, génère ton annonce</title>
<meta name="description" content="Photographie ton vêtement, obtiens marque, taille, état et une annonce Vinted prête à publier — sans blabla, sans donnée inventée.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{{ css }}</style>
</head><body>
{{ header|safe }}
<main>
  <div class="banner">
    Ceci est un outil du réseau NOVAREL. Pour de vrais comparatifs produits (pas de simulation),
    visite <a href="{{ site_url }}" target="_blank" rel="noopener">NOVAREL SITE</a>.
  </div>
  <div class="card">
    <h1>Une photo. Une fiche de vente prête.</h1>
    <p class="lead">Type de vêtement, marque, taille, défauts visibles, et une annonce honnête générée automatiquement.
    Quand l'IA n'est pas sûre, elle le dit — jamais de donnée inventée.</p>
    <form method="post" action="{{ url_for('analyze') }}" enctype="multipart/form-data">
      <input type="file" name="photo" accept="image/*" capture="environment" required>
      <div style="margin-top:14px">
        <button class="btn" type="submit">Analyser la photo</button>
      </div>
    </form>
    <p class="quota">{{ quota_used }} / {{ quota_max }} analyses gratuites utilisées ce mois-ci.</p>
  </div>
  <div class="card">
    <h2>Envie d'un usage illimité ?</h2>
    <p class="lead" style="margin-bottom:14px">La version Pro (abonnement mensuel) est en préparation. Laisse ton email pour être prévenu au lancement — aucun paiement ici, aucune promesse de prix pour l'instant.</p>
    <form method="post" action="{{ url_for('pro_interest') }}" style="display:flex;gap:10px;flex-wrap:wrap">
      <input type="email" name="email" placeholder="ton@email.com" required style="flex:1;min-width:200px">
      <button class="btn secondary" type="submit">Être prévenu·e</button>
    </form>
  </div>
</main>
<a class="footer-link" href="{{ site_url }}" target="_blank" rel="noopener">novarel-site.onrender.com — comparatifs produits réels</a>
</body></html>
"""

RESULT_HTML = """
<!doctype html><html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Résultat de l'analyse — NOVAREL VINTED</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{{ css }}</style>
</head><body>
{{ header|safe }}
<main>
  <div class="card">
    <h1>{{ data.titre_annonce }}</h1>
    <p class="lead">{{ data.type_vetement }} · {{ data.couleur_principale }}</p>

    <div class="tabs">
      <div class="tab active" data-tab="fiche">Fiche produit</div>
      <div class="tab" data-tab="analyse">Analyse</div>
      <div class="tab" data-tab="conseils">Conseils (Camille)</div>
    </div>

    <div class="tabpanel active" id="tab-fiche">
      <h2>Description prête à publier</h2>
      <p>{{ data.description_annonce }}</p>
    </div>

    <div class="tabpanel" id="tab-analyse">
      <h2>Ce que l'IA a observé</h2>
      <ul class="clean">
        <li>Marque : {{ data.marque or "non identifiable sur la photo" }}
          <span class="pill {{ data.marque_confiance }}">{{ data.marque_confiance }}</span></li>
        <li>Taille : {{ data.taille_visible or "non identifiable sur la photo" }}
          <span class="pill {{ data.taille_confiance }}">{{ data.taille_confiance }}</span></li>
        <li>État estimé : {{ data.etat_estime }}</li>
      </ul>
      <h2 style="margin-top:16px">Défauts observés</h2>
      {% if data.defauts_observes %}
      <ul class="clean">{% for d in data.defauts_observes %}<li>{{ d }}</li>{% endfor %}</ul>
      {% else %}
      <p class="lead">Aucun défaut visible sur la photo fournie.</p>
      {% endif %}
    </div>

    <div class="tabpanel" id="tab-conseils">
      <h2>Pour vendre plus vite</h2>
      <ul class="clean">{% for c in data.conseils_optimisation %}<li>{{ c }}</li>{% endfor %}</ul>
    </div>
  </div>
  <a href="{{ url_for('home') }}" class="btn secondary" style="text-decoration:none">Analyser une autre photo</a>
</main>
<script>
document.querySelectorAll('.tab').forEach(function(t){
  t.addEventListener('click', function(){
    document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('active')});
    document.querySelectorAll('.tabpanel').forEach(function(x){x.classList.remove('active')});
    t.classList.add('active');
    document.getElementById('tab-'+t.dataset.tab).classList.add('active');
  });
});
</script>
</body></html>
"""

ERROR_HTML = """
<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Erreur — NOVAREL VINTED</title><style>{{ css }}</style></head><body>
{{ header|safe }}
<main><div class="card"><h1>Ça n'a pas fonctionné</h1><p class="lead">{{ message }}</p>
<a href="{{ url_for('home') }}" class="btn">Réessayer</a></div></main></body></html>
"""


def render(tpl: str, **ctx) -> str:
    return render_template_string(tpl, css=BASE_CSS, header=HEADER_HTML, site_url=SITE_URL, **ctx)


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def home():
    db = get_db()
    vid = get_or_create_visitor_id()
    used = quota_used(db, vid)
    resp = Response(render(HOME_HTML, quota_used=used, quota_max=FREE_QUOTA_PER_MONTH))
    resp.set_cookie("nv_visitor", vid, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
    return resp


@app.post("/analyze")
def analyze():
    db = get_db()
    vid = get_or_create_visitor_id()

    used = quota_used(db, vid)
    if used >= FREE_QUOTA_PER_MONTH:
        return render(
            ERROR_HTML,
            message=(
                f"Quota gratuit atteint ({FREE_QUOTA_PER_MONTH} analyses/mois). "
                "Laisse ton email sur la page d'accueil pour être prévenu·e du lancement de l'offre Pro."
            ),
        ), 429

    file = request.files.get("photo")
    if not file or not file.filename:
        return render(ERROR_HTML, message="Aucune photo reçue."), 400

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    media_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp",
    }.get(ext, file.mimetype or "image/jpeg")

    image_bytes = file.read()
    if not image_bytes:
        return render(ERROR_HTML, message="Photo vide ou illisible."), 400

    try:
        data = analyze_image_with_claude(image_bytes, media_type)
    except VisionAnalysisError as exc:
        logger.warning("Analyse refusée: %s", exc)
        return render(ERROR_HTML, message=str(exc)), 502

    analysis_id = uuid.uuid4().hex
    confidence_flags = json.dumps(
        {"marque": data.get("marque_confiance"), "taille": data.get("taille_confiance")}
    )
    db.execute(
        """
        INSERT INTO analyses (id, created_at, visitor_id, raw_json, title, description, confidence_flags, model)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            analysis_id,
            datetime.now(timezone.utc).isoformat(),
            vid,
            json.dumps(data, ensure_ascii=False),
            data.get("titre_annonce", ""),
            data.get("description_annonce", ""),
            confidence_flags,
            ANTHROPIC_MODEL,
        ),
    )
    quota_increment(db, vid)

    resp = Response(render(RESULT_HTML, data=data))
    resp.set_cookie("nv_visitor", vid, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
    return resp


@app.post("/pro-interest")
def pro_interest():
    email = (request.form.get("email") or "").strip()
    if not email or "@" not in email:
        return render(ERROR_HTML, message="Adresse email invalide."), 400
    db = get_db()
    db.execute(
        "INSERT INTO pro_interest (id, created_at, email) VALUES (?, ?, ?)",
        (uuid.uuid4().hex, datetime.now(timezone.utc).isoformat(), email),
    )
    db.commit()
    return render(
        ERROR_HTML,
        message="Merci ! Tu seras prévenu·e par email au lancement de l'offre Pro.",
    )


@app.get("/healthz")
def healthz():
    return jsonify(
        status="ok",
        vision_configured=bool(ANTHROPIC_API_KEY),
        time=datetime.now(timezone.utc).isoformat(),
    )


@app.errorhandler(HTTPException)
def handle_http_error(exc: HTTPException):
    return render(ERROR_HTML, message=exc.description or "Erreur inattendue."), exc.code


@app.errorhandler(Exception)
def handle_error(exc: Exception):
    logger.exception("Erreur non gérée")
    return render(ERROR_HTML, message="Une erreur inattendue est survenue."), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
