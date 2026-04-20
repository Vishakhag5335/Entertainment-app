"""
Entertainment Planner — Flask Web App
Run: python app.py
Opens at http://localhost:5000  (redirects to /new)
"""

import os
import sys
import uuid
import json
import threading
import time
from pathlib import Path
from flask import Flask, request, jsonify, render_template, redirect
from dotenv import load_dotenv
from agents import run_plan

load_dotenv()

app = Flask(__name__)

# ── Persistent JSON-backed store ───────────────────────────────────────────────
# Stores plan results in data/results.json so they survive server restarts.

DATA_DIR = Path(__file__).parent / "data"
STORE_FILE = DATA_DIR / "results.json"
_lock = threading.Lock()


def _load_store() -> dict:
    """Load results from disk. Returns empty dict if file missing/corrupt."""
    try:
        if STORE_FILE.exists():
            return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_store() -> None:
    """Persist current results_store to disk."""
    try:
        DATA_DIR.mkdir(exist_ok=True)
        STORE_FILE.write_text(
            json.dumps(results_store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"⚠  Failed to save results store: {e}")


results_store: dict = _load_store()


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return redirect("/new")


@app.route("/new")
def new_plan():
    """Landing / search page."""
    return render_template("index.html")


@app.route("/results/<plan_id>")
def view_results(plan_id: str):
    """Results page — handled by SPA."""
    if plan_id not in results_store:
        return redirect("/new")
    return render_template("index.html", plan_id=plan_id)


# ── API ────────────────────────────────────────────────────────────────────────

@app.route("/api/plan", methods=["POST"])
def create_plan():
    """
    Start a new plan in the background.
    Body: { "query": str, "intent": "movies" | "music" | "both" }
    Returns: { "id": str }
    """
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    intent = data.get("intent", "both").strip().lower()

    if not query:
        return jsonify({"error": "Query is required."}), 400

    if intent not in ("movies", "music", "both"):
        intent = "both"

    plan_id = uuid.uuid4().hex[:10]
    with _lock:
        results_store[plan_id] = {
            "status": "processing",
            "query": query,
            "intent": intent,
            "ts": int(time.time() * 1000)
        }
        _save_store()

    thread = threading.Thread(
        target=_process,
        args=(plan_id, query, intent),
        daemon=True,
    )
    thread.start()

    return jsonify({"id": plan_id})


@app.route("/api/result/<plan_id>")
def get_result(plan_id: str):
    """Poll this endpoint to check plan status and retrieve results."""
    entry = results_store.get(plan_id)
    if entry is None:
        return jsonify({"error": "Not found."}), 404
    return jsonify(entry)


@app.route("/api/history", methods=["GET", "DELETE"])
def get_history():
    """Return all past curations from results_store, or clear them."""
    if request.method == "DELETE":
        with _lock:
            results_store.clear()
            _save_store()
        return jsonify({"status": "ok"})
        
    history_list = []
    # Old items without a ts get 0 so they sort to the bottom (newest-first ordering)
    default_ts = 0
    for plan_id, data in results_store.items():
        if data.get("status") == "processing":
            continue
        history_list.append({
            "id": plan_id,
            "query": data.get("query", "Unknown"),
            "intent": data.get("intent", "both"),
            "ts": data.get("ts", default_ts)
        })
    # Sort descending by ts
    history_list.sort(key=lambda x: x["ts"], reverse=True)
    return jsonify(history_list)


@app.route("/api/history/<plan_id>", methods=["DELETE"])
def delete_history_item(plan_id: str):
    """Delete a specific curation from the results_store."""
    with _lock:
        if plan_id in results_store:
            del results_store[plan_id]
            _save_store()
            return jsonify({"status": "ok"})
    return jsonify({"error": "Item not found"}), 404


# ── Background worker ──────────────────────────────────────────────────────────

def _process(plan_id: str, query: str, intent: str) -> None:
    try:
        result = run_plan(query, intent)
        with _lock:
            results_store[plan_id].update({"status": "done", **result})
            _save_store()
    except Exception as exc:
        with _lock:
            results_store[plan_id].update({"status": "error", "error": str(exc)})
            _save_store()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    missing = [k for k in ["GROQ_API_KEY", "SERPER_API_KEY"] if not os.getenv(k)]
    if missing:
        print(f"\n⚠  Missing environment variables: {', '.join(missing)}")
        print("   Copy .env.example → .env and fill in the values.\n")
        sys.exit(1)

    print("\n🎬  Entertainment Planner")
    print("    http://localhost:5000/new\n")
    app.run(host="0.0.0.0", port=5000, debug=False)