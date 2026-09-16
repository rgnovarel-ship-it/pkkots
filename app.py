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
                capital_after REAL
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
        return {
            "id": int(raw["id"]),
            "ts": raw.get("ts") or now_iso(),
            "category": raw.get("category") or "inconnue",
            "strategy": raw.get("strategy") or "inconnue",
            "outcome": raw.get("outcome") or "NEUTRAL",
            "profit": float(raw.get("actual_profit") or 0.0),
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
                "profit,capital_after) VALUES(?,?,?,?,?,?,?)",
                (e["ts"], e["id"], e["category"], e["strategy"], e["outcome"], e["profit"], capital),
            )

        if new_rows:
            c.execute(
                "UPDATE capital_state SET capital=?, peak_capital=?, updated_at=? WHERE id=1",
                (capital, peak, now_iso()),
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
            ],
            "opportunities": [("ts_epoch", "REAL")],
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
                rotation_days, outcome, lesson, confidence, prediction_error
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_iso(), time.time(), strategy["code"], result["category"], strategy["description"],
                result["ask"], result["market"], result["resale"], result["fees"], result["other"],
                result["expected_margin"], result["probability"], result["expected"], result["actual"],
                result["rotation"], result["outcome"], result["lesson"],
                clamp(1 - result["prediction_error"]), result["prediction_error"],
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

    with get_db(write=True) as c:
        c.execute(
            """
            INSERT INTO opportunities(
                ts, ts_epoch, category, item, ask_price, market_low, market_high, resale_price,
                fees, risk, liquidity, trend, confidence, score, expected_profit, recommendation, evidence
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now_iso(), time.time(), category, f"Opportunité simulée — {category}", ask,
                market * 0.90, market * 1.10, resale, fees, risk, liquidity, trend,
                confidence, score, expected_profit, recommendation,
                "Données synthétiques de laboratoire.",
            ),
        )
        c.execute(
            "UPDATE metrics SET opportunities = opportunities + 1 "
            "WHERE id = (SELECT MAX(id) FROM metrics)"
        )

    log_event(
        "Buyer Brain", "Évaluer opportunité",
        f"{recommendation} · score {score:.0%} · profit attendu {expected_profit:+.2f} €",
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
    elif choice < 0.65:
        run_learning_experiment()
    elif choice < 0.85:
        generate_opportunity()
    elif choice < 0.95:
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
        ]:
            c.execute(f"DELETE FROM {table}")

        c.execute(
            """
            UPDATE strategies SET
                tests=0, wins=0, losses=0, neutrals=0,
                profit_sum=0, expected_sum=0, rotation_sum=0,
                confidence=0.50, weight=1.0, calibration_error=0,
                last_result=NULL, updated_at=?
            """,
            (now_iso(),),
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
        "history": history,
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
  $("curiosity").innerHTML=d.curiosity_open.length?d.curiosity_open.map(x=>`<div class="event"><b>${esc(x.question)}</b><div class="small">${esc(x.topic)} · priorité ${pct(x.priority)}</div><input class="tiny" id="answer_${x.id}" placeholder="Répondre (optionnel)…"><button class="tiny" style="margin-top:5px" onclick="resolveCuriosity(${x.id})">Marquer résolue</button></div>`).join(""):"<div class=\"muted\">Aucune question ouverte.</div>";
  $("history").innerHTML=d.history.length?d.history.map(x=>`<tr><td>${esc(x.ts)}</td><td>${esc(x.strategy)}</td><td>${esc(x.category)}</td><td>${pct(x.probability)}</td><td>${esc(x.outcome)} · ${num(x.actual_profit)} €</td><td>${pct(x.prediction_error)}</td><td>${esc(x.lesson)}</td></tr>`).join(""):"<tr><td colspan=\"7\" class=\"muted\">Pas encore d'expériences.</td></tr>";
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

flask>=3.0
requests>=2.31
gunicorn>=21
