"""
NOVAREL — moteur de simulation d'apprentissage stratégique (achat/revente).
Version 1.0 — refonte complète.

Ce fichier reste volontairement en un seul module (comme l'original) pour rester
facile à déployer, mais corrige les bugs de fond et ajoute plusieurs briques
fonctionnelles réelles (voir CHANGELOG.md fourni à côté).
"""

from __future__ import annotations

import contextlib
import csv
import io
import logging
import math
import os
import random
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, render_template_string, request
from werkzeug.exceptions import HTTPException

# ============================================================
# CONFIGURATION / LOGGING
# ============================================================

BASE = Path(__file__).parent
DB = BASE / "novarel.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("novarel")

app = Flask(__name__)

APP_VERSION = "1.0.0"

MODULES = [
    ("CEO / Orchestrateur", "Décide les prochaines actions et priorités", "ACTIVE"),
    ("Market Brain", "Analyse prix, demande, saisonnalité et concurrence", "ACTIVE"),
    ("Buyer Brain", "Score les lots par catégorie et décide quoi acheter en simulation", "ACTIVE"),
    ("Pricing Brain", "Teste prix, plancher, marge et rotation", "ACTIVE"),
    ("Marketing Brain", "Teste titres, descriptions et angles de vente", "ACTIVE"),
    ("Learning Lab", "Crée des hypothèses, expériences et apprend des résultats", "ACTIVE"),
    ("Finance Brain", "Suit CA, marge, cash et risque", "ACTIVE"),
    ("Research Brain", "Alimente la recherche et journalise les sources", "ACTIVE"),
    ("Affiliate Brain", "Teste niches et formats de contenu d'affiliation en simulation", "ACTIVE"),
]

STRATEGIES = [
    ("price_anchor", "Ancrage prix", "Tester un prix légèrement supérieur avec marge de négociation"),
    ("quick_turn", "Rotation rapide", "Privilégier un prix compétitif pour réduire le temps de vente"),
    ("margin_first", "Marge prioritaire", "Refuser les opportunités sous un seuil de marge"),
    ("value_bundle", "Bundle / valeur", "Augmenter la valeur perçue par lot ou combinaison"),
    ("negotiation_zopa", "Négociation ZOPA", "Simuler une zone d'accord avant toute décision"),
    ("seasonal_timing", "Timing saisonnier", "Adapter prix et sélection à la saison"),
    ("scarcity", "Rareté", "Privilégier les références difficiles à trouver"),
    ("conservative", "Conservatrice", "Favoriser probabilité de vente et faible risque"),
]

CATEGORIES = ["mode", "sneakers", "electronique", "collection", "maison", "livres", "outillage", "sport"]

# ------------------------------------------------------------
# Provenance des données : NOVAREL ne doit jamais présenter une
# donnée simulée comme un fait observé. Toute valeur importante
# (prix, score, profit...) porte désormais un statut explicite.
# ------------------------------------------------------------
DATA_STATUS = {
    "ESTIMATED": "estimation",
    "OBSERVED": "observed",
    "VERIFIED": "verified",
    "SIMULATED": "simulation",
    "UNKNOWN": "unknown",
}

# Actions que le Decision Engine peut recommander pour une opportunité.
# STOP et DO_NOT_EXECUTE ne sont jamais des suppressions silencieuses :
# elles restent visibles avec leur raison dans l'historique.
ACTIONS = [
    "RESEARCH_MORE",
    "VERIFY",
    "TEST",
    "OPTIMIZE",
    "SCALE",
    "WAIT",
    "STOP",
    "DO_NOT_EXECUTE",
]

# ============================================================
# AFFILIATE BRAIN — module additif
# ------------------------------------------------------------
# Simule des décisions de marketing d'affiliation (niche + format de
# contenu) avec la même mécanique d'apprentissage que le reste de
# NOVAREL (bandit de Thompson, expériences, connaissances). Comme pour
# le reste de NOVAREL, tout est SIMULATED : aucun vrai lien, aucun
# vrai trafic, aucune vraie commission ne sont générés ici.
# ============================================================

AFFILIATE_NICHES = [
    "tech_gadgets", "fitness", "beaute", "maison_connectee",
    "cuisine", "mode", "jeux_video", "finance_perso",
]

AFFILIATE_STRATEGIES = [
    ("seo_blog", "Blog SEO longue traîne",
     "Articles de comparatif optimisés pour la recherche organique, trafic lent mais durable"),
    ("youtube_review", "Vidéos de test YouTube",
     "Avis produits filmés, forte confiance mais production plus lente"),
    ("tiktok_short", "Contenu court viral",
     "Vidéos courtes à fort potentiel de portée mais conversion plus imprévisible"),
    ("comparison_site", "Site comparatif",
     "Page dédiée à comparer plusieurs produits d'une même catégorie"),
    ("email_list", "Liste email",
     "Recommandations envoyées à une audience déjà engagée, meilleur taux de conversion"),
    ("paid_ads", "Publicité payante",
     "Trafic acheté, rapide à démarrer mais coût d'acquisition à surveiller"),
    ("instagram_influence", "Contenu Instagram",
     "Posts et stories avec lien en bio, dépend de l'engagement de l'audience"),
    ("coupon_deals", "Site de bons plans",
     "Codes promo et deals, fort volume mais commission souvent plus faible"),
]

LEARNING_MODES = {
    # Coefficient d'exploration utilisé par choose_strategy(). Plus il est élevé,
    # plus le système teste des stratégies peu éprouvées plutôt que d'exploiter
    # celles qui marchent déjà.
    "adaptive": 0.30,
    "explorative": 0.55,
    "conservative": 0.12,
}

EXPORTABLE_TABLES = {
    "experiments": "SELECT * FROM experiments ORDER BY id DESC",
    "opportunities": "SELECT * FROM opportunities ORDER BY id DESC",
    "knowledge": "SELECT * FROM knowledge ORDER BY id DESC",
    "strategies": "SELECT * FROM strategies ORDER BY id DESC",
    "events": "SELECT * FROM events ORDER BY id DESC",
    "affiliate_experiments": "SELECT * FROM affiliate_experiments ORDER BY id DESC",
    "affiliate_strategies": "SELECT * FROM affiliate_strategies ORDER BY id DESC",
}


# ============================================================
# BASE DE DONNÉES
# ============================================================

# Verrou global pour sérialiser les écritures entre le thread worker et les
# requêtes Flask. SQLite gère mal les écritures concurrentes même en WAL ;
# ce verrou, combiné à busy_timeout, évite les erreurs "database is locked".
_DB_WRITE_LOCK = threading.RLock()


def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


@contextlib.contextmanager
def get_db(write: bool = False):
    """Fournit une connexion SQLite avec commit/rollback/close automatiques.

    Remplace le motif `c = db(); ...; c.commit(); c.close()` répété partout
    dans l'original, qui fuyait la connexion (et ne faisait jamais de
    rollback) dès qu'une exception survenait en cours de route.
    """
    if write:
        _DB_WRITE_LOCK.acquire()
    conn = db()
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


def _table_columns(c, table):
    return {row[1] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}


def init():
    with get_db(write=True) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings(
                k TEXT PRIMARY KEY,
                v TEXT
            );

            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY,
                ts TEXT, ts_epoch REAL,
                module TEXT, action TEXT, result TEXT,
                score REAL, strategy TEXT, experiment_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS strategies(
                id INTEGER PRIMARY KEY,
                code TEXT UNIQUE, name TEXT, description TEXT,
                tests INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0, neutrals INTEGER DEFAULT 0,
                profit_sum REAL DEFAULT 0, expected_sum REAL DEFAULT 0,
                rotation_sum REAL DEFAULT 0,
                confidence REAL DEFAULT 0.50, weight REAL DEFAULT 1.0,
                calibration_error REAL DEFAULT 0.0,
                last_result TEXT, updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS strategy_category_stats(
                strategy_code TEXT, category TEXT,
                tests INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0, neutrals INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.50,
                PRIMARY KEY(strategy_code, category)
            );

            CREATE TABLE IF NOT EXISTS affiliate_strategies(
                id INTEGER PRIMARY KEY,
                code TEXT UNIQUE, name TEXT, description TEXT,
                tests INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0, neutrals INTEGER DEFAULT 0,
                revenue_sum REAL DEFAULT 0, cost_sum REAL DEFAULT 0,
                confidence REAL DEFAULT 0.50, weight REAL DEFAULT 1.0,
                last_result TEXT, updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS affiliate_niche_stats(
                strategy_code TEXT, niche TEXT,
                tests INTEGER DEFAULT 0, wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.50,
                PRIMARY KEY(strategy_code, niche)
            );

            CREATE TABLE IF NOT EXISTS affiliate_experiments(
                id INTEGER PRIMARY KEY,
                ts TEXT, ts_epoch REAL,
                strategy TEXT, niche TEXT, hypothesis TEXT,
                traffic INTEGER, clicks INTEGER, conversions INTEGER,
                conversion_rate REAL, commission_per_sale REAL,
                revenue REAL, cost REAL, profit REAL,
                outcome TEXT, lesson TEXT, confidence REAL, data_status TEXT DEFAULT 'SIMULATED'
            );

            CREATE TABLE IF NOT EXISTS experiments(
                id INTEGER PRIMARY KEY,
                ts TEXT, ts_epoch REAL,
                strategy TEXT, category TEXT, hypothesis TEXT,
                requested_price REAL, market_value REAL, resale_price REAL,
                fees REAL, other_costs REAL, expected_margin REAL,
                probability REAL, expected_profit REAL, actual_profit REAL,
                rotation_days REAL, outcome TEXT, lesson TEXT,
                confidence REAL, prediction_error REAL
            );

            CREATE TABLE IF NOT EXISTS opportunities(
                id INTEGER PRIMARY KEY,
                ts TEXT, ts_epoch REAL,
                category TEXT, item TEXT, ask_price REAL,
                market_low REAL, market_high REAL, resale_price REAL, fees REAL,
                risk REAL, liquidity REAL, trend REAL, confidence REAL,
                score REAL, expected_profit REAL, recommendation TEXT, evidence TEXT
            );

            CREATE TABLE IF NOT EXISTS knowledge(
                id INTEGER PRIMARY KEY,
                ts TEXT, ts_epoch REAL,
                topic TEXT, insight TEXT, confidence REAL,
                source_type TEXT, corroboration INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS curiosity_questions(
                id INTEGER PRIMARY KEY,
                ts TEXT, topic TEXT, question TEXT, reason TEXT,
                priority REAL DEFAULT 0.50, status TEXT DEFAULT 'open',
                linked_knowledge_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS metrics(
                id INTEGER PRIMARY KEY,
                ts TEXT,
                sim_revenue REAL, sim_profit REAL, sim_invested REAL,
                experiments INTEGER, opportunities INTEGER,
                win_rate REAL, prediction_error REAL, nosi REAL, confidence REAL
            );

            CREATE TABLE IF NOT EXISTS improvements(
                id INTEGER PRIMARY KEY,
                ts TEXT, component TEXT, title TEXT, rationale TEXT,
                expected_gain REAL, risk REAL, status TEXT, evidence TEXT,
                baseline REAL, candidate REAL
            );

            CREATE TABLE IF NOT EXISTS gates(
                id INTEGER PRIMARY KEY,
                ts TEXT, name TEXT, status TEXT, score REAL, reason TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_events_ts_epoch ON events(ts_epoch);
            CREATE INDEX IF NOT EXISTS idx_experiments_ts_epoch ON experiments(ts_epoch);
            CREATE INDEX IF NOT EXISTS idx_experiments_category ON experiments(category);
            CREATE INDEX IF NOT EXISTS idx_opportunities_ts_epoch ON opportunities(ts_epoch);
            CREATE INDEX IF NOT EXISTS idx_opportunities_score ON opportunities(score);
            CREATE INDEX IF NOT EXISTS idx_strategies_confidence ON strategies(confidence);
            CREATE INDEX IF NOT EXISTS idx_catstats_category ON strategy_category_stats(category);
            CREATE INDEX IF NOT EXISTS idx_affexp_ts_epoch ON affiliate_experiments(ts_epoch);
            CREATE INDEX IF NOT EXISTS idx_affexp_niche ON affiliate_experiments(niche);
            CREATE INDEX IF NOT EXISTS idx_affnichestats_niche ON affiliate_niche_stats(niche);
            """
        )

        # ------------------------------------------------------------
        # Migrations de compatibilité : on ajoute les colonnes manquantes
        # sans jamais effacer les données existantes.
        # ------------------------------------------------------------
        migrations = {
            "events": [("strategy", "TEXT"), ("experiment_id", "INTEGER"), ("ts_epoch", "REAL")],
            "experiments": [
                ("strategy", "TEXT"), ("category", "TEXT"), ("hypothesis", "TEXT"),
                ("requested_price", "REAL"), ("market_value", "REAL"), ("resale_price", "REAL"),
                ("fees", "REAL"), ("other_costs", "REAL"), ("expected_margin", "REAL"),
                ("probability", "REAL"), ("expected_profit", "REAL"), ("actual_profit", "REAL"),
                ("rotation_days", "REAL"), ("outcome", "TEXT"), ("lesson", "TEXT"),
                ("confidence", "REAL"), ("prediction_error", "REAL"), ("ts_epoch", "REAL"),
                ("data_status", "TEXT DEFAULT 'SIMULATED'"),
            ],
            "opportunities": [
                ("ts_epoch", "REAL"),
                ("data_status", "TEXT DEFAULT 'SIMULATED'"),
                ("recommended_action", "TEXT"),
            ],
            "metrics": [
                ("sim_revenue", "REAL"), ("sim_profit", "REAL"), ("sim_invested", "REAL"),
                ("experiments", "INTEGER"), ("opportunities", "INTEGER"),
                ("win_rate", "REAL"), ("prediction_error", "REAL"), ("nosi", "REAL"),
            ],
            "knowledge": [("source_type", "TEXT"), ("corroboration", "INTEGER DEFAULT 0"), ("ts_epoch", "REAL")],
            "strategies": [("weight", "REAL DEFAULT 1.0")],
        }

        for table, columns in migrations.items():
            existing = _table_columns(c, table)
            for column, column_type in columns:
                if column not in existing:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

        # Rétro-remplissage de ts_epoch pour les lignes historiques qui ne
        # l'avaient pas encore (calculé depuis la colonne texte `ts`).
        for table in ("events", "experiments", "opportunities", "knowledge"):
            c.execute(
                f"""
                UPDATE {table}
                SET ts_epoch = (julianday(REPLACE(ts, 'T', ' ')) - 2440587.5) * 86400.0
                WHERE ts_epoch IS NULL AND ts IS NOT NULL
                """
            )

        defaults = {
            "running": "1",
            "simulation_only": "1",
            "max_auto_purchase": "0",
            "risk_fraction": "0.10",
            "cycle_seconds": "15",
            "learning_mode": "adaptive",
        }
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES(?,?)", (k, v))

        now = datetime.now().isoformat(timespec="seconds")
        for code, name, description in STRATEGIES:
            c.execute(
                "INSERT OR IGNORE INTO strategies(code,name,description,updated_at) VALUES(?,?,?,?)",
                (code, name, description, now),
            )

        for code, name, description in AFFILIATE_STRATEGIES:
            c.execute(
                "INSERT OR IGNORE INTO affiliate_strategies(code,name,description,updated_at) VALUES(?,?,?,?)",
                (code, name, description, now),
            )

        if not c.execute("SELECT 1 FROM knowledge LIMIT 1").fetchone():
            c.execute(
                "INSERT INTO knowledge(ts,ts_epoch,topic,insight,confidence,source_type,corroboration) "
                "VALUES(?,?,?,?,?,?,?)",
                (now, time.time(), "system",
                 "NOVAREL sépare désormais hypothèse, simulation, résultat et apprentissage.",
                 0.90, "system", 1),
            )

        if not c.execute("SELECT 1 FROM metrics LIMIT 1").fetchone():
            c.execute(
                "INSERT INTO metrics(ts,sim_revenue,sim_profit,sim_invested,experiments,"
                "opportunities,win_rate,prediction_error,nosi,confidence) "
                "VALUES(?,0,0,0,0,0,0,0,1.0,0.50)",
                (now,),
            )


_settings_cache: dict[str, str | None] = {}
_settings_lock = threading.Lock()


def setting(k):
    with _settings_lock:
        if k in _settings_cache:
            return _settings_cache[k]
    with get_db() as c:
        r = c.execute("SELECT v FROM settings WHERE k=?", (k,)).fetchone()
    value = r["v"] if r else None
    with _settings_lock:
        _settings_cache[k] = value
    return value


def set_setting(k, v):
    with get_db(write=True) as c:
        c.execute("UPDATE settings SET v=? WHERE k=?", (v, k))
    with _settings_lock:
        _settings_cache[k] = v


# ============================================================
# UTILS
# ============================================================

def clamp(x, minimum=0, maximum=1):
    return max(minimum, min(maximum, x))


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def log_event(module, action, result, score=None, strategy=None, experiment_id=None):
    with get_db(write=True) as c:
        c.execute(
            "INSERT INTO events(ts,ts_epoch,module,action,result,score,strategy,experiment_id) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (now_iso(), time.time(), module, action, result, score, strategy, experiment_id),
        )


# ============================================================
# STRATEGY ENGINE
# ============================================================

def choose_strategy(category: str | None = None):
    """Sélectionne une stratégie via un bandit de Thompson (bêta postérieure),
    avec une prime d'exploration, une pénalité de mauvaise calibration et,
    désormais, une pondération manuelle (`weight`) et des statistiques
    spécifiques à la catégorie quand elles sont assez fournies (>= 3 tests).
    """
    exploration_scale = LEARNING_MODES.get(setting("learning_mode") or "adaptive", 0.30)

    with get_db() as c:
        rows = c.execute("SELECT * FROM strategies").fetchall()
        cat_stats = {}
        if category:
            cat_stats = {
                r["strategy_code"]: r
                for r in c.execute(
                    "SELECT * FROM strategy_category_stats WHERE category=?", (category,)
                ).fetchall()
            }

    candidates = []
    for r in rows:
        cat = cat_stats.get(r["code"])
        if cat and cat["tests"] >= 3:
            wins_eff, losses_eff, tests_eff = cat["wins"], cat["losses"], cat["tests"]
        else:
            wins_eff, losses_eff, tests_eff = r["wins"], r["losses"], r["tests"]

        posterior = random.betavariate(wins_eff + 1, losses_eff + 1)
        exploration = exploration_scale / math.sqrt(tests_eff + 1)
        calibration_penalty = min(0.20, float(r["calibration_error"]))
        weight = clamp(float(r["weight"] or 1.0), 0.2, 2.0)

        value = (posterior + exploration + 0.15 * float(r["confidence"]) - calibration_penalty) * weight
        candidates.append((value, r))

    return max(candidates, key=lambda x: x[0])[1]


# ============================================================
# SIMULATION
# ============================================================

_STRATEGY_PARAMS = {
    # code: (probabilité de base, liquidité de base, rotation de base en jours)
    "price_anchor": (0.78, 0.68, 8),
    "quick_turn": (0.70, 0.84, 4),
    "margin_first": (0.56, 0.89, 10),
    "value_bundle": (0.76, 0.64, 8),
    "negotiation_zopa": (0.74, 0.74, 7),
    "seasonal_timing": (0.79, 0.68, 9),
    "scarcity": (0.82, 0.60, 13),
    "conservative": (0.63, 0.91, 5),
}


def simulate_experiment(strategy, category):
    market_value = random.uniform(25, 250)
    ask = market_value * random.uniform(0.38, 0.82)

    base_probability, liquidity_base, rotation_base = _STRATEGY_PARAMS[strategy["code"]]

    trend = random.uniform(0.70, 1.25)
    risk = random.uniform(0.04, 0.45)
    liquidity = clamp(liquidity_base + random.gauss(0, 0.10))

    probability = clamp(
        base_probability
        + (trend - 1) * 0.18
        + (liquidity - 0.70) * 0.20
        - risk * 0.20
        + random.gauss(0, 0.09)
    )

    resale = market_value * random.uniform(0.88, 1.10) * trend
    fees = resale * random.uniform(0.055, 0.14) + random.uniform(1, 5)
    other_costs = random.uniform(0.5, 6)
    gross_margin = resale - ask - fees - other_costs
    expected_profit = probability * gross_margin
    rotation = max(2, rotation_base + random.gauss(0, 3))

    sold = random.random() < probability
    if sold:
        realized_price = resale * random.uniform(0.90, 1.02)
        actual_profit = (
            realized_price - ask
            - (realized_price * random.uniform(0.055, 0.14))
            - other_costs
        )
    else:
        actual_profit = -random.uniform(0, max(2, ask * 0.10))

    if actual_profit > 0:
        outcome = "WIN"
    elif actual_profit < 0:
        outcome = "LOSS"
    else:
        outcome = "NEUTRAL"

    prediction_error = abs(probability - (1 if sold else 0))

    lesson = (
        f"{strategy['name']} ({category}) : {outcome.lower()} — "
        f"profit simulé {actual_profit:+.2f} € — "
        f"probabilité prévue {probability:.0%} — {'vente' if sold else 'non-vente'}."
    )

    return {
        "category": category, "ask": ask, "market": market_value, "resale": resale,
        "fees": fees, "other": other_costs, "expected_margin": gross_margin,
        "probability": probability, "expected": expected_profit, "actual": actual_profit,
        "rotation": rotation, "outcome": outcome, "lesson": lesson,
        "prediction_error": prediction_error, "sold": sold,
    }


# ============================================================
# LEARNING ENGINE
# ============================================================

def _update_category_stats(c, strategy_code, category, win, loss, neutral, new_confidence):
    row = c.execute(
        "SELECT * FROM strategy_category_stats WHERE strategy_code=? AND category=?",
        (strategy_code, category),
    ).fetchone()
    if row is None:
        c.execute(
            "INSERT INTO strategy_category_stats(strategy_code,category,tests,wins,losses,neutrals,confidence) "
            "VALUES(?,?,1,?,?,?,?)",
            (strategy_code, category, win, loss, neutral, new_confidence),
        )
        return
    tests = row["tests"] + 1
    old_conf = float(row["confidence"])
    observed = 1.0 if win else (0.5 if neutral else 0.0)
    blended_conf = clamp(old_conf + (observed - old_conf) / max(4, tests))
    c.execute(
        "UPDATE strategy_category_stats SET tests=?, wins=wins+?, losses=losses+?, "
        "neutrals=neutrals+?, confidence=? WHERE strategy_code=? AND category=?",
        (tests, win, loss, neutral, blended_conf, strategy_code, category),
    )


def run_learning_experiment():
    category = random.choice(CATEGORIES)
    strategy = choose_strategy(category)
    result = simulate_experiment(strategy, category)

    win = int(result["outcome"] == "WIN")
    loss = int(result["outcome"] == "LOSS")
    neutral = int(result["outcome"] == "NEUTRAL")

    with get_db(write=True) as c:
        c.execute(
            """
            INSERT INTO experiments(
                ts, ts_epoch, strategy, category, hypothesis,
                requested_price, market_value, resale_price, fees, other_costs,
                expected_margin, probability, expected_profit, actual_profit,
                rotation_days, outcome, lesson, confidence, prediction_error, data_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_iso(), time.time(), strategy["code"], result["category"], strategy["description"],
                result["ask"], result["market"], result["resale"], result["fees"], result["other"],
                result["expected_margin"], result["probability"], result["expected"], result["actual"],
                result["rotation"], result["outcome"], result["lesson"],
                clamp(1 - result["prediction_error"]), result["prediction_error"], "SIMULATED",
            ),
        )
        experiment_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]

        tests = strategy["tests"] + 1
        old_confidence = float(strategy["confidence"])
        observed = 1.0 if win else (0.5 if neutral else 0.0)
        new_confidence = clamp(old_confidence + (observed - old_confidence) / max(8, tests))

        old_calibration = float(strategy["calibration_error"])
        new_calibration = ((old_calibration * (tests - 1)) + result["prediction_error"]) / tests

        # Adaptation légère du poids manuel : une stratégie qui enchaîne les
        # victoires prend un peu plus de poids dans les futurs choix, l'inverse
        # pour les échecs. Borné à [0.2, 2.0] pour rester réversible.
        old_weight = clamp(float(strategy["weight"] or 1.0), 0.2, 2.0)
        weight_step = 0.03
        if result["outcome"] == "WIN":
            new_weight = clamp(old_weight + weight_step, 0.2, 2.0)
        elif result["outcome"] == "LOSS":
            new_weight = clamp(old_weight - weight_step, 0.2, 2.0)
        else:
            new_weight = old_weight

        c.execute(
            """
            UPDATE strategies SET
                tests=?, wins=wins+?, losses=losses+?, neutrals=neutrals+?,
                profit_sum=profit_sum+?, expected_sum=expected_sum+?, rotation_sum=rotation_sum+?,
                confidence=?, weight=?, calibration_error=?, last_result=?, updated_at=?
            WHERE id=?
            """,
            (
                tests, win, loss, neutral,
                result["actual"], result["expected"], result["rotation"],
                new_confidence, new_weight, new_calibration, result["outcome"], now_iso(),
                strategy["id"],
            ),
        )

        _update_category_stats(c, strategy["code"], category, win, loss, neutral, new_confidence)

        c.execute(
            "INSERT INTO knowledge(ts,ts_epoch,topic,insight,confidence,source_type,corroboration) "
            "VALUES(?,?,?,?,?,?,?)",
            (now_iso(), time.time(), "strategy_learning", result["lesson"], new_confidence, "simulation", 0),
        )

        previous = c.execute("SELECT * FROM metrics ORDER BY id DESC LIMIT 1").fetchone()
        simulated_revenue = previous["sim_revenue"] + (result["resale"] if result["sold"] else 0)
        simulated_profit = previous["sim_profit"] + result["actual"]
        simulated_invested = previous["sim_invested"] + result["ask"]
        experiments_count = previous["experiments"] + 1

        totals = c.execute("SELECT SUM(tests) AS tests, SUM(wins) AS wins FROM strategies").fetchone()
        total_tests = totals["tests"] or 0
        total_wins = totals["wins"] or 0
        win_rate = total_wins / max(1, total_tests)

        avg_error = c.execute("SELECT AVG(prediction_error) AS error FROM experiments").fetchone()["error"] or 0

        objective_score = clamp(0.55 + win_rate * 0.45)
        stability_score = clamp(1 - avg_error)
        safety_score = 1.0
        reversibility_score = 1.0
        nosi = (
            objective_score * 0.35
            + stability_score * 0.25
            + safety_score * 0.20
            + reversibility_score * 0.20
        )
        system_confidence = clamp(0.50 + (win_rate - 0.50) * 0.35)

        c.execute(
            "INSERT INTO metrics(ts,sim_revenue,sim_profit,sim_invested,experiments,opportunities,"
            "win_rate,prediction_error,nosi,confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                now_iso(), simulated_revenue, simulated_profit, simulated_invested,
                experiments_count, previous["opportunities"], win_rate, avg_error, nosi, system_confidence,
            ),
        )

    log_event(
        "CEO / Orchestrateur",
        f"Tester stratégie « {strategy['name']} » ({category})",
        (
            f"{result['outcome']} · profit simulé {result['actual']:+.2f} € · "
            f"prévision {result['probability']:.0%} · erreur {result['prediction_error']:.0%}"
        ),
        result["actual"], strategy["code"], experiment_id,
    )


# ============================================================
# AFFILIATE BRAIN — moteur d'apprentissage
# ============================================================

def choose_affiliate_strategy(niche: str | None = None):
    """Même mécanique que choose_strategy() (bandit de Thompson +
    exploration + calibration + poids), appliquée aux stratégies
    d'affiliation plutôt qu'aux stratégies de revente.
    """
    exploration_scale = LEARNING_MODES.get(setting("learning_mode") or "adaptive", 0.30)

    with get_db() as c:
        rows = c.execute("SELECT * FROM affiliate_strategies").fetchall()
        niche_stats = {}
        if niche:
            niche_stats = {
                r["strategy_code"]: r
                for r in c.execute(
                    "SELECT * FROM affiliate_niche_stats WHERE niche=?", (niche,)
                ).fetchall()
            }

    candidates = []
    for r in rows:
        nstat = niche_stats.get(r["code"])
        if nstat and nstat["tests"] >= 3:
            wins_eff, losses_eff, tests_eff = nstat["wins"], nstat["losses"], nstat["tests"]
        else:
            wins_eff, losses_eff, tests_eff = r["wins"], r["losses"], r["tests"]

        posterior = random.betavariate(wins_eff + 1, losses_eff + 1)
        exploration = exploration_scale / math.sqrt(tests_eff + 1)
        weight = clamp(float(r["weight"] or 1.0), 0.2, 2.0)

        value = (posterior + exploration + 0.15 * float(r["confidence"])) * weight
        candidates.append((value, r))

    return max(candidates, key=lambda x: x[0])[1]


_AFFILIATE_NICHE_MULTIPLIERS = {
    "tech_gadgets": 1.15, "fitness": 1.00, "beaute": 1.05, "maison_connectee": 1.10,
    "cuisine": 0.95, "mode": 0.90, "jeux_video": 1.00, "finance_perso": 1.20,
}

_AFFILIATE_STRATEGY_PARAMS = {
    # code: (traffic_min, traffic_max, conv_min, conv_max, commission_min, commission_max, cost_min, cost_max)
    "seo_blog":            (200, 2000, 0.010, 0.030, 3, 15, 5, 20),
    "youtube_review":      (500, 5000, 0.020, 0.040, 5, 25, 10, 50),
    "tiktok_short":        (1000, 20000, 0.003, 0.015, 2, 10, 0, 10),
    "comparison_site":     (300, 3000, 0.020, 0.050, 5, 20, 10, 40),
    "email_list":          (100, 1500, 0.030, 0.080, 5, 20, 5, 15),
    "paid_ads":            (500, 5000, 0.010, 0.030, 5, 20, 50, 300),
    "instagram_influence": (300, 4000, 0.005, 0.020, 3, 15, 0, 20),
    "coupon_deals":        (1000, 10000, 0.010, 0.040, 1, 5, 5, 20),
}


def simulate_affiliate_experiment(strategy, niche):
    (traffic_min, traffic_max, conv_min, conv_max,
     comm_min, comm_max, cost_min, cost_max) = _AFFILIATE_STRATEGY_PARAMS[strategy["code"]]

    niche_mult = _AFFILIATE_NICHE_MULTIPLIERS.get(niche, 1.0)

    traffic = int(random.uniform(traffic_min, traffic_max))
    click_through_rate = clamp(random.uniform(0.25, 0.90))
    clicks = int(traffic * click_through_rate)

    conversion_rate = clamp(random.uniform(conv_min, conv_max) * niche_mult, 0, 1)
    conversions = int(clicks * conversion_rate)

    commission_per_sale = random.uniform(comm_min, comm_max)
    revenue = conversions * commission_per_sale
    cost = random.uniform(cost_min, cost_max)
    profit = revenue - cost

    if profit > 1:
        outcome = "WIN"
    elif profit < -1:
        outcome = "LOSS"
    else:
        outcome = "NEUTRAL"

    lesson = (
        f"{strategy['name']} ({niche}) : {outcome.lower()} — "
        f"{conversions} conversions sur {clicks} clics ({conversion_rate:.1%}) — "
        f"revenu simulé {revenue:.2f} € pour un coût de {cost:.2f} € — "
        f"profit {profit:+.2f} €."
    )

    return {
        "niche": niche, "traffic": traffic, "clicks": clicks, "conversions": conversions,
        "conversion_rate": conversion_rate, "commission_per_sale": commission_per_sale,
        "revenue": revenue, "cost": cost, "profit": profit,
        "outcome": outcome, "lesson": lesson,
    }


def run_affiliate_learning_experiment():
    niche = random.choice(AFFILIATE_NICHES)
    strategy = choose_affiliate_strategy(niche)
    result = simulate_affiliate_experiment(strategy, niche)

    win = int(result["outcome"] == "WIN")
    loss = int(result["outcome"] == "LOSS")
    neutral = int(result["outcome"] == "NEUTRAL")

    with get_db(write=True) as c:
        c.execute(
            """
            INSERT INTO affiliate_experiments(
                ts, ts_epoch, strategy, niche, hypothesis,
                traffic, clicks, conversions, conversion_rate, commission_per_sale,
                revenue, cost, profit, outcome, lesson, confidence, data_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_iso(), time.time(), strategy["code"], niche, strategy["description"],
                result["traffic"], result["clicks"], result["conversions"],
                result["conversion_rate"], result["commission_per_sale"],
                result["revenue"], result["cost"], result["profit"],
                result["outcome"], result["lesson"], strategy["confidence"], "SIMULATED",
            ),
        )
        experiment_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]

        tests = strategy["tests"] + 1
        old_confidence = float(strategy["confidence"])
        observed = 1.0 if win else (0.5 if neutral else 0.0)
        new_confidence = clamp(old_confidence + (observed - old_confidence) / max(8, tests))

        old_weight = clamp(float(strategy["weight"] or 1.0), 0.2, 2.0)
        weight_step = 0.03
        if result["outcome"] == "WIN":
            new_weight = clamp(old_weight + weight_step, 0.2, 2.0)
        elif result["outcome"] == "LOSS":
            new_weight = clamp(old_weight - weight_step, 0.2, 2.0)
        else:
            new_weight = old_weight

        c.execute(
            """
            UPDATE affiliate_strategies SET
                tests=?, wins=wins+?, losses=losses+?, neutrals=neutrals+?,
                revenue_sum=revenue_sum+?, cost_sum=cost_sum+?,
                confidence=?, weight=?, last_result=?, updated_at=?
            WHERE id=?
            """,
            (
                tests, win, loss, neutral,
                result["revenue"], result["cost"],
                new_confidence, new_weight, result["outcome"], now_iso(),
                strategy["id"],
            ),
        )

        nrow = c.execute(
            "SELECT * FROM affiliate_niche_stats WHERE strategy_code=? AND niche=?",
            (strategy["code"], niche),
        ).fetchone()
        if nrow is None:
            c.execute(
                "INSERT INTO affiliate_niche_stats(strategy_code,niche,tests,wins,losses,confidence) "
                "VALUES(?,?,1,?,?,?)",
                (strategy["code"], niche, win, loss, new_confidence),
            )
        else:
            c.execute(
                "UPDATE affiliate_niche_stats SET tests=tests+1, wins=wins+?, losses=losses+?, confidence=? "
                "WHERE strategy_code=? AND niche=?",
                (win, loss, new_confidence, strategy["code"], niche),
            )

        c.execute(
            "INSERT INTO knowledge(ts,ts_epoch,topic,insight,confidence,source_type,corroboration) "
            "VALUES(?,?,?,?,?,?,?)",
            (now_iso(), time.time(), "affiliate_learning", result["lesson"], new_confidence, "simulation", 0),
        )

    log_event(
        "Affiliate Brain",
        f"Tester « {strategy['name']} » sur {niche}",
        (
            f"{result['outcome']} · {result['conversions']} conversions · "
            f"profit simulé {result['profit']:+.2f} €"
        ),
        result["profit"], strategy["code"], experiment_id,
    )


# ============================================================
# DECISION ENGINE
# ============================================================

def choose_action(score: float, confidence: float) -> str:
    """Traduit un score et un niveau de confiance en action recommandée.

    `score` et `confidence` sont attendus sur l'échelle interne 0-1 (le
    document de référence les décrit sur 0-100 ; les seuils ci-dessous
    sont les mêmes, simplement ramenés à 0-1). Une confiance trop faible
    prime toujours sur le score : NOVAREL doit vérifier avant d'agir,
    jamais deviner à la place d'une donnée manquante.
    """
    if confidence < 0.35:
        return "VERIFY"
    if score < 0.20:
        return "STOP"
    if score < 0.45:
        return "RESEARCH_MORE"
    if score < 0.70:
        return "TEST"
    return "OPTIMIZE"


# ============================================================
# OPPORTUNITY ENGINE
# ============================================================

def generate_opportunity():
    category = random.choice(CATEGORIES)
    market = random.uniform(30, 300)
    ask = market * random.uniform(0.35, 0.92)
    resale = market * random.uniform(0.90, 1.12)
    fees = resale * random.uniform(0.055, 0.14) + random.uniform(1, 5)
    risk = random.uniform(0.05, 0.42)
    liquidity = random.uniform(0.40, 0.96)
    trend = random.uniform(0.70, 1.25)
    confidence = clamp(0.50 + liquidity * 0.25 - risk * 0.25)

    gross = resale - ask - fees
    expected_profit = gross * confidence
    margin_ratio = gross / max(ask, 1)

    score = clamp(
        0.30 * clamp(margin_ratio / 0.50)
        + 0.23 * liquidity
        + 0.17 * clamp(trend / 1.20)
        + 0.18 * (1 - risk)
        + 0.12 * confidence
    )

    recommendation = "SIMULER ACHAT" if (score >= 0.68 and expected_profit > 5) else "SURVEILLER"

    # Le score est un MODEL_SCORE : un indicateur interne explicable, jamais
    # une probabilité garantie de gagner de l'argent. Toutes les valeurs
    # d'entrée étant elles-mêmes générées aléatoirement ici, la donnée est
    # étiquetée SIMULATED plutôt que présentée comme une observation réelle.
    recommended_action = choose_action(score, confidence)
    data_status = "SIMULATED"

    with get_db(write=True) as c:
        c.execute(
            """
            INSERT INTO opportunities(
                ts, ts_epoch, category, item, ask_price, market_low, market_high, resale_price,
                fees, risk, liquidity, trend, confidence, score, expected_profit, recommendation, evidence,
                data_status, recommended_action
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_iso(), time.time(), category, f"Opportunité simulée — {category}", ask,
                market * 0.90, market * 1.10, resale, fees, risk, liquidity, trend,
                confidence, score, expected_profit, recommendation,
                "Données synthétiques de laboratoire.",
                data_status, recommended_action,
            ),
        )
        c.execute(
            "UPDATE metrics SET opportunities = opportunities + 1 "
            "WHERE id = (SELECT MAX(id) FROM metrics)"
        )

    log_event(
        "Buyer Brain", "Évaluer opportunité",
        (
            f"{recommendation} · action {recommended_action} · "
            f"MODEL_SCORE {score:.0%} · profit attendu (simulé) {expected_profit:+.2f} €"
        ),
        score,
    )


# ============================================================
# IMPROVEMENT ENGINE
# ============================================================

def analyze_category_performance():
    """Calcule, pour chaque catégorie suffisamment testée, la meilleure
    stratégie observée et journalise le résultat comme connaissance.
    Remplace l'ancienne « proposition » vague de segmentation par catégorie,
    qui est désormais réellement implémentée dans choose_strategy().
    """
    inserted = 0
    with get_db(write=True) as c:
        rows = c.execute(
            """
            SELECT scs.category, s.name AS strategy_name, scs.tests, scs.wins
            FROM strategy_category_stats scs
            JOIN strategies s ON s.code = scs.strategy_code
            WHERE scs.tests >= 3
            """
        ).fetchall()

        best_by_category = {}
        for r in rows:
            win_rate = r["wins"] / r["tests"] if r["tests"] else 0
            current = best_by_category.get(r["category"])
            if current is None or win_rate > current["win_rate"]:
                best_by_category[r["category"]] = {
                    "strategy": r["strategy_name"], "win_rate": win_rate, "tests": r["tests"],
                }

        for category, info in best_by_category.items():
            insight = (
                f"Pour la catégorie « {category} », la stratégie « {info['strategy']} » "
                f"obtient le meilleur taux de réussite observé "
                f"({info['win_rate']:.0%} sur {info['tests']} tests)."
            )
            exists = c.execute(
                "SELECT 1 FROM knowledge WHERE topic='category_performance' AND insight=?",
                (insight,),
            ).fetchone()
            if not exists:
                c.execute(
                    "INSERT INTO knowledge(ts,ts_epoch,topic,insight,confidence,source_type,corroboration) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (now_iso(), time.time(), "category_performance", insight,
                     clamp(info["win_rate"]), "analysis", 1),
                )
                inserted += 1
    return inserted


def propose_improvement():
    with get_db() as c:
        strategies = c.execute(
            "SELECT AVG(confidence) AS confidence, AVG(calibration_error) AS error, "
            "SUM(tests) AS tests, SUM(wins) AS wins FROM strategies"
        ).fetchone()

    average_confidence = float(strategies["confidence"] or 0.50)
    average_error = float(strategies["error"] or 0)
    tests = int(strategies["tests"] or 0)
    wins = int(strategies["wins"] or 0)
    win_rate = wins / max(1, tests)

    if average_error > 0.35:
        component, title = "Learning Lab", "Améliorer la calibration des probabilités"
        rationale = "Les prédictions sont trop éloignées des résultats."
        expected_gain, risk = 0.12, 0.08
        evidence_extra = ""
    elif win_rate < 0.45 and tests >= 8:
        component, title = "CEO / Orchestrateur", "Réduire le poids des stratégies faibles"
        rationale = (
            "Les résultats montrent une destruction de valeur. Le poids adaptatif "
            "(colonne `weight`) ajuste déjà automatiquement chaque stratégie après "
            "chaque expérience ; cette proposition suit son efficacité."
        )
        expected_gain, risk = 0.10, 0.10
        evidence_extra = ""
    elif tests >= 10:
        component, title = "Market Brain", "Analyser la meilleure stratégie par catégorie"
        rationale = "Une stratégie peut être bonne dans une catégorie et mauvaise dans une autre."
        expected_gain, risk = 0.16, 0.12
        added = analyze_category_performance()
        evidence_extra = f"; {added} nouvel(le)s insight(s) catégorie généré(s)"
    else:
        component, title = "Learning Lab", "Augmenter la diversité des hypothèses"
        rationale = "NOVAREL doit explorer avant de privilégier."
        expected_gain, risk = 0.08, 0.06
        evidence_extra = ""

    baseline = average_confidence
    candidate = clamp(baseline + expected_gain * (1 - risk))

    with get_db(write=True) as c:
        c.execute(
            """
            INSERT INTO improvements(
                ts, component, title, rationale, expected_gain, risk, status, evidence, baseline, candidate
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_iso(), component, title, rationale, expected_gain, risk, "PROPOSED",
                (
                    f"tests={tests}; win_rate={win_rate:.1%}; "
                    f"prediction_error={average_error:.1%}{evidence_extra}"
                ),
                baseline, candidate,
            ),
        )

    log_event(
        "Learning Lab", "Proposer amélioration",
        f"{component}: {title} · gain potentiel {expected_gain:.0%}",
        expected_gain,
    )


# ============================================================
# SAFETY / VERIFICATION
# ============================================================

def run_verification():
    with get_db() as c:
        metrics = c.execute("SELECT * FROM metrics ORDER BY id DESC LIMIT 1").fetchone()

    checks = [
        ("Simulation uniquement", setting("simulation_only") == "1", "Le système doit rester en simulation."),
        ("Achat automatique", float(setting("max_auto_purchase")) == 0, "Aucun achat automatique."),
        ("Auto-déploiement", True, "Les améliorations restent proposées."),
        ("Stabilité", (metrics["nosi"] if metrics else 1) >= 0.70, "NOSI inférieur au seuil."),
        ("Réversibilité", True, "Les modifications doivent rester réversibles."),
    ]

    with get_db(write=True) as c:
        for name, ok, reason in checks:
            c.execute(
                "INSERT INTO gates(ts,name,status,score,reason) VALUES(?,?,?,?,?)",
                (now_iso(), name, "PASS" if ok else "BLOCKED", 1.0 if ok else 0.0, reason),
            )


# ============================================================
# CURIOSITÉ
# ============================================================

_CURIOSITY_TEMPLATES = [
    "Qu'est-ce qui pourrait expliquer cette observation sur {topic} ?",
    "Quelle hypothèse testable peut-on déduire de cette observation sur {topic} ?",
    "Dans quelles conditions cette observation sur {topic} ne serait-elle plus vraie ?",
    "Quelle connexion utile peut-on faire entre cette observation et une autre stratégie ?",
]


def generate_curiosity_question():
    """Formule une question exploitable en simulation à partir d'une
    connaissance existante. Aucune recherche externe ni action réelle.
    """
    with get_db() as c:
        rows = c.execute(
            "SELECT id, topic, insight, confidence FROM knowledge ORDER BY id DESC LIMIT 12"
        ).fetchall()

    if not rows:
        return None

    item = random.choice(rows)
    topic = item["topic"] or "marché"
    insight = item["insight"] or "une observation récente"
    question = random.choice(_CURIOSITY_TEMPLATES).format(topic=topic)
    priority = clamp(0.45 + float(item["confidence"] or 0.5) * 0.35 + random.uniform(-0.10, 0.10))
    reason = "Question générée à partir d'une connaissance existante : " + insight[:180]

    with get_db(write=True) as c:
        cur = c.execute(
            "INSERT INTO curiosity_questions(ts,topic,question,reason,priority,status,linked_knowledge_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (now_iso(), topic, question, reason, priority, "open", item["id"]),
        )
        question_id = cur.lastrowid

    log_event("Curiosity", "question", question, score=priority)

    return {"id": question_id, "topic": topic, "question": question, "priority": priority}


# ============================================================
# BOUCLE AUTONOME
# ============================================================

def cycle():
    choice = random.random()
    if choice < 0.10:
        generate_curiosity_question()
    elif choice < 0.45:
        run_learning_experiment()
    elif choice < 0.60:
        run_affiliate_learning_experiment()
    elif choice < 0.80:
        generate_opportunity()
    elif choice < 0.92:
        propose_improvement()
    else:
        run_verification()


_last_cycle_ts = 0.0


def worker():
    global _last_cycle_ts
    while True:
        # Relu à chaque itération : un changement de cycle_seconds via
        # /api/settings prend effet immédiatement, sans redémarrage du process.
        interval = max(
            5,
            int(os.environ.get("NOVAREL_CYCLE_SECONDS") or setting("cycle_seconds") or "15"),
        )
        try:
            if setting("running") == "1":
                cycle()
                _last_cycle_ts = time.time()
        except Exception as e:
            logger.exception("Erreur dans le cycle du worker")
            try:
                log_event("System", "error", str(e))
            except Exception:
                logger.exception("Impossible de journaliser l'erreur du worker")
        time.sleep(interval)


def start_worker():
    if os.environ.get("NOVAREL_WORKER_ENABLED", "1") != "1":
        return
    thread = threading.Thread(target=worker, daemon=True, name="novarel-worker")
    thread.start()


# ============================================================
# ROUTES — PAGES
# ============================================================

@app.route("/")
def index():
    try:
        html = render_template("index.html")
    except Exception:
        html = (
            "<!doctype html><html lang='fr'><body style='background:#07101b;color:#eaf2f8;"
            "font-family:system-ui;padding:40px'>"
            "<h1>NOVAREL</h1><p>Le template principal (templates/index.html) est introuvable.</p>"
            "<p><a href='/analysis' style='color:#9fc4ff'>Ouvrir le Centre d'analyse</a></p>"
            "</body></html>"
        )

    analysis_link = """
    <div style="position:fixed;right:18px;bottom:18px;z-index:9999">
      <a href="/analysis" style="display:inline-block;padding:11px 15px;border-radius:10px;background:#102238;border:1px solid #29405a;color:#eaf2f8;text-decoration:none;font:600 14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.25)">
        🧠 Centre d'analyse
      </a>
    </div>
    """
    if "</body>" in html:
        html = html.replace("</body>", analysis_link + "</body>", 1)
    return html


@app.get("/health")
def health():
    worker_alive = (time.time() - _last_cycle_ts) < (3 * max(5, int(setting("cycle_seconds") or "15")))
    return jsonify(
        {
            "status": "ok",
            "version": APP_VERSION,
            "simulation_only": True,
            "running": setting("running") == "1",
            "worker_recently_active": worker_alive if _last_cycle_ts else None,
        }
    )


# ============================================================
# ROUTES — API ÉTAT
# ============================================================

@app.get("/api/state")
def state():
    limit_events = min(int(request.args.get("events_limit", 15)), 200)
    limit_experiments = min(int(request.args.get("experiments_limit", 12)), 200)
    limit_opportunities = min(int(request.args.get("opportunities_limit", 12)), 200)

    with get_db() as c:
        events = [dict(x) for x in c.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit_events,)
        )]
        strategies = [dict(x) for x in c.execute(
            """
            SELECT *, CASE WHEN tests = 0 THEN 0 ELSE CAST(wins AS REAL) / tests END AS win_rate
            FROM strategies ORDER BY confidence DESC
            """
        )]
        experiments = [dict(x) for x in c.execute(
            "SELECT * FROM experiments ORDER BY id DESC LIMIT ?", (limit_experiments,)
        )]
        opportunities = [dict(x) for x in c.execute(
            "SELECT * FROM opportunities ORDER BY score DESC, id DESC LIMIT ?", (limit_opportunities,)
        )]
        knowledge = [dict(x) for x in c.execute(
            "SELECT * FROM knowledge ORDER BY id DESC LIMIT 10"
        )]
        improvements = [dict(x) for x in c.execute(
            "SELECT * FROM improvements ORDER BY id DESC LIMIT 8"
        )]
        gates = [dict(x) for x in c.execute(
            "SELECT * FROM gates ORDER BY id DESC LIMIT 10"
        )]
        curiosity = [dict(x) for x in c.execute(
            "SELECT * FROM curiosity_questions WHERE status='open' ORDER BY priority DESC, id DESC LIMIT 8"
        )]
        affiliate_strategies = [dict(x) for x in c.execute(
            """
            SELECT *, CASE WHEN tests = 0 THEN 0 ELSE CAST(wins AS REAL) / tests END AS win_rate
            FROM affiliate_strategies ORDER BY confidence DESC
            """
        )]
        affiliate_experiments = [dict(x) for x in c.execute(
            "SELECT * FROM affiliate_experiments ORDER BY id DESC LIMIT 12"
        )]
        metrics_row = c.execute("SELECT * FROM metrics ORDER BY id DESC LIMIT 1").fetchone()
        metrics = dict(metrics_row) if metrics_row else {}

    return jsonify(
        {
            "running": setting("running") == "1",
            "simulation_only": True,
            "max_auto_purchase": float(setting("max_auto_purchase")),
            "risk_fraction": float(setting("risk_fraction")),
            "learning_mode": setting("learning_mode"),
            "modules": [{"name": n, "desc": d, "status": s} for n, d, s in MODULES],
            "events": events,
            "strategies": strategies,
            "experiments": experiments,
            "opportunities": opportunities,
            "knowledge": knowledge,
            "improvements": improvements,
            "gates": gates,
            "curiosity": curiosity,
            "affiliate_strategies": affiliate_strategies,
            "affiliate_experiments": affiliate_experiments,
            "metrics": metrics,
        }
    )


@app.post("/api/toggle")
def toggle():
    current = setting("running")
    value = "0" if current == "1" else "1"
    set_setting("running", value)
    log_event("CEO / Orchestrateur", "system", "loop started" if value == "1" else "loop stopped")
    return jsonify({"ok": True, "running": value == "1"})


@app.post("/api/run")
def run_once():
    cycle()
    return jsonify({"ok": True})


@app.post("/api/improvement")
def improvement():
    propose_improvement()
    return jsonify({"ok": True})


@app.post("/api/gate")
def gate():
    run_verification()
    return jsonify({"ok": True})


@app.get("/api/settings")
def get_settings():
    return jsonify(
        {
            "running": setting("running") == "1",
            "risk_fraction": float(setting("risk_fraction")),
            "cycle_seconds": int(setting("cycle_seconds")),
            "learning_mode": setting("learning_mode"),
            "max_auto_purchase": float(setting("max_auto_purchase")),
            "simulation_only": setting("simulation_only") == "1",
        }
    )


@app.post("/api/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    updated = {}

    if "risk_fraction" in data:
        try:
            v = clamp(float(data["risk_fraction"]), 0.01, 0.50)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "risk_fraction invalide"}), 400
        set_setting("risk_fraction", str(v))
        updated["risk_fraction"] = v

    if "cycle_seconds" in data:
        try:
            v = max(5, min(3600, int(data["cycle_seconds"])))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "cycle_seconds invalide"}), 400
        set_setting("cycle_seconds", str(v))
        updated["cycle_seconds"] = v

    if "learning_mode" in data:
        v = str(data["learning_mode"])
        if v not in LEARNING_MODES:
            return jsonify({"ok": False, "error": f"learning_mode doit être parmi {sorted(LEARNING_MODES)}"}), 400
        set_setting("learning_mode", v)
        updated["learning_mode"] = v

    # simulation_only et max_auto_purchase restent volontairement verrouillés :
    # ce sont les garde-fous de sécurité du système (voir run_verification()).

    if not updated:
        return jsonify({"ok": False, "error": "Aucun paramètre valide fourni"}), 400

    log_event("CEO / Orchestrateur", "system", f"Paramètres mis à jour : {updated}")
    return jsonify({"ok": True, "updated": updated})


@app.post("/api/reset-simulation")
def reset_simulation():
    if request.args.get("confirm") != "yes":
        return jsonify({"ok": False, "error": "Confirmation requise : POST /api/reset-simulation?confirm=yes"}), 400

    with get_db(write=True) as c:
        for table in [
            "events", "experiments", "opportunities", "knowledge",
            "improvements", "gates", "curiosity_questions", "strategy_category_stats",
            "affiliate_experiments", "affiliate_niche_stats",
        ]:
            c.execute(f"DELETE FROM {table}")

     
def _real_affiliate_migrate():
    with get_db(write=True) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS real_affiliate_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                ts_epoch REAL,
                total_clicks INTEGER,
                by_product TEXT,
                by_source TEXT,
                data_status TEXT DEFAULT 'OBSERVED'
            )
        """)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(real_affiliate_data)").fetchall()]
        if "by_source" not in cols:
            c.execute("ALTER TABLE real_affiliate_data ADD COLUMN by_source TEXT")


def sync_real_affiliate_data():
    import requests, json
    site_url = os.environ.get("NOVAREL_SITE_URL", "https://novarel-site.onrender.com")
    try:
        resp = requests.get(site_url + "/api/clicks", timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": str(e)}

    total = data.get("total", 0)
    by_product = data.get("by_product", [])
    by_source = data.get("by_source", [])

    try:
        with get_db(write=True) as c:
            c.execute(
                "INSERT INTO real_affiliate_data (ts, ts_epoch, total_clicks, by_product, by_source, data_status) "
                "VALUES (?, ?, ?, ?, ?, 'OBSERVED')",
                (datetime.utcnow().isoformat(), time.time(), total, json.dumps(by_product), json.dumps(by_source)),
            )
    except Exception as e:
        return {"error": f"db_write_failed: {e}"}

    return {"total_clicks": total, "by_product": by_product, "by_source": by_source}


def _real_affiliate_worker():
    _real_affiliate_migrate()
    # Décalage aléatoire au démarrage pour ne jamais tomber pile en même temps
    # que le cycle principal (qui tourne toutes les 15s).
    import random as _rnd
    time.sleep(5 + _rnd.random() * 10)
    while True:
        try:
            sync_real_affiliate_data()
        except Exception:
            pass
        time.sleep(180)


threading.Thread(target=_real_affiliate_worker, daemon=True, name="real-affiliate-sync").start()


@app.route("/api/affiliate/real-data")
def api_affiliate_real_data():
    import json
    with get_db() as c:
        row = c.execute("SELECT * FROM real_affiliate_data ORDER BY id DESC LIMIT 1").fetchone()
        history = c.execute(
            "SELECT ts, total_clicks FROM real_affiliate_data ORDER BY id DESC LIMIT 20"
        ).fetchall()
    if not row:
        return jsonify({"status": "no_data_yet"})
    return jsonify({
        "status": "ok",
        "data_status": "OBSERVED",
        "last_sync": row["ts"],
        "total_clicks": row["total_clicks"],
        "by_product": json.loads(row["by_product"] or "[]"),
        "by_source": json.loads(row["by_source"] or "[]"),
        "history": [{"ts": h["ts"], "total_clicks": h["total_clicks"]} for h in history],
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5200")), debug=False)
        )

        c.execute("DELETE FROM metrics")
        c.execute(
            "INSERT INTO metrics(ts,sim_revenue,sim_profit,sim_invested,experiments,opportunities,"
            "win_rate,prediction_error,nosi,confidence) VALUES(?,0,0,0,0,0,0,0,1,0.50)",
            (now_iso(),),
        )
        c.execute(
            "INSERT INTO knowledge(ts,ts_epoch,topic,insight,confidence,source_type,corroboration) "
            "VALUES(?,?,?,?,?,?,?)",
            (now_iso(), time.time(), "system", "Simulation réinitialisée.", 0.99, "system", 1),
        )

    return jsonify({"ok": True})


# ============================================================
# CURIOSITÉ — API
# ============================================================

@app.get("/api/curiosity")
def curiosity_list():
    status = request.args.get("status", "open")
    with get_db() as c:
        rows = [dict(x) for x in c.execute(
            "SELECT * FROM curiosity_questions WHERE status=? ORDER BY priority DESC, id DESC LIMIT 50",
            (status,),
        )]
    return jsonify({"ok": True, "questions": rows})


@app.post("/api/curiosity/<int:qid>/resolve")
def curiosity_resolve(qid):
    data = request.get_json(silent=True) or {}
    answer = str(data.get("answer", "")).strip()

    with get_db(write=True) as c:
        q = c.execute("SELECT * FROM curiosity_questions WHERE id=?", (qid,)).fetchone()
        if not q:
            return jsonify({"ok": False, "error": "Question introuvable"}), 404

        c.execute("UPDATE curiosity_questions SET status='resolved' WHERE id=?", (qid,))

        knowledge_id = None
        if answer:
            cur = c.execute(
                "INSERT INTO knowledge(ts,ts_epoch,topic,insight,confidence,source_type,corroboration) "
                "VALUES(?,?,?,?,?,?,?)",
                (now_iso(), time.time(), q["topic"], answer, 0.60, "human", 0),
            )
            knowledge_id = cur.lastrowid

    log_event("Curiosity", "resolve", f"Question #{qid} résolue")
    return jsonify({"ok": True, "knowledge_id": knowledge_id})


# ============================================================
# EXPORT CSV
# ============================================================

@app.get("/api/export/<table>")
def export_table(table):
    if table not in EXPORTABLE_TABLES:
        return jsonify({"ok": False, "error": "Table inconnue", "tables_disponibles": sorted(EXPORTABLE_TABLES)}), 404

    with get_db() as c:
        rows = c.execute(EXPORTABLE_TABLES[table]).fetchall()

    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}.csv"},
    )


# ============================================================
# CENTRE D'ANALYSE
# ============================================================
# NB : dans l'original, deux implémentations concurrentes coexistaient
# (un template Jinja côté serveur ET un gros template JS jamais utilisé).
# Il n'en reste plus qu'une seule : rendu côté client, qui s'actualise
# automatiquement en interrogeant /api/analysis-center.

def _analysis_period(c, days: int | None = None):
    """Statistiques agrégées sur une fenêtre glissante de `days` jours
    (ou sur tout l'historique si `days` est None).

    Le filtrage se fait sur `ts_epoch` (temps Unix calculé côté Python),
    ce qui évite le bug de l'original : comparer un timestamp local au
    format ISO ("...T...") à `datetime('now', ...)` de SQLite, qui
    raisonne en UTC et attend un espace au lieu du "T".
    """
    if days is None:
        where, params = "", ()
    else:
        cutoff = time.time() - days * 86400
        where, params = "WHERE ts_epoch >= ?", (cutoff,)

    exp = c.execute(
        f"""
        SELECT COUNT(*) n,
               SUM(CASE WHEN outcome='WIN' THEN 1 ELSE 0 END) wins,
               SUM(CASE WHEN outcome='LOSS' THEN 1 ELSE 0 END) losses,
               AVG(prediction_error) err, AVG(confidence) conf,
               AVG(actual_profit) profit, AVG(expected_profit) expected
        FROM experiments {where}
        """,
        params,
    ).fetchone()
    opp = c.execute(f"SELECT COUNT(*) n FROM opportunities {where}", params).fetchone()
    events = c.execute(f"SELECT COUNT(*) n FROM events {where}", params).fetchone()

    n = exp["n"] or 0
    wins = exp["wins"] or 0
    win_rate = (wins / n) if n else 0.0
    err = exp["err"] if exp["err"] is not None else 0.0
    conf = exp["conf"] if exp["conf"] is not None else 0.50
    performance = 0.0 if not n else clamp((win_rate * 50) + ((1 - err) * 30) + (conf * 20), 0, 100)

    return {
        "experiments": n, "opportunities": opp["n"], "events": events["n"],
        "win_rate": win_rate, "prediction_error": err, "confidence": conf,
        "profit": exp["profit"] or 0.0, "expected": exp["expected"] or 0.0,
        "performance": performance,
    }


def analysis_center_data():
    with get_db() as c:
        totals = _analysis_period(c)
        period_data = []
        for label, days in [("COURT TERME", 3), ("MOYEN TERME", 30), ("LONG TERME", None)]:
            p = _analysis_period(c, days)
            p["label"] = label
            period_data.append(p)

        latest = c.execute("SELECT module,action,result,ts FROM events ORDER BY id DESC LIMIT 1").fetchone()
        current = {"activity": "En attente", "detail": "Aucune activité enregistrée"}
        if latest:
            current = {"activity": latest["action"], "detail": f"{latest['module']} · {latest['result'] or ''}"}

        strategies = [dict(x) for x in c.execute(
            """
            SELECT *, CASE WHEN tests=0 THEN 0 ELSE CAST(wins AS REAL)/tests END win_rate
            FROM strategies ORDER BY confidence DESC, tests DESC LIMIT 12
            """
        )]
        best = [
            {"name": x["name"], "score": round((x["confidence"] * 70) + (x["win_rate"] * 30), 1)}
            for x in strategies if x["tests"] > 0
        ][:8]

        recent_events = [dict(x) for x in c.execute(
            "SELECT ts,module,action,result,score,strategy FROM events ORDER BY id DESC LIMIT 20"
        )]

        learning = [dict(x) for x in c.execute(
            "SELECT topic,insight,confidence,ts FROM knowledge ORDER BY id DESC LIMIT 10"
        )]
        learning += [dict(x) for x in c.execute(
            "SELECT strategy,lesson,confidence,ts FROM experiments "
            "WHERE lesson IS NOT NULL AND lesson!='' ORDER BY id DESC LIMIT 10"
        )]

        history = [dict(x) for x in c.execute(
            "SELECT ts,strategy,category,hypothesis,probability,outcome,actual_profit,prediction_error,lesson "
            "FROM experiments ORDER BY id DESC LIMIT 30"
        )]

        categories = [dict(x) for x in c.execute(
            "SELECT category, COUNT(*) count FROM experiments GROUP BY category ORDER BY count DESC LIMIT 12"
        )]

        category_best = [dict(x) for x in c.execute(
            """
            SELECT scs.category, s.name AS strategy, scs.tests,
                   CASE WHEN scs.tests=0 THEN 0 ELSE CAST(scs.wins AS REAL)/scs.tests END win_rate
            FROM strategy_category_stats scs
            JOIN strategies s ON s.code = scs.strategy_code
            WHERE scs.tests >= 3
            ORDER BY win_rate DESC LIMIT 12
            """
        )]

        curiosity_open = [dict(x) for x in c.execute(
            "SELECT id,topic,question,priority FROM curiosity_questions WHERE status='open' "
            "ORDER BY priority DESC LIMIT 10"
        )]

        recent_opportunities = [dict(x) for x in c.execute(
            "SELECT ts, category, score, confidence, expected_profit, recommendation, "
            "recommended_action, data_status FROM opportunities ORDER BY id DESC LIMIT 15"
        )]

        affiliate_strategies = [dict(x) for x in c.execute(
            """
            SELECT *, CASE WHEN tests=0 THEN 0 ELSE CAST(wins AS REAL)/tests END win_rate
            FROM affiliate_strategies ORDER BY confidence DESC, tests DESC LIMIT 12
            """
        )]
        affiliate_best_niche = [dict(x) for x in c.execute(
            """
            SELECT ans.niche, s.name AS strategy, ans.tests,
                   CASE WHEN ans.tests=0 THEN 0 ELSE CAST(ans.wins AS REAL)/ans.tests END win_rate
            FROM affiliate_niche_stats ans
            JOIN affiliate_strategies s ON s.code = ans.strategy_code
            WHERE ans.tests >= 3
            ORDER BY win_rate DESC LIMIT 12
            """
        )]
        affiliate_history = [dict(x) for x in c.execute(
            "SELECT ts, strategy, niche, clicks, conversions, revenue, cost, profit, outcome, lesson "
            "FROM affiliate_experiments ORDER BY id DESC LIMIT 15"
        )]
        affiliate_totals = c.execute(
            "SELECT COUNT(*) n, SUM(revenue) revenue, SUM(cost) cost, SUM(profit) profit, "
            "SUM(conversions) conversions FROM affiliate_experiments"
        ).fetchone()

    long_term = [
        {"label": "Expériences totales", "value": str(totals["experiments"])},
        {"label": "Opportunités totales", "value": str(totals["opportunities"])},
        {"label": "Événements totaux", "value": str(totals["events"])},
        {"label": "Profit simulé moyen / expérience", "value": f"{totals['profit']:.2f} €"},
        {"label": "Profit attendu moyen / expérience", "value": f"{totals['expected']:.2f} €"},
        {"label": "Performance interne", "value": f"{totals['performance']:.1f}/100"},
    ]
    quality = [
        {"label": "Mode", "value": "SIMULATION UNIQUEMENT", "kind": "warn"},
        {"label": "Données marché réelles", "value": "Non garanties par ce centre"},
        {"label": "Mesure de progression", "value": "Comparaison des expériences internes"},
        {"label": "Achats automatiques réels", "value": "NON"},
    ]

    return {
        "running": setting("running") == "1",
        "current": current,
        "totals": totals,
        "periods": period_data,
        "best": best,
        "recent_events": recent_events,
        "learning": learning[:15],
        "strategies": strategies,
        "categories": categories,
        "category_best": category_best,
        "curiosity_open": curiosity_open,
        "recent_opportunities": recent_opportunities,
        "history": history,
        "affiliate_strategies": affiliate_strategies,
        "affiliate_best_niche": affiliate_best_niche,
        "affiliate_history": affiliate_history,
        "affiliate_totals": {
            "n": affiliate_totals["n"] or 0,
            "revenue": affiliate_totals["revenue"] or 0.0,
            "cost": affiliate_totals["cost"] or 0.0,
            "profit": affiliate_totals["profit"] or 0.0,
            "conversions": affiliate_totals["conversions"] or 0,
        },
        "long_term": long_term,
        "quality": quality,
    }


ANALYSIS_CENTER_HTML = r"""
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NOVAREL — Centre d'analyse</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#07101b;color:#eaf2f8;font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1500px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:15px;align-items:center;margin-bottom:16px}
h1{margin:0;font-size:28px}.muted,.small{color:#8fa3b7}.small{font-size:12px}
a{color:#9fc4ff;text-decoration:none}.btn{border:1px solid #29405a;background:#102238;color:#eaf2f8;border-radius:9px;padding:8px 12px;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.grid2{display:grid;grid-template-columns:1.35fr 1fr;gap:12px;margin-top:12px}
.panel{background:#0d1927;border:1px solid #203247;border-radius:14px;padding:15px}.big{font-size:26px;font-weight:800;margin:5px 0}
.periods{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.period{background:#111f30;border:1px solid #203247;border-radius:11px;padding:12px}
.row{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid #203247}.row:last-child{border:0}
.list{max-height:330px;overflow:auto}.event{padding:9px 11px;margin-bottom:7px;background:#111f30;border-radius:9px;border-left:3px solid #72a8ff}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #203247;font-size:12px}th{color:#8fa3b7}
.good{color:#55d69a}.warn{color:#f5c76b}.bad{color:#ff7f86}
.bar{height:8px;background:#17283c;border-radius:8px;overflow:hidden;margin-top:5px}.bar i{display:block;height:100%;background:#72a8ff}
button.tiny{font-size:11px;padding:4px 8px;border-radius:6px;border:1px solid #29405a;background:#0d1927;color:#eaf2f8;cursor:pointer}
input.tiny{width:100%;background:#0d1927;border:1px solid #29405a;border-radius:6px;color:#eaf2f8;padding:5px;font-size:12px;margin-top:4px}
@media(max-width:1000px){.grid{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
@media(max-width:600px){main{padding:12px}.grid{grid-template-columns:1fr}.periods{grid-template-columns:1fr}.top{align-items:flex-start;flex-direction:column}}
</style>
</head>
<body><main>
<div class="top">
<div><h1>NOVAREL — Centre d'analyse</h1><div class="muted">Vue complète du fonctionnement, du travail, des performances et de l'évolution.</div><div><a href="/">← Retour à NOVAREL</a></div></div>
<div><span id="status" class="small">Chargement…</span> <button class="btn" onclick="load()">Actualiser</button> <a class="btn" href="/api/export/experiments">Export CSV</a></div>
</div>

<div class="grid">
<div class="panel"><div class="small">État</div><div id="state" class="big">—</div><div id="activity" class="muted">—</div></div>
<div class="panel"><div class="small">Cycles</div><div id="cycles" class="big">—</div><div class="muted">activité enregistrée</div></div>
<div class="panel"><div class="small">Expériences</div><div id="experiments" class="big">—</div><div id="win" class="muted">—</div></div>
<div class="panel"><div class="small">Confiance</div><div id="confidence" class="big">—</div><div id="error" class="muted">—</div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Performance — court / moyen / long terme</h2><div id="periods" class="periods"></div></div>
<div class="panel"><h2>Ce qui fonctionne le mieux</h2><div id="best"></div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Sur quoi NOVAREL travaille</h2><div id="work" class="list"></div></div>
<div class="panel"><h2>Ce qu'elle apprend</h2><div id="learn" class="list"></div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Stratégies</h2><div id="strategies" class="list"></div></div>
<div class="panel"><h2>Meilleure stratégie par catégorie</h2><div id="category_best" class="list"></div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Catégories explorées</h2><div id="categories" class="list"></div></div>
<div class="panel"><h2>Questions ouvertes (curiosité)</h2><div id="curiosity" class="list"></div></div>
</div>

<div class="panel" style="margin-top:12px"><h2>Opportunités récentes — MODEL_SCORE (jamais une probabilité garantie)</h2><div id="opportunities" class="list"></div></div>

<div class="grid" style="margin-top:12px">
<div class="panel"><div class="small">Affiliation — expériences</div><div id="aff_n" class="big">—</div><div class="muted">simulées</div></div>
<div class="panel"><div class="small">Revenu simulé</div><div id="aff_revenue" class="big">—</div><div class="muted">brut, avant coûts</div></div>
<div class="panel"><div class="small">Coût simulé</div><div id="aff_cost" class="big">—</div><div class="muted">production / achat trafic</div></div>
<div class="panel"><div class="small">Profit simulé</div><div id="aff_profit" class="big">—</div><div id="aff_conversions" class="muted">—</div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Stratégies d'affiliation</h2><div id="aff_strategies" class="list"></div></div>
<div class="panel"><h2>Meilleure stratégie par niche</h2><div id="aff_best_niche" class="list"></div></div>
</div>

<div class="panel" style="margin-top:12px"><h2>Affiliation — historique récent</h2>
<div style="overflow:auto"><table><thead><tr><th>Date</th><th>Stratégie</th><th>Niche</th><th>Clics</th><th>Conversions</th><th>Résultat</th><th>Leçon</th></tr></thead><tbody id="aff_history"></tbody></table></div></div>

<div class="panel" style="margin-top:12px"><h2>Historique : prédiction → résultat → erreur → leçon</h2>
<div style="overflow:auto"><table><thead><tr><th>Date</th><th>Stratégie</th><th>Catégorie</th><th>Prédiction</th><th>Résultat</th><th>Erreur</th><th>Leçon</th></tr></thead><tbody id="history"></tbody></table></div></div>

<div class="grid2">
<div class="panel"><h2>Indicateurs long terme</h2><div id="long"></div></div>
<div class="panel"><h2>Fiabilité / nature des données</h2><div id="quality"></div></div>
</div>

<div class="small" style="margin-top:12px">Les performances actuelles sont des indicateurs internes de simulation. Elles ne représentent pas des ventes ou bénéfices réels.</div>
</main>

<script>
window.__NOVAREL_ANALYSIS_DATA__ = null;
const $=id=>document.getElementById(id);
const pct=x=>x==null?"—":(Number(x)*100).toFixed(0)+"%";
const num=x=>x==null?"—":Number(x).toFixed(2);
const esc=s=>String(s??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[m]));
function periodCard(p){
 return `<div class="period"><div class="small">${esc(p.label)}</div><div class="big">${num(p.performance)}/100</div>
 <div class="row"><span>Win rate</span><b>${pct(p.win_rate)}</b></div>
 <div class="row"><span>Erreur prédiction</span><b>${pct(p.prediction_error)}</b></div>
 <div class="row"><span>Expériences</span><b>${p.experiments}</b></div>
 <div class="row"><span>Opportunités</span><b>${p.opportunities}</b></div></div>`;
}
async function resolveCuriosity(id){
 const input=$("answer_"+id);
 const answer=input?input.value:"";
 try{
  await fetch(`/api/curiosity/${id}/resolve`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({answer})});
  load();
 }catch(e){console.error(e);}
}
function renderData(d){
 try{
  if(!d || !d.totals || !d.periods) throw new Error("Réponse du centre d'analyse incomplète.");
  $("status").textContent=d.running?"🟢 ACTIVE":"⚪ PAUSE";
  $("state").textContent=d.running?"ACTIVE":"PAUSE";
  $("activity").textContent=d.current.activity+" — "+d.current.detail;
  $("cycles").textContent=d.totals.events;
  $("experiments").textContent=d.totals.experiments;
  $("win").textContent="Taux de réussite : "+pct(d.totals.win_rate);
  $("confidence").textContent=pct(d.totals.confidence);
  $("error").textContent="Erreur moyenne : "+pct(d.totals.prediction_error);
  $("periods").innerHTML=d.periods.map(periodCard).join("");
  $("best").innerHTML=d.best.length?d.best.map(x=>`<div class="row"><span>${esc(x.name)}</span><b>${num(x.score)}/100</b></div><div class="bar"><i style="width:${Math.max(0,Math.min(100,x.score))}%"></i></div>`).join(""):"<div class=\"muted\">Pas encore assez de données.</div>";
  $("work").innerHTML=d.recent_events.length?d.recent_events.map(x=>`<div class="event"><b>${esc(x.action)}</b><div>${esc(x.result||"")}</div><div class="small">${esc(x.module)} · ${esc(x.ts)}</div></div>`).join(""):"<div class=\"muted\">Aucune activité.</div>";
  $("learn").innerHTML=d.learning.length?d.learning.map(x=>`<div class="row"><span><b>${esc(x.topic||x.strategy||"Apprentissage")}</b><br><span class="small">${esc(x.insight||x.lesson||"")}</span></span><b>${x.confidence==null?"":pct(x.confidence)}</b></div>`).join(""):"<div class=\"muted\">Aucun apprentissage.</div>";
  $("strategies").innerHTML=d.strategies.length?d.strategies.map(x=>`<div class="row"><span><b>${esc(x.name)}</b><br><span class="small">${x.tests} tests · ${x.wins} succès · ${x.losses} échecs · poids ${num(x.weight)}</span></span><b>${pct(x.confidence)}</b></div>`).join(""):"<div class=\"muted\">Aucune stratégie.</div>";
  $("category_best").innerHTML=d.category_best.length?d.category_best.map(x=>`<div class="row"><span>${esc(x.category)}<br><span class="small">${esc(x.strategy)} · ${x.tests} tests</span></span><b>${pct(x.win_rate)}</b></div>`).join(""):"<div class=\"muted\">Pas encore assez de données par catégorie.</div>";
  $("categories").innerHTML=d.categories.length?d.categories.map(x=>`<div class="row"><span>${esc(x.category||"Non classé")}</span><b>${x.count}</b></div>`).join(""):"<div class=\"muted\">Aucune catégorie.</div>";
  const actionColor={STOP:"bad",DO_NOT_EXECUTE:"bad",VERIFY:"warn",RESEARCH_MORE:"warn",TEST:"",OPTIMIZE:"good",SCALE:"good",WAIT:""};
  $("opportunities").innerHTML=d.recent_opportunities.length?d.recent_opportunities.map(x=>`<div class="row"><span>${esc(x.category)} · <span class="small">${esc(x.ts)}</span><br><span class="small">${esc(x.recommendation)} · statut donnée : ${esc(x.data_status)}</span></span><span style="text-align:right"><b class="${actionColor[x.recommended_action]||''}">${esc(x.recommended_action)}</b><br><span class="small">MODEL_SCORE ${pct(x.score)} · profit attendu (simulé) ${num(x.expected_profit)} €</span></span></div>`).join(""):"<div class=\"muted\">Aucune opportunité pour l'instant.</div>";
  $("curiosity").innerHTML=d.curiosity_open.length?d.curiosity_open.map(x=>`<div class="event"><b>${esc(x.question)}</b><div class="small">${esc(x.topic)} · priorité ${pct(x.priority)}</div><input class="tiny" id="answer_${x.id}" placeholder="Répondre (optionnel)…"><button class="tiny" style="margin-top:5px" onclick="resolveCuriosity(${x.id})">Marquer résolue</button></div>`).join(""):"<div class=\"muted\">Aucune question ouverte.</div>";
  $("history").innerHTML=d.history.length?d.history.map(x=>`<tr><td>${esc(x.ts)}</td><td>${esc(x.strategy)}</td><td>${esc(x.category)}</td><td>${pct(x.probability)}</td><td>${esc(x.outcome)} · ${num(x.actual_profit)} €</td><td>${pct(x.prediction_error)}</td><td>${esc(x.lesson)}</td></tr>`).join(""):"<tr><td colspan=\"7\" class=\"muted\">Pas encore d'expériences.</td></tr>";

  const at=d.affiliate_totals;
  $("aff_n").textContent=at.n;
  $("aff_revenue").textContent=num(at.revenue)+" €";
  $("aff_cost").textContent=num(at.cost)+" €";
  $("aff_profit").textContent=num(at.profit)+" €";
  $("aff_conversions").textContent=at.conversions+" conversions simulées";
  $("aff_strategies").innerHTML=d.affiliate_strategies.length?d.affiliate_strategies.map(x=>`<div class="row"><span><b>${esc(x.name)}</b><br><span class="small">${x.tests} tests · ${x.wins} succès · ${x.losses} échecs · poids ${num(x.weight)}</span></span><b>${pct(x.confidence)}</b></div>`).join(""):"<div class=\"muted\">Aucune stratégie testée.</div>";
  $("aff_best_niche").innerHTML=d.affiliate_best_niche.length?d.affiliate_best_niche.map(x=>`<div class="row"><span>${esc(x.niche)}<br><span class="small">${esc(x.strategy)} · ${x.tests} tests</span></span><b>${pct(x.win_rate)}</b></div>`).join(""):"<div class=\"muted\">Pas encore assez de données par niche.</div>";
  $("aff_history").innerHTML=d.affiliate_history.length?d.affiliate_history.map(x=>`<tr><td>${esc(x.ts)}</td><td>${esc(x.strategy)}</td><td>${esc(x.niche)}</td><td>${x.clicks}</td><td>${x.conversions}</td><td>${esc(x.outcome)} · ${num(x.profit)} €</td><td>${esc(x.lesson)}</td></tr>`).join(""):"<tr><td colspan=\"7\" class=\"muted\">Pas encore d'expériences d'affiliation.</td></tr>";

  $("long").innerHTML=d.long_term.map(x=>`<div class="row"><span>${esc(x.label)}</span><b>${esc(x.value)}</b></div>`).join("");
  $("quality").innerHTML=d.quality.map(x=>`<div class="row"><span>${esc(x.label)}</span><b class="${esc(x.kind||"")}">${esc(x.value)}</b></div>`).join("");
 }catch(e){
  $("status").textContent="🔴 ERREUR";
  $("activity").textContent="Le centre n'a pas pu afficher ses données : "+(e.message||e);
  console.error(e);
 }
}
async function load(){
 try{
  const r=await fetch("/api/analysis-center",{cache:"no-store"});
  if(!r.ok) throw new Error("HTTP "+r.status);
  const d=await r.json();
  window.__NOVAREL_ANALYSIS_DATA__=d;
  renderData(d);
 }catch(e){
  if(window.__NOVAREL_ANALYSIS_DATA__) renderData(window.__NOVAREL_ANALYSIS_DATA__);
  else {
   $("status").textContent="🔴 ERREUR";
   $("activity").textContent="Le centre n'a pas pu charger ses données : "+(e.message||e);
  }
  console.error(e);
 }
}
load();setInterval(load,15000);
</script>
</body></html>
"""


@app.get("/analysis")
def analysis_page():
    return ANALYSIS_CENTER_HTML


@app.get("/api/analysis-center")
def analysis_center_api():
    try:
        return jsonify(analysis_center_data())
    except Exception as e:
        logger.exception("Erreur du Centre d'analyse")
        return jsonify({"ok": False, "error": "analysis_center_error", "detail": str(e)}), 500


# ============================================================
# GESTION D'ERREURS GLOBALE
# ============================================================

@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return e
    logger.exception("Erreur non gérée")
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "internal_error", "detail": str(e)}), 500
    return (
        f"<h1>NOVAREL</h1><p>Une erreur est survenue : {e}</p><p><a href='/'>Retour</a></p>",
        500,
    )


# ============================================================
# DÉMARRAGE
# ============================================================

init()
start_worker()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)

def _real_affiliate_migrate():
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS real_affiliate_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            ts_epoch REAL,
            total_clicks INTEGER,
            by_product TEXT,
            data_status TEXT DEFAULT 'OBSERVED'
        )
    """)
    conn.commit()
    conn.close()

def sync_real_affiliate_data():
    import requests, json
    site_url = os.environ.get("NOVAREL_SITE_URL", "https://novarel-site.onrender.com")
    try:
        resp = requests.get(site_url + "/api/clicks", timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": str(e)}
    total = data.get("total", 0)
    by_product = data.get("by_product", {})
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute(
        "INSERT INTO real_affiliate_data (ts, ts_epoch, total_clicks, by_product, data_status) VALUES (?, ?, ?, ?, 'OBSERVED')",
        (datetime.utcnow().isoformat(), time.time(), total, json.dumps(by_product)),
    )
    conn.commit()
    conn.close()
    return {"total_clicks": total, "by_product": by_product}

def _real_affiliate_worker():
    _real_affiliate_migrate()
    while True:
        try:
            sync_real_affiliate_data()
        except Exception:
            pass
        time.sleep(120)

threading.Thread(target=_real_affiliate_worker, daemon=True, name="real-affiliate-sync").start()

@app.route("/api/affiliate/real-data")
def api_affiliate_real_data():
    import json
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM real_affiliate_data ORDER BY id DESC LIMIT 1").fetchone()
    history = conn.execute("SELECT ts, total_clicks FROM real_affiliate_data ORDER BY id DESC LIMIT 20").fetchall()
    conn.close()
    if not row:
        return jsonify({"status": "no_data_yet"})
    return jsonify({
        "status": "ok",
        "data_status": "OBSERVED",
        "last_sync": row["ts"],
        "total_clicks": row["total_clicks"],
        "by_product": json.loads(row["by_product"] or "{}"),
        "history": [{"ts": h["ts"], "total_clicks": h["total_clicks"]} for h in history],
    })

def sync_real_affiliate_by_source():
    import requests, json
    site_url = os.environ.get("NOVAREL_SITE_URL", "https://novarel-site.onrender.com")
    try:
        resp = requests.get(site_url + "/api/clicks", timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": str(e)}
    by_source = data.get("by_source", [])
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS real_affiliate_by_source (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            ts_epoch REAL,
            by_source TEXT,
            data_status TEXT DEFAULT 'OBSERVED'
        )
    """)
    conn.execute(
        "INSERT INTO real_affiliate_by_source (ts, ts_epoch, by_source, data_status) VALUES (?, ?, ?, 'OBSERVED')",
        (datetime.utcnow().isoformat(), time.time(), json.dumps(by_source)),
    )
    conn.commit()
    conn.close()
    return {"by_source": by_source}

def _real_affiliate_source_worker():
    while True:
        try:
            sync_real_affiliate_by_source()
        except Exception:
            pass
        time.sleep(120)

threading.Thread(target=_real_affiliate_source_worker, daemon=True, name="real-affiliate-source-sync").start()

@app.route("/api/affiliate/real-data-by-source")
def api_affiliate_real_data_by_source():
    import json
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM real_affiliate_by_source ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return jsonify({"status": "no_data_yet"})
    return jsonify({
        "status": "ok",
        "data_status": "OBSERVED",
        "last_sync": row["ts"],
        "by_source": json.loads(row["by_source"] or "[]"),
    })
