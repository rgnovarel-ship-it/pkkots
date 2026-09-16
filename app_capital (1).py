"""
NOVAREL CAPITAL — le Finance Brain de NOVAREL, enfin implémenté.

NOVAREL liste un module "Finance Brain" ("Suit CA, marge, cash et risque")
dans son tableau MODULES, mais aucune ligne de code ne l'implémente : chaque
expérience est évaluée isolément, jamais en portefeuille. NOVAREL CAPITAL
comble ce vide en tant qu'application séparée et complémentaire :

  1. Elle se synchronise avec l'API de NOVAREL (lecture seule au départ) et
     transforme le flux d'expériences individuelles en une véritable courbe
     de capital cumulé.
  2. Elle calcule des métriques de portefeuille que NOVAREL ne calcule pas :
     drawdown courant / maximal, exposition et rentabilité par catégorie,
     taux de réussite pondéré par le capital engagé.
  3. Elle produit des "verdicts" — des recommandations de gestion du risque
     lisibles par un humain (ex. réduire risk_fraction en cas de drawdown).
  4. En option (désactivée par défaut, comme tous les garde-fous de
     NOVAREL), elle peut renvoyer ces recommandations à NOVAREL via son
     endpoint /api/settings — une vraie boucle de rétroaction entre les
     deux applications, toujours bornée par les limites de sécurité déjà
     imposées côté NOVAREL (risk_fraction cappé, simulation uniquement).

Aucun achat réel, aucune donnée financière réelle : c'est une couche
d'analyse de portefeuille au-dessus d'un moteur déjà 100% simulé.
"""

from __future__ import annotations

import contextlib
import csv
import io
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

# ============================================================
# CONFIGURATION
# ============================================================

BASE = Path(__file__).parent
DB = BASE / "novarel_capital.db"
APP_VERSION = "1.0.0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("novarel_capital")

app = Flask(__name__)

DEFAULT_SETTINGS = {
    "novarel_base_url": os.environ.get("NOVAREL_BASE_URL", "http://127.0.0.1:5000"),
    "starting_capital": "5000.0",
    "poll_seconds": "20",
    "auto_apply": "0",
    "running": "1",
    # Seuils de déclenchement des verdicts (en fraction de drawdown depuis le pic)
    "drawdown_warning": "0.12",
    "drawdown_critical": "0.25",
}

VERDICT_COOLDOWN_SECONDS = 300  # évite de spammer le même verdict en boucle


# ============================================================
# BASE DE DONNÉES
# ============================================================

_DB_WRITE_LOCK = threading.RLock()


def _connect() -> sqlite3.Connection:
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init():
    with get_db(write=True) as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings(
                k TEXT PRIMARY KEY, v TEXT
            );

            CREATE TABLE IF NOT EXISTS capital_state(
                id INTEGER PRIMARY KEY CHECK (id = 1),
                capital REAL,
                starting_capital REAL,
                peak_capital REAL,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS capital_ledger(
                id INTEGER PRIMARY KEY,
                ts TEXT,
                source_experiment_id INTEGER UNIQUE,
                category TEXT,
                strategy TEXT,
                outcome TEXT,
                profit REAL,
                prediction_error REAL,
                capital_after REAL
            );

            CREATE TABLE IF NOT EXISTS action_snapshot(
                id INTEGER PRIMARY KEY CHECK (id = 1),
                ts TEXT,
                counts_json TEXT,
                total INTEGER
            );

            CREATE TABLE IF NOT EXISTS verdicts(
                id INTEGER PRIMARY KEY,
                ts TEXT,
                severity TEXT,
                title TEXT,
                detail TEXT,
                metric_value REAL,
                suggested_risk_fraction REAL,
                applied INTEGER DEFAULT 0,
                apply_note TEXT
            );

            CREATE TABLE IF NOT EXISTS sync_log(
                id INTEGER PRIMARY KEY,
                ts TEXT,
                status TEXT,
                detail TEXT,
                new_experiments INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_ledger_ts ON capital_ledger(ts);
            CREATE INDEX IF NOT EXISTS idx_ledger_category ON capital_ledger(category);
            CREATE INDEX IF NOT EXISTS idx_verdicts_ts ON verdicts(ts);
            """
        )

        existing_ledger_cols = {
            row[1] for row in c.execute("PRAGMA table_info(capital_ledger)").fetchall()
        }
        if "prediction_error" not in existing_ledger_cols:
            c.execute("ALTER TABLE capital_ledger ADD COLUMN prediction_error REAL")

        for k, v in DEFAULT_SETTINGS.items():
            c.execute("INSERT OR IGNORE INTO settings(k,v) VALUES(?,?)", (k, v))

        if not c.execute("SELECT 1 FROM capital_state WHERE id=1").fetchone():
            starting = float(DEFAULT_SETTINGS["starting_capital"])
            c.execute(
                "INSERT INTO capital_state(id,capital,starting_capital,peak_capital,updated_at) "
                "VALUES(1,?,?,?,?)",
                (starting, starting, starting, now_iso()),
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
        c.execute(
            "INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (k, str(v)),
        )
    with _settings_lock:
        _settings_cache[k] = str(v)


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


# ============================================================
# SYNCHRONISATION AVEC NOVAREL
# ============================================================

def _normalize_experiment(raw: dict) -> dict | None:
    """Uniformise un enregistrement d'expérience, qu'il vienne du CSV
    d'export (valeurs texte) ou du JSON de /api/state (valeurs typées)."""
    try:
        prediction_error = raw.get("prediction_error")
        return {
            "id": int(raw["id"]),
            "ts": raw.get("ts") or now_iso(),
            "category": raw.get("category") or "inconnue",
            "strategy": raw.get("strategy") or "inconnue",
            "outcome": raw.get("outcome") or "NEUTRAL",
            "profit": float(raw.get("actual_profit") or 0.0),
            "prediction_error": float(prediction_error) if prediction_error not in (None, "") else None,
        }
    except (TypeError, ValueError, KeyError):
        return None


def fetch_experiments(base_url: str, timeout: float = 8.0) -> tuple[list[dict], str]:
    """Récupère les expériences NOVAREL. Essaie d'abord l'export CSV complet
    (toutes les expériences, disponible sur les versions de NOVAREL qui
    exposent /api/export), puis se replie sur /api/state (fenêtre limitée
    aux dernières expériences) si l'export est absent — pour rester
    compatible avec plusieurs versions de NOVAREL sans configuration
    supplémentaire.
    """
    url = base_url.rstrip("/")

    try:
        r = requests.get(f"{url}/api/export/experiments", timeout=timeout)
        if r.ok and r.headers.get("Content-Type", "").startswith("text/csv"):
            reader = csv.DictReader(io.StringIO(r.text))
            rows = [n for n in (_normalize_experiment(row) for row in reader) if n]
            return rows, "export_csv"
    except requests.RequestException:
        pass

    try:
        r = requests.get(f"{url}/api/state", timeout=timeout)
        r.raise_for_status()
        data = r.json()
        rows = [n for n in (_normalize_experiment(row) for row in data.get("experiments", [])) if n]
        return rows, "api_state"
    except requests.RequestException as e:
        raise ConnectionError(f"NOVAREL injoignable sur {url} : {e}") from e


def fetch_action_distribution(base_url: str, timeout: float = 8.0) -> dict | None:
    """Récupère les opportunités récentes de NOVAREL et compte la
    répartition des actions du Decision Engine (STOP, TEST, OPTIMIZE...).
    Absent silencieusement sur une version de NOVAREL antérieure au
    Decision Engine (pas de champ recommended_action) : renvoie None.
    """
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/state", timeout=timeout)
        r.raise_for_status()
        opportunities = r.json().get("opportunities", [])
    except requests.RequestException:
        return None

    counts: dict[str, int] = {}
    for o in opportunities:
        action = o.get("recommended_action")
        if action:
            counts[action] = counts.get(action, 0) + 1

    return counts or None


def sync_from_novarel() -> dict:
    base_url = setting("novarel_base_url")

    try:
        experiments, source = fetch_experiments(base_url)
    except ConnectionError as e:
        with get_db(write=True) as c:
            c.execute(
                "INSERT INTO sync_log(ts,status,detail,new_experiments) VALUES(?,?,?,0)",
                (now_iso(), "ERROR", str(e)),
            )
        return {"ok": False, "error": str(e)}

    action_counts = fetch_action_distribution(base_url)

    with get_db(write=True) as c:
        existing_ids = {
            row["source_experiment_id"]
            for row in c.execute("SELECT source_experiment_id FROM capital_ledger")
        }
        new_rows = sorted(
            (e for e in experiments if e["id"] not in existing_ids),
            key=lambda e: e["id"],
        )

        state = c.execute("SELECT * FROM capital_state WHERE id=1").fetchone()
        capital = state["capital"]
        peak = state["peak_capital"]

        for e in new_rows:
            capital += e["profit"]
            peak = max(peak, capital)
            c.execute(
                "INSERT INTO capital_ledger(ts,source_experiment_id,category,strategy,outcome,"
                "profit,prediction_error,capital_after) VALUES(?,?,?,?,?,?,?,?)",
                (e["ts"], e["id"], e["category"], e["strategy"], e["outcome"], e["profit"],
                 e["prediction_error"], capital),
            )

        if new_rows:
            c.execute(
                "UPDATE capital_state SET capital=?, peak_capital=?, updated_at=? WHERE id=1",
                (capital, peak, now_iso()),
            )

        if action_counts is not None:
            import json as _json
            total = sum(action_counts.values())
            c.execute(
                "INSERT INTO action_snapshot(id,ts,counts_json,total) VALUES(1,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET ts=excluded.ts, counts_json=excluded.counts_json, total=excluded.total",
                (now_iso(), _json.dumps(action_counts), total),
            )

        c.execute(
            "INSERT INTO sync_log(ts,status,detail,new_experiments) VALUES(?,?,?,?)",
            (now_iso(), "OK", f"source={source}", len(new_rows)),
        )

    return {"ok": True, "new_experiments": len(new_rows), "source": source, "capital": capital}


# ============================================================
# MÉTRIQUES DE PORTEFEUILLE
# ============================================================

def compute_metrics() -> dict:
    with get_db() as c:
        state = c.execute("SELECT * FROM capital_state WHERE id=1").fetchone()
        ledger = c.execute("SELECT * FROM capital_ledger ORDER BY id ASC").fetchall()
        by_category = c.execute(
            """
            SELECT category,
                   COUNT(*) AS n,
                   SUM(profit) AS profit_sum,
                   SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) AS wins
            FROM capital_ledger GROUP BY category ORDER BY profit_sum DESC
            """
        ).fetchall()

    starting = state["starting_capital"]
    capital = state["capital"]
    peak = state["peak_capital"]

    current_drawdown_pct = ((peak - capital) / peak) if peak > 0 else 0.0

    max_drawdown_pct = 0.0
    running_peak = starting
    for row in ledger:
        running_peak = max(running_peak, row["capital_after"])
        dd = (running_peak - row["capital_after"]) / running_peak if running_peak > 0 else 0.0
        max_drawdown_pct = max(max_drawdown_pct, dd)

    n = len(ledger)
    wins = sum(1 for row in ledger if row["profit"] > 0)
    win_rate = (wins / n) if n else 0.0
    total_return_pct = ((capital - starting) / starting) if starting else 0.0

    # Calibration : NOVAREL prédit-il bien ses propres résultats ? On compare
    # l'erreur de prédiction moyenne récente à celle d'avant, pour détecter
    # une dérive plutôt qu'un simple instantané.
    errors = [row["prediction_error"] for row in ledger if row["prediction_error"] is not None]
    recent_errors = errors[-20:]
    older_errors = errors[:-20] if len(errors) > 20 else []
    calibration_error_recent = (sum(recent_errors) / len(recent_errors)) if recent_errors else None
    calibration_error_older = (sum(older_errors) / len(older_errors)) if older_errors else None
    calibration_drift = (
        calibration_error_recent - calibration_error_older
        if calibration_error_recent is not None and calibration_error_older is not None
        else None
    )

    with get_db() as c:
        snap = c.execute("SELECT * FROM action_snapshot WHERE id=1").fetchone()
    action_distribution = None
    if snap:
        import json as _json
        action_distribution = {"ts": snap["ts"], "total": snap["total"], "counts": _json.loads(snap["counts_json"])}

    return {
        "starting_capital": starting,
        "capital": capital,
        "peak_capital": peak,
        "total_return_pct": total_return_pct,
        "current_drawdown_pct": current_drawdown_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "trades": n,
        "win_rate": win_rate,
        "by_category": [dict(r) for r in by_category],
        "curve": [{"id": r["source_experiment_id"], "capital": r["capital_after"]} for r in ledger[-200:]],
        "calibration_error_recent": calibration_error_recent,
        "calibration_error_older": calibration_error_older,
        "calibration_drift": calibration_drift,
        "action_distribution": action_distribution,
    }


# ============================================================
# MOTEUR DE VERDICTS (Finance Brain)
# ============================================================

def _recent_verdict(c, title: str) -> bool:
    row = c.execute(
        "SELECT ts FROM verdicts WHERE title=? ORDER BY id DESC LIMIT 1", (title,)
    ).fetchone()
    if not row:
        return False
    try:
        last = datetime.fromisoformat(row["ts"])
    except ValueError:
        return False
    return (datetime.now() - last).total_seconds() < VERDICT_COOLDOWN_SECONDS


def _apply_risk_fraction(base_url: str, value: float) -> tuple[bool, str]:
    try:
        r = requests.post(f"{base_url.rstrip('/')}/api/settings", json={"risk_fraction": value}, timeout=6)
        if r.status_code == 404:
            return False, "endpoint /api/settings absent sur cette version de NOVAREL"
        r.raise_for_status()
        body = r.json()
        if not body.get("ok"):
            return False, f"NOVAREL a refusé : {body.get('error')}"
        return True, f"risk_fraction ajusté à {value}"
    except requests.RequestException as e:
        return False, f"échec de connexion : {e}"


def generate_verdicts() -> list[dict]:
    metrics = compute_metrics()
    warning_th = float(setting("drawdown_warning") or 0.12)
    critical_th = float(setting("drawdown_critical") or 0.25)
    auto_apply = setting("auto_apply") == "1"
    base_url = setting("novarel_base_url")

    proposals = []

    dd = metrics["current_drawdown_pct"]
    if dd >= critical_th:
        proposals.append({
            "severity": "critical",
            "title": "Drawdown critique",
            "detail": (
                f"Le capital simulé a chuté de {dd:.0%} depuis son pic "
                f"({metrics['peak_capital']:.2f} € → {metrics['capital']:.2f} €). "
                f"Recommandation : réduire fortement risk_fraction vers le plancher (0.01)."
            ),
            "metric_value": dd,
            "suggested_risk_fraction": 0.01,
        })
    elif dd >= warning_th:
        proposals.append({
            "severity": "warning",
            "title": "Drawdown élevé",
            "detail": (
                f"Drawdown de {dd:.0%} depuis le pic. "
                f"Recommandation : réduire risk_fraction d'environ 30%."
            ),
            "metric_value": dd,
            "suggested_risk_fraction": 0.10,
        })
    elif metrics["trades"] >= 15 and dd < 0.05 and metrics["total_return_pct"] > 0:
        proposals.append({
            "severity": "info",
            "title": "Portefeuille stable",
            "detail": (
                f"Capital en croissance ({metrics['total_return_pct']:+.0%}) avec un drawdown "
                f"faible ({dd:.0%}). Une légère augmentation de risk_fraction est envisageable."
            ),
            "metric_value": metrics["total_return_pct"],
            "suggested_risk_fraction": 0.15,
        })

    for cat in metrics["by_category"]:
        if cat["n"] >= 5 and (cat["profit_sum"] or 0) < 0:
            proposals.append({
                "severity": "warning",
                "title": f"Catégorie déficitaire : {cat['category']}",
                "detail": (
                    f"La catégorie « {cat['category']} » cumule {cat['profit_sum']:.2f} € "
                    f"sur {cat['n']} expériences ({cat['wins']} gains). "
                    f"Recommandation : dépondérer cette catégorie dans les prochains cycles."
                ),
                "metric_value": cat["profit_sum"],
                "suggested_risk_fraction": None,
            })

    # Calibration : NOVAREL se met-il à moins bien prédire ses propres
    # résultats ? Une dérive positive significative mérite un avertissement,
    # même si le capital reste stable pour l'instant.
    drift = metrics["calibration_drift"]
    if drift is not None and drift > 0.10 and metrics["calibration_error_recent"] > 0.30:
        proposals.append({
            "severity": "warning",
            "title": "Dérive de calibration",
            "detail": (
                f"L'erreur de prédiction moyenne est passée de "
                f"{metrics['calibration_error_older']:.0%} à {metrics['calibration_error_recent']:.0%} "
                f"sur les dernières expériences synchronisées. NOVAREL prédit moins bien qu'avant : "
                f"vérifier le Learning Lab avant d'augmenter le risque."
            ),
            "metric_value": drift,
            "suggested_risk_fraction": None,
        })

    # Répartition des actions du Decision Engine : si le Buyer Brain
    # recommande majoritairement d'arrêter ou de ne pas exécuter, c'est un
    # signal de portefeuille à surfacer même avant que ça n'affecte le capital.
    dist = metrics["action_distribution"]
    if dist and dist["total"] >= 5:
        stop_like = dist["counts"].get("STOP", 0) + dist["counts"].get("DO_NOT_EXECUTE", 0)
        stop_ratio = stop_like / dist["total"]
        if stop_ratio >= 0.5:
            proposals.append({
                "severity": "warning",
                "title": "Majorité d'opportunités arrêtées",
                "detail": (
                    f"{stop_ratio:.0%} des {dist['total']} dernières opportunités évaluées par NOVAREL "
                    f"sont recommandées en STOP ou DO_NOT_EXECUTE. Le marché simulé actuel semble peu "
                    f"favorable ; envisager d'attendre plutôt que de forcer de nouvelles expériences."
                ),
                "metric_value": stop_ratio,
                "suggested_risk_fraction": None,
            })

    inserted = []
    with get_db(write=True) as c:
        for p in proposals:
            if _recent_verdict(c, p["title"]):
                continue

            applied = 0
            apply_note = "Application automatique désactivée (auto_apply=0)."
            if auto_apply and p["suggested_risk_fraction"] is not None:
                ok, note = _apply_risk_fraction(base_url, p["suggested_risk_fraction"])
                applied = int(ok)
                apply_note = note

            c.execute(
                "INSERT INTO verdicts(ts,severity,title,detail,metric_value,suggested_risk_fraction,"
                "applied,apply_note) VALUES(?,?,?,?,?,?,?,?)",
                (now_iso(), p["severity"], p["title"], p["detail"], p["metric_value"],
                 p["suggested_risk_fraction"], applied, apply_note),
            )
            inserted.append(p["title"])

    return inserted


# ============================================================
# BOUCLE AUTONOME
# ============================================================

_WORKER_STARTED = False
_WORKER_START_LOCK = threading.Lock()
_last_cycle_ts = 0.0


def worker_cycle():
    result = sync_from_novarel()
    if result.get("ok"):
        generate_verdicts()
    return result


def worker():
    global _last_cycle_ts
    while True:
        interval = max(5, int(setting("poll_seconds") or "20"))
        try:
            if setting("running") == "1":
                worker_cycle()
                _last_cycle_ts = time.time()
        except Exception:
            logger.exception("Erreur dans le cycle du worker NOVAREL CAPITAL")
        time.sleep(interval)


def start_worker():
    global _WORKER_STARTED
    if os.environ.get("NOVAREL_CAPITAL_WORKER_ENABLED", "1") != "1":
        return
    with _WORKER_START_LOCK:
        if _WORKER_STARTED:
            return
        _WORKER_STARTED = True
        threading.Thread(target=worker, daemon=True, name="novarel-capital-worker").start()


# ============================================================
# ROUTES
# ============================================================

@app.get("/health")
def health():
    worker_alive = (time.time() - _last_cycle_ts) < (3 * max(5, int(setting("poll_seconds") or "20")))
    return jsonify({
        "status": "ok",
        "version": APP_VERSION,
        "novarel_base_url": setting("novarel_base_url"),
        "worker_recently_active": worker_alive if _last_cycle_ts else None,
    })


@app.get("/api/capital/state")
def api_state():
    with get_db() as c:
        recent_verdicts = [dict(x) for x in c.execute(
            "SELECT * FROM verdicts ORDER BY id DESC LIMIT 15"
        )]
        recent_sync = [dict(x) for x in c.execute(
            "SELECT * FROM sync_log ORDER BY id DESC LIMIT 10"
        )]
    return jsonify({
        "running": setting("running") == "1",
        "auto_apply": setting("auto_apply") == "1",
        "novarel_base_url": setting("novarel_base_url"),
        "metrics": compute_metrics(),
        "verdicts": recent_verdicts,
        "sync_log": recent_sync,
    })


@app.post("/api/capital/sync")
def api_sync():
    result = sync_from_novarel()
    verdicts = generate_verdicts() if result.get("ok") else []
    return jsonify({**result, "new_verdicts": verdicts})


@app.get("/api/capital/verdicts")
def api_verdicts():
    with get_db() as c:
        rows = [dict(x) for x in c.execute("SELECT * FROM verdicts ORDER BY id DESC LIMIT 50")]
    return jsonify({"ok": True, "verdicts": rows})


@app.get("/api/capital/settings")
def api_get_settings():
    return jsonify({
        "novarel_base_url": setting("novarel_base_url"),
        "starting_capital": float(setting("starting_capital")),
        "poll_seconds": int(setting("poll_seconds")),
        "auto_apply": setting("auto_apply") == "1",
        "running": setting("running") == "1",
        "drawdown_warning": float(setting("drawdown_warning")),
        "drawdown_critical": float(setting("drawdown_critical")),
    })


@app.post("/api/capital/settings")
def api_update_settings():
    data = request.get_json(silent=True) or {}
    updated = {}

    if "novarel_base_url" in data:
        v = str(data["novarel_base_url"]).strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            return jsonify({"ok": False, "error": "novarel_base_url doit commencer par http:// ou https://"}), 400
        set_setting("novarel_base_url", v)
        updated["novarel_base_url"] = v

    if "poll_seconds" in data:
        try:
            v = max(5, min(3600, int(data["poll_seconds"])))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "poll_seconds invalide"}), 400
        set_setting("poll_seconds", v)
        updated["poll_seconds"] = v

    if "auto_apply" in data:
        v = "1" if data["auto_apply"] else "0"
        set_setting("auto_apply", v)
        updated["auto_apply"] = v == "1"

    if "running" in data:
        v = "1" if data["running"] else "0"
        set_setting("running", v)
        updated["running"] = v == "1"

    if "drawdown_warning" in data:
        try:
            v = clamp(float(data["drawdown_warning"]), 0.01, 0.90)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "drawdown_warning invalide"}), 400
        set_setting("drawdown_warning", v)
        updated["drawdown_warning"] = v

    if "drawdown_critical" in data:
        try:
            v = clamp(float(data["drawdown_critical"]), 0.01, 0.95)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "drawdown_critical invalide"}), 400
        set_setting("drawdown_critical", v)
        updated["drawdown_critical"] = v

    if not updated:
        return jsonify({"ok": False, "error": "Aucun paramètre valide fourni"}), 400

    return jsonify({"ok": True, "updated": updated})


@app.post("/api/capital/reset")
def api_reset():
    if request.args.get("confirm") != "yes":
        return jsonify({"ok": False, "error": "Confirmation requise : ?confirm=yes"}), 400

    starting = float(setting("starting_capital") or 5000.0)
    with get_db(write=True) as c:
        c.execute("DELETE FROM capital_ledger")
        c.execute("DELETE FROM verdicts")
        c.execute("DELETE FROM sync_log")
        c.execute(
            "UPDATE capital_state SET capital=?, starting_capital=?, peak_capital=?, updated_at=? WHERE id=1",
            (starting, starting, starting, now_iso()),
        )
    return jsonify({"ok": True})


DASHBOARD_HTML = r"""
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NOVAREL CAPITAL — Finance Brain</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#0a0f17;color:#eaf2f8;font:14px system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1300px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;gap:15px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
h1{margin:0;font-size:26px}.muted,.small{color:#8fa3b7}.small{font-size:12px}
a{color:#9fc4ff;text-decoration:none}.btn{border:1px solid #2a3c52;background:#111d2c;color:#eaf2f8;border-radius:9px;padding:8px 12px;cursor:pointer;font:inherit}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.grid2{display:grid;grid-template-columns:1.4fr 1fr;gap:12px;margin-top:12px}
.panel{background:#0e1621;border:1px solid #1f2e40;border-radius:14px;padding:15px}.big{font-size:26px;font-weight:800;margin:5px 0}
.row{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid #1f2e40}.row:last-child{border:0}
.list{max-height:340px;overflow:auto}
.verdict{padding:10px 12px;margin-bottom:8px;border-radius:9px;border-left:3px solid #72a8ff;background:#111d2c}
.verdict.critical{border-color:#ff7f86}.verdict.warning{border-color:#f5c76b}.verdict.info{border-color:#55d69a}
.pos{color:#55d69a}.neg{color:#ff7f86}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #1f2e40;font-size:12px}th{color:#8fa3b7}
input,select{background:#0e1621;border:1px solid #2a3c52;border-radius:7px;color:#eaf2f8;padding:7px;font:inherit;width:100%}
label{display:block;font-size:12px;color:#8fa3b7;margin-bottom:4px}
.field{margin-bottom:10px}
@media(max-width:1000px){.grid{grid-template-columns:repeat(2,1fr)}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body><main>

<div class="top">
<div><h1>💰 NOVAREL CAPITAL</h1><div class="muted">Le Finance Brain de NOVAREL — vision portefeuille, risque et capital cumulé.</div></div>
<div><span id="status" class="small">Chargement…</span> <button class="btn" onclick="sync()">Synchroniser maintenant</button></div>
</div>

<div class="grid">
<div class="panel"><div class="small">Capital simulé</div><div id="capital" class="big">—</div><div id="return" class="muted">—</div></div>
<div class="panel"><div class="small">Drawdown courant</div><div id="dd" class="big">—</div><div id="ddmax" class="muted">—</div></div>
<div class="panel"><div class="small">Trades intégrés</div><div id="trades" class="big">—</div><div id="winrate" class="muted">—</div></div>
<div class="panel"><div class="small">Source NOVAREL</div><div id="base" class="big" style="font-size:14px;word-break:break-all">—</div><div id="lastsync" class="muted">—</div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Courbe de capital</h2><svg id="curve" viewBox="0 0 600 160" style="width:100%;height:160px"></svg></div>
<div class="panel"><h2>Par catégorie</h2><div id="categories" class="list"></div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Calibration de NOVAREL</h2><div id="calibration"></div></div>
<div class="panel"><h2>Répartition des actions (Decision Engine)</h2><div id="actions" class="list"></div></div>
</div>

<div class="grid2">
<div class="panel"><h2>Verdicts (Finance Brain)</h2><div id="verdicts" class="list"></div></div>
<div class="panel">
<h2>Réglages</h2>
<div class="field"><label>URL de base NOVAREL</label><input id="s_base"></div>
<div class="field"><label>Intervalle de synchro (secondes)</label><input id="s_poll" type="number" min="5"></div>
<div class="field"><label>Application automatique des recommandations</label>
<select id="s_auto"><option value="false">Non (recommandé)</option><option value="true">Oui</option></select></div>
<button class="btn" onclick="saveSettings()">Enregistrer</button>
<div id="settings_msg" class="small" style="margin-top:8px"></div>
</div>
</div>

<div class="small" style="margin-top:12px">Couche d'analyse de portefeuille 100% simulée, au-dessus d'un moteur NOVAREL lui-même 100% simulé. Aucune donnée financière réelle.</div>
</main>
<script>
const $=id=>document.getElementById(id);
const pct=x=>x==null?"—":(Number(x)*100).toFixed(1)+"%";
const eur=x=>x==null?"—":Number(x).toFixed(2)+" €";
const esc=s=>String(s??"").replace(/[&<>"]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[m]));

function drawCurve(points){
  const svg=$("curve");
  if(!points.length){svg.innerHTML='<text x="10" y="80" fill="#8fa3b7" font-size="12">Pas encore de données</text>';return;}
  const vals=points.map(p=>p.capital);
  const min=Math.min(...vals), max=Math.max(...vals);
  const range=(max-min)||1;
  const w=600,h=160,pad=8;
  const step=(w-pad*2)/Math.max(1,points.length-1);
  const path=points.map((p,i)=>{
    const x=pad+i*step;
    const y=h-pad-((p.capital-min)/range)*(h-pad*2);
    return (i===0?"M":"L")+x.toFixed(1)+","+y.toFixed(1);
  }).join(" ");
  const last=vals[vals.length-1], first=vals[0];
  const color = last>=first ? "#55d69a" : "#ff7f86";
  svg.innerHTML = `<path d="${path}" fill="none" stroke="${color}" stroke-width="2"/>`;
}

async function saveSettings(){
  const body={
    novarel_base_url: $("s_base").value.trim(),
    poll_seconds: parseInt($("s_poll").value||"20",10),
    auto_apply: $("s_auto").value==="true",
  };
  try{
    const r=await fetch("/api/capital/settings",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    const d=await r.json();
    $("settings_msg").textContent = d.ok ? "Enregistré." : ("Erreur : "+d.error);
    load();
  }catch(e){ $("settings_msg").textContent = "Erreur : "+e.message; }
}

async function sync(){
  $("status").textContent="Synchronisation…";
  try{
    const r=await fetch("/api/capital/sync",{method:"POST"});
    await r.json();
  }catch(e){}
  load();
}

async function load(){
 try{
  const [stateRes, settingsRes] = await Promise.all([
    fetch("/api/capital/state",{cache:"no-store"}),
    fetch("/api/capital/settings",{cache:"no-store"}),
  ]);
  const d = await stateRes.json();
  const s = await settingsRes.json();

  $("status").textContent = d.running ? "🟢 ACTIVE" : "⚪ PAUSE";
  const m = d.metrics;
  $("capital").textContent = eur(m.capital);
  $("return").innerHTML = `Rendement simulé : <span class="${m.total_return_pct>=0?'pos':'neg'}">${pct(m.total_return_pct)}</span>`;
  $("dd").textContent = pct(m.current_drawdown_pct);
  $("ddmax").textContent = "Max historique : "+pct(m.max_drawdown_pct);
  $("trades").textContent = m.trades;
  $("winrate").textContent = "Taux de réussite : "+pct(m.win_rate);
  $("base").textContent = d.novarel_base_url;
  $("lastsync").textContent = d.sync_log.length ? ("Dernière synchro : "+d.sync_log[0].ts+" ("+d.sync_log[0].status+")") : "Pas encore synchronisé";

  drawCurve(m.curve);

  $("categories").innerHTML = m.by_category.length ? m.by_category.map(c=>
    `<div class="row"><span>${esc(c.category)}<br><span class="small">${c.n} trades · ${c.wins} gains</span></span><b class="${c.profit_sum>=0?'pos':'neg'}">${eur(c.profit_sum)}</b></div>`
  ).join("") : "<div class=\"muted\">Aucune donnée pour l'instant.</div>";

  if(m.calibration_error_recent==null){
    $("calibration").innerHTML = "<div class=\"muted\">Pas encore assez de données de calibration.</div>";
  } else {
    const drift = m.calibration_drift;
    const driftTxt = drift==null ? "" : (drift>0 ? `<span class="neg">+${pct(drift)}</span> vs avant` : `<span class="pos">${pct(drift)}</span> vs avant`);
    $("calibration").innerHTML = `<div class="row"><span>Erreur de prédiction récente</span><b>${pct(m.calibration_error_recent)}</b></div>
    <div class="row"><span>Évolution</span><b>${driftTxt||'—'}</b></div>`;
  }

  const dist = m.action_distribution;
  if(!dist){
    $("actions").innerHTML = "<div class=\"muted\">Pas encore de données (nécessite une version de NOVAREL avec Decision Engine).</div>";
  } else {
    const entries = Object.entries(dist.counts).sort((a,b)=>b[1]-a[1]);
    $("actions").innerHTML = entries.map(([action,n])=>
      `<div class="row"><span>${esc(action)}</span><b>${n} (${pct(n/dist.total)})</b></div>`
    ).join("") + `<div class="small" style="margin-top:6px">Instantané NOVAREL du ${esc(dist.ts)}</div>`;
  }

  $("verdicts").innerHTML = d.verdicts.length ? d.verdicts.map(v=>
    `<div class="verdict ${esc(v.severity)}"><b>${esc(v.title)}</b><div class="small">${esc(v.detail)}</div>
     <div class="small">${v.applied? '✅ appliqué à NOVAREL' : '⏸ non appliqué'} — ${esc(v.apply_note||'')}</div></div>`
  ).join("") : "<div class=\"muted\">Aucun verdict pour l'instant.</div>";

  $("s_base").value = s.novarel_base_url;
  $("s_poll").value = s.poll_seconds;
  $("s_auto").value = s.auto_apply ? "true" : "false";
 }catch(e){
  $("status").textContent = "🔴 ERREUR";
  console.error(e);
 }
}
load();
setInterval(load, 15000);
</script>
</body></html>
"""


@app.get("/")
def dashboard():
    return DASHBOARD_HTML


@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return e
    logger.exception("Erreur non gérée")
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "internal_error", "detail": str(e)}), 500
    return f"<h1>NOVAREL CAPITAL</h1><p>Erreur : {e}</p>", 500


# ============================================================
# DÉMARRAGE
# ============================================================

init()
start_worker()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5100")), debug=False)
