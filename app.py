import json
from datetime import date

from flask import Flask, redirect, render_template, request, url_for

import db
import scoring

app = Flask(__name__)

DAY_OF_WEEK_OPTIONS = ["月", "火", "水", "木", "金", "土", "日"]


@app.before_request
def setup():
    db.init_db()


# --- トップ: クライアント一覧 ---

@app.route("/")
def index():
    clients = db.get_all_clients()
    return render_template("index.html", clients=clients)


@app.route("/clients/new", methods=["POST"])
def client_new():
    name = request.form.get("name", "").strip()
    if name:
        db.create_client(name)
    return redirect(url_for("index"))


@app.route("/clients/<int:client_id>/delete", methods=["POST"])
def client_delete(client_id):
    db.delete_client(client_id)
    return redirect(url_for("index"))


# --- クライアント詳細 ---

@app.route("/clients/<int:client_id>")
def client_detail(client_id):
    client = db.get_client(client_id)
    if not client:
        return redirect(url_for("index"))
    sessions = db.get_client_sessions(client_id)

    by_day = {d: [] for d in DAY_OF_WEEK_OPTIONS}
    no_day = []
    for s in sessions:
        if s["day_of_week"] in by_day:
            by_day[s["day_of_week"]].append(s)
        else:
            no_day.append(s)

    active_days = [d for d in DAY_OF_WEEK_OPTIONS if by_day[d]]
    return render_template(
        "client.html",
        client=client,
        sessions=sessions,
        by_day=by_day,
        active_days=active_days,
        no_day=no_day,
    )


# --- 新規セッション ---

@app.route("/clients/<int:client_id>/sessions/new", methods=["GET", "POST"])
def session_new(client_id):
    client = db.get_client(client_id)
    if not client:
        return redirect(url_for("index"))

    if request.method == "POST":
        session_date = request.form.get("session_date") or str(date.today())
        day_of_week = request.form.get("day_of_week", "")
        notes = request.form.get("notes", "")
        exercise_notes = request.form.get("exercise_notes", "")
        session_id = db.create_session(client_id, session_date, day_of_week, notes, exercise_notes)

        for etype in ("before", "after"):
            fields = {}
            for m in scoring.BODY_MOVEMENTS:
                val = request.form.get(f"{etype}_{m['key']}", "0")
                fields[m["key"]] = int(val) if val in ("0", "2", "4") else 0

            bc = request.form.get(f"{etype}_breathing_count", "")
            fields["breathing_count"] = float(bc) if bc else None
            fields["breathing_type"] = request.form.get(f"{etype}_breathing_type", "")

            scores = scoring.calc_scores(fields)
            fields.update(scores)
            db.upsert_evaluation(session_id, etype, fields)

        return redirect(url_for("session_detail", session_id=session_id))

    today = str(date.today())
    weekday_map = ["月", "火", "水", "木", "金", "土", "日"]
    today_dow = weekday_map[date.today().weekday()]

    return render_template(
        "session_new.html",
        client=client,
        movements=scoring.BODY_MOVEMENTS,
        breathing_types=scoring.BREATHING_TYPES,
        breathing_rate_score=scoring.BREATHING_RATE_SCORE,
        day_options=DAY_OF_WEEK_OPTIONS,
        today=today,
        today_dow=today_dow,
    )


# --- セッション詳細 ---

@app.route("/sessions/<int:session_id>")
def session_detail(session_id):
    session = db.get_session(session_id)
    if not session:
        return redirect(url_for("index"))

    client = db.get_client(session["client_id"])
    before = db.get_evaluation(session_id, "before")
    after = db.get_evaluation(session_id, "after")

    before_dict = dict(before) if before else {}
    after_dict = dict(after) if after else {}

    before_radar = scoring.calc_radar_values(before_dict)
    after_radar = scoring.calc_radar_values(after_dict)
    radar_labels = [a["label"] for a in scoring.RADAR_AXES]

    before_type_label = _type_label(before_dict.get("breathing_type"))
    after_type_label = _type_label(after_dict.get("breathing_type"))

    return render_template(
        "session_detail.html",
        client=client,
        session=session,
        before=before_dict,
        after=after_dict,
        movements=scoring.BODY_MOVEMENTS,
        breathing_types=scoring.BREATHING_TYPES,
        before_radar=json.dumps(before_radar),
        after_radar=json.dumps(after_radar),
        radar_labels=json.dumps(radar_labels),
        before_type_label=before_type_label,
        after_type_label=after_type_label,
    )


@app.route("/sessions/<int:session_id>/delete", methods=["POST"])
def session_delete(session_id):
    session = db.get_session(session_id)
    if not session:
        return redirect(url_for("index"))
    client_id = session["client_id"]
    db.delete_session(session_id)
    return redirect(url_for("client_detail", client_id=client_id))


def _type_label(key):
    if not key:
        return "—"
    for t in scoring.BREATHING_TYPES:
        if t["key"] == key:
            return t["label"]
    return key


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=8080)
