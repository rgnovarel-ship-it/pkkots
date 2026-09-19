
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
import json
import os
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from flask import Flask, Response, abort, redirect, request

BASE = Path(__file__).parent
DB = BASE / "novarel_site.db"
AMAZON_TAG = os.environ.get("AMAZON_TAG", "TON-TAG-21")  # placeholder tant que non configuré

# Balise meta de vérification Google Search Console (méthode "Balise HTML").
# Se configure via une variable d'environnement Render nommée
# GOOGLE_SITE_VERIFICATION (juste le code, ex: "abc123..."), pour que changer
# de token ne demande jamais de modifier le code ni de redéployer.
GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "")

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
        cols = [r["name"] for r in c.execute("PRAGMA table_info(clicks)").fetchall()]
        if "source" not in cols:
            c.execute("ALTER TABLE clicks ADD COLUMN source TEXT DEFAULT 'direct'")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def today_fr() -> str:
    d = datetime.now()
    return f"{d.day} {MONTHS_FR[d.month - 1]} {d.year}"


def _extract_price(price_str: str):
    """Extrait le premier montant chiffré réellement présent dans le texte du prix.
    Ne fabrique jamais de valeur : renvoie (None, None) si aucun montant n'est trouvé.
    """
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(€|\$)", price_str)
    if not m:
        return None, None
    amount = float(m.group(1).replace(",", "."))
    currency = "EUR" if m.group(2) == "€" else "USD"
    return amount, currency


def amazon_search_link(query: str) -> str:
    """Construit un lien de recherche Amazon.fr porteur du tag d'affiliation.
    Fonctionne dès aujourd'hui (recherche réelle) ; le tag prend effet dès
    que AMAZON_TAG est configuré avec le vrai identifiant Associates.
    """
    return f"https://www.amazon.fr/s?k={quote(query)}&tag={AMAZON_TAG}"


def log_click(slug: str, product: str, source: str = "direct"):
    with get_db(write=True) as c:
        c.execute(
            "INSERT INTO clicks(ts,slug,product,referrer,source) VALUES(?,?,?,?,?)",
            (now_iso(), slug, product, request.referrer or "", source),
        )


# ============================================================
# CONTENU RÉEL — article comparatif caméras
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

ARTICLE_INTRO_CAMERAS = (
    "« Sans abonnement » est devenu un argument marketing que presque toutes les marques "
    "utilisent — jusqu'à ce qu'on découvre, une fois la caméra installée, qu'elle n'enregistre "
    "que 24 heures sans le plan cloud payant, ou que la détection intelligente est bloquée sans "
    "abonnement actif. Ce comparatif ne retient que des modèles dont les fonctions essentielles "
    "(enregistrement, détection de mouvement, vision nocturne) fonctionnent réellement sans "
    "dépenser un centime de plus après l'achat."
)

FAQ_CAMERAS = [
    (
        "Est-ce légal d'installer une caméra de surveillance chez moi ?",
        "Oui, sous réserve de respecter les règles fixées par la CNIL : vous ne pouvez filmer que "
        "l'intérieur de votre propriété (maison, jardin, allée privée), jamais la voie publique ni "
        "la propriété de vos voisins. Si une personne extérieure au foyer entre régulièrement chez "
        "vous, elle doit être informée de la présence de la caméra.",
    ),
    (
        "Où faut-il placer une caméra extérieure pour qu'elle soit efficace ?",
        "Les emplacements les plus utiles sont l'entrée principale (à 2,5–3 m de hauteur), le "
        "portail ou garage pour surveiller les véhicules, la façade arrière souvent la plus isolée, "
        "et les angles de la maison qui permettent de couvrir deux façades avec un seul appareil.",
    ),
]

PLACEMENT_TIPS = [
    ("Entrée principale", "Au-dessus de la porte, à 2,5–3 m de hauteur, couvrant l'allée d'accès."),
    ("Portail / garage", "Vue sur les véhicules entrant et sortant."),
    ("Façade arrière", "La cour ou le jardin, souvent la zone la plus isolée d'un logement."),
    ("Angle de la maison", "Permet de couvrir deux façades avec un seul appareil bien placé."),
]


# ============================================================
# CONTENU RÉEL — article comparatif alarmes (niche #2)
# ============================================================

ALARMS = [
    {
        "slug": "somfy-home-alarm-advanced",
        "name": "Somfy Home Alarm Advanced",
        "price": "≈799 €",
        "power": "Secteur + relais GSM (5 ans offerts)",
        "resolution": "Sirène 105 dB",
        "storage": "3 détecteurs IntelliTAG inclus",
        "pros": "Le plus équilibré : double communication Wi-Fi + GSM, aucun abonnement obligatoire",
        "cons": "Le relais GSM devient payant (2,99 €/mois) après 5 ans, en option seulement",
        "search_query": "Somfy Home Alarm Advanced kit",
    },
    {
        "slug": "netatmo-smart-alarm",
        "name": "Netatmo Smart Alarm System",
        "price": "≈350 €",
        "power": "Secteur",
        "resolution": "Sirène 110 dB + caméra intégrée",
        "storage": "Stockage vidéo local — jamais d'abonnement requis",
        "pros": "Le vrai \"zéro frais récurrent\" du comparatif, même pour la vidéo",
        "cons": "Écosystème plus fermé, moins évolutif que Somfy ou Ajax",
        "search_query": "Netatmo Smart Alarm System",
    },
    {
        "slug": "ring-alarm-s",
        "name": "Ring Alarm S",
        "price": "dès 250 €",
        "power": "Batterie de secours 24h",
        "resolution": "Kit évolutif",
        "storage": "Notifications smartphone incluses",
        "pros": "Le prix d'entrée le plus bas du comparatif, kit facile à agrandir",
        "cons": "Contrôle à distance et relais GSM réservés à l'abonnement Ring Protect",
        "search_query": "Ring Alarm S kit sécurité maison",
    },
    {
        "slug": "ajax-hub-2-plus",
        "name": "Ajax Hub 2 Plus",
        "price": "Variable selon config",
        "power": "Double SIM + Ethernet + Wi-Fi",
        "resolution": "Jusqu'à 200 appareils compatibles",
        "storage": "Télésurveillance disponible en option, jamais imposée",
        "pros": "Le plus \"pro\" et évolutif : idéal pour agrandir le système avec le temps",
        "cons": "Configuration plus complexe, budget qui grimpe vite selon les accessoires choisis",
        "search_query": "Ajax Hub 2 Plus alarme maison",
    },
]

ARTICLE_INTRO_ALARMS = (
    "La majorité des alarmes vendues en magasin (Verisure en tête) imposent un abonnement de "
    "télésurveillance obligatoire, souvent entre 30 € et 50 €/mois — soit 360 € à 600 € par an, "
    "sans limite dans le temps. Les 4 systèmes ci-dessous fonctionnent très bien avec un "
    "abonnement optionnel, voire aucun abonnement du tout."
)

FAQ_ALARMS = [
    (
        "Existe-t-il une limite légale de bruit pour une sirène d'alarme ?",
        "Il n'existe pas de norme nationale unique en France : ce sont les préfectures et "
        "municipalités qui fixent les règles. La référence la plus utilisée est 105 dB(A) mesurés "
        "à 1 mètre, pour une durée maximale de 3 minutes pour les sirènes extérieures ; au-delà, un "
        "trouble de voisinage reste possible même si l'installation elle-même est légale.",
    ),
    (
        "Une alarme maison nécessite-t-elle forcément un abonnement ?",
        "Non. Les 4 systèmes de ce comparatif fonctionnent avec un abonnement optionnel, voire sans "
        "aucun abonnement, contrairement aux offres de télésurveillance classiques qui imposent "
        "souvent 30 à 50 €/mois.",
    ),
]


# ============================================================
# CONTENU RÉEL — article comparatif serrures connectées (niche #3)
# ============================================================

LOCKS = [
    {
        "slug": "nuki-smart-lock-ultra",
        "name": "Nuki Smart Lock Ultra",
        "price": "≈349 €",
        "power": "Batterie rechargeable intégrée",
        "resolution": "Wi-Fi, Matter, Thread, Bluetooth",
        "storage": "Cylindre modulaire compatible 96 configurations de porte",
        "pros": "Le plus complet techniquement, aucun abonnement pour les fonctions de base",
        "cons": "Câble de recharge propriétaire, clavier à code vendu séparément",
        "search_query": "Nuki Smart Lock Ultra serrure connectée",
    },
    {
        "slug": "yale-linus-l2",
        "name": "Yale Linus L2",
        "price": "≈238 €",
        "power": "Piles",
        "resolution": "Bluetooth + module Wi-Fi optionnel",
        "storage": "Compatible Google Home, Alexa",
        "pros": "Design discret, écosystème Yale déjà installé chez beaucoup de foyers",
        "cons": "Autonomie de la batterie parfois limitée selon l'usage",
        "search_query": "Yale Linus L2 serrure connectée",
    },
    {
        "slug": "somfy-door-keeper",
        "name": "Somfy Door Keeper",
        "price": "≈250–350 €",
        "power": "Piles",
        "resolution": "Bluetooth (Wi-Fi via passerelle TaHoma en option)",
        "storage": "Remplace le cylindre européen existant, conserve la serrure d'origine",
        "pros": "Certifié A2P — le seul du comparatif dans ce cas, un vrai plus pour l'assurance",
        "cons": "Passerelle TaHoma en supplément si vous voulez le contrôle à distance",
        "search_query": "Somfy Door Keeper serrure connectée",
    },
    {
        "slug": "switchbot-lock-pro",
        "name": "SwitchBot Lock Pro",
        "price": "≈140 €",
        "power": "4 piles AA (6 à 9 mois d'autonomie)",
        "resolution": "Bluetooth (Matter via Hub 2 en option)",
        "storage": "Portée Bluetooth jusqu'à 120 m en extérieur",
        "pros": "L'entrée de gamme du comparatif, aucun abonnement, installation simple",
        "cons": "Fonctions avancées (Wi-Fi, assistants vocaux) nécessitent le Hub 2 en plus",
        "search_query": "SwitchBot Lock Pro serrure connectée",
    },
]

ARTICLE_INTRO_LOCKS = (
    "Une serrure connectée séduit pour le confort, mais un détail est presque toujours ignoré : "
    "votre assurance habitation. La plupart des contrats exigent une serrure certifiée A2P pour "
    "garantir une indemnisation en cas de cambriolage — et beaucoup de serrures connectées "
    "populaires n'ont jamais été soumises à cette certification. Ce comparatif vous dit ce que "
    "chaque modèle change vraiment côté sécurité, pas seulement côté confort."
)

FAQ_LOCKS = [
    (
        "Qu'est-ce que la certification A2P sur une serrure ?",
        "C'est une certification délivrée par le CNPP, organisme indépendant créé par les "
        "assureurs, qui évalue la résistance à l'effraction : une étoile = 5 minutes de résistance "
        "testée en laboratoire, deux étoiles = 10 minutes, trois étoiles = 15 minutes. La plupart "
        "des contrats habitation exigent au moins deux étoiles pour une maison.",
    ),
    (
        "Une serrure connectée peut-elle réduire l'indemnisation en cas de cambriolage ?",
        "Oui, si elle ne correspond pas à ce qu'exige votre contrat d'assurance. Il est recommandé "
        "de demander une confirmation écrite à votre assureur avant l'installation plutôt que de le "
        "découvrir après un sinistre.",
    ),
]


# ============================================================
# CONTENU RÉEL — article comparatif détecteurs de fumée (niche #4)
# ============================================================

SMOKE_DETECTORS = [
    {
        "slug": "google-nest-protect",
        "name": "Google Nest Protect (2ᵉ génération)",
        "price": "≈120–150 €",
        "power": "Piles ou secteur (selon modèle)",
        "resolution": "Détecte fumée ET monoxyde de carbone",
        "storage": "Alerte vocale + notification smartphone",
        "pros": "Le seul du comparatif à couvrir fumée + CO dans un seul appareil",
        "cons": "Prix le plus élevé de la sélection",
        "search_query": "Google Nest Protect détecteur fumée",
    },
    {
        "slug": "netatmo-detecteur-fumee",
        "name": "Netatmo Détecteur de Fumée Intelligent",
        "price": "≈90–110 €",
        "power": "Pile scellée 10 ans",
        "resolution": "Notification smartphone même hors domicile",
        "storage": "Aucune maintenance de pile pendant 10 ans",
        "pros": "Autonomie record : zéro changement de pile pendant une décennie",
        "cons": "Détecte uniquement la fumée, pas le CO",
        "search_query": "Netatmo détecteur de fumée intelligent",
    },
    {
        "slug": "somfy-detecteur-fumee-io",
        "name": "Somfy Détecteur de Fumée io",
        "price": "≈65–90 €",
        "power": "Pile",
        "resolution": "Intégration à l'écosystème Somfy (alarme, volets)",
        "storage": "Notification via l'appli Somfy",
        "pros": "Bon compromis prix/intégration si vous avez déjà du matériel Somfy",
        "cons": "Moins intéressant en dehors de l'écosystème Somfy",
        "search_query": "Somfy détecteur de fumée io",
    },
    {
        "slug": "x-sense-sc07-wx",
        "name": "X-Sense SC07-WX",
        "price": "≈55–80 €",
        "power": "Pile",
        "resolution": "Wi-Fi intégré, notification directe",
        "storage": "Application dédiée avec historique d'alertes",
        "pros": "Le meilleur rapport prix/fonctions connectées du comparatif",
        "cons": "Écosystème moins étendu que Google ou Netatmo",
        "search_query": "X-Sense SC07-WX détecteur fumée connecté",
    },
]

ARTICLE_INTRO_SMOKE = (
    "Contrairement aux caméras ou aux alarmes, ce n'est pas une option : depuis la loi Morange "
    "du 8 mars 2015, tout logement en France doit être équipé d'au moins un détecteur de fumée "
    "conforme à la norme NF EN 14604. Ce n'est pas juste une obligation administrative — en cas "
    "d'incendie, l'absence de détecteur peut réduire l'indemnisation de votre assurance "
    "habitation. Autant choisir un modèle qui vous prévient même quand vous n'êtes pas chez vous."
)

FAQ_SMOKE = [
    (
        "Le détecteur de fumée est-il obligatoire en France ?",
        "Oui, depuis la loi Morange du 8 mars 2015, tout logement doit être équipé d'au moins un "
        "détecteur autonome avertisseur de fumée (DAAF) conforme à la norme NF EN 14604 et marqué "
        "CE, avec une alerte sonore d'au moins 85 dB(A) mesurée à 3 mètres.",
    ),
    (
        "Qui doit installer le détecteur de fumée en location, le propriétaire ou le locataire ?",
        "C'est le propriétaire qui doit l'installer ; le locataire est responsable de son entretien "
        "pendant la durée du bail.",
    ),
]


# ============================================================
# CONTENU RÉEL — article comparatif détecteurs de fuite d'eau (niche #5)
# ============================================================

WATER_LEAK = [
    {
        "slug": "switchbot-detecteur-fuite-eau",
        "name": "SwitchBot Détecteur de fuite d'eau",
        "price": "≈22 €",
        "power": "Pile, Wi-Fi direct (pas de hub requis)",
        "resolution": "IP67, alerte app en cas de fuite",
        "storage": "Notifications smartphone incluses, aucun abonnement",
        "pros": "Le meilleur rapport prix/simplicité : installation en 2 minutes, sans hub",
        "cons": "Un seul capteur par appareil — il en faut plusieurs pour couvrir toute la maison",
        "search_query": "SwitchBot détecteur de fuite d'eau",
    },
    {
        "slug": "x-sense-sws54",
        "name": "X-Sense SWS51/54 (kit + station)",
        "price": "dès 19,99 € l'unité, 59,99 € le kit 3 capteurs + station",
        "power": "Pile, portée jusqu'à 500 m annoncée",
        "resolution": "Alarme 100-120 dB, détection dès 0,4 mm d'eau",
        "storage": "Application dédiée, aucun abonnement",
        "pros": "Idéal pour une buanderie ou une cave éloignée grâce à sa portée",
        "cons": "Le kit avec station coûte plus cher que l'unité seule si vous n'avez qu'un point à couvrir",
        "search_query": "X-Sense SWS54 kit détecteur fuite eau",
    },
    {
        "slug": "us-solid-vanne-motorisee",
        "name": "U.S. Solid — système avec vanne motorisée",
        "price": "≈91 $ (≈85 €)",
        "power": "Secteur/pile selon modèle + vanne à bille motorisée 3/4\"",
        "resolution": "3 capteurs + alarme sonore",
        "storage": "Coupe l'eau automatiquement dès qu'une fuite est détectée",
        "pros": "Le seul qui agit sans vous : il coupe physiquement l'arrivée d'eau, pas juste une alerte",
        "cons": "Installation plus technique (raccordement sur l'arrivée d'eau), budget plus élevé",
        "search_query": "U.S. Solid détecteur fuite eau vanne motorisée",
    },
]

ARTICLE_INTRO_WATER_LEAK = (
    "Un dégât des eaux coûte en moyenne plusieurs milliers d'euros de réparations (parquet, "
    "plâtre, électroménager). Un détecteur à moins de 25 € peut couper l'eau ou vous alerter "
    "avant que ça ne dégénère. C'est aussi la seule catégorie de ce comparatif où plusieurs "
    "assureurs offrent une vraie réduction de prime pour en installer."
)

FAQ_WATER_LEAK = [
    (
        "Un détecteur de fuite d'eau peut-il faire baisser mon assurance habitation ?",
        "Chez plusieurs assureurs français, oui : MAIF et GMF jusqu'à 12% via des partenariats avec "
        "Netatmo et Somfy, Allianz jusqu'à 15% via Homiris, Cardif jusqu'à 15% selon un "
        "questionnaire sur les équipements déclarés. La fourchette observée sur le marché est de "
        "10 à 25% de réduction de prime — à vérifier directement avec votre assureur.",
    ),
    (
        "Combien de capteurs faut-il installer dans une maison ?",
        "Il est recommandé de placer au moins un capteur sous chaque point à risque (évier, "
        "lave-linge, lave-vaisselle, chauffe-eau, WC) plutôt qu'un seul capteur pour toute la "
        "maison : c'est la position du capteur, pas son nombre total, qui détermine si la fuite est "
        "repérée à temps.",
    ),
]


# ============================================================
# GABARIT HTML
# ============================================================

BASE_STYLE = """
:root{--bg:#0a0d13;--accent:#ff7a18;--accent2:#ffb347;--text:#e8edf5;--muted:#93a4b8;--border:#223046}
*{box-sizing:border-box}
body{
margin:0;color:var(--text);font-family:'Inter',system-ui,-apple-system,Segoe UI,Roboto,sans-serif;font-size:16px;line-height:1.6;
background:
  radial-gradient(1200px 600px at 8% -10%,rgba(255,122,24,.10),transparent 60%),
  radial-gradient(1000px 500px at 92% 0%,rgba(88,166,255,.08),transparent 55%),
  linear-gradient(180deg,#0a0d13 0%,#0d1220 100%);
background-attachment:fixed;
}
main{max-width:880px;margin:auto;padding:32px 20px 20px}
h1{font-size:32px;margin:0 0 10px;font-weight:800}
h2{font-size:22px;margin:32px 0 12px;color:#eaf2f8;font-weight:700}
.lede{color:var(--muted);font-size:17px}
a{color:#7ec4ff}
.badge{display:inline-block;background:#132132;border:1px solid #24425f;border-radius:20px;padding:4px 12px;font-size:12px;color:#8fc4ff;margin-bottom:14px}

.site-header{position:sticky;top:0;z-index:50;background:rgba(10,13,19,.72);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
.header-inner{max-width:880px;margin:auto;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}
.logo{display:flex;align-items:center;gap:8px;font-weight:800;letter-spacing:.4px;color:var(--text);text-decoration:none;font-size:18px}
.logo-dot{width:10px;height:10px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 12px rgba(255,122,24,.6)}
.site-nav{display:flex;gap:18px;flex-wrap:wrap}
.site-nav a{color:var(--muted);text-decoration:none;font-size:14px;font-weight:600;transition:color .15s}
.site-nav a:hover{color:var(--text)}

.niche-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px;margin:24px 0}
.niche-card{position:relative;display:block;background:linear-gradient(160deg,rgba(255,255,255,.04),rgba(255,255,255,0)) ,#111925;border:1px solid var(--border);border-radius:16px;padding:22px;text-decoration:none;color:var(--text);transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}
.niche-card:hover{transform:translateY(-4px);border-color:rgba(255,122,24,.5);box-shadow:0 12px 30px rgba(0,0,0,.35),0 0 0 1px rgba(255,122,24,.15)}
.niche-icon{font-size:32px;display:block;margin-bottom:10px}
.niche-card h3{margin:0 0 8px;font-size:18px;color:var(--text)}
.niche-card p{margin:0;color:var(--muted);font-size:14px;line-height:1.5}

.card{position:relative;background:linear-gradient(160deg,rgba(255,255,255,.03),rgba(255,255,255,0)),#111925;border:1px solid var(--border);border-radius:14px;padding:20px;margin:18px 0}
.card h3{margin:0 0 6px;font-size:20px}
.rank-badge{position:absolute;top:-12px;left:20px;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#1a1005;font-weight:800;font-size:12px;padding:4px 10px;border-radius:20px;box-shadow:0 4px 12px rgba(255,122,24,.35)}
.price{color:#7bd88f;font-weight:700}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:14px 0;font-size:14px}
.grid div span{color:#7f93a8}
.pros{color:#7bd88f}.cons{color:#ff9b9b}
.btn{display:inline-block;margin-top:12px;padding:11px 20px;background:linear-gradient(135deg,#ff7a18,#ffb347);color:#1a1005;font-weight:800;border-radius:8px;text-decoration:none;box-shadow:0 6px 16px rgba(255,122,24,.3);transition:transform .15s ease,box-shadow .15s ease}
.btn:hover{transform:translateY(-2px);box-shadow:0 10px 22px rgba(255,122,24,.4)}
table{width:100%;border-collapse:collapse;margin:18px 0;font-size:14px}
th,td{text-align:left;padding:9px;border-bottom:1px solid var(--border)}
th{color:#8fa3b7}
.tips{background:#0f1620;border-left:3px solid #7ec4ff;border-radius:8px;padding:14px 18px;margin:18px 0}
.tips b{display:block;margin-bottom:2px}
footer{color:#6b7c8d;font-size:13px;margin-top:40px;border-top:1px solid var(--border);padding-top:16px}
footer a{color:#8fa3b7}

.breadcrumb{font-size:13px;color:var(--muted);margin:0 0 6px}
.breadcrumb a{color:var(--muted);text-decoration:underline}
.updated-date{color:var(--muted);font-size:13px;margin:0 0 18px}

.mobile-buybar{display:none;position:fixed;left:0;right:0;bottom:0;z-index:60;align-items:center;justify-content:space-between;gap:12px;background:#111925;border-top:1px solid var(--border);padding:10px 14px;box-shadow:0 -6px 20px rgba(0,0,0,.4)}
.mobile-buybar-name{font-weight:700;font-size:14px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mobile-buybar .btn{margin-top:0;padding:9px 16px;white-space:nowrap;flex-shrink:0}
@media (max-width:680px){
.mobile-buybar{display:flex}
main{padding-bottom:88px}
}
"""


SITE_URL = "https://novarel-site.onrender.com"

NAV_LINKS = [
    ("/cameras-exterieures-sans-abonnement", "📷 Caméras"),
    ("/alarmes-maison-sans-abonnement", "🚨 Alarmes"),
    ("/serrures-connectees-sans-abonnement", "🔒 Serrures"),
    ("/detecteurs-fumee-connectes", "🔥 Fumée"),
    ("/detecteurs-fuite-eau-connectes", "💧 Fuite d'eau"),
]

CATEGORY_LABEL = {
    "/cameras-exterieures-sans-abonnement": "Caméras extérieures",
    "/alarmes-maison-sans-abonnement": "Alarmes maison",
    "/serrures-connectees-sans-abonnement": "Serrures connectées",
    "/detecteurs-fumee-connectes": "Détecteurs de fumée",
    "/detecteurs-fuite-eau-connectes": "Détecteurs de fuite d'eau",
}

ARTICLES_INFO = {
    "/cameras-exterieures-sans-abonnement": {
        "emoji": "📷", "title": "Caméras extérieures",
        "desc": "4 modèles comparés sans abonnement.",
    },
    "/alarmes-maison-sans-abonnement": {
        "emoji": "🚨", "title": "Alarmes maison",
        "desc": "4 systèmes qui fonctionnent sans abonnement obligatoire.",
    },
    "/serrures-connectees-sans-abonnement": {
        "emoji": "🔒", "title": "Serrures connectées",
        "desc": "4 modèles, et le point assurance à vérifier avant d'acheter.",
    },
    "/detecteurs-fumee-connectes": {
        "emoji": "🔥", "title": "Détecteurs de fumée",
        "desc": "Obligation légale : comment bien le choisir.",
    },
    "/detecteurs-fuite-eau-connectes": {
        "emoji": "💧", "title": "Détecteurs de fuite d'eau",
        "desc": "Le détecteur le plus rentable de la maison.",
    },
}

RELATED_ARTICLES = {
    "/cameras-exterieures-sans-abonnement": [
        "/alarmes-maison-sans-abonnement", "/serrures-connectees-sans-abonnement",
    ],
    "/alarmes-maison-sans-abonnement": [
        "/cameras-exterieures-sans-abonnement", "/serrures-connectees-sans-abonnement",
    ],
    "/serrures-connectees-sans-abonnement": [
        "/alarmes-maison-sans-abonnement", "/cameras-exterieures-sans-abonnement",
    ],
    "/detecteurs-fumee-connectes": [
        "/detecteurs-fuite-eau-connectes", "/alarmes-maison-sans-abonnement",
    ],
    "/detecteurs-fuite-eau-connectes": [
        "/detecteurs-fumee-connectes", "/alarmes-maison-sans-abonnement",
    ],
}


def breadcrumb_html(path: str, qs: str) -> str:
    home_href = f"/{qs}"
    label = CATEGORY_LABEL[path]
    return (
        '<nav class="breadcrumb" aria-label="Fil d\'Ariane">'
        f'<a href="{home_href}">Accueil</a> <span aria-hidden="true">›</span> '
        f'<span aria-current="page">{label}</span>'
        "</nav>"
    )


def breadcrumb_jsonld(path: str) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": CATEGORY_LABEL[path], "item": f"{SITE_URL}{path}"},
        ],
    }


def products_jsonld(products: list) -> list:
    items = []
    for p in products:
        amount, currency = _extract_price(p["price"])
        offer = {"@type": "Offer", "url": f"{SITE_URL}/go/{p['slug']}"}
        if amount is not None:
            offer["price"] = amount
            offer["priceCurrency"] = currency
        items.append({
            "@type": "Product",
            "name": p["name"],
            "description": p["pros"],
            "offers": offer,
        })
    return items


def faq_jsonld(faq: list) -> dict:
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


def jsonld_script(parts: list) -> str:
    graph = {"@context": "https://schema.org", "@graph": parts}
    data = json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{data}</script>'


def article_jsonld(path: str, products: list, faq: list) -> str:
    parts = [breadcrumb_jsonld(path)]
    parts.extend(products_jsonld(products))
    if faq:
        parts.append(faq_jsonld(faq))
    return jsonld_script(parts)


def faq_html(faq: list) -> str:
    if not faq:
        return ""
    items = "".join(f'<div class="card"><h3>{q}</h3><p>{a}</p></div>' for q, a in faq)
    return f"<h2>Questions fréquentes</h2>{items}"


def related_html(path: str, qs: str) -> str:
    related = RELATED_ARTICLES.get(path, [])
    if not related:
        return ""
    cards = "".join(
        f'<a class="niche-card" href="{p}{qs}">'
        f'<span class="niche-icon" aria-hidden="true">{ARTICLES_INFO[p]["emoji"]}</span>'
        f'<h3>{ARTICLES_INFO[p]["title"]}</h3>'
        f'<p>{ARTICLES_INFO[p]["desc"]}</p>'
        "</a>"
        for p in related
    )
    return f'<h2>Voir aussi</h2><div class="niche-grid">{cards}</div>'


def render_page(
    title: str,
    body: str,
    description: str = "",
    path: str = "/",
    extra_head: str = "",
    sticky: tuple | None = None,
) -> str:
    desc = description or "Comparatifs indépendants de sécurité domestique : caméras, alarmes, serrures connectées. Prix réels, avis honnêtes, sans abonnement caché."
    canonical = f"{SITE_URL}{path}"
    qs = _qs(_src())
    nav_html = "".join(f'<a href="{href}{qs}">{label}</a>' for href, label in NAV_LINKS)
    sticky_html = ""
    if sticky:
        sticky_name, sticky_slug = sticky
        sticky_html = (
            '<div class="mobile-buybar">'
            f'<span class="mobile-buybar-name">{sticky_name}</span>'
            f'<a class="btn mobile-buybar-btn" href="/go/{sticky_slug}{qs}">Voir le prix →</a>'
            "</div>"
        )
    google_verify_tag = (
        f'<meta name="google-site-verification" content="{GOOGLE_SITE_VERIFICATION}">'
        if GOOGLE_SITE_VERIFICATION
        else ""
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
{google_verify_tag}
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{BASE_STYLE}</style>{extra_head}</head>
<body>
<header class="site-header"><div class="header-inner">
<a class="logo" href="/{qs}"><span class="logo-dot" aria-hidden="true"></span>NOVAREL</a>
<nav class="site-nav">{nav_html}</nav>
</div></header>
<main>{body}
<footer>Ce site perçoit une commission sur les achats réalisés via les liens Amazon ci-dessus, sans coût
supplémentaire pour vous. Les avis et comparatifs restent indépendants. <a href="/methodologie{qs}">Notre méthodologie</a>.</footer>
</main>
{sticky_html}
</body></html>"""


def _src() -> str:
    return request.args.get("src", "").strip() or "direct"


def _qs(src: str) -> str:
    return f"?src={quote(src)}" if src and src != "direct" else ""


@app.get("/")
def home():
    src = _src()
    qs = _qs(src)
    body = f"""
<span class="badge">Sécurité domestique connectée</span>
<h1>Comparatifs de sécurité maison, sans blabla marketing</h1>
<p class="lede">On compare des produits réels, sur des critères concrets — jamais de note inventée.</p>
<div class="niche-grid">
<a class="niche-card" href="/cameras-exterieures-sans-abonnement{qs}">
<span class="niche-icon" aria-hidden="true">📷</span>
<h3>Caméras extérieures</h3>
<p>4 modèles comparés sur le seul critère qui compte vraiment : est-ce que ça marche encore une fois l'abonnement refusé ?</p>
</a>
<a class="niche-card" href="/alarmes-maison-sans-abonnement{qs}">
<span class="niche-icon" aria-hidden="true">🚨</span>
<h3>Alarmes maison</h3>
<p>4 systèmes qui fonctionnent sans abonnement obligatoire — et ce que dit vraiment la loi sur les sirènes.</p>
</a>
<a class="niche-card" href="/serrures-connectees-sans-abonnement{qs}">
<span class="niche-icon" aria-hidden="true">🔒</span>
<h3>Serrures connectées</h3>
<p>4 modèles comparés, et le détail assurance que presque personne ne vérifie avant d'acheter.</p>
</a>
<a class="niche-card" href="/detecteurs-fumee-connectes{qs}">
<span class="niche-icon" aria-hidden="true">🔥</span>
<h3>Détecteurs de fumée</h3>
<p>Seul produit du site qui est une obligation légale — voici comment bien le choisir.</p>
</a>
<a class="niche-card" href="/detecteurs-fuite-eau-connectes{qs}">
<span class="niche-icon" aria-hidden="true">💧</span>
<h3>Détecteurs de fuite d'eau</h3>
<p>Le détecteur le plus rentable de la maison — et celui qui fait vraiment baisser votre assurance.</p>
</a>
</div>
"""
    return render_page(
        "Comparatifs sécurité maison sans abonnement — NOVAREL",
        body,
        "Caméras, alarmes, serrures et détecteurs de fumée comparés sans blabla marketing : prix réels, avis honnêtes, aucune note inventée.",
        "/",
    )


def _render_comparatif(
    title: str, badge: str, intro: str, products: list, path: str,
    faq: list, extra_html: str = "",
) -> str:
    src = _src()
    qs = _qs(src)
    cards = ""
    for i, p in enumerate(products):
        link = f"/go/{p['slug']}{qs}"
        rank_badge = f'<span class="rank-badge">#{i + 1}</span>' if i < 3 else ""
        cards += f"""
<div class="card">
{rank_badge}
<h3>{p['name']}</h3>
<div class="price">{p['price']}</div>
<div class="grid">
<div><span>Alimentation :</span> {p['power']}</div>
<div><span>Détails :</span> {p['resolution']}</div>
</div>
<p><b>Inclus :</b> {p['storage']}</p>
<p class="pros">+ {p['pros']}</p>
<p class="cons">− {p['cons']}</p>
<a class="btn" href="{link}">Voir le prix sur Amazon →</a>
</div>
"""
    rows = "".join(
        f"<tr><td>{p['name']}</td><td>{p['price']}</td><td>{p['resolution']}</td>"
        f"<td>{p['power']}</td></tr>"
        for p in products
    )
    body = f"""
{breadcrumb_html(path, qs)}
<span class="badge">{badge}</span>
<p class="updated-date">Dernière mise à jour : {today_fr()}</p>
<h1>{title}</h1>
<p class="lede">{intro}</p>

<table><thead><tr><th>Modèle</th><th>Prix</th><th>Détails</th><th>Alimentation</th></tr></thead>
<tbody>{rows}</tbody></table>

<h2>Le détail des {len(products)} modèles</h2>
{cards}
{extra_html}
<p class="lede" style="margin-top:24px">Les prix indiqués sont des ordres de grandeur constatés au moment de la rédaction ;
vérifiez le prix actuel avant achat, il évolue régulièrement.</p>
{faq_html(faq)}
{related_html(path, qs)}
"""
    return body


@app.get("/cameras-exterieures-sans-abonnement")
def article_cameras():
    tips_html = "".join(
        f'<div class="tips"><b>{label}</b>{tip}</div>' for label, tip in PLACEMENT_TIPS
    )
    extra = f"""
<h2>Est-ce légal d'installer une caméra chez moi ?</h2>
<p>Oui, mais avec des règles précises fixées par la CNIL : vous ne pouvez filmer que <strong>l'intérieur de votre propriété</strong> (maison, jardin, allée privée). Il est interdit de filmer la voie publique — même pour surveiller votre voiture garée devant chez vous — ainsi que la propriété de vos voisins.</p>
<p>Si une personne extérieure à la famille entre régulièrement chez vous (nounou, femme de ménage...), vous devez l'informer de la présence de la caméra. En cas de non-respect, un recours est possible auprès de la CNIL, de la police/gendarmerie ou de la justice.</p>
<h2>Où placer sa caméra pour qu'elle serve vraiment</h2>
<p>Une caméra mal placée manque les intrusions ou devient inutilisable à cause de l'éblouissement solaire.</p>
{tips_html}
"""
    path = "/cameras-exterieures-sans-abonnement"
    body = _render_comparatif(
        "Meilleures caméras extérieures sans abonnement",
        "Comparatif 2026",
        ARTICLE_INTRO_CAMERAS,
        CAMERAS,
        path,
        FAQ_CAMERAS,
        extra,
    )
    return render_page(
        "Meilleures caméras extérieures sans abonnement (2026)",
        body,
        "4 caméras extérieures qui fonctionnent vraiment sans abonnement : Reolink, Blink, EufyCam comparées sur prix, autonomie et stockage. Plus la réglementation CNIL à connaître.",
        path,
        extra_head=article_jsonld(path, CAMERAS, FAQ_CAMERAS),
        sticky=(CAMERAS[0]["name"], CAMERAS[0]["slug"]),
    )


@app.get("/alarmes-maison-sans-abonnement")
def article_alarms():
    extra = """
<h2>Ce que dit la loi sur les sirènes</h2>
<p>Contrairement à une idée reçue, il n'existe pas de norme nationale unique en France : ce sont les <strong>préfectures et municipalités</strong> qui fixent les règles précises. La référence la plus utilisée est <strong>105 dB(A) mesurés à 1 mètre, pour une durée maximale de 3 minutes</strong> pour les sirènes extérieures — au-delà, vous risquez un trouble de voisinage, et une plainte reste possible même si l'installation elle-même est légale. Les sirènes intérieures ne sont pas soumises à cette limite de durée, mais doivent respecter un cycle court dans les immeubles collectifs.</p>
<p><strong>À retenir avant d'installer :</strong> vérifiez que votre sirène est certifiée aux normes en vigueur, et informez vos voisins directs si vous installez une sirène extérieure puissante — ça évite les tensions inutiles.</p>
"""
    path = "/alarmes-maison-sans-abonnement"
    body = _render_comparatif(
        "Meilleures alarmes maison sans abonnement",
        "Comparatif 2026",
        ARTICLE_INTRO_ALARMS,
        ALARMS,
        path,
        FAQ_ALARMS,
        extra,
    )
    return render_page(
        "Meilleures alarmes maison sans abonnement (2026)",
        body,
        "Somfy, Netatmo, Ring, Ajax : 4 alarmes maison sans abonnement obligatoire comparées, plus ce que dit vraiment la loi sur les sirènes en France.",
        path,
        extra_head=article_jsonld(path, ALARMS, FAQ_ALARMS),
        sticky=(ALARMS[0]["name"], ALARMS[0]["slug"]),
    )


@app.get("/serrures-connectees-sans-abonnement")
def article_locks():
    extra = """
<h2>Le détail que presque personne vérifie : votre assurance</h2>
<p>Les assureurs se basent sur la certification <strong>A2P</strong> (délivrée par le CNPP, organisme indépendant créé par les assureurs) pour évaluer la résistance d'une serrure à l'effraction : une étoile = 5 minutes de résistance testée en laboratoire, deux étoiles = 10 minutes, trois étoiles = 15 minutes. La plupart des contrats habitation exigent au moins deux étoiles pour une maison. <strong>En cas de cambriolage, si la serrure installée ne correspond pas à ce qui est exigé dans votre contrat, l'indemnisation peut être réduite, voire refusée.</strong></p>
<p>Pour les serrures connectées spécifiquement, il existe une certification dédiée : <strong>A2P@</strong>, qui combine résistance mécanique et sécurité informatique de l'appareil et de son application. Peu de modèles grand public l'obtiennent.</p>
<p><strong>Ce qu'il faut vérifier avant d'acheter :</strong> une serrure qui remplace uniquement le cylindre (comme la plupart des modèles de ce comparatif) conserve en général le bloc de porte existant — mais le niveau de protection global dépend de l'ensemble de l'installation, pas seulement du cylindre. Le plus sûr reste de demander confirmation écrite à votre assureur avant l'installation, plutôt que de le découvrir après un sinistre.</p>
"""
    path = "/serrures-connectees-sans-abonnement"
    body = _render_comparatif(
        "Meilleures serrures connectées sans abonnement",
        "Comparatif 2026",
        ARTICLE_INTRO_LOCKS,
        LOCKS,
        path,
        FAQ_LOCKS,
        extra,
    )
    return render_page(
        "Meilleures serrures connectées sans abonnement (2026)",
        body,
        "Nuki, Yale, Somfy, SwitchBot comparées — et le point assurance (certification A2P) que la plupart des comparatifs ne mentionnent jamais.",
        path,
        extra_head=article_jsonld(path, LOCKS, FAQ_LOCKS),
        sticky=(LOCKS[0]["name"], LOCKS[0]["slug"]),
    )


@app.get("/detecteurs-fumee-connectes")
def article_smoke():
    extra = """
<h2>Ce n'est pas une option : ce que dit la loi</h2>
<p>Depuis la <strong>loi Morange du 8 mars 2015</strong> (décret n°2011-36), tout logement en France doit être équipé d'au moins un détecteur autonome avertisseur de fumée (DAAF), conforme à la norme <strong>NF EN 14604</strong> et marqué CE. L'appareil doit émettre une alerte sonore d'au moins 85 dB(A) mesurée à 3 mètres.</p>
<p>En location, c'est le <strong>propriétaire</strong> qui doit l'installer ; le <strong>locataire</strong> est responsable de son entretien pendant la durée du bail. En cas d'absence de détecteur lors d'un incendie, l'indemnisation de votre assurance habitation peut être réduite — en plus du risque évident pour la sécurité du foyer.</p>
<p><strong>Ce que la version connectée apporte en plus :</strong> une alerte sur votre téléphone même si vous n'êtes pas chez vous — utile si vous avez un animal, une location saisonnière, ou si vous voulez surveiller une résidence secondaire à distance.</p>
"""
    path = "/detecteurs-fumee-connectes"
    body = _render_comparatif(
        "Meilleurs détecteurs de fumée connectés",
        "Obligation légale + comparatif 2026",
        ARTICLE_INTRO_SMOKE,
        SMOKE_DETECTORS,
        path,
        FAQ_SMOKE,
        extra,
    )
    return render_page(
        "Meilleurs détecteurs de fumée connectés (2026)",
        body,
        "Google Nest Protect, Netatmo, Somfy, X-Sense comparés — et l'obligation légale (loi Morange, norme NF EN 14604) que tout logement français doit respecter.",
        path,
        extra_head=article_jsonld(path, SMOKE_DETECTORS, FAQ_SMOKE),
        sticky=(SMOKE_DETECTORS[0]["name"], SMOKE_DETECTORS[0]["slug"]),
    )


@app.get("/detecteurs-fuite-eau-connectes")
def article_water_leak():
    extra = """
<h2>Ce que ça change vraiment : la réduction d'assurance</h2>
<p>Contrairement aux alarmes anti-intrusion, les détecteurs de fuite d'eau ouvrent droit à de vraies réductions chez plusieurs assureurs français : <strong>MAIF et GMF</strong> jusqu'à 12% via des partenariats avec Netatmo et Somfy, <strong>Allianz</strong> jusqu'à 15% via Homiris, <strong>Cardif</strong> jusqu'à 15% selon un questionnaire sur les équipements déclarés, et <strong>MMA</strong> via leur contrat "Smart Home". Plus largement, la fourchette observée sur le marché est de <strong>10 à 25% de réduction de prime</strong> pour des équipements connectés déclarés et certifiés — vérifiez directement avec votre assureur avant d'acheter en vous basant uniquement sur cet argument.</p>
<p><strong>À retenir avant d'installer :</strong> placez au moins un capteur sous chaque point à risque (évier, lave-linge, lave-vaisselle, chauffe-eau, WC), pas juste un seul pour toute la maison — c'est la position du capteur, pas le nombre d'appareils, qui détermine si la fuite est repérée à temps.</p>
"""
    path = "/detecteurs-fuite-eau-connectes"
    body = _render_comparatif(
        "Meilleurs détecteurs de fuite d'eau connectés",
        "Comparatif 2026",
        ARTICLE_INTRO_WATER_LEAK,
        WATER_LEAK,
        path,
        FAQ_WATER_LEAK,
        extra,
    )
    return render_page(
        "Meilleurs détecteurs de fuite d'eau connectés (2026)",
        body,
        "SwitchBot, X-Sense, U.S. Solid comparés — et les réductions d'assurance habitation (MAIF, Allianz, Cardif) que ce détecteur peut vous faire gagner.",
        path,
        extra_head=article_jsonld(path, WATER_LEAK, FAQ_WATER_LEAK),
        sticky=(WATER_LEAK[0]["name"], WATER_LEAK[0]["slug"]),
    )


@app.get("/methodologie")
def methodologie():
    body = f"""
<span class="badge">Transparence</span>
<p class="updated-date">Dernière mise à jour : {today_fr()}</p>
<h1>Notre méthodologie</h1>
<p class="lede">Comment sont faits les comparatifs de ce site, sans blabla.</p>

<h2>Nos sources</h2>
<p>Les informations techniques (prix, autonomie, compatibilité, résolution) proviennent des fiches
produit officielles des fabricants, de comparatifs indépendants publiés par des médias spécialisés,
et de la réglementation officielle en vigueur (CNIL, lois, normes NF/A2P) citée directement dans
chaque article.</p>

<h2>Nos critères de sélection</h2>
<p>Chaque produit retenu doit fonctionner sans abonnement obligatoire pour ses fonctions essentielles
(enregistrement, détection, alerte). Nous excluons les produits dont les fonctions de base sont
bloquées derrière un plan payant. Le classement (#1, #2, #3) reflète le meilleur équilibre entre
prix, autonomie sans frais récurrents et fiabilité constatée dans les retours d'utilisateurs et
comparatifs consultés.</p>

<h2>Ce que nous ne faisons pas</h2>
<p><strong>Nous ne testons pas physiquement chaque produit.</strong> Ce site s'appuie sur l'analyse
de fiches techniques, de comparatifs tiers et de la réglementation, pas sur des essais en conditions
réelles menés par notre équipe. Nous ne publions aucune note chiffrée inventée : les avantages et
inconvénients listés sont qualitatifs et sourcés.</p>

<h2>Mise à jour des prix</h2>
<p>Les prix affichés sont des ordres de grandeur constatés au moment de la rédaction de chaque
article (voir la date de mise à jour en haut de page). Les prix réels évoluent en permanence sur
Amazon : vérifiez toujours le prix actuel avant achat via le lien fourni.</p>

<h2>Rémunération</h2>
<p>Ce site perçoit une commission sur les achats réalisés via les liens Amazon, sans coût
supplémentaire pour vous. Cette rémunération n'influence pas le classement : elle est identique
quel que soit le produit acheté.</p>
"""
    return render_page(
        "Méthodologie — comment sont faits nos comparatifs — NOVAREL",
        body,
        "Comment ce site sélectionne et compare les produits : sources utilisées, critères, absence de tests physiques déclarée honnêtement, mise à jour des prix.",
        "/methodologie",
    )


@app.get("/go/<slug>")
def go(slug):
    item = next((c for c in CAMERAS + ALARMS + LOCKS + SMOKE_DETECTORS + WATER_LEAK if c["slug"] == slug), None)
    if not item:
        return "Lien inconnu", 404
    log_click(slug, item["name"], _src())
    return redirect(amazon_search_link(item["search_query"]), code=302)


ARTICLE_PATHS = [
    "/",
    "/cameras-exterieures-sans-abonnement",
    "/alarmes-maison-sans-abonnement",
    "/serrures-connectees-sans-abonnement",
    "/detecteurs-fumee-connectes",
    "/detecteurs-fuite-eau-connectes",
    "/methodologie",
]


@app.get("/sitemap.xml")
def sitemap():
    urls = "".join(
        f"<url><loc>{SITE_URL}{p}</loc></url>" for p in ARTICLE_PATHS
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return Response(xml, mimetype="application/xml")


@app.get("/robots.txt")
def robots():
    txt = f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n"
    return Response(txt, mimetype="text/plain")


# Tokens de vérification Google Search Console valides.
# IMPORTANT : liste blanche stricte plutôt que réponse générique à
# n'importe quel token — un serveur qui confirme "vérifié" pour n'importe
# quelle URL google*.html ressemble à un site compromis aux yeux des
# contrôles anti-fraude de Google (d'où l'échec "peut-être piraté").
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

