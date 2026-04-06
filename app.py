"""
Entertainment Planner — Flask Web App
Run: python app.py
Opens at http://localhost:5000  (redirects to /new)
"""

import os
import sys
import uuid
import threading
from flask import Flask, request, jsonify, render_template, redirect
from dotenv import load_dotenv
from agents import run_plan

load_dotenv()

app = Flask(__name__)

# In-memory store { plan_id: { status, query, intent, movies?, music?, plan? } }
# Replace with Redis or a DB for multi-worker / persistent deployments.
results_store: dict = {}


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return redirect("/new")


@app.route("/new")
def new_plan():
    """Landing / search page."""
    return render_template("new.html")


@app.route("/results/<plan_id>")
def view_results(plan_id: str):
    """Results page — content is loaded via polling the /api/result endpoint."""
    if plan_id not in results_store:
        return redirect("/new")
    return render_template("results.html", plan_id=plan_id)


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
    results_store[plan_id] = {
        "status": "processing",
        "query": query,
        "intent": intent,
    }

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


# ── Background worker ──────────────────────────────────────────────────────────

def _process(plan_id: str, query: str, intent: str) -> None:
    try:
        result = run_plan(query, intent)
        results_store[plan_id].update({"status": "done", **result})
    except Exception as exc:
        results_store[plan_id].update({"status": "error", "error": str(exc)})


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